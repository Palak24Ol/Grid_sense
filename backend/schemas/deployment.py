from pydantic import BaseModel
from typing import List, Optional

class DeploymentRequest(BaseModel):
    corridor: str
    event_cause: str
    vehicle_type: str
    hour_of_day: int
    day_of_week: int
    closure_probability: float
    predicted_priority: str
    predicted_duration_mins: float

class DeploymentResponse(BaseModel):
    recommended_station: str
    secondary_station: Optional[str]
    recommended_officer_count: int
    officer_count_rationale: str
    escalation_tier: str
    escalation_rationale: str
    deployment_duration_mins: float
    suggested_junctions: List[str]
    corridor_risk_score: float
    historical_station_incidents: int
