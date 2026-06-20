from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class PredictionRequest(BaseModel):
    corridor: Optional[str] = None
    event_cause: str
    vehicle_type: Optional[str] = None
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)  # 0=Mon ... 6=Sun
    month: Optional[int] = Field(default=None, ge=1, le=12)
    zone: Optional[str] = None
    police_station: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_planned: Optional[bool] = None

class PredictionResponse(BaseModel):
    closure_probability: float
    closure_flag: bool
    priority_probability: float
    predicted_priority: str
    disagreement_flag: bool
    disagreement_reason: Optional[str]
    predicted_duration_mins: float
    duration_bucket: str
    duration_p25: Optional[float]
    duration_p75: Optional[float]
    top_reasons: Optional[List[str]] = None
    model_versions: Dict[str, str]
    inference_ms: int

class AnalogLookupRequest(BaseModel):
    event_cause: str
    corridor: str
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)

class AnalogEvent(BaseModel):
    id: str
    event_cause: str
    corridor: str
    start_datetime: str
    duration_mins: float
    requires_road_closure: bool
    similarity_score: float
    description: Optional[str]

class AnalogLookupResponse(BaseModel):
    analogs: List[AnalogEvent]
    total_analogs_found: int
    sample_size_warning: Optional[str]

class CascadeRequest(BaseModel):
    event_cause: str        # procession, protest, public_event, vip_movement
    corridor: str
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    crowd_size: Optional[str] = None   # "small" | "medium" | "large"
    event_name: Optional[str] = None   # free text label e.g. "IPL Final at Chinnaswamy"

class CascadeAtRiskJunction(BaseModel):
    junction: str
    blackspot_score: float
    latitude: float
    longitude: float
    risk_reason: str

class CascadeAdjacentCorridor(BaseModel):
    corridor: str
    spillover_multiplier: float
    risk_level: str

class CascadeResponse(BaseModel):
    event_cause: str
    primary_corridor: str
    cascade_multiplier: float
    risk_level: str
    data_confidence: str
    sample_count: int
    primary_junctions_at_risk: list[CascadeAtRiskJunction]
    adjacent_corridor_spillover: list[CascadeAdjacentCorridor]
    recommended_officer_buffer: int
    cascade_window_hours: int
    interpretation: str
    crowd_size: Optional[str] = None
    crowd_multiplier: float = 1.0
    event_name: Optional[str] = None
    adjusted_cascade_multiplier: Optional[float] = None