"""
evaluate_forecast.py — Evaluate Prophet junction forecasters.

Prints MAE per junction on the held-out last 14 days.

Run:
    python ml/evaluation/evaluate_forecast.py
"""

import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
PROPHET_DIR = ROOT / "ml" / "artifacts" / "prophet_models"
HOLDOUT_DAYS = 14


def load_hourly_for_junction(df: pd.DataFrame, junction: str) -> pd.DataFrame:
    jdf = df[df["junction"] == junction].copy()
    jdf["hour"] = jdf["start_datetime"].dt.floor("h")
    hourly = jdf.groupby("hour").size().reset_index(name="y")
    hourly = hourly.rename(columns={"hour": "ds"})
    hourly["ds"] = hourly["ds"].dt.tz_localize(None)
    return hourly


def main():
    print("=" * 60)
    print("GridSense — Evaluate Prophet Forecasters")
    print("=" * 60)

    if not PROPHET_DIR.exists() or not list(PROPHET_DIR.glob("*.pkl")):
        print(f"ERROR: No Prophet models found in {PROPHET_DIR}")
        print("Run ml/pipeline/06_train_forecast.py first.")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], format="ISO8601", utc=True, errors="coerce")
    df = df.dropna(subset=["start_datetime", "junction"])
    df = df[df["is_stale_active"].astype(str).str.upper() != "TRUE"]

    model_files = sorted(PROPHET_DIR.glob("*.pkl"))
    print(f"Prophet models found: {len(model_files)}")

    results = []
    for model_file in model_files:
        payload = joblib.load(model_file)
        junction = payload["junction"]
        model = payload["model"]
        stored_mae = payload.get("mae")

        hourly = load_hourly_for_junction(df, junction)
        if len(hourly) < 24:
            continue

        cutoff = hourly["ds"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
        test = hourly[hourly["ds"] > cutoff].copy()

        if len(test) == 0:
            print(f"  {junction}: no holdout data")
            continue

        future = model.make_future_dataframe(periods=len(test), freq="h", include_history=False)
        forecast = model.predict(future)
        preds = forecast["yhat"].clip(lower=0).values[: len(test)]
        actuals = test["y"].values
        mae = float(np.mean(np.abs(preds - actuals)))

        results.append({"junction": junction, "mae": mae, "stored_mae": stored_mae, "n_test": len(test)})

    # Print results sorted by MAE
    results.sort(key=lambda x: x["mae"])
    print(f"\n{'Junction':<40} {'MAE':>8}  {'N Test':>8}")
    print("-" * 60)
    for r in results:
        print(f"  {r['junction']:<38} {r['mae']:>8.3f}  {r['n_test']:>8}")

    if results:
        maes = [r["mae"] for r in results]
        print(f"\n  Mean MAE: {np.mean(maes):.3f}")
        print(f"  Median MAE: {np.median(maes):.3f}")
        print(f"  Max MAE: {max(maes):.3f}")

    print("\n✅ Forecast evaluation complete.")


if __name__ == "__main__":
    main()