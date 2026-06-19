from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from backend.api.dependencies import get_db
from backend.schemas.incident import IncidentListResponse, IncidentSummaryResponse, JunctionsResponse
from backend.db.repositories.incident_repository import IncidentRepository

router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.get("", response_model=IncidentListResponse)
def get_incidents(
    corridor: Optional[str] = None,
    event_cause: Optional[str] = None,
    priority: Optional[str] = None,
    event_type: Optional[str] = None,
    exclude_stale: bool = True,
    limit: int = 2000,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    repo = IncidentRepository(db)
    total, filtered, incidents = repo.get_incidents(
        corridor, event_cause, priority, event_type, exclude_stale, limit, offset
    )
    return IncidentListResponse(
        total=total,
        filtered=filtered,
        incidents=[{
            "id": i.id,
            "event_type": i.event_type,
            "event_cause": i.event_cause,
            "latitude": i.latitude,
            "longitude": i.longitude,
            "corridor": i.corridor,
            "junction": i.junction,
            "police_station": i.police_station,
            "priority": i.priority,
            "requires_road_closure": i.requires_road_closure,
            "start_datetime": i.start_datetime,
            "duration_mins": i.duration_mins,
            "status": i.status,
            "is_stale_active": i.is_stale_active,
        } for i in incidents]
    )

@router.get("/summary", response_model=IncidentSummaryResponse)
def get_summary(db: Session = Depends(get_db)):
    repo = IncidentRepository(db)
    return IncidentSummaryResponse(**repo.get_summary())

@router.get("/junctions", response_model=JunctionsResponse)
def get_junctions(db: Session = Depends(get_db)):
    repo = IncidentRepository(db)
    return JunctionsResponse(junctions=repo.get_junction_aggregates())

# ── Planned Event Lookup ─────────────────────────────────────────────────────
import json as _json
from pathlib import Path as _Path

_ARTIFACTS = _Path(__file__).parent.parent.parent.parent / "ml" / "artifacts"

def _load_json(name: str) -> dict:
    p = _ARTIFACTS / name
    return _json.loads(p.read_text()) if p.exists() else {}


@router.get("/planned-event-lookup")
def planned_event_lookup(event_type: str, corridor: str):
    """
    Given a planned event type + corridor, returns cascade multiplier,
    affected adjacent corridors, and pre-deployment recommendation.
    Directly answers the problem statement: planned events like rallies/festivals.
    """
    cascade_data   = _load_json("cascade_multipliers.json")
    adjacency_data = _load_json("corridor_adjacency.json")
    cri_data       = _load_json("corridor_risk_index.json")

    event_details      = cascade_data.get(event_type, {})
    multiplier         = event_details.get("cascade_multiplier", 1.0)
    affected_junctions = event_details.get("sample_count", 0)

    adjacent_corridors = adjacency_data.get(corridor, [])
    cri_entry          = cri_data.get(corridor, {})
    risk_score         = cri_entry.get("composite_risk_score", 0)
    top_station        = cri_entry.get("top_police_station", "Unknown")

    pre_deploy = multiplier > 1.5 or risk_score >= 57

    if multiplier >= 2.5:   severity = "critical"
    elif multiplier >= 1.5: severity = "high"
    elif multiplier >= 1.0: severity = "medium"
    else:                   severity = "low"

    return {
        "event_type":               event_type,
        "corridor":                 corridor,
        "cascade_multiplier":       round(multiplier, 2),
        "severity":                 severity,
        "affected_junctions_count": affected_junctions,
        "adjacent_corridors":       adjacent_corridors,
        "corridor_risk_score":      risk_score,
        "recommended_station":      top_station,
        "recommended_pre_deployment": pre_deploy,
        "pre_deployment_rationale": (
            f"{event_type.replace('_',' ').title()} events cause {multiplier:.1f}x baseline "
            f"incident rate on {corridor}. "
            f"{'Pre-deployment recommended.' if pre_deploy else 'Standard monitoring.'}"
        ),
        "suggested_diversions": adjacent_corridors[:2],
    }