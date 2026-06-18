from fastapi import APIRouter
from typing import List

from backend.services.forecast_service import (
    get_junction_forecast,
    get_corridors_forecast,
    list_available_junctions,
)
from backend.schemas.forecast import JunctionForecastResponse, CorridorsForecastResponse

router = APIRouter(prefix="/forecast", tags=["forecast"])

@router.get("/junction/{junction}", response_model=JunctionForecastResponse)
def get_junction(junction: str, hours_ahead: int = 72):
    return get_junction_forecast(junction, hours_ahead)

@router.get("/corridors", response_model=CorridorsForecastResponse)
def get_corridors():
    return get_corridors_forecast()

@router.get("/junctions", response_model=dict)
def get_available_junctions():
    """List all junctions that have a trained Prophet model."""
    return {"junctions": list_available_junctions()}
