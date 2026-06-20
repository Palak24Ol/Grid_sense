from fastapi import APIRouter
from typing import Any, Dict, List

from backend.services.logistics_service import (
    get_lcv_risk_summary,
    get_lcv_corridors,
    get_surge_impact,
)

router = APIRouter(prefix="/lcv", tags=["logistics"])


@router.get("/risk")
def get_lcv_risk() -> Dict[str, Any]:
    """LCV risk summary across all corridors — computed live from
    data/processed/lcv_incidents.csv on every call (see logistics_service.py)."""
    return get_lcv_risk_summary()


@router.get("/corridors")
def get_lcv_corridors_route() -> List[Dict[str, Any]]:
    """Per-corridor LCV breakdown with rerouting recommendations."""
    return get_lcv_corridors()


@router.get("/surge-impact")
def get_lcv_surge_impact() -> Dict[str, Any]:
    """Real LCV-specific numbers for the March 7, 2024 weather surge."""
    return get_surge_impact()
