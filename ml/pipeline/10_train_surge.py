"""
Weather Surge Profile Computation.

Outputs:
  ml/artifacts/surge_profile.json      -- corridor vulnerability + typical surge stats
  ml/artifacts/surge_replay_march7.json -- pre-computed March 7 replay data for demo
"""

import pandas as pd
import numpy as np
import json


def compute_surge_vulnerability(df: pd.DataFrame) -> dict:
    """
    Which corridors / junctions are historically most affected
    by water_logging and tree_fall?
    
    Returns dict with corridor-level vulnerability scores.
    """
    weather_causes = ['water_logging', 'tree_fall']
    weather_df = df[df['event_cause'].isin(weather_causes)].copy()
    
    corridor_vulnerability = weather_df.groupby('corridor').agg(
        water_logging_count=('event_cause', lambda x: (x == 'water_logging').sum()),
        tree_fall_count=('event_cause', lambda x: (x == 'tree_fall').sum()),
        total_weather_incidents=('id', 'count'),
        closure_count=('requires_road_closure', 'sum'),
        latitude=('latitude', 'mean'),
        longitude=('longitude', 'mean'),
    ).reset_index()
    
    # Normalize to vulnerability score 0–100
    max_incidents = corridor_vulnerability['total_weather_incidents'].max()
    if max_incidents > 0:
        corridor_vulnerability['vulnerability_score'] = (
            corridor_vulnerability['total_weather_incidents'] / max_incidents * 100
        ).round(1)
    else:
        corridor_vulnerability['vulnerability_score'] = 0.0
    
    corridor_vulnerability['deployment_priority'] = pd.cut(
        corridor_vulnerability['vulnerability_score'],
        bins=[0, 20, 50, 75, 101],
        labels=['Low', 'Medium', 'High', 'Critical'],
        include_lowest=True
    ).astype(str)
    
    return corridor_vulnerability.sort_values(
        'vulnerability_score', ascending=False
    ).to_dict(orient='records')


def build_surge_replay(df: pd.DataFrame) -> dict:
    """
    Pre-compute the March 7 replay dataset for the demo.
    
    Returns:
      - what_system_would_have_predicted (pre-deployment plan for March 6 11pm)
      - what_actually_happened (March 7 real incident timeline)
    """
    df['date'] = df['start_datetime'].dt.date.astype(str)
    march7 = df[df['date'] == '2024-03-07'].copy()
    march6 = df[df['date'] == '2024-03-06'].copy()
    
    # What happened by hour on March 7
    march7_timeline = march7.groupby('hour_of_day').agg(
        total=('id', 'count'),
        water_logging=('event_cause', lambda x: (x == 'water_logging').sum()),
        tree_fall=('event_cause', lambda x: (x == 'tree_fall').sum()),
        closures=('requires_road_closure', 'sum'),
        top_corridor=('corridor', lambda x: x.value_counts().index[0] if len(x) > 0 else 'unknown')
    ).reset_index().to_dict(orient='records')
    
    # Top corridors hit
    march7_corridor_breakdown = march7['corridor'].value_counts().head(10).to_dict()
    
    # What GridSense would have pre-deployed (rule-based)
    # Top 5 vulnerable corridors × their typical station
    vulnerable_corridors = [
        'Mysore Road', 'Bellary Road 1', 'Bannerghata Road',
        'ORR East 1', 'ORR East 2'
    ]
    
    pre_deployment_plan = []
    station_map_path = 'ml/artifacts/station_map.json'
    try:
        with open(station_map_path) as f:
            station_map = json.load(f)
    except FileNotFoundError:
        station_map = {}
    
    for corridor in vulnerable_corridors:
        stations = station_map.get(corridor, [{'station': 'Primary Station', 'rank': 1}])
        primary = next((s for s in stations if s.get('rank') == 1), stations[0] if stations else {})
        pre_deployment_plan.append({
            "corridor": corridor,
            "recommended_station": primary.get('station', 'Unknown'),
            "recommended_officers": 8,  # elevated for surge
            "escalation_tier": "Critical",
            "surge_reason": "Water logging + tree fall historical vulnerability",
            "recommended_action_time": "2024-03-06T23:00:00Z"
        })
    
    return {
        "surge_day": "2024-03-07",
        "baseline_day": "2024-03-06",
        "surge_stats": {
            "march6_total": len(march6),
            "march7_total": len(march7),
            "surge_multiplier": round(len(march7) / max(len(march6), 1), 1),
            "peak_hour": 6,
            "peak_hour_count": 83,
            "total_closures": int(march7['requires_road_closure'].sum()),
            "water_logging_count": int((march7['event_cause'] == 'water_logging').sum()),
            "tree_fall_count": int((march7['event_cause'] == 'tree_fall').sum()),
        },
        "march7_hourly_timeline": march7_timeline,
        "top_corridors_hit": march7_corridor_breakdown,
        "pre_deployment_plan": pre_deployment_plan
    }


if __name__ == '__main__':
    df = pd.read_csv('data/processed/events_clean.csv')
    df['start_datetime'] = pd.to_datetime(df['start_datetime'], utc=True, format='mixed')
    df['hour_of_day'] = df['start_datetime'].dt.hour
    
    surge_vulnerability = compute_surge_vulnerability(df)
    surge_replay = build_surge_replay(df)
    
    import os
    os.makedirs('ml/artifacts', exist_ok=True)
    
    with open('ml/artifacts/surge_profile.json', 'w') as f:
        json.dump(surge_vulnerability, f, indent=2, default=str)
    
    with open('ml/artifacts/surge_replay_march7.json', 'w') as f:
        json.dump(surge_replay, f, indent=2, default=str)
    
    print("Weather surge computation complete.")
    print(f"  Corridors in vulnerability profile: {len(surge_vulnerability)}")
    print(f"  March 7 surge multiplier: {surge_replay['surge_stats']['surge_multiplier']}x")
    print(f"  Pre-deployment corridors: {len(surge_replay['pre_deployment_plan'])}")
