from sqlalchemy.orm import Session
from backend.db.models.triage_log import TriageLog

class TriageLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, triage_log: TriageLog) -> TriageLog:
        self.session.add(triage_log)
        self.session.commit()
        self.session.refresh(triage_log)
        return triage_log
