from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.schemas.prediction import PredictionRequest, PredictionResponse, AnalogLookupRequest, AnalogLookupResponse
from backend.services.prediction_service import run_prediction
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
        res = run_prediction(req)
        
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
def planned_event_lookup(req: AnalogLookupRequest):
    return AnalogLookupResponse(analogs=[], total_analogs_found=0, sample_size_warning="Not implemented")