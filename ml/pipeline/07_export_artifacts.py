"""
07_export_artifacts.py — Build all JSON lookup artifacts and verify all artifacts exist.

Can be run in two modes:
  --json-only    Build corridor_risk_index.json, station_map.json, station_concurrency.json
                 (runs after 01_ingest.py, before model training — unblocks backend)
  (default)      Full run — JSON artifacts + verify all pkl files exist and load

Inputs:
    data/processed/events_clean.csv
    ml/artifacts/closure_model.pkl        (required for full verify only)
    ml/artifacts/priority_model.pkl       (required for full verify only)
    ml/artifacts/encoders.pkl             (required for full verify only)
    ml/artifacts/duration_lookup.json

Outputs:
    ml/artifacts/corridor_risk_index.json
    ml/artifacts/station_map.json
    ml/artifacts/station_concurrency.json

Run:
    python ml/pipeline/07_export_artifacts.py --json-only   # Day 2 (after ingest)
    python ml/pipeline/07_export_artifacts.py               # Day 5 (full verify)
"""

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


# ── JSON Artifact Builders ──────────────────────────────────────────────────────

def build_corridor_risk_index(df: pd.DataFrame) -> dict:
    """Compute composite risk score per corridor.

    composite_risk_score = 0.5 × (high_priority_rate × 100) +
                           0.3 × (closure_rate × 100) +
                           0.2 × min(total_incidents / 10, 100)
    Score is capped at 100.
    """
    print("[07_export] Building corridor_risk_index.json …")

    # Exclude stale active from risk computation
    clean = df[df["is_stale_active"] == False].copy()

    result = {}
    for corridor, group in clean.groupby("corridor"):
        if pd.isna(corridor):
            continue
        total = len(group)
        if total < 5:
            continue

        high_priority_count = int((group["priority"].str.lower() == "high").sum())
        high_priority_rate = high_priority_count / total

        closure_count = int(group["requires_road_closure"].sum())
        closure_rate = closure_count / total

        composite = round(
            0.5 * (high_priority_rate * 100)
            + 0.3 * (closure_rate * 100)
            + 0.2 * min(total / 10, 100),
            1,
        )

        # Top junction (highest incident count in this corridor)
        junction_counts = group["junction"].dropna().value_counts()
        top_junction = str(junction_counts.index[0]) if len(junction_counts) > 0 else None

        # Top police station (mode)
        station_counts = group["police_station"].dropna().value_counts()
        top_station = str(station_counts.index[0]) if len(station_counts) > 0 else None

        # Median duration
        valid_dur = group["duration_mins"].dropna()
        valid_dur = valid_dur[valid_dur.between(0, 5000)]
        median_dur = round(float(valid_dur.median()), 1) if len(valid_dur) > 0 else None

        result[str(corridor)] = {
            "corridor": str(corridor),
            "total_incidents": total,
            "high_priority_count": high_priority_count,
            "high_priority_rate": round(high_priority_rate, 4),
            "closure_count": closure_count,
            "closure_rate": round(closure_rate, 4),
            "composite_risk_score": min(composite, 100.0),
            "top_junction": top_junction,
            "top_police_station": top_station,
            "median_duration_mins": median_dur,
        }

    # Sort by composite_risk_score descending
    result = dict(
        sorted(result.items(), key=lambda x: -x[1]["composite_risk_score"])
    )
    print(f"  Corridors indexed: {len(result)}")
    for corridor, rec in list(result.items())[:5]:
        print(
            f"  {corridor}: score={rec['composite_risk_score']}  "
            f"incidents={rec['total_incidents']}"
        )
    return result


def build_station_map(df: pd.DataFrame) -> dict:
    """Build corridor → top-3 police stations mapping.

    Returns:
        {
          "Mysore Road": [
            {"police_station": "Halasuru Gate", "incident_count": 239, "rank": 1},
            {"police_station": "Yeshwanthpura", "incident_count": 181, "rank": 2},
            ...
          ],
          ...
        }
    """
    print("[07_export] Building station_map.json …")
    clean = df[df["is_stale_active"] == False].copy()

    result = {}
    for corridor, group in clean.groupby("corridor"):
        if pd.isna(corridor) or str(corridor) == "Non-corridor":
            continue
        station_counts = (
            group.groupby("police_station")
            .size()
            .sort_values(ascending=False)
            .head(3)
        )
        stations = [
            {
                "police_station": str(station),
                "incident_count": int(count),
                "rank": i + 1,
            }
            for i, (station, count) in enumerate(station_counts.items())
        ]
        if stations:
            result[str(corridor)] = stations

    print(f"  Corridors mapped: {len(result)}")
    return result


def build_station_concurrency(df: pd.DataFrame) -> dict:
    """Build station × hour × day_of_week → avg/max concurrent active incidents.

    Uses historical closed incidents as proxy for concurrent load:
    at any given hour, count how many open incidents there were.

    Simplified approach: for each incident, it "occupies" station resources
    from start_hour until start_hour + median_duration_hours. We count
    co-occurrence per station × hour × dow bucket.

    Returns flat dict keyed as "station:hour:dow".
    """
    print("[07_export] Building station_concurrency.json …")

    clean = df[df["is_stale_active"] == False].copy()
    clean = clean[clean["start_datetime"].notna()].copy()
    clean["start_datetime"] = pd.to_datetime(clean["start_datetime"], utc=True, errors="coerce")

    # Simple approach: group by police_station × hour_of_day × day_of_week
    # and compute average incidents per time slot as proxy for concurrency
    agg = (
        clean.groupby(["police_station", "hour_of_day", "day_of_week"])
        .size()
        .reset_index(name="incident_count")
    )

    # Total days in dataset per dow
    days_in_dataset = (
        clean.groupby("day_of_week")["start_datetime"]
        .apply(lambda x: x.dt.date.nunique())
    )

    result = {}
    for _, row in agg.iterrows():
        station = str(row["police_station"])
        hour = int(row["hour_of_day"])
        dow = int(row["day_of_week"])
        count = int(row["incident_count"])

        # avg_concurrent = incidents in this slot / weeks in dataset
        n_weeks = max(days_in_dataset.get(dow, 22) / 7, 1)
        avg_concurrent = round(count / n_weeks, 2)
        key = f"{station}:{hour}:{dow}"
        result[key] = {
            "police_station": station,
            "hour_of_day": hour,
            "day_of_week": dow,
            "avg_concurrent": avg_concurrent,
            "max_concurrent": count,
        }

    print(f"  Concurrency records: {len(result):,}")
    return result


# ── Artifact Verification ───────────────────────────────────────────────────────

def verify_artifacts(artifact_dir: Path, json_only: bool = False) -> bool:
    """Check all artifacts exist and are loadable. Returns True if all pass."""
    print("\n[07_export] ── Artifact Verification ──")

    required_json = [
        "duration_lookup.json",
        "corridor_risk_index.json",
        "station_map.json",
        "station_concurrency.json",
        "blackspot_scores.json",
        "neglect_index.json",
        "cascade_multipliers.json",
        "corridor_adjacency.json",
        "surge_profile.json",
        "surge_replay_march7.json",
    ]

    required_pkl = [] if json_only else [
        "encoders.pkl",
        "closure_model.pkl",
        "priority_model.pkl",
    ]

    all_ok = True

    for fname in required_json:
        path = artifact_dir / fname
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                size_kb = path.stat().st_size / 1024
                keys = len(data) if isinstance(data, dict) else len(data)
                print(f"  ✅ {fname}  ({size_kb:.1f} KB  {keys} entries)")
            except Exception as e:
                print(f"  ❌ {fname}  LOAD ERROR: {e}")
                all_ok = False
        else:
            print(f"  ❌ {fname}  MISSING")
            all_ok = False

    for fname in required_pkl:
        path = artifact_dir / fname
        if path.exists():
            try:
                obj = joblib.load(path)
                size_kb = path.stat().st_size / 1024
                print(f"  ✅ {fname}  ({size_kb:.1f} KB  type={type(obj).__name__})")
            except Exception as e:
                print(f"  ❌ {fname}  LOAD ERROR: {e}")
                all_ok = False
        else:
            print(f"  ❌ {fname}  MISSING")
            all_ok = False

    # Check prophet models directory
    prophet_dir = artifact_dir / "prophet_models"
    if prophet_dir.exists():
        prophet_files = list(prophet_dir.glob("*.pkl"))
        print(f"  ✅ prophet_models/  ({len(prophet_files)} junction models)")
    else:
        status = "⚠️ " if json_only else "❌"
        print(f"  {status} prophet_models/  NOT YET TRAINED  (expected after 06_train_forecast.py)")

    return all_ok


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Export GridSense ML artifacts")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only build JSON artifacts (skip pkl verification)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("GridSense — Step 7: Export Artifacts")
    if args.json_only:
        print("  Mode: JSON only (run before model training)")
    else:
        print("  Mode: Full verification")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"[07_export] ERROR: {CLEAN_CSV} not found. Run 01_ingest.py first.")
        sys.exit(1)

    print(f"\n[07_export] Loading {CLEAN_CSV} …")
    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    df["requires_road_closure"] = (
        df["requires_road_closure"].astype(str).str.upper().map(
            {"TRUE": True, "FALSE": False, "1": True, "0": False}
        ).fillna(False)
    )
    df["is_stale_active"] = (
        df["is_stale_active"].astype(str).str.upper().map(
            {"TRUE": True, "FALSE": False, "1": True, "0": False}
        ).fillna(False)
    )
    print(f"[07_export] Rows: {len(df):,}")

    # Build JSON artifacts
    corridor_risk = build_corridor_risk_index(df)
    with open(ARTIFACT_DIR / "corridor_risk_index.json", "w") as f:
        json.dump(corridor_risk, f, indent=2)
    print(f"  -> corridor_risk_index.json saved")

    station_map = build_station_map(df)
    with open(ARTIFACT_DIR / "station_map.json", "w") as f:
        json.dump(station_map, f, indent=2)
    print(f"  -> station_map.json saved")

    concurrency = build_station_concurrency(df)
    with open(ARTIFACT_DIR / "station_concurrency.json", "w") as f:
        json.dump(concurrency, f, indent=2)
    print(f"  -> station_concurrency.json saved")

    # Verify
    ok = verify_artifacts(ARTIFACT_DIR, json_only=args.json_only)

    if ok:
        print("\n[07_export] ✅ All artifacts verified.")
    else:
        print("\n[07_export] ⚠️  Some artifacts missing or unloadable.")
        if not args.json_only:
            sys.exit(1)

    print("\n[07_export] ✅ Done.")


if __name__ == "__main__":
    main()