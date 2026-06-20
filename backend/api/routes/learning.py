"""
learning.py — Post-Event Learning System API

Exposes:
  GET  /learning/summary          — aggregated prediction accuracy metrics
  POST /learning/outcome/{log_id} — record actual outcome for a past prediction
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.api.dependencies import get_db
from backend.db.repositories.triage_log_repository import TriageLogRepository
from backend.core.logging import get_logger

router = APIRouter(prefix="/learning", tags=["learning"])
logger = get_logger(__name__)


class OutcomeUpdate(BaseModel):
    actual_duration_mins: Optional[float] = None
    actual_closure: Optional[bool] = None
    actual_officer_count: Optional[int] = None


@router.get("/summary")
def get_learning_summary(db: Session = Depends(get_db)):
    """
    Returns post-event learning analytics:
    - Duration MAE (predicted vs actual)
    - Closure classification accuracy
    - Disagreement rate
    - Priority distribution
    - Prediction history for chart
    """
    try:
        repo = TriageLogRepository(db)
        return repo.get_learning_summary(limit=200)
    except Exception as e:
        logger.error(f"Learning summary failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outcome/{log_id}")
def record_outcome(
    log_id: str,
    body: OutcomeUpdate,
    db: Session = Depends(get_db),
):
    """
    After an incident resolves, record the actual outcome.
    This feeds the learning dashboard and future model retraining.
    """
    try:
        repo = TriageLogRepository(db)
        updated = repo.update_actual_outcome(
            log_id=log_id,
            actual_duration_mins=body.actual_duration_mins,
            actual_closure=body.actual_closure,
            actual_officer_count=body.actual_officer_count,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Triage log {log_id} not found")
        return {"status": "updated", "log_id": log_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outcome update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))