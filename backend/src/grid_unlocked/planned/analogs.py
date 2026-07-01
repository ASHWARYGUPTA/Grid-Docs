"""Retrieve historical analog events for planned package briefings."""

from __future__ import annotations

import csv
from datetime import datetime

from grid_unlocked.config import settings
from grid_unlocked.ingestion.validator import normalize_cause, parse_bool, parse_datetime
from grid_unlocked.planned.schemas import AnalogEvent


def _ict_hours(start: datetime | None, closed: datetime | None) -> float | None:
    if start is None or closed is None or closed <= start:
        return None
    return round((closed - start).total_seconds() / 3600.0, 2)


def find_analog_events(
    cause: str,
    corridor: str | None,
    *,
    limit: int = 3,
    csv_path=None,
) -> list[AnalogEvent]:
    path = csv_path or settings.astram_csv_path
    if not path.exists():
        return []

    corridor_key = corridor or "Non-corridor"
    matches: list[AnalogEvent] = []

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("event_type") != "planned":
                continue
            try:
                row_cause = normalize_cause(row.get("event_cause"))
            except Exception:
                continue
            if row_cause != cause:
                continue

            row_corridor = row.get("corridor") or "Non-corridor"
            if row_corridor in ("NULL", ""):
                row_corridor = "Non-corridor"

            start = parse_datetime(row.get("start_datetime"))
            closed = parse_datetime(row.get("closed_datetime"))
            matches.append(
                AnalogEvent(
                    event_id=row.get("id", "unknown"),
                    corridor=row_corridor,
                    cause=row_cause,
                    closure=parse_bool(row.get("requires_road_closure"), default=False),
                    ict_h=_ict_hours(start, closed),
                    start_datetime=start,
                )
            )

    def sort_key(a: AnalogEvent) -> tuple[int, str]:
        corridor_match = 0 if a.corridor == corridor_key else 1
        return (corridor_match, a.event_id)

    matches.sort(key=sort_key)
    return matches[:limit]
