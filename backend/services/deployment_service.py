from backend.schemas.deployment import DeploymentRequest, DeploymentResponse, DiversionRoute
from backend.db.repositories.station_repository import StationRepository
from backend.db.repositories.corridor_repository import CorridorRepository
from backend.services.artifact_loader import get_artifacts

# Derived from corridor_adjacency.json — for each corridor, which adjacent
# corridor + road provides the best diversion, and typical extra delay.
_DIVERSION_MAP: dict[str, list[dict]] = {
    "Mysore Road":        [{"via": "ORR West 1",       "road": "Outer Ring Road West",     "extra_mins": 12},
                           {"via": "Old Madras Road",   "road": "NICE Road connector",      "extra_mins": 18}],
    "Bellary Road 1":     [{"via": "Bellary Road 2",   "road": "Yelahanka bypass",          "extra_mins": 8},
                           {"via": "Tumkur Road",       "road": "Peenya Interchange",        "extra_mins": 14}],
    "Bellary Road 2":     [{"via": "Bellary Road 1",   "road": "Hebbal Flyover connector",  "extra_mins": 8},
                           {"via": "ORR North 1",       "road": "ORR North spur",            "extra_mins": 10}],
    "Tumkur Road":        [{"via": "Magadi Road",       "road": "West of Chord Road link",   "extra_mins": 11},
                           {"via": "West of Chord Road","road": "Chord Road connector",      "extra_mins": 9}],
    "Hosur Road":         [{"via": "ORR East 1",        "road": "Silk Board interchange",    "extra_mins": 15},
                           {"via": "Mysore Road",       "road": "NICE Road",                 "extra_mins": 22}],
    "ORR East 1":         [{"via": "ORR East 2",        "road": "Sarjapur Road connector",   "extra_mins": 7},
                           {"via": "Old Airport Road",  "road": "HAL connector",             "extra_mins": 10}],
    "ORR East 2":         [{"via": "ORR East 1",        "road": "Marathahalli Bridge",       "extra_mins": 7},
                           {"via": "Varthur Road",      "road": "Varthur lake road",         "extra_mins": 12}],
    "ORR North 1":        [{"via": "Bellary Road 1",   "road": "Hebbal interchange",        "extra_mins": 9},
                           {"via": "Tumkur Road",       "road": "Peenya cross",              "extra_mins": 13}],
    "ORR North 2":        [{"via": "Tumkur Road",       "road": "Yelahanka cross",           "extra_mins": 6}],
    "Magadi Road":        [{"via": "Bellary Road 1",   "road": "West of Chord Road",        "extra_mins": 10},
                           {"via": "Tumkur Road",       "road": "Peenya link road",          "extra_mins": 12}],
    "Old Madras Road":    [{"via": "Mysore Road",       "road": "KR Puram connector",        "extra_mins": 14},
                           {"via": "CBD 2",             "road": "MG Road flyover",           "extra_mins": 8}],
    "West of Chord Road": [{"via": "Mysore Road",       "road": "Magadi Road junction",      "extra_mins": 9},
                           {"via": "Tumkur Road",       "road": "Rajajinagar connector",     "extra_mins": 7}],
    "Bannerghata Road":   [{"via": "Hosur Road",        "road": "Silk Board flyover",        "extra_mins": 16}],
    "CBD 1":              [{"via": "Old Madras Road",   "road": "Richmond Road link",        "extra_mins": 6}],
    "CBD 2":              [{"via": "Bellary Road 1",   "road": "Mehkri Circle connector",   "extra_mins": 7},
                           {"via": "Old Madras Road",   "road": "KR Circle bypass",          "extra_mins": 9}],
    "Varthur Road":       [{"via": "ORR East 2",        "road": "Marathahalli connector",    "extra_mins": 10}],
    "ORR West 1":         [{"via": "Mysore Road",       "road": "Nayandanahalli junction",   "extra_mins": 8}],
    "Hennur Main Road":   [{"via": "ORR North 1",       "road": "Nagavara ORR junction",     "extra_mins": 11}],
    "Airport New South Road": [{"via": "ORR North 1",  "road": "Hebbal connector",          "extra_mins": 13}],
    "Old Airport Road":   [{"via": "ORR East 1",        "road": "HAL 2nd Stage road",        "extra_mins": 9}],
}

# Cause-based rationale for diversion
_CAUSE_DIVERSION_REASON: dict[str, str] = {
    "vehicle_breakdown": "Stalled vehicle reducing lane capacity",
    "accident":          "Multi-vehicle accident blocking carriageway",
    "pot_holes":         "Road surface hazard causing traffic slowdown",
    "tree_fall":         "Fallen tree obstructing primary carriageway",
    "water_logging":     "Water-logged stretch reducing drivable lanes",
    "construction":      "Active construction narrowing road to single lane",
    "protest":           "Planned protest restricting through-movement",
    "procession":        "Procession route closure for 3-hour window",
    "public_event":      "Event-adjacent road closed for crowd management",
    "vip_movement":      "VIP convoy route temporarily restricted",
}


def _build_diversion_routes(
    corridor: str,
    event_cause: str,
    suggested_junctions: list[str],
    closure_probability: float,
) -> list[DiversionRoute]:
    """
    Build diversion route suggestions from the corridor adjacency map.
    Only surfaces routes when closure probability > 0.25 (meaningful closure risk).
    """
    if closure_probability < 0.25:
        return []

    alternatives = _DIVERSION_MAP.get(corridor, [])
    if not alternatives:
        return []

    rationale_base = _CAUSE_DIVERSION_REASON.get(event_cause, "Incident restricting traffic flow")
    from_junction = suggested_junctions[0] if suggested_junctions else f"{corridor} entry"

    routes = []
    for alt in alternatives[:2]:  # max 2 diversion routes
        routes.append(
            DiversionRoute(
                from_junction=from_junction,
                to_junction=f"{alt['via']} merge point",
                via_road=alt["road"],
                estimated_extra_mins=alt["extra_mins"],
                rationale=f"{rationale_base}. Divert via {alt['via']} using {alt['road']} "
                          f"(+{alt['extra_mins']} mins vs clear route).",
            )
        )
    return routes


def get_deployment_recommendation(
    req: DeploymentRequest,
    station_repo: StationRepository,
    corridor_repo: CorridorRepository,
) -> DeploymentResponse:
    # 1. Escalation tier
    escalation_tier = "Routine"
    if req.closure_probability >= 0.60 or (
        req.predicted_priority == "High" and req.predicted_duration_mins >= 120
    ):
        escalation_tier = "Critical"
    elif (
        req.predicted_priority == "High"
        and req.closure_probability >= 0.25
        and req.predicted_duration_mins < 120
    ):
        escalation_tier = "Elevated"

    # 2. Top station from corridor risk index
    risk_board = corridor_repo.get_corridor_risk_leaderboard()
    target_risk = next((r for r in risk_board if r.corridor == req.corridor), None)

    recommended_station = "Unknown"
    corridor_risk_score = 0.0
    if target_risk:
        recommended_station = target_risk.top_police_station
        corridor_risk_score = target_risk.composite_risk_score

    # 3. Officer count
    concurrency = station_repo.get_concurrency(
        recommended_station, req.hour_of_day, req.day_of_week
    )
    base_officers = 2
    avg_load = concurrency.avg_concurrent if concurrency else 1.0

    extra_officers = 0
    if req.predicted_priority == "High":
        extra_officers += 2
    if req.closure_probability >= 0.35:
        extra_officers += 1

    recommended_officer_count = base_officers + extra_officers

    rationale = (
        f"{recommended_station} average concurrent load at {req.hour_of_day}:00 "
        f"on day {req.day_of_week} is {avg_load:.1f} incidents. "
        f"Adding {extra_officers} for priority/closure risk."
    )
    esc_rationale = (
        f"Priority {req.predicted_priority}, closure probability "
        f"{int(req.closure_probability * 100)}%, predicted duration "
        f"{req.predicted_duration_mins} mins."
    )

    # 4. Suggested junctions
    corridor_junctions_data = corridor_repo.get_corridor_junctions(req.corridor)
    suggested_junctions = [j["junction"] for j in corridor_junctions_data["junctions"][:2]]

    # 5. Diversion routes (new — only when closure risk is meaningful)
    diversion_routes = _build_diversion_routes(
        corridor=req.corridor,
        event_cause=req.event_cause,
        suggested_junctions=suggested_junctions,
        closure_probability=req.closure_probability,
    )

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
        historical_station_incidents=0,
        diversion_routes=diversion_routes,
    )
