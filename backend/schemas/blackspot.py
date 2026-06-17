from pydantic import BaseModel
from typing import Optional

class BlackspotJunctionOut(BaseModel):
    junction: str
    total_incidents: int
    recurrence_weeks: int
    closures: int
    high_priority: int
    corridor: str
    top_cause: str
    peak_hour: int
    latitude: float
    longitude: float
    blackspot_score: float
    blackspot_tier: str  # Chronic / Critical / At Risk / Monitored

class BlackspotListResponse(BaseModel):
    total: int
    chronic_count: int
    critical_count: int
    junctions: list[BlackspotJunctionOut]

class NeglectStationOut(BaseModel):
    police_station: str
    total_incidents: int
    neglected_count: int
    neglect_rate: float
    top_neglected_cause: str

class NeglectIndexResponse(BaseModel):
    stations: list[NeglectStationOut]
