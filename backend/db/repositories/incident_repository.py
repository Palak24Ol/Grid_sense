from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func
from datetime import datetime
from typing import List, Optional, Tuple

from backend.db.models.incident import Incident

class IncidentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_incidents(
        self,
        corridor: Optional[str] = None,
        event_cause: Optional[str] = None,
        priority: Optional[str] = None,
        event_type: Optional[str] = None,
        exclude_stale: bool = True,
        limit: int = 2000,
        offset: int = 0
    ) -> Tuple[int, int, List[Incident]]:
        query = select(Incident)

        if exclude_stale:
            query = query.where(Incident.is_stale_active == False)

        total_query = select(func.count()).select_from(Incident)
        if exclude_stale:
            total_query = total_query.where(Incident.is_stale_active == False)

        total = self.session.execute(total_query).scalar() or 0

        if corridor:
            query = query.where(Incident.corridor == corridor)
        if event_cause:
            query = query.where(Incident.event_cause == event_cause)
        if priority:
            query = query.where(Incident.priority == priority)
        if event_type:
            query = query.where(Incident.event_type == event_type)

        filtered_count_query = select(func.count()).select_from(query.subquery())
        filtered = self.session.execute(filtered_count_query).scalar() or 0

        query = query.order_by(Incident.start_datetime.desc()).offset(offset).limit(limit)
        results = self.session.execute(query).scalars().all()

        return total, filtered, list(results)

    def get_summary(self) -> dict:
        total = self.session.query(func.count(Incident.id)).scalar() or 0
        raw_active = self.session.query(func.count(Incident.id)).filter(Incident.status == 'active').scalar() or 0
        corrected_active = self.session.query(func.count(Incident.id)).filter(
            and_(Incident.status == 'active', Incident.is_stale_active == False)
        ).scalar() or 0
        stale_removed = raw_active - corrected_active
        total_closures = self.session.query(func.count(Incident.id)).filter(Incident.requires_road_closure == True).scalar() or 0
        planned = self.session.query(func.count(Incident.id)).filter(Incident.event_type == 'planned').scalar() or 0
        unplanned = self.session.query(func.count(Incident.id)).filter(Incident.event_type == 'unplanned').scalar() or 0
        
        min_date = self.session.query(func.min(Incident.start_datetime)).scalar()
        max_date = self.session.query(func.max(Incident.start_datetime)).scalar()
        days = (max_date - min_date).days if min_date and max_date else 0

        return {
            "total_incidents": total,
            "corrected_active_count": corrected_active,
            "raw_active_count": raw_active,
            "stale_removed": stale_removed,
            "total_closures": total_closures,
            "planned_count": planned,
            "unplanned_count": unplanned,
            "date_range": {
                "start": min_date.isoformat() if min_date else None,
                "end": max_date.isoformat() if max_date else None,
                "days": days
            }
        }

    def get_junction_aggregates(self) -> List[dict]:
        from sqlalchemy import Integer
        query = select(
            Incident.junction,
            func.avg(Incident.latitude).label('latitude'),
            func.avg(Incident.longitude).label('longitude'),
            func.count(Incident.id).label('incident_count'),
            func.sum(func.cast(Incident.priority == 'High', Integer)).label('high_priority_count'),
            func.sum(func.cast(Incident.requires_road_closure == True, Integer)).label('closure_count')
        ).where(Incident.junction.isnot(None)).group_by(Incident.junction)

        results = self.session.execute(query).all()
        out = []
        for r in results:
            out.append({
                "junction": r.junction,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "incident_count": r.incident_count,
                "high_priority_count": r.high_priority_count or 0,
                "closure_count": r.closure_count or 0,
                "top_cause": "unknown" 
            })
        return out
