"""
time_features.py — Cyclical time feature extraction with day-of-week encoding and rush hour flag.

Cyclical encoding ensures hour 23 and hour 0 are numerically adjacent,
preventing the model from treating midnight as an arbitrary boundary.
Day-of-week encoding similarly ensures Sunday and Monday are adjacent.
The rush hour flag captures morning (7-10) and evening (17-20) peak periods.
"""

import math


def extract_time_features(hour: int, day_of_week: int) -> dict:
    """Return cyclical sin/cos encoding for hour_of_day and day_of_week.

    Args:
        hour: 0-23
        day_of_week: 0=Monday ... 6=Sunday

    Returns dict with keys: hour_sin, hour_cos, dow_sin, dow_cos, is_rush_hour
    """
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)
    dow_sin = math.sin(2 * math.pi * day_of_week / 7)
    dow_cos = math.cos(2 * math.pi * day_of_week / 7)
    is_rush_hour = int(hour in range(7, 11) or hour in range(17, 21))
    return {
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "is_rush_hour": is_rush_hour,
    }