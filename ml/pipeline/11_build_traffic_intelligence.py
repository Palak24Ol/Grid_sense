"""
Build traffic intelligence features from existing GridSense data.

Outputs:
  ml/artifacts/traffic_intelligence_profile.json

This is a prototype feature-engineering step. It avoids new live-data
requirements by deriving density, speed, delay, neighbor, centrality, and
weather proxies from the current incident dataset and existing artifacts.
"""

import json
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
OUT_PROFILE = ARTIFACT_DIR / "traffic_intelligence_profile.json"


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def normalize_map(values: dict, low=0.0, high=100.0) -> dict:
    if not values:
        return {}
    vals = list(values.values())
    min_v = min(vals)
    max_v = max(vals)
    if max_v == min_v:
        return {k: high / 2 for k in values}
    return {
        k: low + (float(v) - min_v) / (max_v - min_v) * (high - low)
        for k, v in values.items()
    }


def build_adjacency_from_data(df: pd.DataFrame) -> dict:
    df_j = df[df["junction"].notna() & df["corridor"].notna()].copy()
    junction_corridors = df_j.groupby("junction")["corridor"].unique().to_dict()
    adjacency = {}
    for corridor in df_j["corridor"].dropna().unique():
        if corridor == "Non-corridor":
            continue
        adjacent = set()
        junctions = df_j[df_j["corridor"] == corridor]["junction"].dropna().unique()
        for junction in junctions:
            for other in junction_corridors.get(junction, []):
                if other != corridor and other != "Non-corridor":
                    adjacent.add(other)
        adjacency[corridor] = sorted(adjacent)
    return adjacency


def betweenness_centrality(adjacency: dict) -> dict:
    """Small pure-Python Brandes centrality for an unweighted road graph."""
    nodes = sorted(set(adjacency) | {n for vals in adjacency.values() for n in vals})
    graph = {node: set(adjacency.get(node, [])) for node in nodes}
    for node, neighbors in list(graph.items()):
        for neighbor in neighbors:
            graph.setdefault(neighbor, set()).add(node)

    centrality = {node: 0.0 for node in graph}
    for source in graph:
        stack = []
        predecessors = {node: [] for node in graph}
        sigma = dict.fromkeys(graph, 0.0)
        distance = dict.fromkeys(graph, -1)
        sigma[source] = 1.0
        distance[source] = 0
        queue = deque([source])

        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            for neighbor in graph[vertex]:
                if distance[neighbor] < 0:
                    queue.append(neighbor)
                    distance[neighbor] = distance[vertex] + 1
                if distance[neighbor] == distance[vertex] + 1:
                    sigma[neighbor] += sigma[vertex]
                    predecessors[neighbor].append(vertex)

        dependency = dict.fromkeys(graph, 0.0)
        while stack:
            vertex = stack.pop()
            for pred in predecessors[vertex]:
                if sigma[vertex] > 0:
                    dependency[pred] += (sigma[pred] / sigma[vertex]) * (1 + dependency[vertex])
            if vertex != source:
                centrality[vertex] += dependency[vertex]

    n = len(graph)
    if n > 2:
        scale = 1 / ((n - 1) * (n - 2))
        centrality = {node: score * scale for node, score in centrality.items()}
    return centrality


def rolling_stats(df: pd.DataFrame) -> dict:
    daily = (
        df.dropna(subset=["corridor", "date"])
        .groupby(["corridor", "date"])
        .size()
        .reset_index(name="incidents")
    )
    stats = {}
    for corridor, group in daily.groupby("corridor"):
        group = group.sort_values("date")
        rolling = group["incidents"].rolling(7, min_periods=1)
        stats[corridor] = {
            "rolling_mean_7d": float(rolling.mean().iloc[-1]),
            "rolling_std_7d": float(rolling.std().fillna(0).iloc[-1]),
        }
    return stats


def main():
    print("=" * 60)
    print("GridSense - Build Traffic Intelligence Profile")
    print("=" * 60)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if not CLEAN_CSV.exists():
        raise FileNotFoundError(f"Missing {CLEAN_CSV}")

    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=["start_datetime", "corridor"])
    df = df[df["corridor"] != "Non-corridor"].copy()
    df["date"] = df["start_datetime"].dt.date.astype(str)
    df["requires_road_closure"] = (
        df["requires_road_closure"].astype(str).str.upper().map({"TRUE": 1, "FALSE": 0}).fillna(0)
    )
    df["is_high_priority"] = df["priority"].astype(str).str.lower().eq("high").astype(int)
    df["duration_mins"] = pd.to_numeric(df["duration_mins"], errors="coerce")

    days = max(1, (df["start_datetime"].max() - df["start_datetime"].min()).days + 1)
    corridor_risk = load_json(ARTIFACT_DIR / "corridor_risk_index.json", {})
    adjacency = load_json(ARTIFACT_DIR / "corridor_adjacency.json", {}) or build_adjacency_from_data(df)
    surge_profile = load_json(ARTIFACT_DIR / "surge_profile.json", [])
    blackspots = load_json(ARTIFACT_DIR / "blackspot_scores.json", [])

    weather_by_corridor = {
        rec["corridor"]: float(rec.get("vulnerability_score", 0.0))
        for rec in surge_profile
        if rec.get("corridor")
    }
    blackspot_by_corridor = {}
    for rec in blackspots:
        corridor = rec.get("corridor")
        if not corridor or corridor == "Non-corridor":
            continue
        blackspot_by_corridor.setdefault(corridor, []).append(float(rec.get("blackspot_score", 0.0)))

    rolling = rolling_stats(df)
    centrality = betweenness_centrality(adjacency)
    grouped = df.groupby("corridor")
    incident_frequency = {corridor: len(group) / days for corridor, group in grouped}
    frequency_score = normalize_map(incident_frequency)
    max_frequency = max(incident_frequency.values()) if incident_frequency else 1.0

    roads = {}
    for corridor, group in grouped:
        total = int(len(group))
        closure_rate = float(group["requires_road_closure"].mean())
        high_priority_rate = float(group["is_high_priority"].mean())
        median_duration = float(group["duration_mins"].median()) if group["duration_mins"].notna().any() else 45.0
        avg_duration = float(group["duration_mins"].mean()) if group["duration_mins"].notna().any() else median_duration
        duration_std = float(group["duration_mins"].std()) if group["duration_mins"].notna().sum() > 1 else 0.0
        density_proxy = clamp(incident_frequency[corridor] / max(max_frequency, 0.001), 0.05, 1.0)
        duration_pressure = clamp(median_duration / 240.0, 0.0, 1.0)
        historical_speed = clamp(
            38.0 - 14.0 * density_proxy - 7.0 * closure_rate - 5.0 * duration_pressure,
            8.0,
            38.0,
        )
        speed_drop_pct = clamp(18.0 + 30.0 * density_proxy + 12.0 * closure_rate, 0.0, 65.0)
        current_speed = historical_speed * (1.0 - speed_drop_pct / 100.0)
        road_centrality = clamp(centrality.get(corridor, 0.0), 0.0, 1.0)
        historical_travel = 8.0 + 7.0 * density_proxy + 5.0 * road_centrality
        current_travel = historical_travel * (1.0 + speed_drop_pct / 100.0 + closure_rate)
        corridor_risk_rec = corridor_risk.get(corridor, {})
        blackspot_scores = blackspot_by_corridor.get(corridor, [])
        max_blackspot = max(blackspot_scores) if blackspot_scores else 0.0

        roads[corridor] = {
            "corridor": corridor,
            "total_incidents": total,
            "incident_frequency_per_day": round(incident_frequency[corridor], 3),
            "historical_density_proxy": round(density_proxy, 3),
            "historical_speed_kmph": round(historical_speed, 1),
            "current_speed_proxy_kmph": round(current_speed, 1),
            "speed_drop_pct_proxy": round(speed_drop_pct, 1),
            "historical_travel_time_proxy_mins": round(historical_travel, 1),
            "current_travel_time_proxy_mins": round(current_travel, 1),
            "delay_ratio_proxy": round(current_travel / max(historical_travel, 1.0), 3),
            "road_centrality": round(road_centrality, 4),
            "historical_congestion_frequency_score": round(frequency_score.get(corridor, 0.0), 1),
            "closure_rate": round(closure_rate, 4),
            "high_priority_rate": round(high_priority_rate, 4),
            "median_duration_mins": round(median_duration, 1),
            "avg_duration_mins": round(avg_duration, 1),
            "duration_std_mins": round(duration_std, 1),
            "rolling_mean_7d": round(rolling.get(corridor, {}).get("rolling_mean_7d", 0.0), 3),
            "rolling_std_7d": round(rolling.get(corridor, {}).get("rolling_std_7d", 0.0), 3),
            "weather_risk_score": round(weather_by_corridor.get(corridor, 0.0), 1),
            "blackspot_score": round(max_blackspot, 1),
            "composite_risk_score": round(float(corridor_risk_rec.get("composite_risk_score", 0.0)), 1),
            "top_junction": corridor_risk_rec.get("top_junction"),
            "top_police_station": corridor_risk_rec.get("top_police_station"),
            "latitude": round(float(group["latitude"].mean()), 6),
            "longitude": round(float(group["longitude"].mean()), 6),
            "capacity_proxy": round(100.0 + 45.0 * road_centrality + 25.0 * (1.0 - density_proxy), 1),
            "adjacent_corridors": adjacency.get(corridor, []),
        }

    for corridor, road in roads.items():
        neighbors = [n for n in adjacency.get(corridor, []) if n in roads]
        if neighbors:
            neighbor_density = float(np.mean([roads[n]["historical_density_proxy"] for n in neighbors]))
            neighbor_speed = float(np.mean([roads[n]["historical_speed_kmph"] for n in neighbors]))
            neighbor_risk = float(np.mean([roads[n]["composite_risk_score"] for n in neighbors]))
            neighbor_capacity = float(np.mean([roads[n]["capacity_proxy"] for n in neighbors]))
            neighbor_influence = clamp((neighbor_density * 60.0 + neighbor_risk * 0.4), 0.0, 100.0)
        else:
            neighbor_density = 0.0
            neighbor_speed = road["historical_speed_kmph"]
            neighbor_influence = 0.0
            neighbor_capacity = road["capacity_proxy"]
        road["neighbor_density_proxy"] = round(neighbor_density, 3)
        road["neighbor_speed_kmph"] = round(neighbor_speed, 1)
        road["neighbor_capacity_proxy"] = round(neighbor_capacity, 1)
        road["neighbor_congestion_influence_score"] = round(neighbor_influence, 1)

    profile = {
        "artifact": "traffic_intelligence_profile",
        "version": "prototype-v1",
        "source": str(CLEAN_CSV.relative_to(ROOT)),
        "global": {
            "total_rows": int(len(df)),
            "observed_days": int(days),
            "corridor_count": int(len(roads)),
            "notes": [
                "Density, speed, delay, and capacity are proxies because no live traffic sensor feed exists.",
                "Road centrality is computed from corridor adjacency using pure-Python Brandes centrality.",
            ],
        },
        "graph": {"adjacency": adjacency},
        "roads": roads,
    }

    with open(OUT_PROFILE, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"Profile saved: {OUT_PROFILE}")
    print(f"Corridors: {len(roads)}")
    top = sorted(roads.values(), key=lambda rec: rec["historical_congestion_frequency_score"], reverse=True)[:5]
    for rec in top:
        print(
            f"  {rec['corridor']}: density={rec['historical_density_proxy']} "
            f"speed={rec['historical_speed_kmph']} centrality={rec['road_centrality']}"
        )


if __name__ == "__main__":
    main()
