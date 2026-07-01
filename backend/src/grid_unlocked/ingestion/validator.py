from datetime import UTC, datetime
from typing import Any

from dateutil import parser as date_parser

from grid_unlocked.config import settings
from grid_unlocked.ingestion.vocab import (
    CAUSE_ALIASES,
    VALID_CORRIDORS,
    VALID_EVENT_TYPES,
    VALID_STATUSES,
)


class IngestValidationError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or value == "" or str(value).upper() == "NULL":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = date_parser.isoparse(str(value))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_bool(value: bool | str | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return default


def normalize_cause(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        raise IngestValidationError("missing event_cause")
    key = str(raw).strip()
    if key in CAUSE_ALIASES:
        return CAUSE_ALIASES[key]
    snake = key.lower().replace(" ", "_").replace("/", "_")
    if snake in CAUSE_ALIASES.values():
        return snake
    raise IngestValidationError(f"unknown event_cause: {raw}")


def normalize_corridor(raw: str | None) -> str | None:
    if raw is None or str(raw).strip() in {"", "NULL", "null"}:
        return None
    corridor = str(raw).strip()
    if corridor not in VALID_CORRIDORS:
        return None
    return corridor


def normalize_status(raw: str | None) -> str:
    if not raw:
        return "active"
    status = str(raw).strip().lower()
    if status not in VALID_STATUSES:
        raise IngestValidationError(f"invalid status: {raw}")
    return status


def normalize_event_type(raw: str | None) -> str:
    if not raw:
        return "unplanned"
    event_type = str(raw).strip().lower()
    if event_type not in VALID_EVENT_TYPES:
        raise IngestValidationError(f"invalid event_type: {raw}")
    return event_type


def validate_bbox(lat: float, lon: float) -> None:
    if not (settings.bbox_lat_min <= lat <= settings.bbox_lat_max):
        raise IngestValidationError(
            f"latitude {lat} outside Bengaluru bbox [{settings.bbox_lat_min}, {settings.bbox_lat_max}]"
        )
    if not (settings.bbox_lon_min <= lon <= settings.bbox_lon_max):
        raise IngestValidationError(
            f"longitude {lon} outside Bengaluru bbox [{settings.bbox_lon_min}, {settings.bbox_lon_max}]"
        )


def validate_required_fields(payload: dict[str, Any]) -> None:
    missing = []
    for field in ("latitude", "longitude", "event_cause", "start_datetime"):
        if payload.get(field) in (None, "", "NULL"):
            missing.append(field)
    if missing:
        raise IngestValidationError(f"missing required fields: {', '.join(missing)}")


def compute_reporting_lag_minutes(
    start: datetime | None, created: datetime | None
) -> float | None:
    if start is None or created is None:
        return None
    delta = created - start
    return round(delta.total_seconds() / 60.0, 2)


def detect_anomalies(
    *,
    lat: float,
    lon: float,
    start: datetime,
    end: datetime | None,
    closed: datetime | None,
    is_planned: bool,
) -> list[str]:
    flags: list[str] = []
    if not (
        settings.bbox_lat_min <= lat <= settings.bbox_lat_max
        and settings.bbox_lon_min <= lon <= settings.bbox_lon_max
    ):
        flags.append("coordinates_outside_bbox")
    if closed and closed < start:
        flags.append("closed_before_start")
    if is_planned and end and start:
        duration_hours = (end - start).total_seconds() / 3600
        if duration_hours > settings.planned_max_duration_hours:
            flags.append("planned_duration_exceeds_72h")
    return flags
