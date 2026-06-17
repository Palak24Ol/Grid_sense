from pydantic import BaseModel
from typing import List, Optional

class JunctionForecastPoint(BaseModel):
    datetime: str
    hour_of_day: int
    predicted_incident_count: float
    yhat_lower: float
    yhat_upper: float
    is_peak_hour: bool

class PeakWindow(BaseModel):
    start_hour: int
    end_hour: int
    label: str

class JunctionForecastResponse(BaseModel):
    junction: str
    corridor: str
    historical_daily_avg: float
    forecast: List[JunctionForecastPoint]
    peak_windows: List[PeakWindow]
    model_mae: Optional[float]

class CorridorForecastSummary(BaseModel):
    corridor: str
    next_24h_predicted_incidents: float
    peak_hour: int
    peak_predicted_count: float
    risk_level: str

class CorridorsForecastResponse(BaseModel):
    generated_at: str
    corridors: List[CorridorForecastSummary]
