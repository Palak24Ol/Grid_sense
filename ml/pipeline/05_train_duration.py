"""
05_train_duration.py — Train Duration Predictor (XGBoost Regressor) + lookup fallback.

Upgraded from v1 (pure median lookup) to v2 (ML model with lookup fallback).

Model predicts log(duration_mins + 1) to handle right-skewed distribution.
Lookup table kept as fallback for unseen categories and comparison baseline.

Inputs:
    data/processed/events_clean.csv
    ml/artifacts/encoders.pkl

Outputs:
    ml/artifacts/duration_model.pkl
    ml/artifacts/duration_lookup.json     (statistical fallback)
    ml/artifacts/duration_meta.json

Run:
    python ml/pipeline/05_train_duration.py
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, median_absolute_error
from xgboost import XGBRegressor

ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MODEL = ARTIFACT_DIR / "duration_model.pkl"
OUT_LOOKUP = ARTIFACT_DIR / "duration_lookup.json"
OUT_META = ARTIFACT_DIR / "duration_meta.json"

VALID_DURATION_MIN = 1
VALID_DURATION_MAX = 5000

FEATURE_COLS = [
    "event_cause_encoded", "corridor_encoded", "vehicle_type_encoded",
    "hour_of_day", "day_of_week", "month",
    "is_high_priority_corridor", "is_rush_hour",
]

XGBOOST_PARAMS = {
    "n_estimators": 300,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "random_state": 42,
    "verbosity": 0,
    "n_jobs": -1,
}


def build_duration_lookup(df: pd.DataFrame) -> dict:
    """Compute median, p25, p75 duration per event_cause (fallback table)."""
    dur_df = df[df["duration_mins"].between(VALID_DURATION_MIN, VALID_DURATION_MAX)].copy()
    print(f"[05_duration] Valid duration rows for lookup: {len(dur_df):,} / {len(df):,}")

    lookup = {}
    for cause, group in dur_df.groupby("event_cause"):
        if pd.isna(cause) or str(cause).strip() == "":
            continue
        durations = group["duration_mins"].dropna()
        if len(durations) < 5:
            continue
        lookup[str(cause)] = {
            "median": round(float(np.median(durations)), 1),
            "p25": round(float(np.percentile(durations, 25)), 1),
            "p75": round(float(np.percentile(durations, 75)), 1),
            "count": int(len(durations)),
        }

    global_dur = dur_df["duration_mins"].dropna()
    lookup["__default__"] = {
        "median": round(float(np.median(global_dur)), 1),
        "p25": round(float(np.percentile(global_dur, 25)), 1),
        "p75": round(float(np.percentile(global_dur, 75)), 1),
        "count": int(len(global_dur)),
    }
    return lookup


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build feature columns for duration model."""
    encoders = joblib.load(ARTIFACT_DIR / "encoders.pkl")

    def safe_encode(le, series):
        known = set(le.classes_)
        return np.array(
            [le.transform([v])[0] if v in known else -1 for v in series], dtype=int
        )

    feat = pd.DataFrame(index=df.index)
    for col in ["event_cause", "corridor", "vehicle_type"]:
        filled = df[col].fillna("__MISSING__").astype(str)
        le = encoders.get(col)
        feat[f"{col}_encoded"] = safe_encode(le, filled) if le else -1

    feat["hour_of_day"] = df["hour_of_day"].fillna(0).astype(int)
    feat["day_of_week"] = df["day_of_week"].fillna(0).astype(int)
    feat["month"] = df["month"].fillna(1).astype(int)
    feat["is_high_priority_corridor"] = df["is_high_priority_corridor"].fillna(False).astype(int)
    feat["is_rush_hour"] = df["hour_of_day"].apply(
        lambda h: int(h in range(7, 11) or h in range(17, 21))
    ).fillna(0).astype(int)

    return feat


def main():
    print("=" * 60)
    print("GridSense v2 — Step 5: Duration Model (XGBoost Regressor + Lookup)")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"[05_duration] ERROR: {CLEAN_CSV} not found. Run 01_ingest.py first.")
        sys.exit(1)

    if not (ARTIFACT_DIR / "encoders.pkl").exists():
        print("[05_duration] ERROR: encoders.pkl not found. Run 02_feature_engineer.py first.")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], format="mixed", utc=True, errors="coerce")
    df["duration_mins"] = pd.to_numeric(df["duration_mins"], errors="coerce")
    print(f"[05_duration] Loaded {len(df):,} rows")

    # ── Build and save lookup table (fallback) ─────────────────────────────
    print("\n[05_duration] Building lookup table (statistical fallback) ...")
    lookup = build_duration_lookup(df)
    with open(OUT_LOOKUP, "w") as f:
        json.dump(lookup, f, indent=2)
    print(f"[05_duration] Lookup saved -> {OUT_LOOKUP} ({len(lookup) - 1} causes)")

    # ── Filter to valid training data ──────────────────────────────────────
    train_df = df[
        (df["status"].isin(["closed", "resolved"]))
        & (df["duration_mins"].between(VALID_DURATION_MIN, VALID_DURATION_MAX))
        & (df["start_datetime"].notna())
    ].copy()
    train_df = train_df.sort_values("start_datetime").reset_index(drop=True)
    print(f"\n[05_duration] Training data (closed/resolved, valid duration): {len(train_df):,} rows")

    if len(train_df) < 100:
        print("[05_duration] WARNING: Too few valid records for ML model. Keeping lookup only.")
        sys.exit(0)

    # ── Build features ─────────────────────────────────────────────────────
    feat = build_features(train_df)
    y = np.log1p(train_df["duration_mins"].values)  # Log-transform

    # ── Time-based split ───────────────────────────────────────────────────
    n = len(feat)
    split_point = int(n * 0.8)
    X_train = feat[FEATURE_COLS].iloc[:split_point]
    y_train = y[:split_point]
    X_test = feat[FEATURE_COLS].iloc[split_point:]
    y_test = y[split_point:]
    y_test_raw = train_df["duration_mins"].values[split_point:]

    print(f"  Train: {len(X_train):,}  Test: {len(X_test):,}")

    # ── Train XGBoost Regressor ────────────────────────────────────────────
    print("\n[05_duration] Training XGBoost Regressor on log(duration) ...")
    model = XGBRegressor(**XGBOOST_PARAMS)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    # ── Evaluate ───────────────────────────────────────────────────────────
    preds_log = model.predict(X_test)
    preds = np.expm1(preds_log)  # Inverse log-transform
    preds = np.clip(preds, 0, VALID_DURATION_MAX)

    mae = mean_absolute_error(y_test_raw, preds)
    medae = median_absolute_error(y_test_raw, preds)

    # Lookup-table baseline: predict cause-specific median
    lookup_preds = []
    for _, row in train_df.iloc[split_point:].iterrows():
        cause = row["event_cause"]
        entry = lookup.get(cause, lookup.get("__default__", {"median": 45.0}))
        lookup_preds.append(entry["median"])
    lookup_preds = np.array(lookup_preds)
    lookup_mae = mean_absolute_error(y_test_raw, lookup_preds)
    lookup_medae = median_absolute_error(y_test_raw, lookup_preds)

    print(f"\n{'=' * 50}")
    print(f"  XGBoost MAE:    {mae:.1f} mins")
    print(f"  XGBoost MedAE:  {medae:.1f} mins")
    print(f"  Lookup MAE:     {lookup_mae:.1f} mins (baseline)")
    print(f"  Lookup MedAE:   {lookup_medae:.1f} mins (baseline)")
    improvement = (lookup_mae - mae) / lookup_mae * 100
    print(f"  Improvement:    {improvement:+.1f}% MAE vs lookup baseline")

    # ── Feature importances ────────────────────────────────────────────────
    print("\n── Feature Importances ──")
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for feat_name, imp in feat_imp:
        bar = "█" * int(imp * 80)
        print(f"  {feat_name:<35} {imp:.4f}  {bar}")

    # ── Save model + meta ──────────────────────────────────────────────────
    joblib.dump(model, OUT_MODEL)
    meta = {
        "feature_cols": FEATURE_COLS,
        "target": "log1p(duration_mins)",
        "mae": round(mae, 1),
        "medae": round(medae, 1),
        "lookup_mae": round(lookup_mae, 1),
        "improvement_pct": round(improvement, 1),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "version": "v2",
        "split_method": "time_based",
    }
    with open(OUT_META, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nModel saved -> {OUT_MODEL} ({OUT_MODEL.stat().st_size / 1024:.1f} KB)")
    print(f"Meta saved  -> {OUT_META}")
    print(f"Lookup saved -> {OUT_LOOKUP}")
    print("\n✅ Done.")


if __name__ == "__main__":
    main()