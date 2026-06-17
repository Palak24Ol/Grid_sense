from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID

from backend.db.base import Base

class TriageLog(Base):
    __tablename__ = "triage_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(String(50), nullable=True)
    corridor = Column(String(100), nullable=True)
    event_cause = Column(String(50), nullable=True)
    vehicle_type = Column(String(30), nullable=True)
    hour_of_day = Column(Integer, nullable=True)
    day_of_week = Column(Integer, nullable=True)
    closure_probability = Column(Float, nullable=True)
    priority_probability = Column(Float, nullable=True)
    predicted_priority = Column(String(10), nullable=True)
    disagreement_flag = Column(Boolean, nullable=True)
    predicted_duration_mins = Column(Float, nullable=True)
    recommended_station = Column(String(100), nullable=True)
    recommended_officer_count = Column(Integer, nullable=True)
    escalation_tier = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
