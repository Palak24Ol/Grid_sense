"""
schemas/health.py — Health check response schema.
"""

from typing import Optional
from pydantic import BaseModel


class ArtifactStatus(BaseModel):
    encoders: bool
    closure_model: bool
    priority_model: bool
    duration_lookup: bool
    corridor_risk_index: bool
    station_map: bool
    station_concurrency: bool
    prophet_models_count: int


class HealthResponse(BaseModel):
    status: str                    # ok | degraded | down
    database: bool
    artifacts: ArtifactStatus
    mock_mode: bool
    version: str = "1.0.0"