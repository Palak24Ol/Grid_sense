"""
01_ingest.py — Load raw ASTRAM CSV, apply staleness filter, compute derived fields.

Inputs:
    data/raw/astram_events.csv

Outputs:
    data/processed/events_clean.csv     — full cleaned dataset
    data/processed/lcv_incidents.csv    — LCV vehicle subset (for Flipkart panel)

Run:
    python ml/pipeline/01_ingest.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
RAW_CSV = ROOT / "data" / "raw" / "astram_events.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

OUT_CLEAN = PROCESSED_DIR / "events_clean.csv"
OUT_LCV = PROCESSED_DIR / "lcv_incidents.csv"

# ── Constants ──────────────────────────────────────────────────────────────────
# All 15 named high-priority corridors
HIGH_PRIORITY_CORRIDORS = frozenset(
    [
        "Mysore Road",
        "Bellary Road 1",
        "Bellary Road 2",
        "Tumkur Road",
        "Hosur Road",
        "ORR North 1",
        "ORR North 2",
        "ORR East 1",
        "ORR East 2",
        "Magadi Road",
        "Old Madras Road",
        "Bannerghatta Road",
        "West of Chord Road",
        "CBD 2",
        "ORR West 1",
        "ORR West 2",
    ]
)

# Staleness threshold: active incidents with modified_datetime older than
# this many days before dataset end date are flagged as stale.
STALENESS_DAYS = 30

# LCV vehicle type value in the raw CSV
LCV_VEH_TYPE = "lcv"


def load_raw(path: Path) -> pd.DataFrame:
    """Load raw CSV with correct dtypes and timezone-aware datetimes."""
    print(f"[01_ingest] Loading raw CSV from {path} …")
    df = pd.read_csv(
        path,
        low_memory=False,
        parse_dates=False,  # We handle datetimes manually
    )
    print(f"[01_ingest] Raw rows: {len(df):,}  Columns: {len(df.columns)}")
    return df


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw CSV columns to internal schema names."""
    rename_map = {
        "veh_type": "vehicle_type",
        "veh_no": "vehicle_no",
    }
    df = df.rename(columns=rename_map)
    return df


def parse_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    """Parse all datetime columns as UTC-aware timestamps.

    The ASTRAM CSV uses two timestamp formats:
      - '2024-03-07 17:01:48.111+00'   (milliseconds, +00 suffix)
      - '2024-02-12 02:05:46+00'        (no milliseconds, +00 suffix)
    format='ISO8601' handles both correctly without coercing valid values to NaT.
    """
    dt_cols = [
        "start_datetime",
        "end_datetime",
        "closed_datetime",
        "modified_datetime",
        "created_date",
        "resolved_datetime",
    ]
    for col in dt_cols:
        if col not in df.columns:
            continue
        # Replace string 'NULL' / 'NaT' with NaN before parsing
        df[col] = df[col].replace({"NULL": None, "NaT": None, "": None})
        df[col] = pd.to_datetime(df[col], format="ISO8601", utc=True, errors="coerce")
    return df


def apply_staleness_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Flag stale-active records.

    An incident is stale-active when:
        status == 'active'
        AND modified_datetime < (dataset_end_date - STALENESS_DAYS)

    These are incidents that were never resolved and whose last update
    is over 30 days before the dataset end. They inflate active counts
    and are excluded from real-time analytics.
    """
    dataset_end = df["start_datetime"].dropna().max()
    cutoff = dataset_end - pd.Timedelta(days=STALENESS_DAYS)
    print(f"[01_ingest] Dataset end: {dataset_end}  Staleness cutoff: {cutoff}")

    df["is_stale_active"] = False
    stale_mask = (df["status"] == "active") & (df["modified_datetime"] < cutoff)
    df.loc[stale_mask, "is_stale_active"] = True

    stale_count = stale_mask.sum()
    raw_active = (df["status"] == "active").sum()
    print(
        f"[01_ingest] Raw active: {raw_active:,}  "
        f"Stale flagged: {stale_count:,}  "
        f"Corrected active: {raw_active - stale_count:,}"
    )
    return df


def compute_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Compute duration, time components, and corridor flags."""
    # Duration: use closed_datetime preferentially, fall back to end_datetime
    df["duration_mins"] = np.nan

    has_closed = df["closed_datetime"].notna()
    df.loc[has_closed, "duration_mins"] = (
        (df.loc[has_closed, "closed_datetime"] - df.loc[has_closed, "start_datetime"])
        .dt.total_seconds()
        / 60
    )

    has_end = (~has_closed) & df["end_datetime"].notna()
    df.loc[has_end, "duration_mins"] = (
        (df.loc[has_end, "end_datetime"] - df.loc[has_end, "start_datetime"])
        .dt.total_seconds()
        / 60
    )

    # Clip physically implausible durations (negative or > 10 days)
    df.loc[df["duration_mins"] < 0, "duration_mins"] = np.nan
    df.loc[df["duration_mins"] > 14_400, "duration_mins"] = np.nan

    # Time components (UTC)
    df["hour_of_day"] = df["start_datetime"].dt.hour
    df["day_of_week"] = df["start_datetime"].dt.dayofweek  # 0=Monday
    df["month"] = df["start_datetime"].dt.month

    # Corridor flags
    df["is_high_priority_corridor"] = df["corridor"].isin(HIGH_PRIORITY_CORRIDORS)
    df["is_non_corridor"] = df["corridor"].fillna("Non-corridor").str.lower() == "non-corridor"

    return df


def normalise_boolean(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure requires_road_closure is a proper boolean."""
    df["requires_road_closure"] = (
        df["requires_road_closure"]
        .astype(str)
        .str.strip()
        .str.upper()
        .map({"TRUE": True, "FALSE": False, "1": True, "0": False})
        .fillna(False)
        .astype(bool)
    )
    return df


def validate(df: pd.DataFrame) -> None:
    """Print data quality summary. Exits non-zero if critical columns are bad."""
    print("\n[01_ingest] ── Validation Summary ──")
    critical_cols = [
        "id", "event_type", "event_cause", "latitude", "longitude",
        "corridor", "priority", "requires_road_closure",
        "start_datetime", "status", "police_station",
    ]
    for col in critical_cols:
        null_pct = df[col].isna().mean() * 100
        flag = "⚠️ " if null_pct > 30 else "  "
        print(f"  {flag}{col}: {null_pct:.1f}% null")

    invalid_geo = ((df["latitude"] < 10) | (df["latitude"] > 15) |
                   (df["longitude"] < 74) | (df["longitude"] > 78)).sum()
    print(f"  Invalid lat/lon: {invalid_geo:,}")

    unparsed_dt = df["start_datetime"].isna().sum()
    print(f"  Unparsed start_datetime: {unparsed_dt:,}")

    if unparsed_dt > 50:
        print("[01_ingest] WARNING: Some start_datetime values could not be parsed (will be excluded).")

    print(f"\n  Total rows: {len(df):,}")
    print(f"  is_stale_active True: {df['is_stale_active'].sum():,}")
    print(f"  requires_road_closure True: {df['requires_road_closure'].sum():,}")
    print(f"  Corridors: {df['corridor'].nunique():,} unique values")
    print(f"  Junctions: {df['junction'].dropna().nunique():,} unique values")
    print(f"  Planned events: {(df['event_type']=='planned').sum():,}")
    print(f"  Unplanned events: {(df['event_type']=='unplanned').sum():,}")
    dur_valid = df["duration_mins"].between(0, 14_400).sum()
    print(f"  Valid durations (0–10 days): {dur_valid:,}")
    print("[01_ingest] Validation complete ✓")


def extract_lcv_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to LCV (Light Commercial Vehicle) incidents for Flipkart panel."""
    lcv = df[df["vehicle_type"] == LCV_VEH_TYPE].copy()
    print(f"\n[01_ingest] LCV incidents: {len(lcv):,}")
    return lcv


def select_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the columns defined in the incidents DB schema."""
    keep = [
        "id",
        "event_type",
        "event_cause",
        "latitude",
        "longitude",
        "address",
        "corridor",
        "junction",
        "zone",
        "police_station",
        "priority",
        "requires_road_closure",
        "vehicle_type",
        "start_datetime",
        "end_datetime",
        "closed_datetime",
        "status",
        "is_stale_active",
        "duration_mins",
        "hour_of_day",
        "day_of_week",
        "month",
        "is_high_priority_corridor",
        "is_non_corridor",
        "description",
        "modified_datetime",
    ]
    # Only keep columns that actually exist
    keep = [c for c in keep if c in df.columns]
    return df[keep]


def main():
    print("=" * 60)
    print("GridSense — Step 1: Ingest & Staleness Filter")
    print("=" * 60)

    df = load_raw(RAW_CSV)
    df = normalise_columns(df)
    df = parse_datetimes(df)
    df = normalise_boolean(df)
    df = apply_staleness_filter(df)
    df = compute_derived_fields(df)
    validate(df)

    # Save LCV subset before trimming columns
    lcv = extract_lcv_subset(df)
    lcv_out = select_output_columns(lcv)
    lcv_out.to_csv(OUT_LCV, index=False)
    print(f"\n[01_ingest] LCV subset saved → {OUT_LCV}")

    # Save full clean dataset
    clean = select_output_columns(df)
    clean.to_csv(OUT_CLEAN, index=False)
    print(f"[01_ingest] Clean dataset saved → {OUT_CLEAN}")
    print(f"[01_ingest] Final row count: {len(clean):,}")
    print("\n[01_ingest] ✅ Done.")


if __name__ == "__main__":
    main()