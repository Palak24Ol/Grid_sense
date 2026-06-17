from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.schemas.deployment import DeploymentRequest, DeploymentResponse
from backend.services.deployment_service import get_deployment_recommendation
from backend.db.repositories.station_repository import StationRepository
from backend.db.repositories.corridor_repository import CorridorRepository
from backend.db.repositories.incident_repository import IncidentRepository
from backend.api.dependencies import get_db

router = APIRouter(prefix="/deploy", tags=["deployment"])

@router.post("/recommend", response_model=DeploymentResponse)
def recommend_deployment(req: DeploymentRequest, db: Session = Depends(get_db)):
    station_repo = StationRepository(db)
    corridor_repo = CorridorRepository(db)
    return get_deployment_recommendation(req, station_repo, corridor_repo)
