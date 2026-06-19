"""ASTraM training vocabulary — 17 cause classes, 22 corridors."""

# Canonical cause labels (test_demo ingested only to dead-letter)
VALID_CAUSES: frozenset[str] = frozenset(
    {
        "accident",
        "congestion",
        "construction",
        "debris",
        "fog_low_visibility",
        "others",
        "pot_holes",
        "procession",
        "protest",
        "public_event",
        "road_conditions",
        "tree_fall",
        "vehicle_breakdown",
        "vip_movement",
        "water_logging",
        "unknown_obstruction",
        "test_demo",
    }
)

CAUSE_ALIASES: dict[str, str] = {
    "Debris": "debris",
    "debris": "debris",
    "Fog / Low Visibility": "fog_low_visibility",
    "fog / low visibility": "fog_low_visibility",
    "accident": "accident",
    "congestion": "congestion",
    "construction": "construction",
    "others": "others",
    "pot_holes": "pot_holes",
    "procession": "procession",
    "protest": "protest",
    "public_event": "public_event",
    "road_conditions": "road_conditions",
    "test_demo": "test_demo",
    "tree_fall": "tree_fall",
    "vehicle_breakdown": "vehicle_breakdown",
    "vip_movement": "vip_movement",
    "water_logging": "water_logging",
}

VALID_CORRIDORS: frozenset[str] = frozenset(
    {
        "Airport New South Road",
        "Bannerghata Road",
        "Bellary Road 1",
        "Bellary Road 2",
        "CBD 1",
        "CBD 2",
        "Hennur Main Road",
        "Hosur Road",
        "IRR(Thanisandra road)",
        "Magadi Road",
        "Mysore Road",
        "Non-corridor",
        "ORR East 1",
        "ORR East 2",
        "ORR North 1",
        "ORR North 2",
        "ORR West 1",
        "Old Airport Road",
        "Old Madras Road",
        "Tumkur Road",
        "Varthur Road",
        "West of Chord Road",
    }
)

VALID_STATUSES: frozenset[str] = frozenset({"active", "closed", "resolved"})
VALID_EVENT_TYPES: frozenset[str] = frozenset({"planned", "unplanned"})
VALID_SOURCES: frozenset[str] = frozenset({"astram", "planned_portal", "field", "citizen"})

DROPPED_CAUSES: frozenset[str] = frozenset({"test_demo"})
