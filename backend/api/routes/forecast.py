from fastapi import APIRouter

from backend.services.forecast_service import get_junction_forecast, get_corridors_forecast
from backend.schemas.forecast import JunctionForecastResponse, CorridorsForecastResponse

router = APIRouter(prefix="/forecast", tags=["forecast"])

@router.get("/junction/{junction}", response_model=JunctionForecastResponse)
def get_junction(junction: str, hours_ahead: int = 72):
    return get_junction_forecast(junction, hours_ahead)

@router.get("/corridors", response_model=CorridorsForecastResponse)
def get_corridors():
    return get_corridors_forecast()
