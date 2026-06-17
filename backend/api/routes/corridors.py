from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.schemas.corridor import CorridorRiskResponse, CorridorJunctionsResponse
from backend.db.repositories.corridor_repository import CorridorRepository

router = APIRouter(prefix="/corridors", tags=["corridors"])

@router.get("/risk", response_model=CorridorRiskResponse)
def get_corridor_risk(db: Session = Depends(get_db)):
    repo = CorridorRepository(db)
    risks = repo.get_corridor_risk_leaderboard()
    return CorridorRiskResponse(corridors=[{
        "corridor": r.corridor,
        "total_incidents": r.total_incidents,
        "high_priority_rate": r.high_priority_rate,
        "closure_rate": r.closure_rate,
        "composite_risk_score": r.composite_risk_score,
        "top_junction": r.top_junction,
        "top_police_station": r.top_police_station,
        "median_duration_mins": r.median_duration_mins
    } for r in risks])

@router.get("/{corridor}/junctions", response_model=CorridorJunctionsResponse)
def get_corridor_junctions(corridor: str, db: Session = Depends(get_db)):
    repo = CorridorRepository(db)
    data = repo.get_corridor_junctions(corridor)
    return CorridorJunctionsResponse(**data)