"""
prediction_service.py — v2

Builds feature vectors for the v2 closure and severity models, which expect
19 and 20 features respectively (lat_bin, lon_bin, cause_closure_rate,
station_priority_rate, is_daytime, is_planned, corridor_density_log, etc.)
on top of the original v1 feature set.

KEY DESIGN DECISION: the feature vector is built dynamically from
`arts.closure_meta["feature_cols"]` / `arts.priority_meta["feature_cols"]`
rather than a hardcoded list. If the models are retrained with a different
feature set, this service adapts automatically instead of silently
producing a wrong-shape input (which is what broke in v1->v2 migration).
"""

import math
import time
from typing import Optional, Dict

import numpy as np
import pandas as pd

from backend.schemas.prediction import PredictionRequest, PredictionResponse
from backend.services.artifact_loader import get_artifacts
from backend.core.logging import get_logger

logger = get_logger(__name__)

HIGH_PRIORITY_CORRIDORS = frozenset([
    "Mysore Road", "Bellary Road 1", "Bellary Road 2", "Tumkur Road",
    "Hosur Road", "ORR North 1", "ORR North 2", "ORR East 1",
    "ORR East 2", "Magadi Road", "Old Madras Road", "Bannerghatta Road",
    "West of Chord Road", "CBD 2", "ORR West 1", "ORR West 2",
])

# Default lat/lon used only when the caller doesn't supply coordinates —
# centred roughly on Bengaluru so lat_bin/lon_bin land in a sane mid-range
# bucket rather than clipping to an edge bin.
DEFAULT_LAT = 12.97
DEFAULT_LON = 77.59

_NO_VALUE = {"", "null", "nan", "none", "n/a", "na"}


def _safe_encode(encoders: dict, col: str, value: Optional[str]) -> int:
    le = encoders.get(col)
    if le is None:
        return -1
    if value is None or str(value).strip().lower() in _NO_VALUE:
        if "__MISSING__" in le.classes_:
            return int(le.transform(["__MISSING__"])[0])
        return -1
    try:
        return int(le.transform([str(value)])[0])
    except ValueError:
        if "__MISSING__" in le.classes_:
            return int(le.transform(["__MISSING__"])[0])
        return -1


def _build_base_features(req: PredictionRequest, encoders: dict) -> dict:
    """Build every feature either model could possibly need. Each training
    script selects its own subset via feature_cols, so it's fine to compute
    a superset here."""

    corridor = req.corridor
    is_non_corridor = int(
        not corridor or str(corridor).strip().lower() in ("non-corridor", "", "null", "nan")
    )
    is_high_priority_corridor = (
        int(corridor.strip() in HIGH_PRIORITY_CORRIDORS) if not is_non_corridor else 0
    )

    hour_sin = math.sin(2 * math.pi * req.hour_of_day / 24)
    hour_cos = math.cos(2 * math.pi * req.hour_of_day / 24)

    month = req.month if req.month is not None else 6  # fallback: mid-year default

    lat = req.latitude if req.latitude is not None else DEFAULT_LAT
    lon = req.longitude if req.longitude is not None else DEFAULT_LON
    lat_bin = int(np.clip(int((lat - 12.8) / 0.05), 0, 15))
    lon_bin = int(np.clip(int((lon - 77.3) / 0.05), 0, 15))

    is_daytime = int(8 <= req.hour_of_day <= 20)
    is_planned = int(bool(req.is_planned)) if req.is_planned is not None else 0

    has_vehicle_type = int(
        req.vehicle_type is not None and str(req.vehicle_type).strip().lower() not in _NO_VALUE
    )
    has_zone = int(
        req.zone is not None and str(req.zone).strip().lower() not in _NO_VALUE
    )

    return {
        "corridor_encoded":          _safe_encode(encoders, "corridor", corridor),
        "event_cause_encoded":       _safe_encode(encoders, "event_cause", req.event_cause),
        "vehicle_type_encoded":      _safe_encode(encoders, "vehicle_type", req.vehicle_type),
        "police_station_encoded":   _safe_encode(encoders, "police_station", req.police_station),
        "zone_encoded":              _safe_encode(encoders, "zone", req.zone),
        "hour_of_day":               req.hour_of_day,
        "day_of_week":               req.day_of_week,
        "month":                     month,
        "hour_sin":                  hour_sin,
        "hour_cos":                  hour_cos,
        "is_high_priority_corridor": is_high_priority_corridor,
        "is_non_corridor":           is_non_corridor,
        "has_vehicle_type":          has_vehicle_type,
        "has_zone":                  has_zone,
        "lat_bin":                   lat_bin,
        "lon_bin":                   lon_bin,
        "is_daytime":                is_daytime,
        "is_planned":                is_planned,
        # placeholders — filled in by _apply_encoding_lookups before use
        "cause_closure_rate":        None,
        "station_priority_rate":     None,
        "corridor_density_log":      None,
    }


def _apply_encoding_lookups(
    feature_dict: dict,
    req: PredictionRequest,
    closure_lookups: Optional[dict],
    priority_lookups: Optional[dict],
) -> dict:
    """Fill target-encoded features from the lookup tables exported at
    training time (closure_encoding_lookups.json / priority_encoding_lookups.json).
    Falls back to each table's own __default__ entry if the cause/corridor
    was never seen in training."""

    cause = req.event_cause
    corridor = req.corridor or "Non-corridor"

    if closure_lookups:
        cc_rate = closure_lookups.get("cause_closure_rate", {})
        sp_rate = closure_lookups.get("station_priority_rate", {})
        feature_dict["cause_closure_rate"] = cc_rate.get(cause, cc_rate.get("__default__", 0.08))
        feature_dict["station_priority_rate"] = sp_rate.get(corridor, sp_rate.get("__default__", 0.5))
    else:
        feature_dict.setdefault("cause_closure_rate", 0.08)
        feature_dict.setdefault("station_priority_rate", 0.5)

    if priority_lookups:
        cc_rate = priority_lookups.get("cause_closure_rate", {})
        cd_log  = priority_lookups.get("corridor_density_log", {})
        # priority model's own cause_closure_rate may differ slightly from
        # closure model's (different train fold) — recompute from its table
        feature_dict["cause_closure_rate"] = cc_rate.get(cause, cc_rate.get("__default__", feature_dict["cause_closure_rate"]))
        feature_dict["corridor_density_log"] = cd_log.get(corridor, cd_log.get("__default__", 0.0))
    else:
        feature_dict.setdefault("corridor_density_log", 0.0)

    return feature_dict


def _vector_for(feature_dict: dict, feature_cols: list) -> pd.DataFrame:
    """Select + order exactly the columns the model was trained on."""
    row = {c: feature_dict[c] for c in feature_cols}
    return pd.DataFrame([row], columns=feature_cols)


def run_prediction(req: PredictionRequest) -> PredictionResponse:
    t0 = time.perf_counter()
    arts = get_artifacts()

    if not arts.all_core_loaded:
        logger.warning("Artifacts not ready — serving mock prediction")
        return PredictionResponse(
            closure_probability=0.08,
            closure_flag=False,
            priority_probability=0.20,
            predicted_priority="Low",
            disagreement_flag=False,
            disagreement_reason=None,
            predicted_duration_mins=45.0,
            duration_bucket="short",
            duration_p25=15.0,
            duration_p75=90.0,
            model_versions={"closure_model": "mock", "priority_model": "mock"},
            inference_ms=int((time.perf_counter() - t0) * 1000),
        )

    feature_dict = _build_base_features(req, arts.encoders)
    feature_dict = _apply_encoding_lookups(
        feature_dict, req, arts.closure_encoding_lookups, arts.priority_encoding_lookups
    )

    # Build each model's input using ITS OWN feature_cols from meta —
    # this is what makes the service immune to future retrains changing
    # the feature set.
    closure_cols  = arts.closure_meta["feature_cols"]
    priority_cols = arts.priority_meta["feature_cols"]

    X_closure  = _vector_for(feature_dict, closure_cols)
    X_priority = _vector_for(feature_dict, priority_cols)

    closure_threshold  = arts.closure_meta.get("threshold", 0.5)
    priority_threshold = arts.priority_meta.get("threshold", 0.5)

    closure_prob = float(arts.closure_model.predict_proba(X_closure)[0][1])
    closure_flag = closure_prob >= closure_threshold

    # priority_model (v2) actually predicts requires_road_closure as a
    # data-driven severity proxy — see priority_meta["note"]. We surface it
    # under the existing "priority" response fields so the frontend contract
    # doesn't change, but treat its threshold independently.
    severity_prob = float(arts.priority_model.predict_proba(X_priority)[0][1])
    predicted_priority = "High" if severity_prob >= priority_threshold else "Low"

    is_non_corridor = feature_dict["is_non_corridor"]
    disagreement_flag = bool(is_non_corridor and predicted_priority == "High")
    disagreement_reason = (
        "This incident is off the named corridors. The current system defaults "
        "these to Low priority. Our model predicts High severity based on cause, "
        "vehicle type, and time pattern."
        if disagreement_flag else None
    )

    duration_rec = (
        arts.duration_lookup.get(req.event_cause)
        or arts.duration_lookup.get("__default__", {"median": 45.0, "p25": 15.0, "p75": 90.0})
    )
    predicted_duration_mins = float(duration_rec.get("median", 45.0))
    duration_p25 = float(duration_rec.get("p25", 15.0))
    duration_p75 = float(duration_rec.get("p75", 90.0))

    duration_bucket = "short"
    if predicted_duration_mins > 120:
        duration_bucket = "long"
    elif predicted_duration_mins > 60:
        duration_bucket = "medium"

    inference_ms = int((time.perf_counter() - t0) * 1000)

    return PredictionResponse(
        closure_probability=round(closure_prob, 4),
        closure_flag=closure_flag,
        priority_probability=round(severity_prob, 4),
        predicted_priority=predicted_priority,
        disagreement_flag=disagreement_flag,
        disagreement_reason=disagreement_reason,
        predicted_duration_mins=predicted_duration_mins,
        duration_bucket=duration_bucket,
        duration_p25=duration_p25,
        duration_p75=duration_p75,
        model_versions={
            "closure_model": arts.closure_meta.get("version", "v2"),
            "priority_model": arts.priority_meta.get("version", "v2"),
        },
        inference_ms=inference_ms,
    )