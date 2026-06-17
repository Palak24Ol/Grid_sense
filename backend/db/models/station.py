"""
db/models/station.py — Station concurrency and duration lookup ORM models.
"""

from sqlalchemy import Column, Float, Integer, String, UniqueConstraint

from backend.db.base import Base


class StationConcurrency(Base):
    __tablename__ = "station_concurrency"

    id = Column(Integer, primary_key=True, autoincrement=True)
    police_station = Column(String(100), nullable=False)
    hour_of_day = Column(Integer, nullable=False)    # 0–23
    day_of_week = Column(Integer, nullable=False)    # 0–6
    avg_concurrent = Column(Float, nullable=False)
    max_concurrent = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "police_station", "hour_of_day", "day_of_week",
            name="uq_station_hour_dow",
        ),
    )


class DurationLookup(Base):
    __tablename__ = "duration_lookup"

    event_cause = Column(String(50), primary_key=True)
    median_duration_mins = Column(Float, nullable=False)
    p25_duration_mins = Column(Float)
    p75_duration_mins = Column(Float)
    sample_count = Column(Integer, nullable=False)