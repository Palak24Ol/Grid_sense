"""
Gateway B - Traffic Intelligence packaging.

This gateway keeps Road Stress, Shockwave, Vehicle Surge, Domino, and
Congestion Cost as simulation / forecasting / decision-support outputs.
It does not present them as high-accuracy production ML.

Outputs are isolated under ml/gateway_b/.

Run:
    python ml/gateway_b/package_traffic_intelligence.py
"""

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent
ARTIFACT_SOURCE = ROOT / "ml" / "artifacts"
GATEWAY_DIR = ROOT / "ml" / "gateway_b"
SIM_DIR = GATEWAY_DIR / "simulation_outputs"
IMPORTANCE_DIR = GATEWAY_DIR / "feature_importance"
RISK_DIR = GATEWAY_DIR / "risk_profiles"
EVAL_DIR = GATEWAY_DIR / "evaluations"
INTELLIGENCE_PROFILE_PATH = RISK_DIR / "gateway_b_intelligence_profile.json"

for path in (SIM_DIR, IMPORTANCE_DIR, RISK_DIR, EVAL_DIR):
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, payload) -> None:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def copy_if_exists(src_name: str, dst_dir: Path) -> bool:
    src = ARTIFACT_SOURCE / src_name
    if not src.exists():
        return False
    shutil.copy2(src, dst_dir / src_name)
    return True


def stress_level(score: float) -> str:
    if score <= 30:
        return "Healthy"
    if score <= 60:
        return "Moderate"
    if score <= 80:
        return "High Stress"
    return "Critical"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def normalize(value: float, max_value: float, scale: float = 100.0) -> float:
    if max_value <= 0:
        return 0.0
    return clamp(value / max_value * scale, 0.0, scale)


def station_load_score(station_map: dict, corridor: str) -> tuple[float, int, str | None]:
    stations = station_map.get(corridor, [])
    if not stations:
        return 0.0, 0, None
    max_count = max((s.get("incident_count", 0) for rows in station_map.values() for s in rows), default=1)
    top_station = max(stations, key=lambda row: row.get("incident_count", 0))
    count = int(top_station.get("incident_count", 0))
    return normalize(count, max_count), count, top_station.get("police_station")


def build_stress_outputs(profile: dict, corridor_risk: dict, station_map: dict) -> list[dict]:
    roads = profile.get("roads", {})
    rows = []
    max_incidents = max((rec.get("total_incidents", 0) for rec in corridor_risk.values()), default=1)
    max_duration = max((rec.get("median_duration_mins", 0) for rec in corridor_risk.values()), default=1)
    for corridor, rec in roads.items():
        risk = corridor_risk.get(corridor, {})
        road_importance = clamp(
            0.55 * rec.get("road_centrality", 0) * 100
            + 0.45 * normalize(risk.get("total_incidents", rec.get("total_incidents", 0)), max_incidents)
        )
        closure_frequency = clamp(risk.get("closure_rate", rec.get("closure_rate", 0)) * 100)
        priority_frequency = clamp(risk.get("high_priority_rate", rec.get("high_priority_rate", 0)) * 100)
        duration_risk = normalize(
            risk.get("median_duration_mins", rec.get("median_duration_mins", 0)),
            max_duration,
        )
        station_score, station_count, primary_station = station_load_score(station_map, corridor)
        neighbor_component = clamp(rec.get("neighbor_congestion_influence_score", 0))
        score = (
            0.22 * road_importance
            + 0.18 * closure_frequency
            + 0.18 * priority_frequency
            + 0.16 * duration_risk
            + 0.12 * station_score
            + 0.14 * neighbor_component
        )
        level = stress_level(score)
        factors = {
            "road_importance": round(road_importance, 1),
            "closure_frequency": round(closure_frequency, 1),
            "priority_frequency": round(priority_frequency, 1),
            "duration_risk": round(duration_risk, 1),
            "station_load": round(station_score, 1),
            "neighbor_influence": round(neighbor_component, 1),
        }
        top_reasons = sorted(factors.items(), key=lambda item: item[1], reverse=True)[:3]
        rows.append({
            "corridor": corridor,
            "stress_score": round(score, 1),
            "stress_level": level,
            "factors": factors,
            "factor_weights": {
                "road_importance": 0.22,
                "closure_frequency": 0.18,
                "priority_frequency": 0.18,
                "duration_risk": 0.16,
                "station_load": 0.12,
                "neighbor_influence": 0.14,
            },
            "station_incident_load": station_count,
            "top_police_station": primary_station or rec.get("top_police_station"),
            "top_junction": rec.get("top_junction"),
            "latitude": rec.get("latitude"),
            "longitude": rec.get("longitude"),
            "explanation": (
                f"{corridor} is {level} because "
                + ", ".join(f"{name.replace('_', ' ')}={value:.1f}" for name, value in top_reasons)
                + "."
            ),
        })
    return sorted(rows, key=lambda row: row["stress_score"], reverse=True)


def build_shockwave_sample(profile: dict, stress_rows: list[dict], source_corridor: str) -> dict:
    adjacency = profile.get("graph", {}).get("adjacency", {})
    stress_by_corridor = {row["corridor"]: row for row in stress_rows}
    source = stress_by_corridor.get(source_corridor, {})
    source_stress = source.get("stress_score", 50)
    source_importance = source.get("factors", {}).get("road_importance", 50)
    affected = []
    first_hop = adjacency.get(source_corridor, [])[:8]
    second_hop = []
    for corridor in first_hop:
        second_hop.extend([n for n in adjacency.get(corridor, []) if n != source_corridor])
    candidates = [(1, c) for c in first_hop] + [(2, c) for c in dict.fromkeys(second_hop) if c not in first_hop][:8]
    for idx, (hop, corridor) in enumerate(candidates, start=1):
        own = stress_by_corridor.get(corridor, {})
        own_stress = own.get("stress_score", 35)
        road_importance = own.get("factors", {}).get("road_importance", 35)
        neighbor_influence = own.get("factors", {}).get("neighbor_influence", 25)
        probability = min(
            0.95,
            0.12
            + 0.0032 * source_stress
            + 0.0025 * source_importance
            + 0.0026 * own_stress
            + 0.0016 * road_importance
            + 0.0012 * neighbor_influence
            - 0.07 * (hop - 1),
        )
        spread_time = round(5 + hop * 7 + idx * 1.4 + (100 - source_stress) / 14, 1)
        affected.append({
            "corridor": corridor,
            "hop_distance": hop,
            "congestion_probability": round(probability, 3),
            "estimated_spread_time_mins": spread_time,
            "projected_stress_score": round(min(100, own_stress + probability * 20), 1),
            "explanation": (
                f"Spread risk uses corridor relationship hop={hop}, source stress={source_stress:.1f}, "
                f"road importance={road_importance:.1f}, neighbor influence={neighbor_influence:.1f}."
            ),
        })
    affected.sort(key=lambda row: (row["estimated_spread_time_mins"], -row["congestion_probability"]))
    return {
        "source_corridor": source_corridor,
        "mode": "simulation_decision_support",
        "spread_forecast": "Corridor relationship + road importance + neighbor influence simulation.",
        "affected_roads": affected,
        "forecast_windows": {
            "5_min": [r for r in affected if r["estimated_spread_time_mins"] <= 5],
            "15_min": [r for r in affected if r["estimated_spread_time_mins"] <= 15],
            "30_min": [r for r in affected if r["estimated_spread_time_mins"] <= 30],
        },
    }


def build_vehicle_surge_sample(profile: dict, stress_rows: list[dict], corridor: str) -> dict:
    roads = profile.get("roads", {})
    rec = roads.get(corridor, {})
    stress_by_corridor = {row["corridor"]: row for row in stress_rows}
    stress = stress_by_corridor.get(corridor, {}).get("stress_score", 50)
    current = rec.get("historical_density_proxy", 0.4) * rec.get("capacity_proxy", 120)
    incoming_rate = max(1.0, rec.get("incident_frequency_per_day", 0.5) * (2.2 + stress / 70))
    outgoing_rate = max(0.25, incoming_rate * (0.88 - min(stress, 95) / 250))
    surge_index = incoming_rate - outgoing_rate
    flow_balance_index = incoming_rate / max(outgoing_rate, 0.01)
    return {
        "corridor": corridor,
        "mode": "simulation_decision_support",
        "current_vehicles_proxy": round(current, 1),
        "incoming_vehicle_rate_per_min_proxy": round(incoming_rate, 2),
        "outgoing_vehicle_rate_per_min_proxy": round(outgoing_rate, 2),
        "flow_balance_index": round(flow_balance_index, 2),
        "vehicle_surge_index": round(surge_index, 2),
        "interpretation": (
            "Flow balance above 1.0 means vehicles are entering faster than they leave; "
            f"current proxy balance is {flow_balance_index:.2f}."
        ),
        "windows": [
            {
                "minutes": minutes,
                "net_accumulated_vehicles": round(surge_index * minutes, 1),
                "additional_waiting_time_mins": round((surge_index * minutes) / max(rec.get("capacity_proxy", 120), 1) * 12, 1),
            }
            for minutes in (5, 15, 30)
        ],
    }


def build_domino_sample(profile: dict, stress_rows: list[dict], corridor: str) -> dict:
    shockwave = build_shockwave_sample(profile, stress_rows, corridor)
    stress_by_corridor = {row["corridor"]: row for row in stress_rows}
    source_stress = stress_by_corridor.get(corridor, {}).get("stress_score", 50)
    scenarios = []
    tipping_point = None
    for extra_vehicles in (5, 10, 15):
        pressure_delta = extra_vehicles * 1.8
        source_after = min(100, source_stress + pressure_delta)
        impacted = []
        critical_roads = []
        for road in shockwave["affected_roads"][:6]:
            before_stress = stress_by_corridor.get(road["corridor"], {}).get("stress_score", 35)
            after_stress = min(100, before_stress + pressure_delta * road["congestion_probability"] / max(road["hop_distance"], 1))
            level_after = stress_level(after_stress)
            if after_stress >= 80:
                critical_roads.append(road["corridor"])
            impacted.append({
                "corridor": road["corridor"],
                "before_stress": round(before_stress, 1),
                "after_stress": round(after_stress, 1),
                "after_level": level_after,
                "estimated_wait_added_mins": round((after_stress - before_stress) / 5, 1),
            })
        scenario = {
            "extra_vehicles": extra_vehicles,
            "source_before_stress": round(source_stress, 1),
            "source_after_stress": round(source_after, 1),
            "source_after_level": stress_level(source_after),
            "critical_threshold_crossed": bool(source_after >= 80 or critical_roads),
            "critical_roads": critical_roads,
            "impacted_roads": impacted,
        }
        if scenario["critical_threshold_crossed"] and tipping_point is None:
            tipping_point = {
                "extra_vehicles": extra_vehicles,
                "reason": "First simulated scenario where source or connected roads cross Critical stress.",
                "critical_roads": critical_roads or [corridor],
            }
        scenarios.append(scenario)
    return {
        "source_corridor": corridor,
        "scenario": "prototype domino spread after incremental vehicle pressure",
        "mode": "simulation_decision_support",
        "critical_threshold": 80,
        "tipping_point": tipping_point,
        "scenarios": scenarios,
        "explanation": "Tests +5, +10, and +15 vehicle pressure and flags the first Critical threshold crossing.",
    }


def build_cost_sample(stress_rows: list[dict]) -> dict:
    candidates = stress_rows[:2]
    routes = []
    for idx, row in enumerate(candidates, start=1):
        distance = 5 + idx * 1.5
        speed = max(8, 38 - row["stress_score"] / 3)
        travel_time = distance / speed * 60
        free_flow_time = distance / 38 * 60
        delay = max(0, travel_time - free_flow_time)
        fuel_cost = distance / 12 * 100 * (1 + row["stress_score"] / 300)
        time_cost = travel_time / 60 * 180
        idle_cost = delay / 60 * 1.1 * 100
        economic_cost = fuel_cost + time_cost + idle_cost
        routes.append({
            "route_id": f"route_{idx}",
            "corridor": row["corridor"],
            "distance_km": round(distance, 1),
            "stress_score": row["stress_score"],
            "travel_time_mins": round(travel_time, 1),
            "cost_breakdown": {
                "fuel_cost": round(fuel_cost, 2),
                "time_cost": round(time_cost, 2),
                "idle_cost": round(idle_cost, 2),
                "economic_cost": round(economic_cost, 2),
            },
            "explanation": (
                f"Cost combines fuel ({fuel_cost:.0f}), travel-time value ({time_cost:.0f}), "
                f"and idle delay ({idle_cost:.0f}) under stress {row['stress_score']:.1f}."
            ),
        })
    routes.sort(key=lambda r: r["cost_breakdown"]["economic_cost"])
    return {
        "mode": "simulation_decision_support",
        "routes": routes,
        "best_route_id": routes[0]["route_id"] if routes else None,
        "explanation_layer": "Economic cost is decomposed into fuel, time, and idle components for decision support.",
    }


def main() -> None:
    print("=" * 60)
    print("Gateway B - Traffic Intelligence")
    print("=" * 60)
    profile = load_json(ARTIFACT_SOURCE / "traffic_intelligence_profile.json", {"roads": {}, "graph": {"adjacency": {}}})
    corridor_risk = load_json(ARTIFACT_SOURCE / "corridor_risk_index.json", {})
    station_map = load_json(ARTIFACT_SOURCE / "station_map.json", {})
    stress_rows = build_stress_outputs(profile, corridor_risk, station_map)
    source_corridor = stress_rows[0]["corridor"] if stress_rows else "Mysore Road"

    shockwave = build_shockwave_sample(profile, stress_rows, source_corridor)
    vehicle_surge = build_vehicle_surge_sample(profile, stress_rows, source_corridor)
    domino = build_domino_sample(profile, stress_rows, source_corridor)
    congestion_cost = build_cost_sample(stress_rows)

    save_json(SIM_DIR / "road_stress_leaderboard.json", stress_rows)
    save_json(SIM_DIR / "shockwave_sample.json", shockwave)
    save_json(SIM_DIR / "vehicle_surge_sample.json", vehicle_surge)
    save_json(SIM_DIR / "domino_sample.json", domino)
    save_json(SIM_DIR / "congestion_cost_sample.json", congestion_cost)

    copied = {
        "risk_profiles": [
            name for name in ["traffic_intelligence_profile.json", "corridor_risk_index.json", "blackspot_scores.json", "surge_profile.json"]
            if copy_if_exists(name, RISK_DIR)
        ],
        "feature_importance": [
            name for name in ["traffic_intelligence_feature_importance.json", "full_feature_importance_ranked.csv", "closure_feature_importance.json"]
            if copy_if_exists(name, IMPORTANCE_DIR)
        ],
        "evaluations": [
            name for name in ["traffic_intelligence_evaluation.json", "closure_threshold_analysis.json", "feature_ablation_report.json"]
            if copy_if_exists(name, EVAL_DIR)
        ],
    }

    report = {
        "gateway": "B",
        "name": "Traffic Intelligence",
        "positioning": "Simulation, forecasting, and decision support. Not high-accuracy production ML.",
        "kept_features": [
            "Road Stress",
            "Shockwave",
            "Vehicle Surge",
            "Domino",
            "Congestion Cost",
        ],
        "evaluation_policy": {
            "claim": "Use as prototype simulation layer.",
            "do_not_claim": "Do not claim production-grade congestion prediction accuracy without live traffic labels.",
            "reason": "Current data is incident history, not continuous live vehicle flow/speed ground truth.",
        },
        "generated_outputs": {
            "simulation_outputs": str(SIM_DIR),
            "feature_importance": str(IMPORTANCE_DIR),
            "risk_profiles": str(RISK_DIR),
            "evaluations": str(EVAL_DIR),
        },
        "copied_artifacts": copied,
        "stress_leaderboard_count": len(stress_rows),
    }
    intelligence_profile = {
        "gateway": "B",
        "name": "Gateway B Intelligence Profile",
        "positioning": report["positioning"],
        "road_stress": {
            "levels": ["Healthy", "Moderate", "High", "Critical"],
            "factors": [
                "road_importance",
                "closure_frequency",
                "priority_frequency",
                "duration_risk",
                "station_load",
                "neighbor_influence",
            ],
            "leaderboard": stress_rows,
        },
        "shockwave_prediction": shockwave,
        "domino_simulator": domino,
        "vehicle_surge": vehicle_surge,
        "congestion_cost": congestion_cost,
        "decision_support_note": "Outputs are explainable simulations built from current historical incident artifacts.",
    }
    save_json(EVAL_DIR / "gateway_b_evaluation_report.json", report)
    save_json(RISK_DIR / "gateway_b_manifest.json", report)
    save_json(INTELLIGENCE_PROFILE_PATH, intelligence_profile)
    print(f"[gateway_b] Simulation outputs saved -> {SIM_DIR}")
    print(f"[gateway_b] Evaluation report saved -> {EVAL_DIR / 'gateway_b_evaluation_report.json'}")
    print(f"[gateway_b] Intelligence profile saved -> {INTELLIGENCE_PROFILE_PATH}")


if __name__ == "__main__":
    main()
