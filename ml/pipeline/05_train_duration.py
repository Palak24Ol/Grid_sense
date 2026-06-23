"""
05_train_duration.py — Build duration lookup table from historical data.

No ML model — pure statistical lookup: median, p25, p75 per event_cause.

Inputs:
    data/processed/events_clean.csv

Outputs:
    ml/artifacts/duration_lookup.json

Format:
    {
      "vehicle_breakdown": {
        "median": 40.7,
        "p25": 18.2,
        "p75": 93.6,
        "count": 2841
      },
      ...
    }

Run:
    python ml/pipeline/05_train_duration.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = ARTIFACT_DIR / "duration_lookup.json"

VALID_DURATION_MIN = 0
VALID_DURATION_MAX = 5000


def build_duration_lookup(df: pd.DataFrame) -> dict:
    """Compute median, p25, p75 duration per event_cause.

    Only uses rows where duration is within valid bounds.
    """
    # Filter to valid durations
    dur_df = df[df["duration_mins"].between(VALID_DURATION_MIN, VALID_DURATION_MAX)].copy()
    print(f"[05_duration] Valid duration rows: {len(dur_df):,} / {len(df):,}")

    lookup = {}
    for cause, group in dur_df.groupby("event_cause"):
        if pd.isna(cause) or str(cause).strip() == "":
            continue
        durations = group["duration_mins"].dropna()
        if len(durations) < 5:
            # Too few samples — skip, will fall back to global median
            continue
        lookup[str(cause)] = {
            "median": round(float(np.median(durations)), 1),
            "p25": round(float(np.percentile(durations, 25)), 1),
            "p75": round(float(np.percentile(durations, 75)), 1),
            "count": int(len(durations)),
        }
        print(
            f"  {cause}: n={len(durations):,}  "
            f"median={lookup[cause]['median']}  "
            f"p25={lookup[cause]['p25']}  "
            f"p75={lookup[cause]['p75']}"
        )

    # Add global fallback
    global_dur = dur_df["duration_mins"].dropna()
    lookup["__default__"] = {
        "median": round(float(np.median(global_dur)), 1),
        "p25": round(float(np.percentile(global_dur, 25)), 1),
        "p75": round(float(np.percentile(global_dur, 75)), 1),
        "count": int(len(global_dur)),
    }
    print(
        f"\n  __default__ (global fallback): n={len(global_dur):,}  "
        f"median={lookup['__default__']['median']}"
    )

    return lookup


def main():
    print("=" * 60)
    print("GridSense — Step 5: Duration Lookup Table")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"[05_duration] ERROR: {CLEAN_CSV} not found. Run 01_ingest.py first.")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    df["duration_mins"] = pd.to_numeric(df["duration_mins"], errors="coerce")
    print(f"[05_duration] Loaded {len(df):,} rows")

    print("\n[05_duration] Computing duration statistics per event_cause …")
    lookup = build_duration_lookup(df)

    with open(OUT_JSON, "w") as f:
        json.dump(lookup, f, indent=2)

    print(f"\n[05_duration] Saved → {OUT_JSON}")
    print(f"[05_duration] Event causes in lookup: {len(lookup) - 1}")  # -1 for __default__
    print("\n[05_duration] ✅ Done.")


if __name__ == "__main__":
    main()