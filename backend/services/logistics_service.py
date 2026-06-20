"""
logistics_service.py — LCV (Light Commercial Vehicle) corridor risk panel.

Replaces the old `flipkart.py` route, which returned hardcoded Python dicts
that LOOKED live (a `generated_at: utcnow()` timestamp on numbers that never
changed) but were actually a one-time snapshot that had already drifted from
the real data — e.g. it claimed a "5.6x surge, 28 incidents" for the March 7
2024 weather event, when the dataset's actual LCV incident count for that
day is 6 (≈1.4x the per-day baseline). See README "Known Limitations" for
the full note on this.

Everything below is computed from data/processed/lcv_incidents.csv on every
request. The dataset is ~650 rows, so a full groupby is sub-millisecond —
there's no reason to cache a wrong answer for the sake of "performance".

The only hand-curated (non-computed) content is `_CORRIDOR_HUBS`: real
named industrial/distribution hubs along each corridor. That's genuine
domain knowledge, not a statistic, so it can't be derived from the CSV —
it's kept separate and clearly labeled so it's never confused with the
computed numbers around it.
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from backend.config import get_settings
from backend.services.deployment_service import DIVERSION_MAP
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Curated domain knowledge — NOT derived from the dataset (the CSV has no
# "distribution hub" column). Limited to corridors with enough LCV volume
# (>=15 incidents) for the hub context to be meaningfully actionable.
_CORRIDOR_HUBS: Dict[str, List[str]] = {
    "Tumkur Road":     ["Peenya Industrial Area", "Nelamangala Hub"],
    "Bellary Road 1":  ["Hebbal Distribution Centre", "Manyata Tech Park"],
    "Mysore Road":     ["Kengeri Hub", "Rajarajeshwari Nagar"],
    "ORR North 2":     ["Yelahanka Sorting Centre"],
    "Bellary Road 2":  ["Yelahanka Cross Hub"],
}


def _lcv_csv_path() -> Path:
    settings = get_settings()
    # data/processed sits alongside ml/artifacts at the project root
    return settings.artifact_path.parent.parent / "data" / "processed" / "lcv_incidents.csv"


def _load_lcv_df() -> pd.DataFrame | None:
    path = _lcv_csv_path()
    if not path.exists():
        logger.warning(f"lcv_incidents.csv not found at {path} — run ml/pipeline/01_ingest.py")
        return None
    df = pd.read_csv(path)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce", utc=True)
    return df


def _risk_tier(rank: int, n_corridors: int) -> str:
    """Top third of corridors by incident volume = high, middle third =
    medium, bottom third = low. Rank-based rather than a hardcoded count
    threshold, so it stays sensible as the dataset grows."""
    if n_corridors <= 1:
        return "medium"
    pct = rank / (n_corridors - 1)
    if pct <= 1 / 3:
        return "high"
    if pct <= 2 / 3:
        return "medium"
    return "low"


def get_lcv_risk_summary() -> Dict[str, Any]:
    df = _load_lcv_df()
    if df is None or df.empty:
        return {
            "error": "LCV data not available — run the ingest pipeline (ml/pipeline/01_ingest.py) first.",
            "corridors": [],
        }

    real_corridors = df[df["corridor"].notna() & (df["corridor"] != "Non-corridor")]
    span_days = (df["start_datetime"].max() - df["start_datetime"].min()).days
    span_weeks = round(span_days / 7, 1) if span_days else 1.0
    daily_avg_all_corridors = len(real_corridors) / max(span_days, 1)

    grouped = (
        real_corridors.groupby("corridor")
        .agg(
            incident_count=("id", "count"),
            avg_delay_mins=("duration_mins", "mean"),
            closure_rate=("requires_road_closure", "mean"),
        )
        .sort_values("incident_count", ascending=False)
    )

    # Last 7 days of the dataset's own date range, as a stand-in for
    # "currently active" — there is no live feed yet (see README Future
    # Scope), and every row in this historical CSV has status
    # closed/resolved, so claiming a literal "active right now" count would
    # be fabricated. This is the closest honest proxy: recent volume.
    recent_cutoff = df["start_datetime"].max() - pd.Timedelta(days=7)
    recent_by_corridor = (
        real_corridors[real_corridors["start_datetime"] >= recent_cutoff]
        .groupby("corridor")["id"]
        .count()
    )

    corridors_out = []
    n = len(grouped)
    for rank, (corridor, row) in enumerate(grouped.iterrows()):
        top_cause = (
            real_corridors.loc[real_corridors["corridor"] == corridor, "event_cause"]
            .mode()
            .iloc[0]
        )
        alt = DIVERSION_MAP.get(corridor, [{}])[0]
        corridors_out.append({
            "corridor": corridor,
            "incident_count": int(row["incident_count"]),
            "recent_7d_incidents": int(recent_by_corridor.get(corridor, 0)),
            "avg_delay_mins": round(float(row["avg_delay_mins"]), 1) if pd.notna(row["avg_delay_mins"]) else None,
            "closure_rate": round(float(row["closure_rate"]), 3),
            "risk_level": _risk_tier(rank, n),
            "top_cause": top_cause,
            "impacted_hubs": _CORRIDOR_HUBS.get(corridor, []),
            "suggested_reroute": (
                f"Via {alt['via']} \u2192 {alt['road']}" if alt else None
            ),
            "reroute_extra_mins": alt.get("extra_mins") if alt else None,
        })

    high_risk = [c for c in corridors_out if c["risk_level"] == "high"]
    medium_risk = [c for c in corridors_out if c["risk_level"] == "medium"]

    return {
        "data_note": (
            "Computed live from data/processed/lcv_incidents.csv (historical "
            f"ASTRAM data, {span_weeks} weeks). No real-time feed is wired up yet "
            "— 'recent_7d_incidents' reflects the last 7 days of the dataset's "
            "own date range, not the current calendar date. See README Future Scope."
        ),
        "total_lcv_incidents_dataset": int(len(df)),
        "dataset_period_weeks": span_weeks,
        "weekly_avg_lcv_incidents": round(len(df) / span_weeks, 1) if span_weeks else len(df),
        "high_risk_corridors": len(high_risk),
        "medium_risk_corridors": len(medium_risk),
        "corridors": corridors_out,
        "surge_day_reference": get_surge_impact(df, daily_avg_all_corridors),
    }


def get_lcv_corridors() -> List[Dict[str, Any]]:
    return get_lcv_risk_summary().get("corridors", [])


def get_surge_impact(df: pd.DataFrame | None = None, daily_avg: float | None = None) -> Dict[str, Any]:
    """Real LCV-specific numbers for the March 7 2024 weather event already
    used elsewhere in the app (see ml/artifacts/surge_replay_march7.json,
    which covers ALL incident types — this is the LCV subset of that same
    day, computed directly so the two panels can never silently disagree)."""
    own_load = df is None
    if own_load:
        df = _load_lcv_df()
    if df is None or df.empty:
        return {"error": "LCV data not available."}

    if daily_avg is None:
        real_corridors = df[df["corridor"].notna() & (df["corridor"] != "Non-corridor")]
        span_days = max((df["start_datetime"].max() - df["start_datetime"].min()).days, 1)
        daily_avg = len(real_corridors) / span_days

    surge_day = df[df["start_datetime"].dt.date.astype(str) == "2024-03-07"]
    corridors_hit = sorted(c for c in surge_day["corridor"].dropna().unique() if c != "Non-corridor")
    primary_cause = (
        surge_day["event_cause"].mode().iloc[0] if not surge_day.empty else None
    )
    total_delay_hrs = round(surge_day["duration_mins"].sum() / 60, 1) if not surge_day.empty else 0.0

    return {
        "date": "2024-03-07",
        "total_lcv_incidents": int(len(surge_day)),
        "baseline_daily_avg": round(daily_avg, 1),
        "surge_multiplier": round(len(surge_day) / daily_avg, 1) if daily_avg else None,
        "primary_cause": primary_cause,
        "corridors_blocked": corridors_hit,
        "estimated_total_delay_hrs": total_delay_hrs,
        "note": (
            "LCV-specific subset of the citywide March 7 surge "
            "(see /surge/replay-march7 for the full-dataset version, 250 "
            "incidents / 4.3x — this figure is LCV vehicles only)."
        ),
    }
