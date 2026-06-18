"""
06_train_forecast.py — Train Facebook Prophet per CORRIDOR (not junction).

Corridor-level aggregation gives 298–743 incidents per series vs 15-64 for
junctions. This produces visible daily/weekly peaks in the 72-hour forecast
instead of near-zero flat lines.

Inputs:
    data/processed/events_clean.csv

Outputs:
    ml/artifacts/prophet_models/{CorridorName}.pkl  (one per corridor)

Run:
    python ml/pipeline/06_train_forecast.py
"""

import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT        = Path(__file__).parent.parent.parent
CLEAN_CSV   = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR= ROOT / "ml" / "artifacts"
PROPHET_DIR = ARTIFACT_DIR / "prophet_models"
PROPHET_DIR.mkdir(parents=True, exist_ok=True)

MIN_INCIDENTS = 50   # corridor must have >= 50 incidents
HOLDOUT_DAYS  = 14
FORECAST_HOURS= 72

# Top corridors by incident count — these are the ones worth modelling
TARGET_CORRIDORS = [
    "Mysore Road",
    "Bellary Road 1",
    "Tumkur Road",
    "Bellary Road 2",
    "Hosur Road",
    "ORR North 1",
    "Old Madras Road",
    "Magadi Road",
    "ORR East 1",
    "ORR North 2",
    "Bannerghata Road",
    "ORR East 2",
]


def load_data(path: Path) -> pd.DataFrame:
    print(f"[06_forecast] Loading {path} …")
    df = pd.read_csv(path, low_memory=False)
    df["start_datetime"] = pd.to_datetime(
        df["start_datetime"], format="mixed", utc=True, errors="coerce"
    )
    df = df.dropna(subset=["start_datetime", "corridor"])
    df = df[df["is_stale_active"].astype(str).str.upper() != "TRUE"]
    df = df[df["corridor"] != "Non-corridor"]
    print(f"[06_forecast] Usable rows: {len(df):,}")
    return df


def build_hourly_series(df: pd.DataFrame, corridor: str) -> pd.DataFrame:
    """Aggregate all incidents on a corridor to hourly counts."""
    sub = df[df["corridor"] == corridor].copy()
    sub["hour"] = sub["start_datetime"].dt.floor("h")
    hourly = sub.groupby("hour").size().reset_index(name="y")
    hourly = hourly.rename(columns={"hour": "ds"})
    hourly["ds"] = hourly["ds"].dt.tz_localize(None)  # Prophet needs tz-naive

    if len(hourly) < 2:
        return hourly

    # Fill missing hours with 0 so Prophet sees a continuous series
    full_range = pd.date_range(
        start=hourly["ds"].min(),
        end=hourly["ds"].max(),
        freq="h",
    )
    hourly = (
        hourly.set_index("ds")
              .reindex(full_range, fill_value=0)
              .reset_index()
    )
    hourly.columns = ["ds", "y"]
    return hourly


def train_prophet_model(hourly: pd.DataFrame, corridor: str):
    """Fit Prophet. Returns (model, mae) or (None, None)."""
    try:
        from prophet import Prophet
    except ImportError:
        print("  [WARNING] prophet not installed.")
        return None, None

    if len(hourly) < 48:
        return None, None

    cutoff = hourly["ds"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train  = hourly[hourly["ds"] <= cutoff].copy()
    test   = hourly[hourly["ds"] >  cutoff].copy()

    if len(train) < 48:
        return None, None

    import logging
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=0.8,
        changepoint_prior_scale=0.1,   # slightly more flexible than junction models
        seasonality_mode="additive",
    )
    model.fit(train)

    mae = None
    if len(test) > 0:
        future   = model.make_future_dataframe(periods=len(test), freq="h", include_history=False)
        forecast = model.predict(future)
        preds    = forecast["yhat"].clip(lower=0).values[: len(test)]
        actuals  = test["y"].values
        mae      = float(np.mean(np.abs(preds - actuals)))

    return model, mae


def save_model(model, corridor: str, mae, total_incidents: int) -> Path:
    safe_name = corridor.replace("/", "_").replace("\\", "_").replace(" ", "_")
    path = PROPHET_DIR / f"{safe_name}.pkl"
    joblib.dump({
        "model":           model,
        "corridor":        corridor,
        "level":           "corridor",   # ← marks this as corridor-level
        "mae":             mae,
        "total_incidents": total_incidents,
    }, path)
    return path


def main():
    print("=" * 60)
    print("GridSense — Step 6: Train Prophet CORRIDOR Forecasters")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found. Run 01_ingest.py first.")
        sys.exit(1)

    df = load_data(CLEAN_CSV)

    results, failed = [], []

    for i, corridor in enumerate(TARGET_CORRIDORS):
        count = len(df[df["corridor"] == corridor])
        if count < MIN_INCIDENTS:
            print(f"\n[{i+1}/{len(TARGET_CORRIDORS)}] {corridor} — skipped ({count} incidents)")
            failed.append(corridor)
            continue

        print(f"\n[{i+1}/{len(TARGET_CORRIDORS)}] {corridor} ({count} incidents) …")
        hourly = build_hourly_series(df, corridor)
        print(f"  Hourly rows: {len(hourly)}  Max in 1h: {hourly['y'].max()}  Mean: {hourly['y'].mean():.3f}")

        model, mae = train_prophet_model(hourly, corridor)
        if model is None:
            print("  Skipped (insufficient data)")
            failed.append(corridor)
            continue

        path = save_model(model, corridor, mae, count)
        mae_str = f"{mae:.3f}" if mae is not None else "n/a"
        print(f"  Saved -> {path.name}  MAE={mae_str}")
        results.append({"corridor": corridor, "mae": mae, "incidents": count})

    print(f"\n── Summary ──")
    print(f"  Trained: {len(results)}  Failed/Skipped: {len(failed)}")
    if results:
        maes = [r["mae"] for r in results if r["mae"] is not None]
        if maes:
            print(f"  Avg MAE: {np.mean(maes):.3f}  Min: {min(maes):.3f}  Max: {max(maes):.3f}")
    print(f"\nDone. Models saved to: {PROPHET_DIR}")


if __name__ == "__main__":
    main()