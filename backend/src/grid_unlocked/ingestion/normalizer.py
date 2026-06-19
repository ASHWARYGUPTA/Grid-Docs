import json
import uuid
from datetime import UTC, datetime
from typing import Any

from grid_unlocked.ingestion.schemas import IngestSource, NormalizedEvent, RawEventPayload
from grid_unlocked.ingestion.vocab import DROPPED_CAUSES
from grid_unlocked.ingestion.validator import (
    IngestValidationError,
    compute_reporting_lag_minutes,
    detect_anomalies,
    normalize_cause,
    normalize_corridor,
    normalize_event_type,
    normalize_status,
    parse_bool,
    parse_datetime,
    validate_bbox,
    validate_required_fields,
)


def _ensure_event_id(raw: RawEventPayload) -> str:
    if raw.event_id and str(raw.event_id).strip():
        return str(raw.event_id).strip()
    return f"GEN-{uuid.uuid4().hex[:12].upper()}"


def normalize_payload(
    payload: dict[str, Any] | RawEventPayload,
    source: IngestSource,
) -> NormalizedEvent:
    raw = payload if isinstance(payload, RawEventPayload) else RawEventPayload.model_validate(payload)
    data = raw.model_dump(by_alias=True, exclude_none=False)

    validate_required_fields(data)

    event_cause = normalize_cause(raw.event_cause)
    if event_cause in DROPPED_CAUSES:
        raise IngestValidationError(f"dropped cause: {event_cause}")

    lat = float(raw.latitude)  # type: ignore[arg-type]
    lon = float(raw.longitude)  # type: ignore[arg-type]
    validate_bbox(lat, lon)

    event_type = normalize_event_type(raw.event_type)
    is_planned = event_type == "planned"
    start = parse_datetime(raw.start_datetime)
    if start is None:
        raise IngestValidationError("invalid start_datetime")

    end = parse_datetime(raw.end_datetime)
    created = parse_datetime(raw.created_date)
    closed = parse_datetime(raw.closed_datetime)
    status = normalize_status(raw.status)

    authenticated = parse_bool(raw.authenticated, default=source != IngestSource.CITIZEN)
    if source == IngestSource.CITIZEN:
        authenticated = False

    anomaly_flags = detect_anomalies(
        lat=lat,
        lon=lon,
        start=start,
        end=end,
        closed=closed,
        is_planned=is_planned,
    )

    return NormalizedEvent(
        event_id=_ensure_event_id(raw),
        source=source,
        event_type=event_type,
        is_planned=is_planned,
        event_cause=event_cause,
        status=status,
        authenticated=authenticated,
        latitude=lat,
        longitude=lon,
        address=raw.address,
        corridor=normalize_corridor(raw.corridor),
        zone=raw.zone if raw.zone not in (None, "", "NULL") else None,
        junction=raw.junction if raw.junction not in (None, "", "NULL") else None,
        police_station=raw.police_station if raw.police_station not in (None, "", "NULL") else None,
        priority=raw.priority if raw.priority not in (None, "", "NULL") else None,
        requires_road_closure=parse_bool(raw.requires_road_closure, default=False),
        start_datetime=start,
        end_datetime=end,
        created_date=created,
        closed_datetime=closed,
        reporting_lag_minutes=compute_reporting_lag_minutes(start, created),
        description=raw.description,
        veh_type=raw.veh_type,
        anomaly_flags=anomaly_flags,
        ingested_at=datetime.now(UTC),
    )


def astram_row_to_payload(row: dict[str, str]) -> dict[str, Any]:
    """Map ASTraM CSV export row to ingest payload."""
    return {
        "id": row.get("id"),
        "event_type": row.get("event_type"),
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "address": row.get("address") or None,
        "event_cause": row.get("event_cause"),
        "requires_road_closure": row.get("requires_road_closure", "FALSE"),
        "start_datetime": row.get("start_datetime"),
        "end_datetime": row.get("end_datetime") if row.get("end_datetime") not in ("NULL", "") else None,
        "status": row.get("status"),
        "authenticated": row.get("authenticated"),
        "created_date": row.get("created_date"),
        "closed_datetime": row.get("closed_datetime") if row.get("closed_datetime") not in ("NULL", "") else None,
        "corridor": row.get("corridor") if row.get("corridor") not in ("NULL", "") else None,
        "zone": row.get("zone") if row.get("zone") not in ("NULL", "") else None,
        "junction": row.get("junction") if row.get("junction") not in ("NULL", "") else None,
        "police_station": row.get("police_station") if row.get("police_station") not in ("NULL", "") else None,
        "priority": row.get("priority") if row.get("priority") not in ("NULL", "") else None,
        "description": row.get("description") or None,
        "veh_type": row.get("veh_type") if row.get("veh_type") not in ("NULL", "") else None,
    }


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)
