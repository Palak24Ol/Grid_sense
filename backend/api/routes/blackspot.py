from fastapi import APIRouter, Depends
from backend.services.blackspot_service import BlackspotService
from backend.schemas.blackspot import BlackspotListResponse, NeglectIndexResponse

router = APIRouter(prefix="/blackspot", tags=["blackspot"])

@router.get("/junctions", response_model=BlackspotListResponse)
async def get_blackspot_junctions(
    tier: str | None = None,        # Filter: Chronic / Critical / At Risk / Monitored
    corridor: str | None = None,    # Filter by corridor
    min_score: float | None = None, # Filter by minimum blackspot score
    service: BlackspotService = Depends()
):
    """
    Returns ranked list of chronic blackspot junctions.
    Tier filter: Chronic (score > 70), Critical (50-70), At Risk (30-50), Monitored (< 30).
    """
    return service.get_blackspots(tier=tier, corridor=corridor, min_score=min_score)


@router.get("/neglect", response_model=NeglectIndexResponse)
async def get_neglect_index(service: BlackspotService = Depends()):
    """
    Returns per-station neglect index: how often incidents stay open
    5x+ longer than expected for their cause.
    """
    return service.get_neglect_index()


@router.get("/junctions/{junction}", response_model=dict)
async def get_junction_profile(junction: str, service: BlackspotService = Depends()):
    """
    Full profile for a single junction:
    - Blackspot score + tier
    - Week-by-week recurrence timeline (for sparkline chart)
    - Cause breakdown
    - Historical incident list (last 20)
    """
    return service.get_junction_profile(junction)
