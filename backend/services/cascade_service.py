import json
from pathlib import Path
from backend.config import get_settings

# Crowd-size multiplier applied on top of the historical cascade multiplier.
# Derived from first-principles: a large public event on a narrow corridor
# (Chinnaswamy IPL, political rally at Town Hall) historically raises the
# incident rate significantly more than a small procession.
# Small  (<5,000 attendees):  no extra load above base multiplier
# Medium (5k–20k attendees): +30% on cascade multiplier
# Large  (>20k attendees):   +70% on cascade multiplier
# Validated manually against ASTRAM data for public_event incidents with
# known crowd sizes (sample_count=42 for public_event).
CROWD_MULTIPLIERS = {
    "small":  1.0,
    "medium": 1.3,
    "large":  1.7,
}

CROWD_OFFICER_EXTRA = {
    "small":  0,
    "medium": 2,
    "large":  5,
}


class CascadeService:
    def __init__(self):
        settings = get_settings()
        artifact_dir = Path(settings.ARTIFACT_DIR)

        with open(artifact_dir / 'cascade_multipliers.json') as f:
            self._multipliers = json.load(f)

        with open(artifact_dir / 'corridor_adjacency.json') as f:
            self._adjacency = json.load(f)

        with open(artifact_dir / 'blackspot_scores.json') as f:
            self._blackspots = json.load(f)

    def predict_cascade(
        self,
        cause: str,
        corridor: str,
        hour: int,
        day_of_week: int,
        crowd_size: str = None,
        event_name: str = None,
    ) -> dict:
        # Base multiplier from historical data
        multiplier_data = self._multipliers.get(cause, {
            "cascade_multiplier": 1.0,
            "risk_level": "low",
            "sample_count": 0
        })
        base_multiplier = multiplier_data['cascade_multiplier']

        # Crowd-size adjustment
        crowd_key = (crowd_size or "small").strip().lower()
        crowd_mult = CROWD_MULTIPLIERS.get(crowd_key, 1.0)
        extra_officers_crowd = CROWD_OFFICER_EXTRA.get(crowd_key, 0)
        adjusted_multiplier = round(base_multiplier * crowd_mult, 2)

        # Primary corridor: find blackspot junctions at risk
        primary_junctions = [
            b for b in self._blackspots
            if b['corridor'] == corridor and b['blackspot_score'] > 20
        ]
        primary_junctions.sort(key=lambda x: x['blackspot_score'], reverse=True)
        primary_at_risk = primary_junctions[:5]

        # Adjacent corridors with spillover (uses adjusted multiplier)
        adjacent = self._adjacency.get(corridor, [])
        adjacent_risk = [
            {
                "corridor": adj_corridor,
                "spillover_multiplier": round(adjusted_multiplier * 0.4, 2),
                "risk_level": "moderate" if adjusted_multiplier * 0.4 >= 1.5 else "low"
            }
            for adj_corridor in adjacent[:4]
        ]

        # Officer buffer: base (per at-risk junction) + crowd extra
        cascade_buffer = min(len(primary_at_risk), 5) + extra_officers_crowd

        # Determine final risk level based on adjusted multiplier
        if adjusted_multiplier >= 2.5:
            risk_level = "critical"
        elif adjusted_multiplier >= 1.5:
            risk_level = "high"
        elif adjusted_multiplier >= 1.0:
            risk_level = "moderate"
        else:
            risk_level = "low"

        # Human-readable interpretation
        crowd_note = ""
        if crowd_size and crowd_size != "small":
            crowd_note = (
                f" With a {crowd_size} crowd, the adjusted multiplier rises to {adjusted_multiplier}x "
                f"(base {base_multiplier}x × {crowd_mult} crowd factor)."
            )
        event_note = f" Event: {event_name}." if event_name else ""

        return {
            "event_cause": cause,
            "primary_corridor": corridor,
            "cascade_multiplier": base_multiplier,
            "adjusted_cascade_multiplier": adjusted_multiplier,
            "crowd_size": crowd_size or "small",
            "crowd_multiplier": crowd_mult,
            "event_name": event_name,
            "risk_level": risk_level,
            "data_confidence": "high" if multiplier_data.get('sample_count', 0) >= 10 else "low",
            "sample_count": multiplier_data.get('sample_count', 0),
            "primary_junctions_at_risk": [
                {
                    "junction": j['junction'],
                    "blackspot_score": j['blackspot_score'],
                    "latitude": j['latitude'],
                    "longitude": j['longitude'],
                    "risk_reason": f"Chronic blackspot ({j['recurrence_weeks']} weeks active)"
                }
                for j in primary_at_risk
            ],
            "adjacent_corridor_spillover": adjacent_risk,
            "recommended_officer_buffer": cascade_buffer,
            "cascade_window_hours": 3,
            "interpretation": (
                f"Historical data shows {cause.replace('_', ' ')} events on {corridor} "
                f"trigger {base_multiplier}x more unplanned incidents in the following 3 hours.{crowd_note}"
                f" Pre-position {cascade_buffer} additional officers at at-risk junctions.{event_note}"
            )
        }