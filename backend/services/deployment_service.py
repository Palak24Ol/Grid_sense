from backend.schemas.deployment import DeploymentRequest, DeploymentResponse
from backend.db.repositories.station_repository import StationRepository
from backend.db.repositories.corridor_repository import CorridorRepository
from backend.db.repositories.incident_repository import IncidentRepository

def get_deployment_recommendation(
    req: DeploymentRequest,
    station_repo: StationRepository,
    corridor_repo: CorridorRepository,
) -> DeploymentResponse:
    # 1. Determine Escalation Tier
    escalation_tier = "Routine"
    if req.closure_probability >= 0.60 or (req.predicted_priority == "High" and req.predicted_duration_mins >= 120):
        escalation_tier = "Critical"
    elif req.predicted_priority == "High" and req.closure_probability >= 0.25 and req.predicted_duration_mins < 120:
        escalation_tier = "Elevated"

    # 2. Get top station for the corridor
    # This comes from corridor_station_map which is part of CorridorRiskIndex ideally
    # Let's do a simplified lookup or use the station map if we had a method for it.
    # For now, let's just pick a default or query the top station from corridor risk.
    risk_board = corridor_repo.get_corridor_risk_leaderboard()
    target_risk = next((r for r in risk_board if r.corridor == req.corridor), None)
    
    recommended_station = "Unknown"
    corridor_risk_score = 0.0
    if target_risk:
        recommended_station = target_risk.top_police_station
        corridor_risk_score = target_risk.composite_risk_score
        
    # 3. Determine Officer Count based on concurrent load
    concurrency = station_repo.get_concurrency(recommended_station, req.hour_of_day, req.day_of_week)
    base_officers = 2
    avg_load = concurrency.avg_concurrent if concurrency else 1.0
    
    extra_officers = 0
    if req.predicted_priority == "High":
        extra_officers += 2
    if req.closure_probability >= 0.35:
        extra_officers += 1

    recommended_officer_count = base_officers + extra_officers
    
    rationale = f"{recommended_station} average concurrent load at {req.hour_of_day}:00 on day {req.day_of_week} is {avg_load:.1f} incidents. Adding {extra_officers} for priority/closure risk."
    esc_rationale = f"Priority {req.predicted_priority}, closure probability {int(req.closure_probability * 100)}%, predicted duration {req.predicted_duration_mins} mins."

    # 4. Get suggested junctions
    corridor_junctions_data = corridor_repo.get_corridor_junctions(req.corridor)
    suggested_junctions = [j['junction'] for j in corridor_junctions_data['junctions'][:2]]

    return DeploymentResponse(
        recommended_station=recommended_station,
        secondary_station=None,
        recommended_officer_count=recommended_officer_count,
        officer_count_rationale=rationale,
        escalation_tier=escalation_tier,
        escalation_rationale=esc_rationale,
        deployment_duration_mins=req.predicted_duration_mins,
        suggested_junctions=suggested_junctions,
        corridor_risk_score=corridor_risk_score,
        historical_station_incidents=0  # Should be queried from station map
    )
