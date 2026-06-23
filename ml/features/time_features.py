"""
time_features.py — Cyclical time feature extraction.

Cyclical encoding ensures hour 23 and hour 0 are numerically adjacent,
preventing the model from treating midnight as an arbitrary boundary.
"""

import math


def extract_time_features(hour: int, day_of_week: int) -> dict:
    """Return cyclical sin/cos encoding for hour_of_day.

    Args:
        hour: 0–23
        day_of_week: 0=Monday … 6=Sunday

    Returns dict with keys: hour_sin, hour_cos
    (day_of_week is passed through as-is in the feature vector)
    """
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)
    return {
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
    }