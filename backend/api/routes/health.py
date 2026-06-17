"""
api/routes/health.py — GET /health

Used by Docker healthcheck, load balancer probes, and the frontend
status indicator. Returns database + artifact availability.
"""

from fastapi import APIRouter
from backend.db.connection import check_db_connection
from backend.services.artifact_loader import get_artifacts
from backend.schemas.health import HealthResponse, ArtifactStatus
from backend.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    db_ok = check_db_connection()
    arts = get_artifacts()
    status_dict = arts.get_artifact_status()

    all_ok = db_ok and arts.all_core_loaded
    status = "ok" if all_ok else ("degraded" if db_ok else "down")

    return HealthResponse(
        status=status,
        database=db_ok,
        artifacts=ArtifactStatus(**status_dict),
        mock_mode=settings.MOCK_MODE or not arts.all_core_loaded,
    )