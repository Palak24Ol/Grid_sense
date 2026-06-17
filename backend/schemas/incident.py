from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime

class IncidentBase(BaseModel):
    id: str
    event_type: str
    event_cause: str
    latitude: float
    longitude: float
    corridor: Optional[str]
    junction: Optional[str]
    police_station: str
    priority: str
    requires_road_closure: bool
    start_datetime: datetime
    duration_mins: Optional[float]
    status: str
    is_stale_active: bool

class IncidentListResponse(BaseModel):
    total: int
    filtered: int
    incidents: List[IncidentBase]
    
class IncidentSummaryResponse(BaseModel):
    total_incidents: int
    corrected_active_count: int
    raw_active_count: int
    stale_removed: int
    total_closures: int
    planned_count: int
    unplanned_count: int
    date_range: Dict[str, Optional[str | int]]

class JunctionAggregate(BaseModel):
    junction: str
    latitude: float
    longitude: float
    incident_count: int
    high_priority_count: int
    closure_count: int
    top_cause: str

class JunctionsResponse(BaseModel):
    junctions: List[JunctionAggregate]