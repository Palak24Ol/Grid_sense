import sys
import warnings
import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*httpx.*")
warnings.filterwarnings("ignore", message=".*NumPy.*")

sys.path.insert(0, '.')
from backend.main import create_app

@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c

scenarios = [
    {'event_cause': 'accident',           'corridor': None, 'vehicle_type': 'heavy_vehicle', 'hour_of_day': 21, 'day_of_week': 2},
    {'event_cause': 'fire',               'corridor': None, 'vehicle_type': 'heavy_vehicle', 'hour_of_day': 8,  'day_of_week': 0},
    {'event_cause': 'vehicle_breakdown',  'corridor': None, 'vehicle_type': None,             'hour_of_day': 12, 'day_of_week': 5},
    {'event_cause': 'tree_fall',          'corridor': None, 'vehicle_type': 'heavy_vehicle', 'hour_of_day': 4,  'day_of_week': 3},
    {'event_cause': 'protest',            'corridor': None, 'vehicle_type': None,             'hour_of_day': 18, 'day_of_week': 4},
]

@pytest.mark.parametrize("scenario", scenarios)
def test_predict_triage(client, scenario):
    response = client.post('/api/v1/predict/triage', json=scenario)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "priority_probability" in data
    assert "predicted_priority" in data
    assert "disagreement_flag" in data
    
    assert data["predicted_priority"] in ["High", "Medium", "Low"]
    assert isinstance(data["priority_probability"], float)
    assert 0.0 <= data["priority_probability"] <= 1.0


def test_closure_rate_varies_by_cause(client):
    high_risk = client.post('/api/v1/predict/triage', json={
        'event_cause': 'tree_fall', 'corridor': None, 'hour_of_day': 14, 'day_of_week': 2
    }).json()
    low_risk = client.post('/api/v1/predict/triage', json={
        'event_cause': 'vehicle_breakdown', 'corridor': None, 'hour_of_day': 14, 'day_of_week': 2
    }).json()
    # tree_fall has a ~48% historical closure rate, vehicle_breakdown ~5% —
    # if these come back equal/close, the encoding lookups are broken again.
    assert high_risk['closure_probability'] > low_risk['closure_probability'] + 0.2
    assert high_risk['priority_probability'] > low_risk['priority_probability'] + 0.2
