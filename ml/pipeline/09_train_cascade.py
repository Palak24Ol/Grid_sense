"""
Cascade Ripple Computation — measures how planned events elevate
unplanned incident rates on the same corridor within a 3-hour window.

Outputs:
  ml/artifacts/cascade_multipliers.json
  ml/artifacts/corridor_adjacency.json
"""

import pandas as pd
import numpy as np
import json


def compute_cascade_multipliers(df: pd.DataFrame) -> dict:
    """
    For each planned event_cause, compute:
      - avg_unplanned_in_3h_window (same corridor, within 3 hours after planned event)
      - baseline_avg (same corridor, random 3h window with no planned event nearby)
      - cascade_multiplier = window_avg / baseline_avg
    
    Returns dict keyed by event_cause.
    """
    planned = df[df['event_type'] == 'planned'].copy()
    unplanned = df[df['event_type'] == 'unplanned'].copy()
    
    # Baseline: avg unplanned incidents per 3h window per corridor
    # Total unplanned per corridor / total 3h windows in dataset (150 days × 8 windows/day)
    total_windows = 150 * 8
    baseline_by_corridor = (
        unplanned.groupby('corridor').size() / total_windows
    ).to_dict()
    
    results = {}
    
    for cause in planned['event_cause'].unique():
        cause_planned = planned[
            (planned['event_cause'] == cause) &
            (~planned['corridor'].isin(['Non-corridor'])) &
            (planned['corridor'].notna())
        ]
        
        window_counts = []
        baselines = []
        
        for _, p_row in cause_planned.iterrows():
            corridor = p_row['corridor']
            window_start = p_row['start_datetime']
            window_end = window_start + pd.Timedelta(hours=3)
            
            count = len(unplanned[
                (unplanned['corridor'] == corridor) &
                (unplanned['start_datetime'] >= window_start) &
                (unplanned['start_datetime'] <= window_end)
            ])
            window_counts.append(count)
            baselines.append(baseline_by_corridor.get(corridor, 0.1))
        
        if len(window_counts) < 3:
            continue
        
        avg_window = np.mean(window_counts)
        avg_baseline = np.mean(baselines)
        multiplier = avg_window / avg_baseline if avg_baseline > 0 else 1.0
        
        results[cause] = {
            "cause": cause,
            "sample_count": len(window_counts),
            "avg_unplanned_3h_window": round(avg_window, 3),
            "avg_baseline_3h": round(avg_baseline, 3),
            "cascade_multiplier": round(multiplier, 2),
            "risk_level": (
                "critical" if multiplier >= 4.0 else
                "high" if multiplier >= 2.5 else
                "moderate" if multiplier >= 1.5 else
                "low"
            )
        }
    
    return results


def compute_corridor_adjacency(df: pd.DataFrame) -> dict:
    """
    Build a simple adjacency map: which corridors share junctions?
    Two corridors are adjacent if any junction appears in both.
    Used to propagate cascade ripples to nearby corridors.
    
    Returns dict: { corridor: [list of adjacent corridors] }
    """
    df_j = df[df['junction'].notna() & df['corridor'].notna()].copy()
    
    # Junction → corridors map
    junction_corridors = df_j.groupby('junction')['corridor'].unique().to_dict()
    
    # Build adjacency
    adjacency = {}
    all_corridors = df_j['corridor'].unique()
    
    for corridor in all_corridors:
        if corridor == 'Non-corridor':
            continue
        junctions_in_corridor = df_j[df_j['corridor'] == corridor]['junction'].unique()
        adjacent = set()
        for junc in junctions_in_corridor:
            for adj_corridor in junction_corridors.get(junc, []):
                if adj_corridor != corridor and adj_corridor != 'Non-corridor':
                    adjacent.add(adj_corridor)
        adjacency[corridor] = list(adjacent)
    
    return adjacency


if __name__ == '__main__':
    df = pd.read_csv('data/processed/events_clean.csv')
    df['start_datetime'] = pd.to_datetime(df['start_datetime'], utc=True, format='mixed')
    
    multipliers = compute_cascade_multipliers(df)
    adjacency = compute_corridor_adjacency(df)
    
    import os
    os.makedirs('ml/artifacts', exist_ok=True)
    
    with open('ml/artifacts/cascade_multipliers.json', 'w') as f:
        json.dump(multipliers, f, indent=2)
    
    with open('ml/artifacts/corridor_adjacency.json', 'w') as f:
        json.dump(adjacency, f, indent=2)
    
    print(f"Cascade computation complete.")
    print(f"  Causes with multipliers: {len(multipliers)}")
    for cause, data in sorted(multipliers.items(), key=lambda x: -x[1]['cascade_multiplier']):
        print(f"  {cause}: {data['cascade_multiplier']}x ({data['risk_level']})")
    print(f"  Corridors in adjacency map: {len(adjacency)}")
