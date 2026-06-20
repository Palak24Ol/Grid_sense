"""
02_feature_engineer.py — Build feature matrix and fit LabelEncoders (v2).

v2 improvements:
  - Cyclical day-of-week encoding (dow_sin, dow_cos)
  - Rolling corridor event counts (corridor_events_4h, corridor_events_24h)
  - Rush hour flag (is_rush_hour)
  - Composite severity target (y_severity) for differentiated priority model
  - start_datetime passthrough for time-based train/test splitting

Inputs:
    data/processed/events_clean.csv

Outputs:
    data/processed/feature_matrix.csv    — model-ready feature set + targets
    ml/artifacts/encoders.pkl            — fitted LabelEncoders for cat columns

Run:
    python ml/pipeline/02_feature_engineer.py
"""

import sys
import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
OUT_FEATURES = ROOT / "data" / "processed" / "feature_matrix.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

CATEGORICAL_COLS = ["corridor", "event_cause", "vehicle_type", "police_station", "zone"]


def load_clean(path: Path) -> pd.DataFrame:
    print(f"[02_feature] Loading clean CSV from {path} …")
    df = pd.read_csv(path, low_memory=False)
    print(f"[02_feature] Rows: {len(df):,}")
    return df


def fit_encoders(df: pd.DataFrame) -> dict:
    """Fit one LabelEncoder per categorical column.

    Missing / null values are filled with '__MISSING__' before fitting
    so the encoder can represent them as a valid class.
    Unknown labels at inference time are handled by encode_input() → -1.
    """
    encoders = {}
    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            print(f"[02_feature] ⚠️  Column '{col}' not found — skipping encoder")
            continue
        le = LabelEncoder()
        values = df[col].fillna("__MISSING__").astype(str)
        le.fit(values)
        encoders[col] = le
        print(f"[02_feature]   {col}: {len(le.classes_)} classes")
    return encoders


def safe_transform(le: LabelEncoder, series: pd.Series) -> np.ndarray:
    """Transform with unseen label handling (maps to -1)."""
    known = set(le.classes_)
    result = np.array(
        [le.transform([v])[0] if v in known else -1 for v in series], dtype=int
    )
    return result


def compute_rolling_corridor_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Compute rolling event counts per corridor in the preceding 4h and 24h windows.

    Must be computed BEFORE train/test split to represent historical context,
    but each row only looks BACKWARDS (no future leakage).
    """
    print("[02_feature] Computing rolling corridor event counts ...")
    dt = pd.to_datetime(df["start_datetime"], format="mixed", utc=True, errors="coerce")

    counts_4h = np.zeros(len(df), dtype=int)
    counts_24h = np.zeros(len(df), dtype=int)

    # Sort by time for efficient computation
    sort_idx = dt.argsort()
    dt_sorted = dt.iloc[sort_idx].values
    corridor_sorted = df["corridor"].iloc[sort_idx].values

    # For each corridor, compute backward-looking counts
    from collections import defaultdict
    corridor_times = defaultdict(list)

    for pos, orig_idx in enumerate(sort_idx):
        corr = corridor_sorted[pos]
        current_time = dt_sorted[pos]
        if pd.isna(current_time) or pd.isna(corr):
            continue

        # Count events in same corridor within the lookback windows
        history = corridor_times[corr]
        c4 = 0
        c24 = 0
        for prev_time in reversed(history):
            diff_hours = (current_time - prev_time) / np.timedelta64(1, "h")
            if diff_hours > 24:
                break
            c24 += 1
            if diff_hours <= 4:
                c4 += 1

        counts_4h[orig_idx] = c4
        counts_24h[orig_idx] = c24
        history.append(current_time)

    print(f"[02_feature]   corridor_events_4h  — mean: {np.mean(counts_4h):.2f}  max: {np.max(counts_4h)}")
    print(f"[02_feature]   corridor_events_24h — mean: {np.mean(counts_24h):.2f}  max: {np.max(counts_24h)}")

    return pd.DataFrame(
        {"corridor_events_4h": counts_4h, "corridor_events_24h": counts_24h},
        index=df.index,
    )


def build_feature_matrix(df: pd.DataFrame, encoders: dict) -> pd.DataFrame:
    """Build the feature vector used by closure, severity, and duration models.

    v2 additions: dow_sin, dow_cos, corridor_events_4h, corridor_events_24h,
    is_rush_hour, y_severity (composite target).
    """
    feat = pd.DataFrame(index=df.index)

    # ── Categorical encoded ────────────────────────────────────────────────────
    for col in CATEGORICAL_COLS:
        out_col = f"{col}_encoded"
        if col in encoders:
            filled = df[col].fillna("__MISSING__").astype(str)
            feat[out_col] = safe_transform(encoders[col], filled)
        else:
            feat[out_col] = -1

    # ── Time features ──────────────────────────────────────────────────────────
    feat["hour_of_day"] = df["hour_of_day"].fillna(0).astype(int)
    feat["day_of_week"] = df["day_of_week"].fillna(0).astype(int)
    feat["month"] = df["month"].fillna(1).astype(int)

    # Cyclical hour encoding
    feat["hour_sin"] = np.sin(2 * np.pi * feat["hour_of_day"] / 24)
    feat["hour_cos"] = np.cos(2 * np.pi * feat["hour_of_day"] / 24)

    # Cyclical day-of-week encoding (fixes raw integer encoding)
    feat["dow_sin"] = np.sin(2 * np.pi * feat["day_of_week"] / 7)
    feat["dow_cos"] = np.cos(2 * np.pi * feat["day_of_week"] / 7)

    # Rush hour flag
    feat["is_rush_hour"] = feat["hour_of_day"].apply(
        lambda h: int(h in range(7, 11) or h in range(17, 21))
    )

    # ── Corridor flags ─────────────────────────────────────────────────────────
    feat["is_high_priority_corridor"] = (
        df["is_high_priority_corridor"].fillna(False).astype(int)
    )
    feat["is_non_corridor"] = df["is_non_corridor"].fillna(False).astype(int)

    # ── Missingness flags ──────────────────────────────────────────────────────
    feat["has_vehicle_type"] = df["vehicle_type"].notna().astype(int)
    feat["has_zone"] = df["zone"].notna().astype(int)

    # ── Rolling temporal features ──────────────────────────────────────────────
    rolling = compute_rolling_corridor_counts(df)
    feat["corridor_events_4h"] = rolling["corridor_events_4h"].values
    feat["corridor_events_24h"] = rolling["corridor_events_24h"].values

    # ── Target vectors ─────────────────────────────────────────────────────────
    feat["y_closure"] = df["requires_road_closure"].fillna(False).astype(int)
    feat["y_priority"] = (df["priority"].str.strip().str.lower() == "high").astype(int)

    # Duration target — only rows with valid duration
    feat["y_duration"] = pd.to_numeric(df["duration_mins"], errors="coerce")
    feat.loc[~feat["y_duration"].between(0, 5000), "y_duration"] = np.nan

    # Composite severity target — multi-signal (differentiates from y_closure)
    # severity = 0.4 * closure + 0.3 * long_duration + 0.3 * high_disruption_cause
    cause_median = df.groupby("event_cause")["duration_mins"].transform("median")
    duration_mins = pd.to_numeric(df["duration_mins"], errors="coerce")
    is_long_duration = (duration_mins > cause_median).fillna(False).astype(float)
    high_disruption_causes = {"accident", "public_event", "protest", "procession", "vip_movement"}
    is_high_disruption = df["event_cause"].isin(high_disruption_causes).astype(float)
    severity_score = (
        0.4 * feat["y_closure"].astype(float)
        + 0.3 * is_long_duration
        + 0.3 * is_high_disruption
    )
    feat["y_severity"] = (severity_score >= 0.35).astype(int)

    # ── Passthrough columns for reference ─────────────────────────────────────
    feat["id"] = df["id"].values
    feat["corridor"] = df["corridor"].values
    feat["event_cause"] = df["event_cause"].values
    feat["is_stale_active"] = df["is_stale_active"].fillna(False).astype(int)
    # start_datetime needed for time-based train/test splitting
    feat["start_datetime"] = df["start_datetime"].values

    return feat


def validate_features(feat: pd.DataFrame) -> None:
    print("\n[02_feature] ── Feature Matrix Summary ──")
    model_cols = [
        "corridor_encoded", "event_cause_encoded", "vehicle_type_encoded",
        "hour_of_day", "day_of_week", "month",
        "hour_sin", "hour_cos", "dow_sin", "dow_cos",
        "is_high_priority_corridor", "is_non_corridor",
        "has_vehicle_type", "has_zone",
        "is_rush_hour", "corridor_events_4h", "corridor_events_24h",
    ]
    for col in model_cols:
        null_pct = feat[col].isna().mean() * 100
        print(f"  {col}: min={feat[col].min():.2f}  max={feat[col].max():.2f}  null={null_pct:.1f}%")

    print(f"\n  y_closure  positives: {feat['y_closure'].sum():,} / {len(feat):,} "
          f"({feat['y_closure'].mean()*100:.1f}%)")
    print(f"  y_priority positives: {feat['y_priority'].sum():,} / {len(feat):,} "
          f"({feat['y_priority'].mean()*100:.1f}%)")
    print(f"  y_severity positives: {feat['y_severity'].sum():,} / {len(feat):,} "
          f"({feat['y_severity'].mean()*100:.1f}%)")
    valid_dur = feat["y_duration"].notna().sum()
    print(f"  y_duration valid rows: {valid_dur:,}")
    print("[02_feature] Validation ✓")


def main():
    print("=" * 60)
    print("GridSense — Step 2: Feature Engineering")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"[02_feature] ERROR: {CLEAN_CSV} not found. Run 01_ingest.py first.")
        sys.exit(1)

    df = load_clean(CLEAN_CSV)

    # Fit and save encoders
    print("\n[02_feature] Fitting LabelEncoders …")
    encoders = fit_encoders(df)
    encoder_path = ARTIFACT_DIR / "encoders.pkl"
    joblib.dump(encoders, encoder_path)
    print(f"[02_feature] Encoders saved → {encoder_path}")

    # Build feature matrix
    print("\n[02_feature] Building feature matrix …")
    feat = build_feature_matrix(df, encoders)
    validate_features(feat)

    feat.to_csv(OUT_FEATURES, index=False)
    print(f"\n[02_feature] Feature matrix saved → {OUT_FEATURES}")
    print(f"[02_feature] Shape: {feat.shape}")
    print("\n[02_feature] ✅ Done.")


if __name__ == "__main__":
    main()