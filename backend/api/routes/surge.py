from fastapi import APIRouter, Depends
from backend.services.surge_service import SurgeService
from backend.schemas.surge import SurgeVulnerabilityResponse, SurgeReplayResponse

router = APIRouter(prefix="/surge", tags=["surge"])


@router.get("/vulnerability", response_model=SurgeVulnerabilityResponse)
async def get_surge_vulnerability(service: SurgeService = Depends()):
    """
    Returns per-corridor vulnerability to weather-driven surge events.
    Used to populate the surge mode overlay on the map.
    """
    return service.get_vulnerability()


@router.get("/replay/march7", response_model=SurgeReplayResponse)
async def get_march7_replay(service: SurgeService = Depends()):
    """
    Returns the March 7, 2024 surge replay dataset.
    Includes: what GridSense would have pre-deployed at 11pm March 6,
    and what actually happened hour-by-hour on March 7.
    Used for the demo's "What would have happened" moment.
    """
    return service.get_march7_replay()


@router.post("/trigger")
async def trigger_surge_mode(payload: dict, service: SurgeService = Depends()):
    """
    Webhook endpoint for external weather alerts (production concept).
    In demo: called manually to simulate a weather alert being received.
    Fires the city-wide pre-deployment plan.
    
    Body: { "alert_type": "heavy_rain", "severity": "red", "source": "IMD" }
    """
    return service.generate_surge_deployment_plan(alert=payload)
