"""
db/models/incident.py — Incident ORM model.

Maps to the `incidents` table. Read-only at runtime (seeded once from CSV).
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Float, Index, Integer,
    String, Text, TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP

from backend.db.base import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(20), primary_key=True)
    event_type = Column(String(20), nullable=False)
    event_cause = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text)
    corridor = Column(String(100))          # NULL for Non-corridor
    junction = Column(String(100))
    zone = Column(String(50))               # NULL for ~58% of records
    police_station = Column(String(100), nullable=False)
    priority = Column(String(10), nullable=False)   # 'High' or 'Low'
    requires_road_closure = Column(Boolean, nullable=False, default=False)
    vehicle_type = Column(String(30))
    start_datetime = Column(PG_TIMESTAMP(timezone=True), nullable=False)
    end_datetime = Column(PG_TIMESTAMP(timezone=True))
    closed_datetime = Column(PG_TIMESTAMP(timezone=True))
    status = Column(String(20), nullable=False)     # closed | resolved | active
    is_stale_active = Column(Boolean, nullable=False, default=False)
    duration_mins = Column(Float)
    hour_of_day = Column(Integer)
    day_of_week = Column(Integer)           # 0=Mon, 6=Sun
    month = Column(Integer)
    is_high_priority_corridor = Column(Boolean, nullable=False, default=False)
    is_non_corridor = Column(Boolean, nullable=False, default=False)
    description = Column(Text)
    created_at = Column(
        PG_TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
    )

    __table_args__ = (
        Index("idx_incidents_corridor", "corridor"),
        Index("idx_incidents_junction", "junction"),
        Index("idx_incidents_start_datetime", "start_datetime"),
        Index("idx_incidents_status", "status"),
        Index("idx_incidents_priority", "priority"),
        Index("idx_incidents_police_station", "police_station"),
        Index("idx_incidents_geo", "latitude", "longitude"),
        # Partial index — most common query pattern
        Index(
            "idx_incidents_non_stale_corridor",
            "corridor",
            postgresql_where="is_stale_active = FALSE",
        ),
    )