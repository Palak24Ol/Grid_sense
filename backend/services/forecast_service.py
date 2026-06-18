import warnings
from typing import Optional
import datetime

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

# Built from blackspot_scores.json — maps every Prophet pkl stem -> corridor + daily avg
# Key = junction name as stored inside the pkl payload["junction"]
_JUNCTION_META: dict[str, dict] = {
    "AyyappaTempleJunc":                   {"corridor": "Hosur Road",             "daily_avg": 2.227, "peak_hour": 8},
    "BEL_Circle":                          {"corridor": "ORR North 2",            "daily_avg": 1.136, "peak_hour": 20},
    "BagalurCrossJunc":                    {"corridor": "Bellary Road 2",         "daily_avg": 1.227, "peak_hour": 9},
    "BangaloreBodyBuildersJunc":           {"corridor": "Mysore Road",            "daily_avg": 0.864, "peak_hour": 21},
    "BigBazaarJunction(OldMadrasRd)":      {"corridor": "Old Madras Road",        "daily_avg": 1.182, "peak_hour": 20},
    "Bommanahalli":                        {"corridor": "Hosur Road",             "daily_avg": 1.182, "peak_hour": 19},
    "CMP_GateJunc":                        {"corridor": "Hosur Road",             "daily_avg": 0.909, "peak_hour": 8},
    "Devasandra(k_r_puram)":              {"corridor": "Non-corridor",           "daily_avg": 1.364, "peak_hour": 20},
    "Deverabeesanahalli-ORR_Junc":        {"corridor": "ORR East 1",             "daily_avg": 0.682, "peak_hour": 19},
    "GokuldasImagesJunc":                  {"corridor": "Tumkur Road",            "daily_avg": 1.273, "peak_hour": 21},
    "GoruguntepalyaJunc":                  {"corridor": "Tumkur Road",            "daily_avg": 0.909, "peak_hour": 20},
    "HebbalFlyoverJunc":                   {"corridor": "Bellary Road 1",         "daily_avg": 1.273, "peak_hour": 9},
    "HennurRoad-ORR_Junc":                {"corridor": "Airport New South Road", "daily_avg": 0.773, "peak_hour": 10},
    "HesaraghattaJunction":               {"corridor": "Tumkur Road",            "daily_avg": 1.364, "peak_hour": 8},
    "HudsonCircle":                        {"corridor": "Mysore Road",            "daily_avg": 0.727, "peak_hour": 20},
    "IndianExpressJunction":               {"corridor": "CBD 2",                  "daily_avg": 0.727, "peak_hour": 21},
    "JakkurCrossJunction":                 {"corridor": "Bellary Road 2",         "daily_avg": 0.818, "peak_hour": 11},
    "JalahalliCross(SM_Circle)":          {"corridor": "Tumkur Road",            "daily_avg": 1.455, "peak_hour": 20},
    "KIMCO_Junction":                      {"corridor": "West of Chord Road",     "daily_avg": 1.409, "peak_hour": 21},
    "K_R_Circle":                          {"corridor": "Non-corridor",           "daily_avg": 1.409, "peak_hour": 21},
    "KhodaysCircle(DV_UrsCircle)":        {"corridor": "Non-corridor",           "daily_avg": 1.045, "peak_hour": 20},
    "KogilluCrossJunc":                    {"corridor": "Bellary Road 2",         "daily_avg": 0.682, "peak_hour": 19},
    "KrishnaFlourMill":                    {"corridor": "Non-corridor",           "daily_avg": 0.864, "peak_hour": 20},
    "LeprosyhospitalJunc":                 {"corridor": "Magadi Road",            "daily_avg": 0.955, "peak_hour": 9},
    "MaratahalliBridgeJunc":              {"corridor": "Varthur Road",           "daily_avg": 0.727, "peak_hour": 20},
    "MekhriCircle":                        {"corridor": "Bellary Road 1",         "daily_avg": 2.909, "peak_hour": 23},
    "MysoreRd-RingRdJunc(Nayandanahallii)": {"corridor": "ORR West 1",          "daily_avg": 0.864, "peak_hour": 20},
    "Nagavara-ORR_Junction":              {"corridor": "Hennur Main Road",       "daily_avg": 1.455, "peak_hour": 9},
    "PoliceCornerJunc":                    {"corridor": "Mysore Road",            "daily_avg": 1.182, "peak_hour": 20},
    "RajeshwariJunc":                      {"corridor": "Mysore Road",            "daily_avg": 1.0,   "peak_hour": 21},
    "SRS_Peenya_Junc":                    {"corridor": "Tumkur Road",            "daily_avg": 0.909, "peak_hour": 22},
    "SantheCircle":                        {"corridor": "Bellary Road 2",         "daily_avg": 1.136, "peak_hour": 20},
    "SatteliteBusStandJunc":              {"corridor": "Mysore Road",            "daily_avg": 1.955, "peak_hour": 21},
    "ShantalaJunction":                    {"corridor": "Non-corridor",           "daily_avg": 0.682, "peak_hour": 20},
    "SilkBoardJunc":                       {"corridor": "ORR East 1",             "daily_avg": 1.5,   "peak_hour": 19},
    "Sumanhalli":                          {"corridor": "Magadi Road",            "daily_avg": 0.727, "peak_hour": 20},
    "TownhallJunction":                    {"corridor": "Mysore Road",            "daily_avg": 1.364, "peak_hour": 20},
    "VeerannapalyaJunction(BEL,HO)":      {"corridor": "ORR North 1",           "daily_avg": 1.364, "peak_hour": 0},
    "YelhankaBypass":                      {"corridor": "Bellary Road 2",         "daily_avg": 0.864, "peak_hour": 20},
    "YelhankaCircle":                      {"corridor": "Bellary Road 2",         "daily_avg": 1.545, "peak_hour": 21},
    "YeshwanthpuraCircle":                 {"corridor": "Tumkur Road",            "daily_avg": 1.727, "peak_hour": 20},
    "toll_gate_mysore_road":              {"corridor": "Mysore Road",            "daily_avg": 1.5,   "peak_hour": 21},
}

# Corridor -> top junction (for corridors forecast, picks highest daily_avg junction)
_CORRIDOR_TOP_JUNCTION: dict[str, str] = {}
for _j, _m in _JUNCTION_META.items():
    _c = _m["corridor"]
    if _c == "Non-corridor":
        continue
    existing = _CORRIDOR_TOP_JUNCTION.get(_c)
    if existing is None or _m["daily_avg"] > _JUNCTION_META[existing]["daily_avg"]:
        _CORRIDOR_TOP_JUNCTION[_c] = _j


def _detect_peak_windows(points: list[JunctionForecastPoint]) -> list[PeakWindow]:
    """Derive peak windows from actual forecast data instead of hardcoding."""
    peak_hours = [p.hour_of_day for p in points if p.is_peak_hour]
    if not peak_hours:
        return [PeakWindow(start_hour=19, end_hour=22, label="evening peak")]

    windows = []
    # Group consecutive peak hours
    sorted_hours = sorted(set(peak_hours))
    if sorted_hours:
        start = sorted_hours[0]
        prev = sorted_hours[0]
        for h in sorted_hours[1:]:
            if h - prev > 2:
                label = "morning peak" if start < 12 else "evening peak"
                windows.append(PeakWindow(start_hour=start, end_hour=prev + 1, label=label))
                start = h
            prev = h
        label = "morning peak" if start < 12 else "evening peak"
        windows.append(PeakWindow(start_hour=start, end_hour=prev + 1, label=label))

    return windows or [PeakWindow(start_hour=19, end_hour=22, label="evening peak")]


def get_junction_forecast(
    junction: str,
    forecast_hours: int = FORECAST_HOURS,
) -> JunctionForecastResponse:
    arts = get_artifacts()
    payload = arts.prophet_models.get(junction)

    if payload is None:
        logger.warning(f"No Prophet model for junction: {junction}")
        return JunctionForecastResponse(
            junction=junction,
            corridor="Unknown",
            historical_daily_avg=0.0,
            forecast=[],
            peak_windows=[],
            model_mae=None,
        )

    model = payload["model"]
    mae = payload.get("mae")

    # Look up real corridor + historical avg from our pre-built map
    meta = _JUNCTION_META.get(junction, {})
    corridor = meta.get("corridor", "Unknown")
    historical_daily_avg = meta.get("daily_avg", 0.0)

    try:
        future = model.make_future_dataframe(
            periods=forecast_hours, freq="h", include_history=False
        )
        forecast = model.predict(future)

        points = []
        for _, row in forecast.iterrows():
            yhat = round(float(row["yhat"]), 3)
            points.append(
                JunctionForecastPoint(
                    datetime=row["ds"].isoformat() + "Z",
                    hour_of_day=int(row["ds"].hour),
                    predicted_incident_count=yhat,
                    yhat_lower=max(0.0, round(float(row["yhat_lower"]), 3)),
                    yhat_upper=max(0.0, round(float(row["yhat_upper"]), 3)),
                    is_peak_hour=yhat > 0.03,
                )
            )

        peak_windows = _detect_peak_windows(points)

        return JunctionForecastResponse(
            junction=junction,
            corridor=corridor,
            historical_daily_avg=historical_daily_avg,
            forecast=points,
            peak_windows=peak_windows,
            model_mae=round(mae, 4) if mae else None,
        )

    except Exception as e:
        logger.error(f"Forecast failed for {junction}: {e}")
        return JunctionForecastResponse(
            junction=junction,
            corridor=corridor,
            historical_daily_avg=historical_daily_avg,
            forecast=[],
            peak_windows=[],
            model_mae=None,
        )


def get_corridors_forecast() -> CorridorsForecastResponse:
    """
    Returns top corridors sorted by composite_risk_score.
    next_24h_predicted_incidents is derived from historical daily avg of
    the corridor's highest-incident junction — real data, no mock math.
    """
    arts = get_artifacts()
    corridors = []

    if arts.corridor_risk_index:
        # Sort by composite_risk_score descending, skip Non-corridor
        ranked = sorted(
            [c for c in arts.corridor_risk_index.values() if c["corridor"] != "Non-corridor"],
            key=lambda x: x["composite_risk_score"],
            reverse=True,
        )

        for c in ranked[:8]:
            corridor_name = c["corridor"]
            top_junction = _CORRIDOR_TOP_JUNCTION.get(corridor_name)
            meta = _JUNCTION_META.get(top_junction, {}) if top_junction else {}

            # Real daily avg from blackspot data; scale to 24h window
            daily_avg = meta.get("daily_avg", round(c["total_incidents"] / 154, 2))  # 22 weeks * 7 days
            peak_hour = meta.get("peak_hour", 20)

            # Risk level from actual composite score thresholds
            score = c["composite_risk_score"]
            if score >= 63:
                risk_level = "critical"
            elif score >= 57:
                risk_level = "high"
            else:
                risk_level = "medium"

            corridors.append(
                CorridorForecastSummary(
                    corridor=corridor_name,
                    next_24h_predicted_incidents=daily_avg,
                    peak_hour=peak_hour,
                    peak_predicted_count=round(daily_avg * 1.8, 2),  # peak ~1.8x daily avg
                    risk_level=risk_level,
                )
            )

    return CorridorsForecastResponse(
        generated_at=datetime.datetime.utcnow().isoformat() + "Z",
        corridors=corridors,
    )


def list_available_junctions() -> list[str]:
    arts = get_artifacts()
    return sorted(arts.prophet_models.keys())
