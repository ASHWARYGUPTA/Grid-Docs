"""M02 constants — temporal windows, corridor graph stub (OSM deferred to Phase 2)."""

from zoneinfo import ZoneInfo

from grid_unlocked.ingestion.vocab import VALID_CORRIDORS

IST = ZoneInfo("Asia/Kolkata")

PEAK_HOURS = frozenset(range(7, 11)) | frozenset(range(17, 22))
NAMED_CORRIDORS = frozenset(c for c in VALID_CORRIDORS if c != "Non-corridor")

# MVP corridor centrality (betweenness proxy until OSM graph ingest)
CORRIDOR_CENTRALITY: dict[str, float] = {
    "ORR East 1": 0.95,
    "ORR East 2": 0.93,
    "ORR North 1": 0.92,
    "ORR North 2": 0.90,
    "ORR West 1": 0.91,
    "Bellary Road 1": 0.88,
    "Bellary Road 2": 0.86,
    "Old Airport Road": 0.85,
    "CBD 1": 0.85,
    "CBD 2": 0.83,
    "Hosur Road": 0.82,
    "Mysore Road": 0.80,
    "Tumkur Road": 0.78,
    "Old Madras Road": 0.77,
    "Bannerghata Road": 0.75,
    "Magadi Road": 0.72,
    "West of Chord Road": 0.70,
    "Varthur Road": 0.68,
    "Hennur Main Road": 0.65,
    "IRR(Thanisandra road)": 0.64,
    "Airport New South Road": 0.80,
    "Non-corridor": 0.15,
}

# Adjacent corridors for GCDH neighbor queries (MVP static map)
CORRIDOR_NEIGHBORS: dict[str, list[str]] = {
    "ORR East 1": ["ORR East 2", "Old Airport Road", "Hosur Road"],
    "ORR East 2": ["ORR East 1", "ORR North 2", "Old Madras Road"],
    "ORR North 1": ["ORR North 2", "Bellary Road 1", "Hebbal"],
    "ORR North 2": ["ORR North 1", "ORR East 2", "ORR West 1"],
    "ORR West 1": ["ORR North 2", "Mysore Road", "Tumkur Road"],
    "Mysore Road": ["ORR West 1", "Bannerghata Road"],
    "Tumkur Road": ["ORR West 1", "West of Chord Road"],
    "Old Airport Road": ["ORR East 1", "CBD 1"],
    "Hosur Road": ["ORR East 1", "Bannerghata Road"],
    "Bellary Road 1": ["ORR North 1", "Bellary Road 2"],
    "Bellary Road 2": ["Bellary Road 1", "CBD 2"],
    "Non-corridor": [],
}

VEH_COMPLEXITY_BASE: dict[str, float] = {
    "heavy_vehicle": 1.0,
    "truck": 0.9,
    "lcv": 0.7,
    "bmtc_bus": 0.8,
    "private_car": 0.3,
    "two_wheeler": 0.2,
}

DEFAULT_VEH_COMPLEXITY = 0.5
DEFAULT_CENTRALITY = 0.25
DEFAULT_PRIOR_ICT_H = 1.0
DEFAULT_PRIOR_CLOSURE_RATE = 0.083

FEATURE_CACHE_TTL_SECONDS = 86400  # 24 h
BIAS_WEIGHT_MIN = 0.5
BIAS_WEIGHT_MAX = 3.0
