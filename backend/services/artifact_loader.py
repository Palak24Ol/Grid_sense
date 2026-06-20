"""
services/artifact_loader.py — Singleton loader for all ML artifacts.

Loads every artifact once at startup and caches in memory.
All services import from here — never call joblib.load() directly in routes.

Usage:
    from backend.services.artifact_loader import get_artifacts
    arts = get_artifacts()
    model = arts.closure_model
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import joblib

from backend.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Artifacts:
    closure_model: Optional[object] = None
    priority_model: Optional[object] = None
    encoders: Optional[dict] = None
    duration_lookup: Optional[dict] = None
    duration_model: Optional[object] = None
    duration_meta: Optional[dict] = None
    corridor_risk_index: Optional[dict] = None
    station_map: Optional[dict] = None
    station_concurrency: Optional[dict] = None
    prophet_models: dict = field(default_factory=dict)   # junction → {model, mae}
    closure_meta: Optional[dict] = None
    priority_meta: Optional[dict] = None
    closure_encoding_lookups: Optional[dict] = None
    priority_encoding_lookups: Optional[dict] = None

    @property
    def all_core_loaded(self) -> bool:
        """True if all non-Prophet artifacts are loaded."""
        return all([
            self.closure_model is not None,
            self.priority_model is not None,
            self.encoders is not None,
            self.duration_lookup is not None,
            self.corridor_risk_index is not None,
            self.station_map is not None,
            self.station_concurrency is not None,
            self.closure_meta is not None,
            self.priority_meta is not None,
            self.closure_encoding_lookups is not None,
            self.priority_encoding_lookups is not None,
        ])

    def get_artifact_status(self) -> dict:
        return {
            "encoders": self.encoders is not None,
            "closure_model": self.closure_model is not None,
            "priority_model": self.priority_model is not None,
            "duration_lookup": self.duration_lookup is not None,
            "corridor_risk_index": self.corridor_risk_index is not None,
            "station_map": self.station_map is not None,
            "station_concurrency": self.station_concurrency is not None,
            "closure_meta": self.closure_meta is not None,
            "priority_meta": self.priority_meta is not None,
            "closure_encoding_lookups": self.closure_encoding_lookups is not None,
            "priority_encoding_lookups": self.priority_encoding_lookups is not None,
            "duration_model": self.duration_model is not None,
            "duration_meta": self.duration_meta is not None,
            "prophet_models_count": len(self.prophet_models),
        }


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        logger.warning(f"Artifact not found: {path.name}")
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        logger.info(f"Loaded {path.name} ({len(data)} entries)")
        return data
    except Exception as e:
        logger.error(f"Failed to load {path.name}: {e}")
        return None


def _load_pkl(path: Path) -> Optional[object]:
    if not path.exists():
        logger.warning(f"Artifact not found: {path.name}")
        return None
    try:
        obj = joblib.load(path)
        size_kb = path.stat().st_size / 1024
        logger.info(f"Loaded {path.name} ({size_kb:.0f} KB, type={type(obj).__name__})")
        return obj
    except Exception as e:
        logger.error(f"Failed to load {path.name}: {e}")
        return None


def _load_prophet_models(prophet_dir: Path) -> dict:
    if not prophet_dir.exists():
        logger.warning("prophet_models/ directory not found")
        return {}
    models = {}
    for pkl_path in prophet_dir.glob("*.pkl"):
        try:
            payload = joblib.load(pkl_path)
            junction = payload.get("junction", pkl_path.stem)
            models[junction] = payload
        except Exception as e:
            logger.warning(f"Could not load prophet model {pkl_path.name}: {e}")
    logger.info(f"Loaded {len(models)} Prophet junction models")
    return models


@lru_cache(maxsize=1)
def get_artifacts() -> Artifacts:
    """Load all artifacts once and cache forever. Thread-safe via lru_cache."""
    settings = get_settings()
    artifact_dir = settings.artifact_path

    logger.info(f"Loading artifacts from {artifact_dir}")

    arts = Artifacts(
        closure_model=_load_pkl(artifact_dir / "closure_model.pkl"),
        priority_model=_load_pkl(artifact_dir / "priority_model.pkl"),
        encoders=_load_pkl(artifact_dir / "encoders.pkl"),
        duration_lookup=_load_json(artifact_dir / "duration_lookup.json"),
        duration_model=_load_pkl(artifact_dir / "duration_model.pkl"),
        duration_meta=_load_json(artifact_dir / "duration_meta.json"),
        corridor_risk_index=_load_json(artifact_dir / "corridor_risk_index.json"),
        station_map=_load_json(artifact_dir / "station_map.json"),
        station_concurrency=_load_json(artifact_dir / "station_concurrency.json"),
        prophet_models=_load_prophet_models(artifact_dir / "prophet_models"),
        closure_meta=_load_json(artifact_dir / "closure_meta.json"),
        priority_meta=_load_json(artifact_dir / "priority_meta.json"),
        closure_encoding_lookups=_load_json(artifact_dir / "closure_encoding_lookups.json"),
        priority_encoding_lookups=_load_json(artifact_dir / "priority_encoding_lookups.json"),
    )

    if arts.all_core_loaded:
        logger.info("All core artifacts loaded successfully ✓")
    else:
        logger.warning("Some artifacts missing — running in mock/degraded mode")

    return arts