from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional

from backend.db.models.corridor import CorridorRiskIndex, CorridorStationMap
from backend.db.models.incident import Incident
from sqlalchemy import func, Integer

class CorridorRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_corridor_risk_leaderboard(self) -> List[CorridorRiskIndex]:
        query = select(CorridorRiskIndex).order_by(CorridorRiskIndex.composite_risk_score.desc())
        return list(self.session.execute(query).scalars().all())

    def get_corridor_junctions(self, corridor: str) -> dict:
        # Get total incidents for the corridor
        total_query = select(CorridorRiskIndex.total_incidents).where(CorridorRiskIndex.corridor == corridor)
        total_incidents = self.session.execute(total_query).scalar() or 0

        # Group by junction
        query = select(
            Incident.junction,
            func.count(Incident.id).label('incident_count'),
            func.sum(func.cast(Incident.priority == 'High', Integer)).label('high_priority_count'),
            func.sum(func.cast(Incident.requires_road_closure == True, Integer)).label('closure_count')
        ).where(Incident.corridor == corridor).where(Incident.junction.isnot(None)).group_by(Incident.junction)
        
        results = self.session.execute(query).all()
        junctions = []
        for r in results:
            share = (r.incident_count / total_incidents) if total_incidents > 0 else 0.0
            junctions.append({
                "junction": r.junction,
                "incident_count": r.incident_count,
                "share_of_corridor": round(share, 3),
                "high_priority_count": r.high_priority_count or 0,
                "closure_count": r.closure_count or 0
            })
            
        return {
            "corridor": corridor,
            "total_incidents": total_incidents,
            "junctions": junctions
        }
