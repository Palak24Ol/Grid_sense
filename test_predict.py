import sys
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from backend.main import create_app
app = create_app()
client = TestClient(app)

scenarios = [
    {'event_cause': 'accident', 'corridor': None, 'vehicle_type': 'heavy_vehicle', 'hour_of_day': 21, 'day_of_week': 2},
    {'event_cause': 'fire', 'corridor': None, 'vehicle_type': 'heavy_vehicle', 'hour_of_day': 8, 'day_of_week': 0},
    {'event_cause': 'vehicle_breakdown', 'corridor': None, 'vehicle_type': None, 'hour_of_day': 12, 'day_of_week': 5},
    {'event_cause': 'tree_fall', 'corridor': None, 'vehicle_type': 'heavy_vehicle', 'hour_of_day': 4, 'day_of_week': 3},
    {'event_cause': 'protest', 'corridor': None, 'vehicle_type': None, 'hour_of_day': 18, 'day_of_week': 4},
]
for s in scenarios:
    r = client.post('/api/v1/predict/triage', json=s)
    if r.status_code != 200:
        print(s['event_cause'], '-> HTTP', r.status_code, r.text[:300])
        continue
    d = r.json()
    print(f"{s['event_cause']:<20} proba_high={d['priority_probability']:.3f}  pred={d['predicted_priority']:<5}  disagree={d['disagreement_flag']}")
