"""
06_train_forecast.py — Train Facebook Prophet for top junctions.

One model per junction with >= 15 incidents.
Aggregates incident data to hourly counts and fits Prophet with
daily + weekly seasonality.

Inputs:
    data/processed/events_clean.csv

Outputs:
    ml/artifacts/prophet_models/{JunctionName}.pkl  (one per junction)

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

ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
PROPHET_DIR = ARTIFACT_DIR / "prophet_models"
PROPHET_DIR.mkdir(parents=True, exist_ok=True)

MIN_INCIDENTS = 15  # Minimum incidents for a junction to get a model
HOLDOUT_DAYS = 14   # Days held out for MAE evaluation
FORECAST_HOURS = 72


def load_data(path: Path) -> pd.DataFrame:
    print(f"[06_forecast] Loading data from {path} …")
    df = pd.read_csv(path, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], format="ISO8601", utc=True, errors="coerce")
    df = df.dropna(subset=["start_datetime", "junction"])
    df = df[df["is_stale_active"].astype(str).str.upper() != "TRUE"]
    print(f"[06_forecast] Usable rows: {len(df):,}")
    return df


def get_target_junctions(df: pd.DataFrame) -> list[str]:
    """Return junctions with >= MIN_INCIDENTS, sorted by count descending."""
    counts = df["junction"].value_counts()
    target = counts[counts >= MIN_INCIDENTS].index.tolist()
    print(f"[06_forecast] Junctions with >= {MIN_INCIDENTS} incidents: {len(target)}")
    for j in target[:5]:
        print(f"  {j}: {counts[j]} incidents")
    return target


def build_hourly_series(df: pd.DataFrame, junction: str) -> pd.DataFrame:
    """Aggregate incidents at a junction to hourly counts."""
    jdf = df[df["junction"] == junction].copy()
    # Floor to hour
    jdf["hour"] = jdf["start_datetime"].dt.floor("h")
    hourly = jdf.groupby("hour").size().reset_index(name="y")
    hourly = hourly.rename(columns={"hour": "ds"})
    hourly["ds"] = hourly["ds"].dt.tz_localize(None)  # Prophet requires tz-naive

    # Fill missing hours with 0 between first and last incident
    if len(hourly) < 2:
        return hourly

    full_range = pd.date_range(
        start=hourly["ds"].min(),
        end=hourly["ds"].max(),
        freq="h",
    )
    hourly = hourly.set_index("ds").reindex(full_range, fill_value=0).reset_index()
    hourly.columns = ["ds", "y"]
    return hourly


def train_prophet_model(hourly: pd.DataFrame, junction: str):
    """Fit Prophet model. Returns (model, mae) or (None, None) on failure."""
    try:
        from prophet import Prophet
    except ImportError:
        print("  [WARNING] prophet not installed. Skipping.")
        return None, None

    if len(hourly) < 48:
        return None, None

    # Hold out last HOLDOUT_DAYS for evaluation
    cutoff = hourly["ds"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train = hourly[hourly["ds"] <= cutoff].copy()
    test = hourly[hourly["ds"] > cutoff].copy()

    if len(train) < 24:
        return None, None

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=0.8,
        changepoint_prior_scale=0.05,
    )

    # Suppress Prophet output
    import logging
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    model.fit(train)

    # Evaluate on holdout
    mae = None
    if len(test) > 0:
        future = model.make_future_dataframe(
            periods=len(test), freq="h", include_history=False
        )
        forecast = model.predict(future)
        preds = forecast["yhat"].clip(lower=0).values[: len(test)]
        actuals = test["y"].values
        mae = float(np.mean(np.abs(preds - actuals)))

    return model, mae


def save_model(model, junction: str, mae: float | None) -> None:
    """Serialise model to pkl. Sanitise junction name for filesystem."""
    # Replace characters that are invalid in filenames
    safe_name = junction.replace("/", "_").replace("\\", "_").replace(" ", "_")
    path = PROPHET_DIR / f"{safe_name}.pkl"
    payload = {
        "model": model,
        "junction": junction,
        "mae": mae,
    }
    joblib.dump(payload, path)
    return path


def main():
    print("=" * 60)
    print("GridSense — Step 6: Train Prophet Junction Forecasters")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"[06_forecast] ERROR: {CLEAN_CSV} not found. Run 01_ingest.py first.")
        sys.exit(1)

    df = load_data(CLEAN_CSV)
    target_junctions = get_target_junctions(df)

    results = []
    failed = []

    for i, junction in enumerate(target_junctions):
        print(f"\n[06_forecast] [{i+1}/{len(target_junctions)}] {junction} …")
        hourly = build_hourly_series(df, junction)
        print(f"  Hourly rows: {len(hourly)}  Total incidents: {hourly['y'].sum()}")

        model, mae = train_prophet_model(hourly, junction)

        if model is None:
            print(f"  ⚠️  Skipped (insufficient data)")
            failed.append(junction)
            continue

        path = save_model(model, junction, mae)
        mae_str = f"{mae:.3f}" if mae is not None else "n/a"
        print(f"  ✅ Saved → {path.name}  MAE={mae_str}")
        results.append({"junction": junction, "mae": mae})

    print(f"\n[06_forecast] ── Summary ──")
    print(f"  Trained: {len(results)}  Failed/Skipped: {len(failed)}")

    if results:
        maes = [r["mae"] for r in results if r["mae"] is not None]
        if maes:
            print(f"  Avg MAE: {np.mean(maes):.3f}  Min: {min(maes):.3f}  Max: {max(maes):.3f}")

    if failed:
        print(f"  Skipped junctions: {failed[:5]}")

    print(f"\n[06_forecast] Prophet models saved to: {PROPHET_DIR}")
    print(f"[06_forecast] Model files: {len(list(PROPHET_DIR.glob('*.pkl')))}")
    print("\n[06_forecast] ✅ Done.")


if __name__ == "__main__":
    main()