"""
forecast_service.py — Corridor-level Prophet forecasting.

Models are trained on hourly incident counts per corridor (not junction),
giving 235–735 incidents per series and real visible daily/weekly peaks.
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

# Corridor → peak_hour derived from blackspot_scores.json
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

# pkl filename stem → corridor name
def _pkl_stem(corridor: str) -> str:
    return corridor.replace("/", "_").replace("\\", "_").replace(" ", "_")

def _detect_peak_windows(points: list[JunctionForecastPoint]) -> list[PeakWindow]:
    peak_hours = sorted({p.hour_of_day for p in points if p.is_peak_hour})
    if not peak_hours:
        return [PeakWindow(start_hour=19, end_hour=22, label="evening peak")]

    windows = []
    start = prev = peak_hours[0]
    for h in peak_hours[1:]:
        if h - prev > 2:
            label = "morning peak" if start < 12 else "evening peak"
            windows.append(PeakWindow(start_hour=start, end_hour=prev + 1, label=label))
            start = h
        prev = h
    label = "morning peak" if start < 12 else "evening peak"
    windows.append(PeakWindow(start_hour=start, end_hour=prev + 1, label=label))
    return windows


def get_junction_forecast(
    junction: str,
    forecast_hours: int = FORECAST_HOURS,
) -> JunctionForecastResponse:
    """
    `junction` param now accepts either a corridor name (new) or a junction
    name (legacy). Corridor names are tried first against the new pkl stems.
    """
    arts = get_artifacts()

    # Try corridor-level model first (new)
    stem = _pkl_stem(junction)
    payload = arts.prophet_models.get(stem) or arts.prophet_models.get(junction)

    if payload is None:
        logger.warning(f"No Prophet model for: {junction}")
        return JunctionForecastResponse(
            junction=junction, corridor="Unknown",
            historical_daily_avg=0.0, forecast=[],
            peak_windows=[], model_mae=None,
        )

    model = payload["model"]
    mae   = payload.get("mae")
    # corridor field in new pkls; fallback for old junction pkls
    corridor = payload.get("corridor", junction)
    meta     = _CORRIDOR_META.get(corridor, {})
    daily_avg = meta.get("daily_avg", 0.0)

    try:
        future   = model.make_future_dataframe(periods=forecast_hours, freq="h", include_history=False)
        forecast = model.predict(future)

        # Dynamic peak threshold: mean + 0.5*std of this specific forecast
        yhat_vals = forecast["yhat"].clip(lower=0)
        peak_threshold = float(yhat_vals.mean() + 0.5 * yhat_vals.std())
        peak_threshold = max(peak_threshold, 0.05)  # floor so flat models still show some peaks

        points = []
        for _, row in forecast.iterrows():
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
    """Top corridors by composite risk score with 24h incident prediction."""
    arts = get_artifacts()
    corridors = []

    if arts.corridor_risk_index:
        ranked = sorted(
            [c for c in arts.corridor_risk_index.values() if c["corridor"] != "Non-corridor"],
            key=lambda x: x["composite_risk_score"],
            reverse=True,
        )
        for c in ranked[:8]:
            name  = c["corridor"]
            meta  = _CORRIDOR_META.get(name, {})
            score = c["composite_risk_score"]

            if score >= 63:   risk_level = "critical"
            elif score >= 57: risk_level = "high"
            else:             risk_level = "medium"

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


def list_available_junctions() -> list[str]:
    """Returns corridor names (new) for the dropdown."""
    arts = get_artifacts()
    names = []
    for key, payload in arts.prophet_models.items():
        # Prefer the human-readable corridor name stored inside the pkl
        corridor = payload.get("corridor", key)
        names.append(corridor)
    return sorted(set(names))
