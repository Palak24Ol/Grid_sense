from sqlalchemy import Column, String, Float, Boolean, DateTime

from backend.db.base import Base

class PlannedEvent(Base):
    __tablename__ = "planned_events"

    id = Column(String(20), primary_key=True)
    event_cause = Column(String(50), nullable=False)
    corridor = Column(String(100), nullable=True)
    junction = Column(String(100), nullable=True)
    police_station = Column(String(100), nullable=True)
    start_datetime = Column(DateTime(timezone=True), nullable=True)
    requires_road_closure = Column(Boolean, nullable=True)
    duration_mins = Column(Float, nullable=True)
    priority = Column(String(10), nullable=True)
    description = Column(String, nullable=True)
