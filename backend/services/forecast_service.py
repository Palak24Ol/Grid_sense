"""
forecast_service.py — Corridor-level Prophet forecasting.
Models use extra regressors: is_weekend, is_morning_peak, is_evening_peak, is_night.
Must add these to future dataframe before calling model.predict().
"""
import warnings
import datetime
from typing import Optional

import pandas as pd

from backend.schemas.forecast import (
    JunctionForecastResponse,
    JunctionForecastPoint,
    PeakWindow,
    CorridorsForecastResponse,
    CorridorForecastSummary,
)
from backend.services.artifact_loader import get_artifacts
from backend.core.logging import get_logger

warnings.filterwarnings("ignore")
logger = get_logger(__name__)

FORECAST_HOURS = 72

_CORRIDOR_META: dict[str, dict] = {
    "Mysore Road":            {"peak_hour": 20, "daily_avg": 2.909},
    "Bellary Road 1":         {"peak_hour": 23, "daily_avg": 2.227},
    "Tumkur Road":            {"peak_hour": 20, "daily_avg": 1.727},
    "Bellary Road 2":         {"peak_hour": 21, "daily_avg": 1.545},
    "Hosur Road":             {"peak_hour": 19, "daily_avg": 1.182},
    "ORR North 1":            {"peak_hour": 0,  "daily_avg": 1.364},
    "Old Madras Road":        {"peak_hour": 20, "daily_avg": 1.182},
    "Magadi Road":            {"peak_hour": 9,  "daily_avg": 0.955},
    "ORR East 1":             {"peak_hour": 19, "daily_avg": 1.500},
    "ORR North 2":            {"peak_hour": 20, "daily_avg": 1.136},
    "Bannerghata Road":       {"peak_hour": 19, "daily_avg": 1.000},
    "ORR East 2":             {"peak_hour": 19, "daily_avg": 0.727},
    "West of Chord Road":     {"peak_hour": 21, "daily_avg": 1.409},
    "ORR West 1":             {"peak_hour": 20, "daily_avg": 0.864},
    "Hennur Main Road":       {"peak_hour": 9,  "daily_avg": 1.455},
    "Airport New South Road": {"peak_hour": 10, "daily_avg": 0.773},
    "Old Airport Road":       {"peak_hour": 20, "daily_avg": 1.152},
    "Varthur Road":           {"peak_hour": 20, "daily_avg": 0.727},
    "CBD 2":                  {"peak_hour": 21, "daily_avg": 0.727},
    "CBD 1":                  {"peak_hour": 21, "daily_avg": 0.727},
    "IRR(Thanisandra road)":  {"peak_hour": 9,  "daily_avg": 1.267},
}


def _add_regressors(future: "pd.DataFrame") -> "pd.DataFrame":
    """Add all extra regressors the corridor models were trained with."""
    hour = future["ds"].dt.hour
    future["hour_of_day"]     = hour
    future["is_weekend"]      = future["ds"].dt.dayofweek.isin([5, 6]).astype(int)
    future["is_morning_peak"] = hour.isin(range(7, 11)).astype(int)
    future["is_evening_peak"] = hour.isin(range(17, 22)).astype(int)
    future["is_night"]        = hour.isin(list(range(0, 5)) + [23]).astype(int)
    return future


def _detect_peak_windows(points: list) -> list:
    peak_hours = sorted({p.hour_of_day for p in points if p.is_peak_hour})
    if not peak_hours:
        return [PeakWindow(start_hour=19, end_hour=22, label="evening peak")]
    windows, start, prev = [], peak_hours[0], peak_hours[0]
    for h in peak_hours[1:]:
        if h - prev > 2:
            windows.append(PeakWindow(
                start_hour=start, end_hour=prev + 1,
                label="morning peak" if start < 12 else "evening peak"
            ))
            start = h
        prev = h
    windows.append(PeakWindow(
        start_hour=start, end_hour=prev + 1,
        label="morning peak" if start < 12 else "evening peak"
    ))
    return windows


def _pkl_stem(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def get_junction_forecast(
    junction: str,
    forecast_hours: int = FORECAST_HOURS,
) -> JunctionForecastResponse:
    """
    `junction` param accepts corridor names (e.g. "Mysore Road").
    Looks up the corridor-level pkl, adds regressors, runs Prophet.
    """
    arts = get_artifacts()
    stem = _pkl_stem(junction)
    payload = arts.prophet_models.get(stem) or arts.prophet_models.get(junction)

    if payload is None:
        logger.warning(f"No Prophet model found for: {junction}")
        return JunctionForecastResponse(
            junction=junction, corridor="Unknown",
            historical_daily_avg=0.0, forecast=[],
            peak_windows=[], model_mae=None,
        )

    model    = payload["model"]
    mae      = payload.get("mae")
    corridor = payload.get("corridor", junction)
    meta     = _CORRIDOR_META.get(corridor, {})
    daily_avg = meta.get("daily_avg", 0.0)

    try:
        future = model.make_future_dataframe(periods=forecast_hours, freq="h", include_history=False)
        future = _add_regressors(future)
        fc     = model.predict(future)

        yhat_vals = fc["yhat"].clip(lower=0)
        peak_threshold = float(yhat_vals.mean() + 0.5 * yhat_vals.std())
        peak_threshold = max(peak_threshold, 0.03)

        points = []
        for _, row in fc.iterrows():
            yhat = max(0.0, round(float(row["yhat"]), 4))
            points.append(JunctionForecastPoint(
                datetime=row["ds"].isoformat() + "Z",
                hour_of_day=row["ds"].hour,
                predicted_incident_count=yhat,
                yhat_lower=max(0.0, round(float(row["yhat_lower"]), 4)),
                yhat_upper=max(0.0, round(float(row["yhat_upper"]), 4)),
                is_peak_hour=float(row["yhat"]) > peak_threshold,
            ))

        return JunctionForecastResponse(
            junction=corridor,
            corridor=corridor,
            historical_daily_avg=daily_avg,
            forecast=points,
            peak_windows=_detect_peak_windows(points),
            model_mae=round(mae, 4) if mae else None,
        )

    except Exception as e:
        logger.error(f"Forecast failed for {junction}: {e}")
        return JunctionForecastResponse(
            junction=junction, corridor=corridor,
            historical_daily_avg=daily_avg, forecast=[],
            peak_windows=[], model_mae=None,
        )


def get_corridors_forecast() -> CorridorsForecastResponse:
    arts = get_artifacts()
    corridors = []
    if arts.corridor_risk_index:
        ranked = sorted(
            [c for c in arts.corridor_risk_index.values() if c["corridor"] != "Non-corridor"],
            key=lambda x: x["composite_risk_score"], reverse=True,
        )
        for c in ranked[:8]:
            name  = c["corridor"]
            meta  = _CORRIDOR_META.get(name, {})
            score = c["composite_risk_score"]
            risk_level = "critical" if score >= 63 else "high" if score >= 57 else "medium"
            corridors.append(CorridorForecastSummary(
                corridor=name,
                next_24h_predicted_incidents=meta.get("daily_avg", round(c["total_incidents"] / 154, 2)),
                peak_hour=meta.get("peak_hour", 20),
                peak_predicted_count=round(meta.get("daily_avg", 1.0) * 1.8, 2),
                risk_level=risk_level,
            ))
    return CorridorsForecastResponse(
        generated_at=datetime.datetime.utcnow().isoformat() + "Z",
        corridors=corridors,
    )


def list_available_junctions() -> list:
    arts = get_artifacts()
    names = []
    for key, payload in arts.prophet_models.items():
        corridor = payload.get("corridor", key)
        names.append(corridor)
    return sorted(set(names))
