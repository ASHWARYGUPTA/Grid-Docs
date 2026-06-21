import re

# (compiled case-insensitive regex, cause) — cause MUST be a member of
# ingestion.vocab.VALID_CAUSES. First match wins.
_CAUSE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"water|flood|logging", re.I), "water_logging"),
    (re.compile(r"accident|crash|collision", re.I), "accident"),
    (re.compile(r"breakdown|broke\s*down|stalled", re.I), "vehicle_breakdown"),
    (re.compile(r"tree|fallen\s*tree|branch", re.I), "tree_fall"),
    (re.compile(r"pothole|pot\s*hole|crater", re.I), "pot_holes"),
]
DEFAULT_CAUSE = "unknown_obstruction"
DEFAULT_CONFIDENCE = 0.2
MATCH_CONFIDENCE = 0.65


def infer_cause_hint(description: str | None) -> tuple[str, float]:
    if not description:
        return DEFAULT_CAUSE, DEFAULT_CONFIDENCE
    for pattern, cause in _CAUSE_PATTERNS:
        if pattern.search(description):
            return cause, MATCH_CONFIDENCE
    return DEFAULT_CAUSE, DEFAULT_CONFIDENCE
