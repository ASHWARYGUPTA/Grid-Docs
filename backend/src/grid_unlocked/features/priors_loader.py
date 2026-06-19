import csv
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.db.models import CausePriorRow, CorridorCausePriorRow, HourBiasWeightRow
from grid_unlocked.features.constants import BIAS_WEIGHT_MAX, BIAS_WEIGHT_MIN
from grid_unlocked.ingestion.validator import normalize_cause, parse_bool, parse_datetime

IST_TZ = ZoneInfo("Asia/Kolkata")


def _normalize_cause_safe(raw: str | None) -> str | None:
    try:
        return normalize_cause(raw)
    except Exception:
        return None


def _ict_hours(start: datetime | None, closed: datetime | None) -> float | None:
    if start is None or closed is None:
        return None
    if closed <= start:
        return None
    return (closed - start).total_seconds() / 3600.0


async def priors_need_seed(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count()).select_from(CorridorCausePriorRow))
    return (count or 0) == 0


async def seed_priors_from_csv(session: AsyncSession, csv_path=None) -> dict[str, int]:
    path = csv_path or settings.astram_csv_path
    if not path.exists():
        raise FileNotFoundError(f"ASTraM CSV not found: {path}")

    hour_counts: dict[int, int] = defaultdict(int)
    corridor_cause_rows: list[dict] = []
    cause_rows: dict[str, list[dict]] = defaultdict(list)

    cc_agg: dict[tuple[str, str], list[dict]] = defaultdict(list)

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("event_cause") == "test_demo":
                continue

            cause = _normalize_cause_safe(row.get("event_cause"))
            if not cause:
                continue

            start = parse_datetime(row.get("start_datetime"))
            closed = parse_datetime(row.get("closed_datetime"))
            if start:
                hour_counts[start.astimezone(IST_TZ).hour] += 1

            corridor = row.get("corridor")
            if corridor in ("NULL", "", None):
                corridor = "Non-corridor"

            closure = parse_bool(row.get("requires_road_closure"), default=False)
            ict = _ict_hours(start, closed)

            record = {"closure": closure, "ict": ict}
            cause_rows[cause].append(record)
            cc_agg[(corridor, cause)].append(record)

    # Hour bias weights
    if hour_counts:
        counts = list(hour_counts.values())
        median_count = statistics.median(counts)
        for hour in range(24):
            logged = hour_counts.get(hour, 0)
            if logged == 0:
                weight = BIAS_WEIGHT_MAX
            else:
                weight = median_count / logged
            weight = max(BIAS_WEIGHT_MIN, min(BIAS_WEIGHT_MAX, weight))
            session.add(
                HourBiasWeightRow(hour_ist=hour, logged_count=logged, bias_weight=round(weight, 3))
            )

    # Cause-global priors
    for cause, records in cause_rows.items():
        closures = [r["closure"] for r in records]
        icts = [r["ict"] for r in records if r["ict"] is not None]
        session.add(
            CausePriorRow(
                cause=cause,
                global_closure_rate=round(sum(closures) / len(closures), 4) if closures else 0.083,
                global_median_ict_h=round(statistics.median(icts), 2) if icts else 1.0,
                sample_count=len(records),
            )
        )

    # Corridor×cause priors
    for (corridor, cause), records in cc_agg.items():
        closures = [r["closure"] for r in records]
        icts = [r["ict"] for r in records if r["ict"] is not None]
        session.add(
            CorridorCausePriorRow(
                corridor=corridor,
                cause=cause,
                closure_rate=round(sum(closures) / len(closures), 4) if closures else 0.083,
                median_ict_h=round(statistics.median(icts), 2) if icts else 1.0,
                sample_count=len(records),
            )
        )
        corridor_cause_rows.append({"corridor": corridor, "cause": cause})

    await session.commit()
    return {
        "hour_weights": 24,
        "corridor_cause_priors": len(corridor_cause_rows),
        "cause_priors": len(cause_rows),
        "source": str(path),
        "seeded_at": datetime.now(UTC).isoformat(),
    }
