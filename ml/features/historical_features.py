"""
historical_features.py — JSON artifact lookup helpers.

All functions load from pre-computed JSON artifacts in ml/artifacts/.
No database queries at inference time — keeps prediction latency under 50ms.

Artifacts produced by 07_export_artifacts.py:
  - station_map.json        → corridor → [ranked stations]
  - station_concurrency.json → station:hour:dow → avg/max concurrent
  - corridor_risk_index.json → corridor → composite_risk_score
"""

import json
import math
from functools import lru_cache
from pathlib import Path

ARTIFACT_DIR = Path(__file__).parent.parent / "artifacts"


@lru_cache(maxsize=1)
def _load_station_map(artifact_dir: str) -> dict:
    path = Path(artifact_dir) / "station_map.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_station_concurrency(artifact_dir: str) -> dict:
    path = Path(artifact_dir) / "station_concurrency.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_corridor_risk(artifact_dir: str) -> dict:
    path = Path(artifact_dir) / "corridor_risk_index.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def get_station_recommendation(
    corridor: str | None,
    artifact_dir: Path = ARTIFACT_DIR,
) -> tuple[str | None, str | None]:
    """Return (primary_station, secondary_station) for a corridor.

    Falls back to (None, None) if corridor is unknown / non-corridor.
    """
    station_map = _load_station_map(str(artifact_dir))
    if not corridor or corridor not in station_map:
        return None, None
    stations = station_map[corridor]  # list sorted by rank
    primary = stations[0]["police_station"] if len(stations) > 0 else None
    secondary = stations[1]["police_station"] if len(stations) > 1 else None
    return primary, secondary


def get_station_concurrency(
    station: str,
    hour: int,
    day_of_week: int,
    artifact_dir: Path = ARTIFACT_DIR,
) -> dict:
    """Return avg_concurrent and max_concurrent for a station at a given time.

    Returns defaults (0.0, 0) if key not found.
    """
    concurrency = _load_station_concurrency(str(artifact_dir))
    key = f"{station}:{hour}:{day_of_week}"
    record = concurrency.get(key, {})
    return {
        "avg_concurrent": record.get("avg_concurrent", 0.0),
        "max_concurrent": record.get("max_concurrent", 0),
    }


def get_corridor_risk(
    corridor: str | None,
    artifact_dir: Path = ARTIFACT_DIR,
) -> float:
    """Return composite_risk_score (0–100) for a corridor.

    Returns 0.0 for unknown / non-corridor.
    """
    risk_index = _load_corridor_risk(str(artifact_dir))
    if not corridor or corridor not in risk_index:
        return 0.0
    return float(risk_index[corridor].get("composite_risk_score", 0.0))


def get_corridor_risk_record(
    corridor: str | None,
    artifact_dir: Path = ARTIFACT_DIR,
) -> dict:
    """Return the full risk record dict for a corridor, or empty dict."""
    risk_index = _load_corridor_risk(str(artifact_dir))
    if not corridor or corridor not in risk_index:
        return {}
    return risk_index[corridor]