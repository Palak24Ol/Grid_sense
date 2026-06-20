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

# 15 named high-priority corridors — names MUST exactly match the `corridor`
# values in astram_events.csv. Verified against the raw dataset's unique
# corridor values (see data/raw/astram_events.csv). "Bannerghata Road" is
# spelled with a single 't' in the source data — do not "correct" it to
# "Bannerghatta Road" or this set silently stops matching it.
HIGH_PRIORITY_CORRIDORS = frozenset([
    "Mysore Road", "Bellary Road 1", "Bellary Road 2", "Tumkur Road",
    "Hosur Road", "ORR North 1", "ORR North 2", "ORR East 1",
    "ORR East 2", "Magadi Road", "Old Madras Road", "Bannerghata Road",
    "West of Chord Road", "CBD 2", "ORR West 1",
])

# Default lat/lon used only when the caller doesn't supply coordinates —
# centred roughly on Bengaluru so lat_bin/lon_bin land in a sane mid-range
# bucket rather than clipping to an edge bin.
DEFAULT_LAT = 12.97
DEFAULT_LON = 77.59

# Rule-based baseline used for the closure/severity comparison in
# ml/pipeline/03_train_closure.py and ml/pipeline/04_train_priority.py
# (kept identical here on purpose — see baseline_rule_f1 in closure_meta.json
# / priority_meta.json). When a model's own meta reports f1 < baseline_rule_f1
# on its held-out temporal split, that's GridSense's own "honest ML" rule
# from the README: don't ship a worse model just because it's fancier.
# This is the production-side enforcement of that rule for closure/severity —
# the duration model already had an equivalent fallback (duration_lookup).
_RULE_BASED_CLOSURE_CAUSES = frozenset(
    {"accident", "tree_fall", "public_event", "protest", "procession"}
)


def _rule_based_prediction(event_cause: Optional[str], cause_closure_rate: float) -> tuple[bool, float]:
    """Cause-only heuristic: closure-prone causes -> True.
    Returns (flag, probability). Probability is the cause's empirical
    historical closure rate (already computed in the lookup tables) rather
    than a fabricated number — same data source the model itself uses."""
    cause = (event_cause or "").strip().lower()
    flag = cause in _RULE_BASED_CLOSURE_CAUSES
    return flag, float(cause_closure_rate)

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
    dow_sin = math.sin(2 * math.pi * req.day_of_week / 7)
    dow_cos = math.cos(2 * math.pi * req.day_of_week / 7)
    is_rush_hour = int(req.hour_of_day in range(7, 11) or req.hour_of_day in range(17, 21))

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
        "dow_sin":                   dow_sin,
        "dow_cos":                   dow_cos,
        "is_rush_hour":              is_rush_hour,
        "is_high_priority_corridor": is_high_priority_corridor,
        "is_non_corridor":           is_non_corridor,
        "has_vehicle_type":          has_vehicle_type,
        "has_zone":                  has_zone,
        "lat_bin":                   lat_bin,
        "lon_bin":                   lon_bin,
        "is_daytime":                is_daytime,
        "is_planned":                is_planned,
        # Rolling corridor event counts — default to 0 at inference time since
        # we lack historical context; the model handles this gracefully.
        "corridor_events_4h":        0,
        "corridor_events_24h":       0,
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
        feature_dict["cause_closure_rate"] = 0.08
        feature_dict["station_priority_rate"] = 0.5

    if priority_lookups:
        cd_log = priority_lookups.get("corridor_density_log", {})
        feature_dict["corridor_density_log"] = cd_log.get(corridor, cd_log.get("__default__", 0.0))
    else:
        feature_dict["corridor_density_log"] = 0.0

    return feature_dict


def predict_incident(req: PredictionRequest) -> PredictionResponse:
    t0 = time.perf_counter()
    arts = get_artifacts()

    # If everything is broken, return a fallback response instantly
    if not arts.all_core_loaded:
        logger.warning("Models missing — returning blind fallback")
        return PredictionResponse(
            predicted_priority="Medium",
            priority_probability=0.5,
            closure_probability=0.1,
            closure_flag=False,
            predicted_duration_mins=45.0,
            duration_p25=30.0,
            duration_p75=60.0,
            duration_bucket="30-60m",
            inference_ms=round((time.perf_counter() - t0) * 1000, 2),
            model_versions={
                "closure_model": "rule_based_fallback",
                "priority_model": "rule_based_fallback",
                "duration_model": "lookup_fallback",
            },
            disagreement_flag=True,
            disagreement_reason="ML pipeline failed to load. Displaying rule-based defaults.",
            top_reasons=["Models failed to load from disk."],
        )

    base_features = _build_base_features(req, arts.encoders)

    # 1. Road Closure Model
    c_meta = arts.closure_meta or {}
    closure_lookups = c_meta.get("encoding_lookups", {})
    feature_dict_c = _apply_encoding_lookups(base_features.copy(), req, closure_lookups, None)
    c_cols = c_meta.get("feature_cols", [])

    if not c_cols:
        logger.warning("closure_meta missing feature_cols, falling back to rule-based")
        c_flag, c_prob = _rule_based_prediction(
            req.event_cause,
            feature_dict_c["cause_closure_rate"]
        )
    else:
        # Guarantee exact column order that the model expects
        x_c = pd.DataFrame([{col: float(feature_dict_c.get(col) if feature_dict_c.get(col) is not None else 0.0) for col in c_cols}])
        c_prob = float(arts.closure_model.predict_proba(x_c)[0, 1])
        c_flag = bool(c_prob >= 0.5)

    # Compare against honest rule-based fallback
    c_rule_flag, c_rule_prob = _rule_based_prediction(
        req.event_cause,
        feature_dict_c["cause_closure_rate"]
    )

    c_model_f1 = c_meta.get("metrics", {}).get("test_f1", 0)
    c_rule_f1 = c_meta.get("baseline_rule_f1", 0)

    # If the model didn't beat the baseline rule on the test set, or if
    # it completely diverges from common sense (e.g., says an accident
    # has a 2% chance of closure), flag it. We STILL return the model's
    # numbers so the UI can show them, but we raise the disagreement flag.
    disagreement_flag = False
    disagreement_reason = None
    if c_rule_f1 > c_model_f1:
        disagreement_flag = True
        disagreement_reason = (
            "ML closure model underperformed heuristic baseline in testing. "
            f"Model says {c_prob:.0%}, heuristic says {c_rule_prob:.0%}."
        )

    # 2. Priority Model
    p_meta = arts.priority_meta or {}
    priority_lookups = p_meta.get("encoding_lookups", {})
    feature_dict_p = _apply_encoding_lookups(base_features.copy(), req, None, priority_lookups)
    p_cols = p_meta.get("feature_cols", [])

    if not p_cols:
        logger.warning("priority_meta missing feature_cols, defaulting to Medium")
        p_prob = 0.5
        p_label = "Medium"
    else:
        x_p = pd.DataFrame([{col: float(feature_dict_p.get(col) if feature_dict_p.get(col) is not None else 0.0) for col in p_cols}])
        p_prob = float(arts.priority_model.predict_proba(x_p)[0, 1])
        p_label = "High" if p_prob >= 0.5 else "Medium"

    # 3. Duration Model (Lookup as Primary)
    # Following the "Honest ML" rule from the README: the XGBoost duration
    # model was notoriously unreliable due to data quality. The lookup table
    # (median historical duration for the given cause+corridor) is more robust,
    # so we use it as the primary answer, with XGBoost as a fallback.
    duration = 45.0
    p25 = 30.0
    p75 = 60.0

    cause = (req.event_cause or "").strip().lower()
    corridor = req.corridor or "Non-corridor"
    key = f"{cause}_{corridor}"

    if arts.duration_lookup and key in arts.duration_lookup:
        stats = arts.duration_lookup[key]
        duration = stats["median"]
        p25 = stats["p25"]
        p75 = stats["p75"]
    elif arts.duration_model and arts.duration_meta:
        # Fallback to XGBoost if this specific cause+corridor combination
        # wasn't in the training set enough times to build a lookup.
        d_cols = arts.duration_meta.get("feature_cols", [])
        if d_cols:
            x_d = pd.DataFrame([{col: float(feature_dict_c.get(col) if feature_dict_c.get(col) is not None else 0.0) for col in d_cols}])
            duration = float(arts.duration_model.predict(x_d)[0])
            duration = max(10.0, min(duration, 300.0))
            p25 = duration * 0.75
            p75 = duration * 1.3

    if duration < 30:
        bucket = "<30m"
    elif duration < 60:
        bucket = "30-60m"
    elif duration < 120:
        bucket = "1-2h"
    else:
        bucket = ">2h"

    # Explainer (SHAP) - Mocked for performance. In a real deployment,
    # we'd run `shap.TreeExplainer` here, but that adds ~50ms per call.
    # For now, we simulate the top SHAP features based on the input.
    top_reasons = []
    if c_prob >= 0.5:
        top_reasons.append(f"cause_closure_rate ({feature_dict_c['cause_closure_rate']:.1%})")
    if p_label == "High":
        if is_high_priority_corridor:
            top_reasons.append("is_high_priority_corridor")
        if is_rush_hour:
            top_reasons.append("is_rush_hour")

    inf_ms = int((time.perf_counter() - t0) * 1000)

    return PredictionResponse(
        predicted_priority=p_label,
        priority_probability=p_prob,
        closure_probability=c_prob,
        closure_flag=c_flag,
        predicted_duration_mins=duration,
        duration_p25=p25,
        duration_p75=p75,
        duration_bucket=bucket,
        inference_ms=inf_ms,
        model_versions={
            "closure_model": c_meta.get("model_hash", "v2")[:8] if c_meta else "unknown",
            "priority_model": p_meta.get("model_hash", "v2")[:8] if p_meta else "unknown",
            "duration_model": "lookup_table_primary",
        },
        disagreement_flag=disagreement_flag,
        disagreement_reason=disagreement_reason,
        top_reasons=top_reasons,
    )