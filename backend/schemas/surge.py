from pydantic import BaseModel
from typing import Optional

class SurgeCorridorOut(BaseModel):
    corridor: str
    water_logging_count: int
    tree_fall_count: int
    total_weather_incidents: int
    closure_count: int
    vulnerability_score: float
    deployment_priority: str  # Critical / High / Medium / Low
    latitude: float
    longitude: float

class SurgeVulnerabilityResponse(BaseModel):
    critical_count: int
    high_count: int
    corridors: list[SurgeCorridorOut]

class SurgeHourlyPoint(BaseModel):
    hour_of_day: int
    total: int
    water_logging: int
    tree_fall: int
    closures: int
    top_corridor: str

class PreDeploymentItem(BaseModel):
    corridor: str
    recommended_station: str
    recommended_officers: int
    escalation_tier: str
    surge_reason: str
    recommended_action_time: str

class SurgeStats(BaseModel):
    march6_total: int
    march7_total: int
    surge_multiplier: float
    peak_hour: int
    peak_hour_count: int
    total_closures: int
    water_logging_count: int
    tree_fall_count: int

class SurgeReplayResponse(BaseModel):
    surge_day: str
    baseline_day: str
    surge_stats: SurgeStats
    march7_hourly_timeline: list[SurgeHourlyPoint]
    top_corridors_hit: dict
    pre_deployment_plan: list[PreDeploymentItem]
