"""
db/models/corridor.py — Corridor risk index and station map ORM models.
"""

from sqlalchemy import (
    Column, Float, Integer, String, UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP

from backend.db.base import Base


class CorridorRiskIndex(Base):
    __tablename__ = "corridor_risk_index"

    corridor = Column(String(100), primary_key=True)
    total_incidents = Column(Integer, nullable=False)
    high_priority_count = Column(Integer, nullable=False)
    high_priority_rate = Column(Float, nullable=False)
    closure_count = Column(Integer, nullable=False)
    closure_rate = Column(Float, nullable=False)
    composite_risk_score = Column(Float, nullable=False)   # 0–100
    top_junction = Column(String(100))
    top_police_station = Column(String(100))
    median_duration_mins = Column(Float)
    updated_at = Column(
        PG_TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
    )


class CorridorStationMap(Base):
    __tablename__ = "corridor_station_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    corridor = Column(
        String(100),
        ForeignKey("corridor_risk_index.corridor", ondelete="CASCADE"),
        nullable=False,
    )
    police_station = Column(String(100), nullable=False)
    incident_count = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)   # 1=primary, 2=secondary, 3=tertiary

    __table_args__ = (
        UniqueConstraint("corridor", "rank", name="uq_corridor_rank"),
    )