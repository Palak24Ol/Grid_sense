import json
from pathlib import Path
from backend.config import get_settings

class SurgeService:
    def __init__(self):
        settings = get_settings()
        artifact_dir = Path(settings.ARTIFACT_DIR)
        with open(artifact_dir / 'surge_profile.json') as f:
            self._vulnerability = json.load(f)
        with open(artifact_dir / 'surge_replay_march7.json') as f:
            self._replay = json.load(f)
    
    def get_vulnerability(self):
        return {
            "corridors": self._vulnerability,
            "critical_count": sum(1 for c in self._vulnerability if c['deployment_priority'] == 'Critical'),
            "high_count": sum(1 for c in self._vulnerability if c['deployment_priority'] == 'High'),
        }
    
    def get_march7_replay(self):
        return self._replay
    
    def generate_surge_deployment_plan(self, alert: dict):
        """
        When a weather alert fires, return a city-wide pre-deployment plan
        using surge_profile.json vulnerability rankings.
        """
        critical_corridors = [
            c for c in self._vulnerability
            if c['deployment_priority'] in ('Critical', 'High')
        ]
        return {
            "alert_received": alert,
            "surge_mode": "ACTIVE",
            "corridors_to_pre_deploy": len(critical_corridors),
            "total_officers_recommended": len(critical_corridors) * 6,
            "deployment_plan": critical_corridors[:8],  # Top 8 corridors
            "recommended_action_by": "2 hours before forecast rainfall window"
        }
