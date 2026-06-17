"""
services/analytics_service.py — Analytics queries against the incidents table.

All queries run against PostgreSQL. Returns typed Pydantic-compatible dicts.
"""

from typing import Optional

from sqlalchemy import func, text, case
from sqlalchemy.orm import Session

from backend.db.models.incident import Incident
from backend.schemas.analytics import (
    AnalyticsSummaryResponse,
    HourlyBucket,
    DailyBucket,
    CauseBreakdown,
    HeatmapResponse,
    HeatmapPoint,
    StalenessReportResponse,
)
from backend.core.logging import get_logger

logger = get_logger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_analytics_summary(db: Session, corridor: Optional[str] = None) -> AnalyticsSummaryResponse:
    """Full analytics summary, optionally filtered by corridor."""
    q = db.query(Incident)
    if corridor:
        q = q.filter(Incident.corridor == corridor)

    total = q.count()
    stale = q.filter(Incident.is_stale_active == True).count()
    corrected_active = q.filter(
        Incident.status == "active",
        Incident.is_stale_active == False,
    ).count()
    high_priority = q.filter(Incident.priority == "High").count()
    closures = q.filter(Incident.requires_road_closure == True).count()

    # Duration stats (non-stale only)
    dur_q = q.filter(
        Incident.is_stale_active == False,
        Incident.duration_mins.isnot(None),
        Incident.duration_mins.between(0, 5000),
    )
    avg_dur_row = dur_q.with_entities(func.avg(Incident.duration_mins)).scalar()
    med_dur_row = dur_q.with_entities(
        func.percentile_cont(0.5).within_group(Incident.duration_mins)
    ).scalar()

    # Hourly distribution
    hourly_rows = (
        db.query(
            Incident.hour_of_day,
            func.count(Incident.id).label("incident_count"),
            func.avg(Incident.duration_mins).label("avg_duration"),
            func.sum(case((Incident.requires_road_closure == True, 1), else_=0)).label("closure_count"),
        )
        .filter(Incident.hour_of_day.isnot(None))
        .group_by(Incident.hour_of_day)
        .order_by(Incident.hour_of_day)
        .all()
    )
    hourly_distribution = [
        HourlyBucket(
            hour=row.hour_of_day,
            incident_count=row.incident_count,
            avg_duration_mins=round(float(row.avg_duration), 1) if row.avg_duration else None,
            closure_count=row.closure_count or 0,
        )
        for row in hourly_rows
    ]

    # Daily distribution
    daily_rows = (
        db.query(
            Incident.day_of_week,
            func.count(Incident.id).label("incident_count"),
            func.avg(Incident.duration_mins).label("avg_duration"),
        )
        .filter(Incident.day_of_week.isnot(None))
        .group_by(Incident.day_of_week)
        .order_by(Incident.day_of_week)
        .all()
    )
    daily_distribution = [
        DailyBucket(
            day_of_week=row.day_of_week,
            day_name=DAY_NAMES[row.day_of_week],
            incident_count=row.incident_count,
            avg_duration_mins=round(float(row.avg_duration), 1) if row.avg_duration else None,
        )
        for row in daily_rows
    ]

    # Cause breakdown
    cause_rows = (
        db.query(
            Incident.event_cause,
            func.count(Incident.id).label("count"),
            func.avg(Incident.duration_mins).label("avg_duration"),
            func.sum(case((Incident.requires_road_closure == True, 1), else_=0)).label("closure_count"),
        )
        .group_by(Incident.event_cause)
        .order_by(func.count(Incident.id).desc())
        .all()
    )
    cause_breakdown = [
        CauseBreakdown(
            event_cause=row.event_cause,
            count=row.count,
            percentage=round(row.count / total * 100, 2) if total > 0 else 0.0,
            avg_duration_mins=round(float(row.avg_duration), 1) if row.avg_duration else None,
            closure_count=row.closure_count or 0,
        )
        for row in cause_rows
    ]

    return AnalyticsSummaryResponse(
        total_incidents=total,
        stale_active_flagged=stale,
        corrected_active_count=corrected_active,
        high_priority_count=high_priority,
        high_priority_rate=round(high_priority / total, 4) if total > 0 else 0.0,
        closure_count=closures,
        closure_rate=round(closures / total, 4) if total > 0 else 0.0,
        avg_duration_mins=round(float(avg_dur_row), 1) if avg_dur_row else None,
        median_duration_mins=round(float(med_dur_row), 1) if med_dur_row else None,
        hourly_distribution=hourly_distribution,
        daily_distribution=daily_distribution,
        cause_breakdown=cause_breakdown,
    )


def get_heatmap_data(
    db: Session,
    exclude_stale: bool = True,
) -> HeatmapResponse:
    """Return geo points for heatmap rendering."""
    q = db.query(
        Incident.latitude,
        Incident.longitude,
        Incident.corridor,
        Incident.junction,
    )
    if exclude_stale:
        q = q.filter(Incident.is_stale_active == False)

    # Group by rounded lat/lng to reduce frontend payload
    rows = q.all()
    from collections import defaultdict
    grid: dict[tuple, dict] = defaultdict(lambda: {"weight": 0, "corridor": None, "junction": None})

    for row in rows:
        key = (round(row.latitude, 4), round(row.longitude, 4))
        grid[key]["weight"] += 1
        grid[key]["corridor"] = row.corridor
        grid[key]["junction"] = row.junction

    points = [
        HeatmapPoint(
            lat=lat,
            lng=lng,
            weight=float(data["weight"]),
            corridor=data["corridor"],
            junction=data["junction"],
        )
        for (lat, lng), data in grid.items()
    ]

    return HeatmapResponse(points=points, total_points=len(points))


def get_staleness_report(db: Session) -> StalenessReportResponse:
    """Return staleness report for the corrected active count panel."""
    total_active = db.query(Incident).filter(Incident.status == "active").count()
    stale_count = db.query(Incident).filter(
        Incident.status == "active",
        Incident.is_stale_active == True,
    ).count()
    corrected_active = total_active - stale_count

    stale_rows = (
        db.query(Incident)
        .filter(Incident.status == "active", Incident.is_stale_active == True)
        .order_by(Incident.start_datetime)
        .limit(50)
        .all()
    )

    stale_list = [
        {
            "id": r.id,
            "event_cause": r.event_cause,
            "corridor": r.corridor,
            "police_station": r.police_station,
            "start_datetime": r.start_datetime.isoformat() if r.start_datetime else None,
        }
        for r in stale_rows
    ]

    return StalenessReportResponse(
        total_active=total_active,
        stale_active_count=stale_count,
        corrected_active_count=corrected_active,
        stale_rate=round(stale_count / total_active, 4) if total_active > 0 else 0.0,
        stale_incidents=stale_list,
    )