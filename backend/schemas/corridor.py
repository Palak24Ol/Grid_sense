from pydantic import BaseModel
from typing import List

class CorridorRiskResponseItem(BaseModel):
    corridor: str
    total_incidents: int
    high_priority_rate: float
    closure_rate: float
    composite_risk_score: float
    top_junction: str
    top_police_station: str
    median_duration_mins: float

class CorridorRiskResponse(BaseModel):
    corridors: List[CorridorRiskResponseItem]

class CorridorJunctionItem(BaseModel):
    junction: str
    incident_count: int
    share_of_corridor: float
    high_priority_count: int
    closure_count: int

class CorridorJunctionsResponse(BaseModel):
    corridor: str
    total_incidents: int
    junctions: List[CorridorJunctionItem]