"""
Blackspot Engine — no ML model, pure analytics computation.
Outputs: blackspot_scores.json, neglect_index.json
"""

import pandas as pd
import numpy as np
import json

def compute_blackspot_scores(df: pd.DataFrame) -> dict:
    """
    Compute BlackspotScore for each junction with >= 5 incidents.
    
    Score formula:
        BlackspotScore = (total_incidents * 0.4)
                       + (recurrence_weeks * 3)
                       + (closures * 5)
                       + (high_priority_count * 0.3)
    
    Returns dict keyed by junction name.
    """
    df_j = df[df['junction'].notna()].copy()
    df_j['week_num'] = df_j['start_datetime'].dt.isocalendar().week.astype(int)
    
    # Weekly presence matrix
    junction_weekly = df_j.groupby(['junction', 'week_num']).size().unstack(fill_value=0)
    weeks_active = (junction_weekly > 0).sum(axis=1)
    
    # Aggregate stats per junction
    junc_stats = df_j.groupby('junction').agg(
        total_incidents=('id', 'count'),
        closures=('requires_road_closure', 'sum'),
        high_priority=('priority', lambda x: (x == 'High').sum()),
        corridor=('corridor', lambda x: x.mode()[0] if len(x) > 0 else 'Unknown'),
        top_cause=('event_cause', lambda x: x.value_counts().index[0]),
        peak_hour=('hour_of_day', lambda x: x.value_counts().index[0]),
        latitude=('latitude', 'mean'),
        longitude=('longitude', 'mean'),
    ).join(weeks_active.rename('recurrence_weeks'))
    
    # Filter to junctions with >= 5 incidents
    junc_stats = junc_stats[junc_stats['total_incidents'] >= 5].copy()
    
    junc_stats['blackspot_score'] = (
        junc_stats['total_incidents'] * 0.4
        + junc_stats['recurrence_weeks'] * 3
        + junc_stats['closures'] * 5
        + junc_stats['high_priority'] * 0.3
    ).round(1)
    
    junc_stats['blackspot_tier'] = pd.cut(
        junc_stats['blackspot_score'],
        bins=[0, 30, 50, 70, 999],
        labels=['Monitored', 'At Risk', 'Critical', 'Chronic']
    ).astype(str)
    
    # Sort by score descending
    junc_stats = junc_stats.sort_values('blackspot_score', ascending=False)
    
    return junc_stats.reset_index().to_dict(orient='records')


def compute_neglect_index(df: pd.DataFrame) -> dict:
    """
    Identify incidents open 5x+ longer than the median for their event_cause.
    Aggregate by police_station to find chronically under-responding stations.
    
    Returns dict: { police_station: { neglect_count, neglect_rate, top_cause } }
    """
    # Only use closed records with valid duration
    valid = df[
        (df['duration_mins'] > 0) &
        (df['duration_mins'] < 5000) &
        (df['status'].isin(['closed', 'resolved']))
    ].copy()
    
    # Median per cause
    cause_medians = valid.groupby('event_cause')['duration_mins'].median()
    valid['expected_duration'] = valid['event_cause'].map(cause_medians)
    valid['neglect_ratio'] = valid['duration_mins'] / valid['expected_duration']
    valid['is_neglected'] = valid['neglect_ratio'] > 5
    
    # Per station summary
    station_summary = valid.groupby('police_station').agg(
        total_incidents=('id', 'count'),
        neglected_count=('is_neglected', 'sum'),
        top_neglected_cause=('event_cause', lambda x: x[valid.loc[x.index, 'is_neglected']].value_counts().index[0]
                              if valid.loc[x.index, 'is_neglected'].any() else 'none')
    )
    station_summary['neglect_rate'] = (
        station_summary['neglected_count'] / station_summary['total_incidents']
    ).round(3)
    
    return station_summary.reset_index().to_dict(orient='records')


if __name__ == '__main__':
    import sys
    sys.path.append('.')
    
    df = pd.read_csv('data/processed/events_clean.csv')
    df['start_datetime'] = pd.to_datetime(df['start_datetime'], utc=True, format='mixed')
    df['closed_datetime'] = pd.to_datetime(df['closed_datetime'], utc=True, format='mixed', errors='coerce')
    df['duration_mins'] = (df['closed_datetime'] - df['start_datetime']).dt.total_seconds() / 60
    df['hour_of_day'] = df['start_datetime'].dt.hour
    
    blackspot_scores = compute_blackspot_scores(df)
    neglect_index = compute_neglect_index(df)
    
    import os
    os.makedirs('ml/artifacts', exist_ok=True)
    
    with open('ml/artifacts/blackspot_scores.json', 'w') as f:
        json.dump(blackspot_scores, f, indent=2, default=str)
    
    with open('ml/artifacts/neglect_index.json', 'w') as f:
        json.dump(neglect_index, f, indent=2, default=str)
    
    print(f"Blackspot engine complete.")
    print(f"  Total junctions scored: {len(blackspot_scores)}")
    print(f"  Chronic tier (score > 70): {sum(1 for r in blackspot_scores if r['blackspot_tier'] == 'Chronic')}")
    print(f"  Neglect index: {len(neglect_index)} stations analyzed")
