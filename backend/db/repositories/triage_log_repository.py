from sqlalchemy.orm import Session
from sqlalchemy import func, case, text
from backend.db.models.triage_log import TriageLog
from typing import Optional

class TriageLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, triage_log: TriageLog) -> TriageLog:
        self.session.add(triage_log)
        self.session.commit()
        self.session.refresh(triage_log)
        return triage_log

    def update_actual_outcome(
        self,
        log_id: str,
        actual_duration_mins: Optional[float] = None,
        actual_closure: Optional[bool] = None,
        actual_officer_count: Optional[int] = None,
    ) -> Optional[TriageLog]:
        """Record what actually happened after the incident resolved."""
        log = self.session.query(TriageLog).filter(TriageLog.id == log_id).first()
        if not log:
            return None
        if actual_duration_mins is not None:
            log.actual_duration_mins = actual_duration_mins
        if actual_closure is not None:
            log.actual_closure = actual_closure
        if actual_officer_count is not None:
            log.actual_officer_count = actual_officer_count
        self.session.commit()
        self.session.refresh(log)
        return log

    def get_learning_summary(self, limit: int = 200) -> dict:
        """
        Aggregate triage log entries to power the Post-Event Learning dashboard.
        Returns accuracy metrics, drift indicators, and recent prediction history.
        """
        rows = (
            self.session.query(TriageLog)
            .order_by(TriageLog.created_at.desc())
            .limit(limit)
            .all()
        )

        total = len(rows)
        if total == 0:
            return _empty_summary()

        # -- Accuracy metrics (where actual outcomes were recorded) --
        with_actual_duration = [
            r for r in rows
            if getattr(r, "actual_duration_mins", None) is not None
            and r.predicted_duration_mins is not None
        ]
        with_actual_closure = [
            r for r in rows
            if getattr(r, "actual_closure", None) is not None
        ]

        duration_errors = []
        for r in with_actual_duration:
            err = abs(r.actual_duration_mins - r.predicted_duration_mins)
            duration_errors.append(err)

        closure_correct = sum(
            1 for r in with_actual_closure
            if bool(r.actual_closure) == bool(r.closure_probability >= 0.31)
        )

        mae = round(sum(duration_errors) / len(duration_errors), 1) if duration_errors else None
        closure_acc = round(closure_correct / len(with_actual_closure) * 100, 1) if with_actual_closure else None

        # -- Prediction history for chart (last 50) --
        recent = rows[:50]
        history = []
        for r in reversed(recent):
            history.append({
                "id": str(r.id),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "corridor": r.corridor or "Unknown",
                "event_cause": r.event_cause or "unknown",
                "predicted_priority": r.predicted_priority,
                "predicted_duration_mins": r.predicted_duration_mins,
                "actual_duration_mins": getattr(r, "actual_duration_mins", None),
                "closure_probability": round(r.closure_probability, 3) if r.closure_probability else None,
                "actual_closure": getattr(r, "actual_closure", None),
                "disagreement_flag": r.disagreement_flag,
                "escalation_tier": r.escalation_tier,
                "hour_of_day": r.hour_of_day,
            })

        # -- Cause breakdown --
        cause_counts: dict = {}
        priority_counts = {"High": 0, "Medium": 0, "Low": 0}
        disagreement_count = 0
        for r in rows:
            cause = r.event_cause or "unknown"
            cause_counts[cause] = cause_counts.get(cause, 0) + 1
            p = r.predicted_priority or "Medium"
            priority_counts[p] = priority_counts.get(p, 0) + 1
            if r.disagreement_flag:
                disagreement_count += 1

        # -- Duration bias: are we over or under predicting? --
        biases = []
        for r in with_actual_duration:
            bias = r.predicted_duration_mins - r.actual_duration_mins
            biases.append(bias)
        mean_bias = round(sum(biases) / len(biases), 1) if biases else None

        return {
            "total_predictions": total,
            "with_actual_outcomes": len(with_actual_duration),
            "duration_mae_mins": mae,
            "duration_mean_bias_mins": mean_bias,
            "closure_accuracy_pct": closure_acc,
            "disagreement_rate_pct": round(disagreement_count / total * 100, 1),
            "priority_distribution": priority_counts,
            "cause_distribution": cause_counts,
            "prediction_history": history,
        }


def _empty_summary() -> dict:
    return {
        "total_predictions": 0,
        "with_actual_outcomes": 0,
        "duration_mae_mins": None,
        "duration_mean_bias_mins": None,
        "closure_accuracy_pct": None,
        "disagreement_rate_pct": 0.0,
        "priority_distribution": {"High": 0, "Medium": 0},
        "cause_distribution": {},
        "prediction_history": [],
    }