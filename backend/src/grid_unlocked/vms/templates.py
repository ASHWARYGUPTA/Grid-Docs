"""M11 — VMS Template Engine.

Converts a diversion route into board-friendly English text.
Constraints from spec:
  - ≤ 120 characters total
  - ≤ 3 lines
  - Must include the primary alternate route name

DEFERRED D-M11-02: Kannada/English bilingual support — Phase 1.5.
A static lookup table for common Bengaluru road names in Kannada script
will be added (e.g., "Outer Ring Road" → "ಔಟರ್ ರಿಂಗ್ ರೋಡ್").
"""

from __future__ import annotations

import re

MAX_CHARS = 120
MAX_LINES = 3

# Common Bengaluru road abbreviations to keep text short
_ABBREVS: list[tuple[str, str]] = [
    ("Outer Ring Road", "ORR"),
    ("Inner Ring Road", "IRR"),
    ("Bannerghata Road", "Bannerghata Rd"),
    ("Bannerghatta Road", "Bannerghata Rd"),
    ("Hosur Road", "Hosur Rd"),
    ("Sarjapur Road", "Sarjapur Rd"),
    ("Koramangala", "Koramangala"),
    ("Whitefield", "Whitefield"),
    ("Marathahalli", "Marathahalli"),
    ("Banerghatta National Park Road", "BNP Rd"),
    ("Junction", "Jn"),
    ("Layout", "Layout"),
]


def _abbreviate(text: str) -> str:
    """Apply abbreviations to shorten road names without losing identity."""
    for full, short in _ABBREVS:
        text = re.sub(re.escape(full), short, text, flags=re.IGNORECASE)
    return text


def render_board_text(
    route_summary: str,
    path: list[str],
    description: str,
    eta_delta_min: float,
    capacity_class: str,
) -> str:
    """
    Render a diversion route as ≤3 line, ≤120 char LED board text.

    Output format (English):
        Line 1: DIVERSION ALERT
        Line 2: USE ALT: <abbreviated route>
        Line 3: +Xmin | <capacity> CAPACITY

    Falls back to description if route_summary is empty.
    """
    # Line 1 — fixed header
    line1 = "DIVERSION ALERT"

    # Line 2 — primary alt route, abbreviated to fit
    alt = route_summary or description or (path[0] if path else "alternate route")
    alt = _abbreviate(alt)
    line2 = f"USE ALT: {alt}"
    if len(line2) > 55:
        # Truncate but keep enough to identify the road
        line2 = line2[:52] + "..."

    # Line 3 — ETA delta and capacity
    eta_str = f"+{eta_delta_min:.0f}min" if eta_delta_min > 0 else "SAME ETA"
    cap = capacity_class.upper()
    line3 = f"{eta_str} | {cap} CAPACITY"

    board_text = "\n".join([line1, line2, line3])

    # Final safety check — truncate if over 120 chars total (excl. newlines)
    inline = " | ".join([line1, line2, line3])
    if len(inline) > MAX_CHARS:
        # Drop line 3 and truncate line 2 more aggressively
        line2_short = line2[:MAX_CHARS - len(line1) - 4]
        board_text = "\n".join([line1, line2_short])

    return board_text


def render_from_route(route: dict) -> str:
    """
    Render board text from a serialised DiversionRoute dict.
    Handles missing keys gracefully.
    """
    return render_board_text(
        route_summary=route.get("route_summary", ""),
        path=route.get("path", []),
        description=route.get("description", ""),
        eta_delta_min=float(route.get("eta_delta_min", 0)),
        capacity_class=route.get("capacity_class", "medium"),
    )
