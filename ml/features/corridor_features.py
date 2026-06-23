"""
corridor_features.py — Corridor classification flags.

The 15 named corridors are Flipkart's high-priority zones. All incidents
on these corridors get is_high_priority_corridor = True.
Non-corridor incidents are a special class where the operational system
historically defaults to Low priority — the disagreement flag fires here.
"""

HIGH_PRIORITY_CORRIDORS: frozenset[str] = frozenset(
    [
        "Mysore Road",
        "Bellary Road 1",
        "Bellary Road 2",
        "Tumkur Road",
        "Hosur Road",
        "ORR North 1",
        "ORR North 2",
        "ORR East 1",
        "ORR East 2",
        "Magadi Road",
        "Old Madras Road",
        "Bannerghatta Road",
        "West of Chord Road",
        "CBD 2",
        "ORR West 1",
        "ORR West 2",
    ]
)


def get_corridor_flags(corridor: str | None) -> dict:
    """Return boolean flags for corridor classification.

    Args:
        corridor: Raw corridor name from request / dataset.
                  'Non-corridor', None, or empty → is_non_corridor = True.

    Returns dict with keys:
        is_high_priority_corridor: 1 if corridor is in the named set
        is_non_corridor: 1 if corridor is None / 'Non-corridor' / empty
    """
    if not corridor or str(corridor).strip().lower() in (
        "non-corridor",
        "null",
        "nan",
        "none",
        "",
    ):
        return {
            "is_high_priority_corridor": 0,
            "is_non_corridor": 1,
        }

    in_priority_set = corridor.strip() in HIGH_PRIORITY_CORRIDORS
    return {
        "is_high_priority_corridor": int(in_priority_set),
        "is_non_corridor": 0,
    }