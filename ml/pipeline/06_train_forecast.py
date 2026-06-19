"""
06_train_forecast.py — Train Prophet corridor forecasters v2.

Improvements over v1:
  1. Exogenous regressors: is_weekend, hour_bin (morning/evening peak flags)
     — these are the strongest patterns in Bengaluru traffic data
  2. Stronger changepoint_prior_scale (0.15 vs 0.1) for more flexibility
  3. Multiplicative seasonality mode — incident counts scale with corridor load
  4. Reports both training MAE AND SMAPE (scale-free %) for interpretability
  5. Saves evaluation summary to JSON for the backend to surface

Inputs:
    data/processed/events_clean.csv

Outputs:
    ml/artifacts/prophet_models/{CorridorName}.pkl  (one per corridor)
    ml/artifacts/forecast_eval.json

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

ROOT         = Path(__file__).parent.parent.parent
CLEAN_CSV    = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
PROPHET_DIR  = ARTIFACT_DIR / "prophet_models"
PROPHET_DIR.mkdir(parents=True, exist_ok=True)
OUT_EVAL     = ARTIFACT_DIR / "forecast_eval.json"

MIN_INCIDENTS = 50
HOLDOUT_DAYS  = 14
FORECAST_HRS  = 72

TARGET_CORRIDORS = [
    "Mysore Road", "Bellary Road 1", "Tumkur Road", "Bellary Road 2",
    "Hosur Road", "ORR North 1", "Old Madras Road", "Magadi Road",
    "ORR East 1", "ORR North 2", "Bannerghata Road", "ORR East 2",
]


def load_data(path: Path) -> pd.DataFrame:
    print(f"[06] Loading {path} …")
    df = pd.read_csv(path, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], format="mixed", utc=True, errors="coerce")
    df = df.dropna(subset=["start_datetime", "corridor"])
    df = df[df["is_stale_active"].astype(str).str.upper() != "TRUE"]
    df = df[df["corridor"] != "Non-corridor"]
    print(f"[06] Usable rows: {len(df):,}")
    return df


def build_hourly_series(df: pd.DataFrame, corridor: str) -> pd.DataFrame:
    sub  = df[df["corridor"] == corridor].copy()
    sub["hour"] = sub["start_datetime"].dt.floor("h")
    hourly = sub.groupby("hour").size().reset_index(name="y")
    hourly = hourly.rename(columns={"hour": "ds"})
    hourly["ds"] = hourly["ds"].dt.tz_localize(None)

    # Fill missing hours with 0
    full_range = pd.date_range(start=hourly["ds"].min(), end=hourly["ds"].max(), freq="h")
    hourly = (
        hourly.set_index("ds")
              .reindex(full_range, fill_value=0)
              .reset_index()
    )
    hourly.columns = ["ds", "y"]

    # Exogenous regressors — computed from the timestamp
    hourly["is_weekend"]     = (hourly["ds"].dt.dayofweek >= 5).astype(float)
    hourly["is_morning_peak"]= hourly["ds"].dt.hour.between(7, 10).astype(float)
    hourly["is_evening_peak"]= hourly["ds"].dt.hour.between(17, 20).astype(float)
    hourly["is_night"]       = (~hourly["ds"].dt.hour.between(6, 21)).astype(float)
    return hourly


def smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Symmetric Mean Absolute Percentage Error — scale-free."""
    denom = (np.abs(actual) + np.abs(predicted)) / 2
    mask  = denom > 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs(actual[mask] - predicted[mask]) / denom[mask]) * 100)


def train_prophet(hourly: pd.DataFrame, corridor: str):
    try:
        from prophet import Prophet
        import logging
        logging.getLogger("prophet").setLevel(logging.ERROR)
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
    except ImportError:
        print("  ERROR: prophet not installed.")
        return None, None, None

    if len(hourly) < 72:
        return None, None, None

    cutoff = hourly["ds"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train  = hourly[hourly["ds"] <= cutoff].copy()
    test   = hourly[hourly["ds"] >  cutoff].copy()

    if len(train) < 72:
        return None, None, None

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=0.8,
        changepoint_prior_scale=0.15,
        seasonality_prior_scale=12,
        seasonality_mode="multiplicative",
    )

    # Add exogenous regressors
    for reg in ["is_weekend", "is_morning_peak", "is_evening_peak", "is_night"]:
        model.add_regressor(reg)

    model.fit(train)

    mae, smape_val = None, None
    if len(test) > 0:
        future = test[["ds", "is_weekend", "is_morning_peak", "is_evening_peak", "is_night"]].copy()
        forecast = model.predict(future)
        preds    = forecast["yhat"].clip(lower=0).values[:len(test)]
        actuals  = test["y"].values
        mae      = float(np.mean(np.abs(preds - actuals)))
        smape_val= smape(actuals, preds)

    return model, mae, smape_val


def main():
    print("=" * 60)
    print("GridSense v2 — Train Prophet Corridor Forecasters")
    print("Enhancements: regressors (weekend, peak hours), multiplicative seasonality")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found.")
        sys.exit(1)

    df = load_data(CLEAN_CSV)

    results, failed = [], []

    for i, corridor in enumerate(TARGET_CORRIDORS):
        count = len(df[df["corridor"] == corridor])
        print(f"\n[{i+1}/{len(TARGET_CORRIDORS)}] {corridor} ({count} incidents)")

        if count < MIN_INCIDENTS:
            print(f"  Skipped (< {MIN_INCIDENTS} incidents)")
            failed.append(corridor)
            continue

        hourly = build_hourly_series(df, corridor)
        print(f"  Hourly rows: {len(hourly)}  mean/hr: {hourly['y'].mean():.3f}  max: {hourly['y'].max()}")

        model, mae, smape_val = train_prophet(hourly, corridor)
        if model is None:
            print("  Skipped (insufficient data)")
            failed.append(corridor)
            continue

        safe_name = corridor.replace("/", "_").replace(" ", "_")
        path = PROPHET_DIR / f"{safe_name}.pkl"
        joblib.dump({
            "model":           model,
            "corridor":        corridor,
            "level":           "corridor",
            "mae":             mae,
            "smape":           smape_val,
            "total_incidents": count,
            "regressors":      ["is_weekend", "is_morning_peak", "is_evening_peak", "is_night"],
            "version":         "v2",
        }, path)

        mae_str   = f"{mae:.3f}"   if mae   is not None else "n/a"
        smape_str = f"{smape_val:.1f}%" if smape_val is not None else "n/a"
        print(f"  Saved → {path.name}  MAE={mae_str}  SMAPE={smape_str}")
        results.append({"corridor": corridor, "mae": mae, "smape": smape_val, "incidents": count})

    # Summary
    print(f"\n{'─'*50}")
    print(f"Trained: {len(results)}  Failed/Skipped: {len(failed)}")
    if results:
        maes   = [r["mae"]   for r in results if r["mae"]   is not None]
        smapes = [r["smape"] for r in results if r["smape"] is not None]
        if maes:
            print(f"\n  MAE   — mean: {np.mean(maes):.3f}  min: {min(maes):.3f}  max: {max(maes):.3f}")
        if smapes:
            print(f"  SMAPE — mean: {np.mean(smapes):.1f}%  min: {min(smapes):.1f}%  max: {max(smapes):.1f}%")

    eval_out = {
        "version": "v2",
        "corridors": results,
        "mean_mae":   round(float(np.mean([r["mae"] for r in results if r["mae"] is not None])), 3),
        "mean_smape": round(float(np.mean([r["smape"] for r in results if r["smape"] is not None])), 1),
    }
    with open(OUT_EVAL, "w") as f:
        json.dump(eval_out, f, indent=2)
    print(f"\nEval summary → {OUT_EVAL}")
    print("\n✅ Done.")


if __name__ == "__main__":
    main()