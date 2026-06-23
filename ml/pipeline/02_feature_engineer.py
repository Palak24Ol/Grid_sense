"""
02_feature_engineer.py - Build feature matrix and fit LabelEncoders.

Inputs:
    data/processed/events_clean.csv

Outputs:
    data/processed/feature_matrix.csv    - model-ready feature set + targets
    ml/artifacts/encoders.pkl            - fitted LabelEncoders for cat columns

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
    print(f"[02_feature] Loading clean CSV from {path} ...")
    df = pd.read_csv(path, low_memory=False)
    print(f"[02_feature] Rows: {len(df):,}")
    return df


def fit_encoders(df: pd.DataFrame) -> dict:
    """Fit one LabelEncoder per categorical column.

    Missing / null values are filled with '__MISSING__' before fitting
    so the encoder can represent them as a valid class.
    Unknown labels at inference time are handled by encode_input() -> -1.
    """
    encoders = {}
    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            print(f"[02_feature] WARNING: Column '{col}' not found - skipping encoder")
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


def build_feature_matrix(df: pd.DataFrame, encoders: dict) -> pd.DataFrame:
    """Build the feature matrix used by downstream model scripts.

    Target-derived historical rate features are intentionally not calculated
    here. They are computed inside the training script with train-only,
    cross-fold target encoding to avoid leakage.
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
    feat["is_peak_hour"] = (
        feat["hour_of_day"].between(8, 10)
        | feat["hour_of_day"].between(17, 20)
    ).astype(int)
    feat["is_weekend"] = feat["day_of_week"].isin([5, 6]).astype(int)
    feat["is_night"] = (
        (feat["hour_of_day"] >= 22) | (feat["hour_of_day"] <= 5)
    ).astype(int)

    # Cyclical encoding
    feat["hour_sin"] = np.sin(2 * np.pi * feat["hour_of_day"] / 24)
    feat["hour_cos"] = np.cos(2 * np.pi * feat["hour_of_day"] / 24)

    # ── Corridor flags ─────────────────────────────────────────────────────────
    feat["is_high_priority_corridor"] = (
        df["is_high_priority_corridor"].fillna(False).astype(int)
    )
    feat["is_non_corridor"] = df["is_non_corridor"].fillna(False).astype(int)

    # ── Missingness flags ──────────────────────────────────────────────────────
    feat["has_vehicle_type"] = df["vehicle_type"].notna().astype(int)
    feat["has_zone"] = df["zone"].notna().astype(int)
    station_values = df["police_station"].fillna("__MISSING__").astype(str)
    station_load = station_values.value_counts().to_dict()
    feat["station_load"] = station_values.map(station_load).fillna(0).astype(int)

    # ── Target vectors ─────────────────────────────────────────────────────────
    feat["y_closure"] = df["requires_road_closure"].fillna(False).astype(int)
    feat["y_priority"] = (df["priority"].str.strip().str.lower() == "high").astype(int)

    # Duration target — only rows with valid duration
    feat["y_duration"] = pd.to_numeric(df["duration_mins"], errors="coerce")
    # Clip to valid range for duration training; set out-of-range to NaN
    feat.loc[~feat["y_duration"].between(0, 5000), "y_duration"] = np.nan

    # ── Passthrough columns for reference ─────────────────────────────────────
    feat["id"] = df["id"].values
    feat["corridor"] = df["corridor"].values
    feat["event_cause"] = df["event_cause"].values
    feat["priority"] = df["priority"].values
    event_cause = df["event_cause"].fillna("__MISSING__").astype(str)
    corridor = df["corridor"].fillna("__MISSING__").astype(str)
    priority = df["priority"].fillna("__MISSING__").astype(str)
    police_station = df["police_station"].fillna("__MISSING__").astype(str)
    feat["cause_corridor_key"] = event_cause + "_" + corridor
    feat["cause_priority_key"] = event_cause + "_" + priority
    feat["cause_station_key"] = event_cause + "_" + police_station
    feat["police_station"] = police_station
    feat["zone"] = df["zone"].fillna("__MISSING__").astype(str)
    feat["is_stale_active"] = df["is_stale_active"].fillna(False).astype(int)

    return feat


def validate_features(feat: pd.DataFrame) -> None:
    print("\n[02_feature] -- Feature Matrix Summary --")
    model_cols = [
        "corridor_encoded", "event_cause_encoded", "vehicle_type_encoded",
        "police_station_encoded", "zone_encoded",
        "hour_of_day", "day_of_week", "month",
        "hour_sin", "hour_cos", "is_peak_hour", "is_weekend", "is_night",
        "is_high_priority_corridor", "is_non_corridor",
        "has_vehicle_type", "has_zone", "station_load",
    ]
    for col in model_cols:
        null_pct = feat[col].isna().mean() * 100
        print(f"  {col}: min={feat[col].min():.2f}  max={feat[col].max():.2f}  null={null_pct:.1f}%")

    print(f"\n  y_closure  positives: {feat['y_closure'].sum():,} / {len(feat):,} "
          f"({feat['y_closure'].mean()*100:.1f}%)")
    print(f"  y_priority positives: {feat['y_priority'].sum():,} / {len(feat):,} "
          f"({feat['y_priority'].mean()*100:.1f}%)")
    valid_dur = feat["y_duration"].notna().sum()
    print(f"  y_duration valid rows: {valid_dur:,}")
    print("[02_feature] Validation OK")


def main():
    print("=" * 60)
    print("GridSense - Step 2: Feature Engineering")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"[02_feature] ERROR: {CLEAN_CSV} not found. Run 01_ingest.py first.")
        sys.exit(1)

    df = load_clean(CLEAN_CSV)

    # Fit and save encoders
    print("\n[02_feature] Fitting LabelEncoders ...")
    encoders = fit_encoders(df)
    encoder_path = ARTIFACT_DIR / "encoders.pkl"
    joblib.dump(encoders, encoder_path)
    print(f"[02_feature] Encoders saved -> {encoder_path}")

    # Build feature matrix
    print("\n[02_feature] Building feature matrix ...")
    feat = build_feature_matrix(df, encoders)
    validate_features(feat)

    feat.to_csv(OUT_FEATURES, index=False)
    print(f"\n[02_feature] Feature matrix saved -> {OUT_FEATURES}")
    print(f"[02_feature] Shape: {feat.shape}")
    print("\n[02_feature] Done.")


if __name__ == "__main__":
    main()
