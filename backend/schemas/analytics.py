"""
schemas/analytics.py — Pydantic models for analytics / heatmap endpoints.
"""

from typing import Optional
from pydantic import BaseModel


class HourlyBucket(BaseModel):
    hour: int
    incident_count: int
    avg_duration_mins: Optional[float]
    closure_count: int


class DailyBucket(BaseModel):
    day_of_week: int        # 0=Monday
    day_name: str
    incident_count: int
    avg_duration_mins: Optional[float]


class CauseBreakdown(BaseModel):
    event_cause: str
    count: int
    percentage: float
    avg_duration_mins: Optional[float]
    closure_count: int


class AnalyticsSummaryResponse(BaseModel):
    total_incidents: int
    stale_active_flagged: int
    corrected_active_count: int
    high_priority_count: int
    high_priority_rate: float
    closure_count: int
    closure_rate: float
    avg_duration_mins: Optional[float]
    median_duration_mins: Optional[float]
    hourly_distribution: list[HourlyBucket]
    daily_distribution: list[DailyBucket]
    cause_breakdown: list[CauseBreakdown]


class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    weight: float           # incident count or risk score
    corridor: Optional[str]
    junction: Optional[str]


class HeatmapResponse(BaseModel):
    points: list[HeatmapPoint]
    total_points: int


class ForecastPoint(BaseModel):
    ds: str                 # ISO datetime string
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ForecastResponse(BaseModel):
    junction: str
    forecast_hours: int
    points: list[ForecastPoint]
    model_mae: Optional[float]
    available: bool = True


class StalenessReportResponse(BaseModel):
    total_active: int
    stale_active_count: int
    corrected_active_count: int
    stale_rate: float
    stale_incidents: list[dict]