from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional

from backend.db.models.station import StationConcurrency

class StationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_concurrency(self, police_station: str, hour_of_day: int, day_of_week: int) -> Optional[StationConcurrency]:
        query = select(StationConcurrency).where(
            StationConcurrency.police_station == police_station,
            StationConcurrency.hour_of_day == hour_of_day,
            StationConcurrency.day_of_week == day_of_week
        )
        return self.session.execute(query).scalar_one_or_none()
