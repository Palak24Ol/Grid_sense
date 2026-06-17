import math
import time
from typing import Optional, Dict

import pandas as pd

from backend.schemas.prediction import PredictionRequest, PredictionResponse
from backend.services.artifact_loader import get_artifacts
from backend.core.logging import get_logger

logger = get_logger(__name__)

CLOSURE_THRESHOLD = 0.35

CLOSURE_FEATURE_ORDER = [
    "corridor_encoded",
    "event_cause_encoded",
    "vehicle_type_encoded",
    "hour_of_day",
    "day_of_week",
    "month",
    "hour_sin",
    "hour_cos",
    "is_high_priority_corridor",
    "is_non_corridor",
    "has_vehicle_type",
    "has_zone",
]

PRIORITY_FEATURE_ORDER = [
    "event_cause_encoded",
    "vehicle_type_encoded",
    "hour_of_day",
    "day_of_week",
    "month",
    "hour_sin",
    "hour_cos",
    "is_high_priority_corridor",
    "has_vehicle_type",
    "has_zone",
]

HIGH_PRIORITY_CORRIDORS = frozenset([
    "Mysore Road", "Bellary Road 1", "Bellary Road 2", "Tumkur Road",
    "Hosur Road", "ORR North 1", "ORR North 2", "ORR East 1",
    "ORR East 2", "Magadi Road", "Old Madras Road", "Bannerghatta Road",
    "West of Chord Road", "CBD 2", "ORR West 1", "ORR West 2",
])

def _safe_encode(encoders: dict, col: str, value: Optional[str]) -> int:
    if value is None or str(value).strip().lower() in ("", "null", "nan", "none"):
        return -1
    le = encoders.get(col)
    if le is None:
        return -1
    try:
        return int(le.transform([str(value)])[0])
    except ValueError:
        return -1

def run_prediction(req: PredictionRequest) -> PredictionResponse:
    t0 = time.perf_counter()
    arts = get_artifacts()

    corridor = req.corridor
    is_non_corridor = int(not corridor or str(corridor).strip().lower() in ("non-corridor", "", "null", "nan"))
    is_high_priority_corridor = int(corridor.strip() in HIGH_PRIORITY_CORRIDORS) if not is_non_corridor else 0

    hour_sin = math.sin(2 * math.pi * req.hour_of_day / 24)
    hour_cos = math.cos(2 * math.pi * req.hour_of_day / 24)
    
    # Month is not provided in PredictionRequest, assume current month or default to 6 for testing
    month = 6 

    feature_dict = {
        "corridor_encoded": _safe_encode(arts.encoders, "corridor", corridor) if arts.all_core_loaded else -1,
        "event_cause_encoded": _safe_encode(arts.encoders, "event_cause", req.event_cause) if arts.all_core_loaded else -1,
        "vehicle_type_encoded": _safe_encode(arts.encoders, "vehicle_type", req.vehicle_type) if arts.all_core_loaded else -1,
        "hour_of_day": req.hour_of_day,
        "day_of_week": req.day_of_week,
        "month": month,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "is_high_priority_corridor": is_high_priority_corridor,
        "is_non_corridor": is_non_corridor,
        "has_vehicle_type": int(req.vehicle_type is not None and req.vehicle_type != ""),
        "has_zone": 0,  # zone is not in request
    }

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
            inference_ms=int((time.perf_counter() - t0) * 1000)
        )

    # Closure
    X_closure = pd.DataFrame([[feature_dict[c] for c in CLOSURE_FEATURE_ORDER]], columns=CLOSURE_FEATURE_ORDER)
    closure_prob = float(arts.closure_model.predict_proba(X_closure)[0][1])
    closure_flag = closure_prob >= CLOSURE_THRESHOLD

    # Priority
    X_priority = pd.DataFrame([[feature_dict[c] for c in PRIORITY_FEATURE_ORDER]], columns=PRIORITY_FEATURE_ORDER)
    priority_prob = float(arts.priority_model.predict_proba(X_priority)[0][1])
    predicted_priority = "High" if priority_prob >= 0.5 else "Low"

    # Disagreement
    disagreement_flag = bool(is_non_corridor and predicted_priority == "High")
    disagreement_reason = "This incident is off the named corridors. The current system defaults these to Low priority. Our model predicts High based on cause, vehicle type, and time pattern." if disagreement_flag else None

    # Duration
    duration_rec = arts.duration_lookup.get(req.event_cause) or arts.duration_lookup.get("__default__", {"median": 45.0, "p25": 15.0, "p75": 90.0})
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
        priority_probability=round(priority_prob, 4),
        predicted_priority=predicted_priority,
        disagreement_flag=disagreement_flag,
        disagreement_reason=disagreement_reason,
        predicted_duration_mins=predicted_duration_mins,
        duration_bucket=duration_bucket,
        duration_p25=duration_p25,
        duration_p75=duration_p75,
        model_versions={"closure_model": "v1.0", "priority_model": "v1.0"},
        inference_ms=inference_ms
    )