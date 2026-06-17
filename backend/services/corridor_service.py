"""
services/corridor_service.py — Corridor risk index and station map queries.
"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.db.models.corridor import CorridorRiskIndex, CorridorStationMap
from backend.schemas.corridor import (
    CorridorRiskResponse,
    CorridorRiskListResponse,
    CorridorStationMapResponse,
    StationMapEntry,
)
from backend.core.logging import get_logger

logger = get_logger(__name__)


def get_all_corridor_risks(
    db: Session,
    min_score: Optional[float] = None,
    limit: int = 50,
) -> CorridorRiskListResponse:
    q = db.query(CorridorRiskIndex).order_by(
        CorridorRiskIndex.composite_risk_score.desc()
    )
    if min_score is not None:
        q = q.filter(CorridorRiskIndex.composite_risk_score >= min_score)
    q = q.limit(limit)
    rows = q.all()
    return CorridorRiskListResponse(
        total=len(rows),
        results=[CorridorRiskResponse.model_validate(r) for r in rows],
    )


def get_corridor_risk(db: Session, corridor: str) -> Optional[CorridorRiskResponse]:
    row = db.query(CorridorRiskIndex).filter(
        CorridorRiskIndex.corridor == corridor
    ).first()
    if not row:
        return None
    return CorridorRiskResponse.model_validate(row)


def get_station_map_for_corridor(
    db: Session, corridor: str
) -> Optional[CorridorStationMapResponse]:
    rows = (
        db.query(CorridorStationMap)
        .filter(CorridorStationMap.corridor == corridor)
        .order_by(CorridorStationMap.rank)
        .all()
    )
    if not rows:
        return None
    return CorridorStationMapResponse(
        corridor=corridor,
        stations=[StationMapEntry.model_validate(r) for r in rows],
    )