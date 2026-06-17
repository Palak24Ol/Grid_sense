import json
from pathlib import Path
from backend.config import get_settings

class BlackspotService:
    def __init__(self):
        settings = get_settings()
        artifact_dir = Path(settings.ARTIFACT_DIR)
        with open(artifact_dir / 'blackspot_scores.json') as f:
            self._blackspots = json.load(f)
        with open(artifact_dir / 'neglect_index.json') as f:
            self._neglect = json.load(f)
    
    def get_blackspots(self, tier=None, corridor=None, min_score=None):
        results = self._blackspots
        if tier:
            results = [r for r in results if r['blackspot_tier'] == tier]
        if corridor:
            results = [r for r in results if r['corridor'] == corridor]
        if min_score:
            results = [r for r in results if r['blackspot_score'] >= min_score]
        return {
            "total": len(results),
            "junctions": results,
            "chronic_count": sum(1 for r in self._blackspots if r['blackspot_tier'] == 'Chronic'),
            "critical_count": sum(1 for r in self._blackspots if r['blackspot_tier'] == 'Critical'),
        }
    
    def get_neglect_index(self):
        sorted_neglect = sorted(self._neglect, key=lambda x: x['neglect_rate'], reverse=True)
        return {"stations": sorted_neglect}
    
    def get_junction_profile(self, junction: str):
        match = next((r for r in self._blackspots if r['junction'] == junction), None)
        if not match:
            return {"error": f"Junction '{junction}' not found or below threshold"}
        return match
