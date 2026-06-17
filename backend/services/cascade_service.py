import json
from pathlib import Path
from backend.config import get_settings

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
    
    def predict_cascade(self, cause: str, corridor: str, hour: int, day_of_week: int) -> dict:
        # Get multiplier for this cause
        multiplier_data = self._multipliers.get(cause, {
            "cascade_multiplier": 1.0,
            "risk_level": "low",
            "sample_count": 0
        })
        multiplier = multiplier_data['cascade_multiplier']
        
        # Primary corridor: find blackspot junctions at risk
        primary_junctions = [
            b for b in self._blackspots
            if b['corridor'] == corridor and b['blackspot_score'] > 20
        ]
        
        # Sort by score, take top 5
        primary_junctions.sort(key=lambda x: x['blackspot_score'], reverse=True)
        primary_at_risk = primary_junctions[:5]
        
        # Adjacent corridors with spillover risk (multiplier × 0.4 = secondary risk)
        adjacent = self._adjacency.get(corridor, [])
        adjacent_risk = [
            {
                "corridor": adj_corridor,
                "spillover_multiplier": round(multiplier * 0.4, 2),
                "risk_level": "moderate" if multiplier * 0.4 >= 1.5 else "low"
            }
            for adj_corridor in adjacent[:4]  # top 4 adjacent only
        ]
        
        # Officer buffer recommendation
        # Base: planned deployment handles primary event
        # Buffer: +1 per at-risk junction, capped at +5
        cascade_buffer = min(len(primary_at_risk), 5)
        
        return {
            "event_cause": cause,
            "primary_corridor": corridor,
            "cascade_multiplier": multiplier,
            "risk_level": multiplier_data.get('risk_level', 'low'),
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
                f"Historical data shows planned {cause} events on {corridor} "
                f"trigger {multiplier}x more unplanned incidents in the following 3 hours. "
                f"Pre-position {cascade_buffer} additional officers at at-risk junctions."
            )
        }
