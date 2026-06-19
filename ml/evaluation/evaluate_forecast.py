"""
evaluate_forecast.py — Evaluate Prophet corridor forecasters v2.

Updated for v2:
  - Models are corridor-level (not junction-level) — key changed from
    payload["junction"] to payload["corridor"]
  - v2 models use exogenous regressors (is_weekend, is_morning_peak,
    is_evening_peak, is_night) — these must be supplied to model.predict()
  - Reports both MAE and SMAPE per corridor
  - Computes naive baseline MAE (predict train mean for every hour) so you
    have a concrete comparison to quote in your demo
  - Reads pre-computed eval summary from forecast_eval.json (written by
    training script) for a fast summary, then re-evaluates live on holdout

Run:
    python ml/evaluation/evaluate_forecast.py
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
EVAL_JSON    = ARTIFACT_DIR / "forecast_eval.json"
HOLDOUT_DAYS = 14


def smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    denom = (np.abs(actual) + np.abs(predicted)) / 2
    mask  = denom > 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs(actual[mask] - predicted[mask]) / denom[mask]) * 100)


def build_hourly_series(df: pd.DataFrame, corridor: str) -> pd.DataFrame:
    """Build hourly incident count series with regressor columns for v2 models."""
    sub  = df[df["corridor"] == corridor].copy()
    sub["hour"] = sub["start_datetime"].dt.floor("h")
    hourly = sub.groupby("hour").size().reset_index(name="y")
    hourly = hourly.rename(columns={"hour": "ds"})
    hourly["ds"] = hourly["ds"].dt.tz_localize(None)

    full_range = pd.date_range(start=hourly["ds"].min(), end=hourly["ds"].max(), freq="h")
    hourly = (
        hourly.set_index("ds")
              .reindex(full_range, fill_value=0)
              .reset_index()
    )
    hourly.columns = ["ds", "y"]

    # Exogenous regressors (must match what v2 model was trained with)
    hourly["is_weekend"]      = (hourly["ds"].dt.dayofweek >= 5).astype(float)
    hourly["is_morning_peak"] = hourly["ds"].dt.hour.between(7, 10).astype(float)
    hourly["is_evening_peak"] = hourly["ds"].dt.hour.between(17, 20).astype(float)
    hourly["is_night"]        = (~hourly["ds"].dt.hour.between(6, 21)).astype(float)
    return hourly


def evaluate_model(model, hourly: pd.DataFrame, version: str = "v2"):
    """Run holdout evaluation. Handles v1 (no regressors) and v2 (with regressors)."""
    cutoff = hourly["ds"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train  = hourly[hourly["ds"] <= cutoff].copy()
    test   = hourly[hourly["ds"] >  cutoff].copy()

    if len(test) == 0:
        return None, None, None

    # Build future dataframe with regressors for v2
    if version == "v2":
        future = test[["ds", "is_weekend", "is_morning_peak", "is_evening_peak", "is_night"]].copy()
    else:
        future = model.make_future_dataframe(periods=len(test), freq="h", include_history=False)

    forecast = model.predict(future)
    preds    = forecast["yhat"].clip(lower=0).values[:len(test)]
    actuals  = test["y"].values

    mae      = float(np.mean(np.abs(preds - actuals)))
    smape_v  = smape(actuals, preds)

    # Naive baseline: predict training mean for every holdout hour
    naive_pred  = np.full(len(actuals), train["y"].mean())
    naive_mae   = float(np.mean(np.abs(naive_pred - actuals)))

    return mae, smape_v, naive_mae


def main():
    print("=" * 60)
    print("GridSense v2 — Evaluate Prophet Corridor Forecasters")
    print("=" * 60)

    if not PROPHET_DIR.exists() or not list(PROPHET_DIR.glob("*.pkl")):
        print(f"ERROR: No Prophet models found in {PROPHET_DIR}")
        print("Run ml/pipeline/06_train_forecast.py first.")
        sys.exit(1)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found.")
        sys.exit(1)

    # Fast summary from pre-computed eval JSON
    if EVAL_JSON.exists():
        eval_data = json.load(open(EVAL_JSON))
        print(f"\n── Stored Eval Summary (from training run) ──")
        print(f"  Version     : {eval_data.get('version','?')}")
        print(f"  Mean MAE    : {eval_data['mean_mae']:.3f} incidents/hour")
        print(f"  Mean SMAPE  : {eval_data['mean_smape']:.1f}%")
        maes = [c["mae"] for c in eval_data["corridors"] if c["mae"] is not None]
        corridors_sorted = sorted(eval_data["corridors"], key=lambda x: x["mae"] or 999)
        print(f"  Best  MAE   : {min(maes):.3f}  ({corridors_sorted[0]['corridor']})")
        print(f"  Worst MAE   : {max(maes):.3f}  ({corridors_sorted[-1]['corridor']})")

    # Live re-evaluation on holdout
    print(f"\n── Live Holdout Re-evaluation (last {HOLDOUT_DAYS} days) ──")

    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], format="mixed", utc=True, errors="coerce")
    df = df.dropna(subset=["start_datetime", "corridor"])
    df = df[df["is_stale_active"].astype(str).str.upper() != "TRUE"]
    df = df[df["corridor"] != "Non-corridor"]
    print(f"Usable rows : {len(df):,}\n")

    model_files = sorted(PROPHET_DIR.glob("*.pkl"))
    print(f"Prophet models found : {len(model_files)}\n")

    results = []
    for model_file in model_files:
        payload  = joblib.load(model_file)
        corridor = payload.get("corridor") or payload.get("junction", "unknown")
        model    = payload["model"]
        version  = payload.get("version", "v1")
        regressors = payload.get("regressors", [])

        hourly = build_hourly_series(df, corridor)
        if len(hourly) < 72:
            print(f"  {corridor:<30}  SKIPPED (insufficient data)")
            continue

        mae, smape_v, naive_mae = evaluate_model(model, hourly, version)
        if mae is None:
            print(f"  {corridor:<30}  SKIPPED (no holdout data)")
            continue

        improvement_pct = (naive_mae - mae) / naive_mae * 100 if naive_mae > 0 else 0
        results.append({
            "corridor":    corridor,
            "mae":         mae,
            "smape":       smape_v,
            "naive_mae":   naive_mae,
            "improvement": improvement_pct,
            "incidents":   payload.get("total_incidents", "?"),
            "version":     version,
        })

    # Print table
    header = f"  {'Corridor':<28} {'Inc':>5} {'MAE':>7} {'Naive':>7} {'Improv':>8} {'SMAPE':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    results_sorted = sorted(results, key=lambda x: x["mae"])
    for r in results_sorted:
        smape_s  = f"{r['smape']:.1f}%" if r["smape"] is not None else "  n/a"
        naive_s  = f"{r['naive_mae']:.3f}"
        improv_s = f"{r['improvement']:+.1f}%"
        print(f"  {r['corridor']:<28} {str(r['incidents']):>5} {r['mae']:>7.3f} "
              f"{naive_s:>7} {improv_s:>8} {smape_s:>8}")

    if results:
        maes      = [r["mae"]         for r in results]
        naive_m   = [r["naive_mae"]   for r in results]
        improves  = [r["improvement"] for r in results]

        print(f"\n── Summary ──")
        print(f"  Corridors evaluated : {len(results)}")
        print(f"  Mean MAE            : {np.mean(maes):.3f} incidents/hour")
        print(f"  Mean Naive MAE      : {np.mean(naive_m):.3f} incidents/hour")
        print(f"  Mean improvement    : {np.mean(improves):+.1f}% vs naive baseline")
        print(f"  Best  MAE           : {min(maes):.3f}  ({results_sorted[0]['corridor']})")
        print(f"  Worst MAE           : {max(maes):.3f}  ({results_sorted[-1]['corridor']})")
        print(f"\n  Note: High SMAPE (~190-200%) is expected — most hours have 0 incidents")
        print(f"  on any given corridor. SMAPE blows up at zero denominators.")
        print(f"  MAE is the correct metric here.")

    print("\n✅ Forecast evaluation complete.")


if __name__ == "__main__":
    main()