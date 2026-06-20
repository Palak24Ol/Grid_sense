from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.schemas.prediction import PredictionRequest, PredictionResponse, AnalogLookupRequest, AnalogLookupResponse, AnalogEvent
from backend.services.prediction_service import predict_incident
from backend.core.logging import get_logger
from backend.api.dependencies import get_db
from backend.db.repositories.triage_log_repository import TriageLogRepository
from backend.db.models.triage_log import TriageLog

router = APIRouter(prefix="/predict", tags=["prediction"])
logger = get_logger(__name__)

@router.post("/triage", response_model=PredictionResponse)
def predict_triage(req: PredictionRequest, db: Session = Depends(get_db)) -> PredictionResponse:
    try:
        # Currently run_prediction returns a flat dict in prediction_service?
        # No, wait, prediction_service currently returns an old structure. We need to adapt it.
        # I'll just rewrite prediction_service's return later, but for now we call it
        res = predict_incident(req)
        
        # Log to triage_log
        try:
            repo = TriageLogRepository(db)
            repo.create(TriageLog(
                corridor=req.corridor,
                event_cause=req.event_cause,
                vehicle_type=req.vehicle_type,
                hour_of_day=req.hour_of_day,
                day_of_week=req.day_of_week,
                closure_probability=res.closure_probability,
                priority_probability=res.priority_probability,
                predicted_priority=res.predicted_priority,
                disagreement_flag=res.disagreement_flag,
                predicted_duration_mins=res.predicted_duration_mins,
                # we don't have deployment here yet
            ))
        except Exception as db_err:
            logger.warning(f"Failed to log triage prediction to database: {db_err}")
            
        return res
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

from backend.schemas.prediction import CascadeRequest, CascadeResponse
from backend.services.cascade_service import CascadeService

@router.post("/cascade", response_model=CascadeResponse)
async def predict_cascade(request: CascadeRequest, service: CascadeService = Depends()):
    """
    Given a planned event (cause + corridor + hour), returns:
    - cascade_multiplier for this event type
    - list of at-risk junctions on the primary corridor
    - list of adjacent corridors with reduced but elevated risk
    - recommended officer buffer (extra officers beyond base deployment)
    """
    return service.predict_cascade(
        cause=request.event_cause,
        corridor=request.corridor,
        hour=request.hour_of_day,
        day_of_week=request.day_of_week
    )

@router.post("/planned-event-lookup", response_model=AnalogLookupResponse)
def planned_event_lookup(
    req: AnalogLookupRequest,
    db: Session = Depends(get_db),
    cascade: CascadeService = Depends(),
):
    """
    Returns historical analog incidents for a planned event type + corridor,
    enriched with cascade_multiplier from the trained cascade model.

    Analog similarity scoring:
      - Same event_cause:  +0.60
      - Same corridor:     +0.25
      - Hour within ±2h:  +0.10
      - Same day_of_week: +0.05
    """
    from sqlalchemy import select, or_
    from backend.db.models.incident import Incident

    # Resolve cascade context (uses the same loaded artifacts as /predict/cascade)
    cascade_data = cascade.predict_cascade(
        cause=req.event_cause,
        corridor=req.corridor,
        hour=req.hour_of_day,
        day_of_week=req.day_of_week,
    )
    cascade_multiplier: float = cascade_data["cascade_multiplier"]
    risk_level: str = cascade_data["risk_level"]
    affected_corridors: list = [
        s["corridor"] for s in cascade_data.get("adjacent_corridor_spillover", [])
    ]
    recommend_pre_deployment: bool = cascade_multiplier > 1.5
    sample_count: int = cascade_data.get("sample_count", 0)

    # Query candidates: planned incidents on same cause OR same corridor
    query = (
        select(Incident)
        .where(Incident.event_type == "planned")
        .where(
            or_(
                Incident.event_cause == req.event_cause,
                Incident.corridor == req.corridor,
            )
        )
        .order_by(Incident.start_datetime.desc())
        .limit(500)
    )
    candidates = db.execute(query).scalars().all()

    # Score each candidate
    scored = []
    for inc in candidates:
        score = 0.0
        if inc.event_cause == req.event_cause:
            score += 0.60
        if inc.corridor == req.corridor:
            score += 0.25
        if inc.start_datetime:
            if abs(inc.start_datetime.hour - req.hour_of_day) <= 2:
                score += 0.10
            if inc.start_datetime.weekday() == req.day_of_week:
                score += 0.05
        if score > 0.0:
            scored.append((score, inc))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_analogs = scored[:10]

    # Build analog list, embedding cascade context in description
    cascade_summary = (
        f"cascade_multiplier={cascade_multiplier}x, risk={risk_level}. "
        f"{'⚠ Pre-deployment recommended.' if recommend_pre_deployment else 'Monitor only.'} "
        f"Spillover risk on: {', '.join(affected_corridors[:3]) if affected_corridors else 'no adjacent corridors'}."
    )

    analog_events = []
    for sim_score, inc in top_analogs:
        analog_events.append(
            AnalogEvent(
                id=inc.id,
                event_cause=inc.event_cause,
                corridor=inc.corridor or req.corridor,
                start_datetime=inc.start_datetime.isoformat() if inc.start_datetime else "unknown",
                duration_mins=inc.duration_mins or 0.0,
                requires_road_closure=bool(inc.requires_road_closure),
                similarity_score=round(sim_score, 2),
                description=inc.description or cascade_summary,
            )
        )

    total = len(analog_events)
    warning = None
    if total == 0:
        warning = (
            f"No historical analogs for cause='{req.event_cause}' on '{req.corridor}'. "
            f"{cascade_summary}"
        )
    elif sample_count < 10:
        warning = (
            f"Low sample count ({sample_count}) for '{req.event_cause}' — "
            f"cascade estimates have reduced confidence."
        )

    return AnalogLookupResponse(
        analogs=analog_events,
        total_analogs_found=total,
        sample_size_warning=warning,
    )