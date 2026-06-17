"""
encoders.py — LabelEncoder load/encode utilities.

Note: The raw CSV uses 'veh_type' for vehicle type. Internally we normalise
this to 'vehicle_type' in every feature dict so the rest of the codebase
(including the FastAPI request model) can use the cleaner name.
"""

import joblib
import numpy as np
from pathlib import Path

ARTIFACT_DIR = Path(__file__).parent.parent / "artifacts"

# Columns that get LabelEncoded. Order matters — must match feature_engineer.
CATEGORICAL_COLS = ["corridor", "event_cause", "vehicle_type", "police_station", "zone"]


def load_encoders(artifact_dir: Path = ARTIFACT_DIR) -> dict:
    """Load fitted LabelEncoders from encoders.pkl.

    Returns a dict keyed by column name.
    Raises FileNotFoundError if artifact is missing.
    """
    path = artifact_dir / "encoders.pkl"
    if not path.exists():
        raise FileNotFoundError(
            f"encoders.pkl not found at {path}. "
            "Run ml/pipeline/02_feature_engineer.py first."
        )
    return joblib.load(path)


def encode_input(
    corridor: str | None,
    event_cause: str,
    vehicle_type: str | None,
    police_station: str | None = None,
    zone: str | None = None,
    encoders: dict | None = None,
    artifact_dir: Path = ARTIFACT_DIR,
) -> dict:
    """Encode categorical inputs for model inference.

    Unknown or missing labels map to -1 (treated as 'unknown category').
    Loads encoders from disk if not provided.
    """
    if encoders is None:
        encoders = load_encoders(artifact_dir)

    def safe_encode(col: str, value: str | None) -> int:
        if value is None or str(value).strip().lower() in ("", "null", "nan", "none"):
            return -1
        le = encoders.get(col)
        if le is None:
            return -1
        try:
            return int(le.transform([str(value)])[0])
        except ValueError:
            # Unseen label
            return -1

    return {
        "corridor_encoded": safe_encode("corridor", corridor),
        "event_cause_encoded": safe_encode("event_cause", event_cause),
        "vehicle_type_encoded": safe_encode("vehicle_type", vehicle_type),
        "police_station_encoded": safe_encode("police_station", police_station),
        "zone_encoded": safe_encode("zone", zone),
    }