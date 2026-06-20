"""M13 — replay buffer construction.

buffer = 0.8 x recent_closed(N weeks) U 0.2 x anchor_sample(stratified)
strata = corridor x cause x peak_flag x is_planned

Recent pool: NormalizedEventRow rows closed within the rolling window, run
through the same feature engineering as the CSV anchor pool (training_core)
so both pools land in one consistent DataFrame.

Anchor pool: a stratified sample of the full ASTraM CSV corpus (the fixed
historical sample the spec calls for — already >= 1,500 records as the full
corpus is 8,170 rows).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.db.models import ApprovalRecordRow, NormalizedEventRow
from grid_unlocked.learning.training_core import build_feature_rows, load_csv_frame

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class BufferResult:
    df: pd.DataFrame
    recent_count: int
    anchor_count: int
    recent_pct: float
    anchor_pct: float
    strata: dict[str, int]
    status: str  # ready | anchor_only
    reject_reason_counts: dict[str, int]


def _strata_key(corridor: str, cause: str, is_peak: bool, is_planned: bool) -> str:
    return f"{corridor}|{cause}|peak={int(is_peak)}|planned={int(is_planned)}"


async def _load_recent_pool(session: AsyncSession, window_weeks: int) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(weeks=window_weeks)
    rows = (
        await session.scalars(
            select(NormalizedEventRow)
            .where(NormalizedEventRow.status == "closed")
            .where(NormalizedEventRow.closed_datetime.is_not(None))
            .where(NormalizedEventRow.closed_datetime >= cutoff)
        )
    ).all()

    out: list[dict] = []
    for row in rows:
        # SQLite (aiosqlite) round-trips datetimes as naive; Postgres keeps
        # tzinfo. Normalize to UTC-aware here so this pool's `start` column
        # is comparable/sortable against the CSV anchor pool's tz-aware
        # timestamps once concatenated.
        start = row.start_datetime
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        closed = row.closed_datetime
        if closed is not None and closed.tzinfo is None:
            closed = closed.replace(tzinfo=UTC)

        ict = None
        if closed and start and closed > start:
            ict = (closed - start).total_seconds() / 3600.0
        out.append(
            {
                "cause": row.event_cause,
                "corridor": row.corridor or "Non-corridor",
                "is_planned": row.is_planned,
                "closure": int(row.requires_road_closure),
                "duration_h": ict if ict is not None else float("nan"),
                "event_observed": int(ict is not None),
                "veh_type": row.veh_type,
                "start": start,
                "event_id": row.event_id,
                "pool": "recent",
            }
        )
    return out


async def reject_reason_counts(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.scalars(
            select(ApprovalRecordRow.reason_code).where(ApprovalRecordRow.action == "reject")
        )
    ).all()
    counts: dict[str, int] = {}
    for reason in rows:
        key = reason or "unspecified"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _stratified_anchor_sample(anchor_df: pd.DataFrame, *, target_count: int) -> pd.DataFrame:
    """Stratified sample over corridor x cause x peak x planned, sized to
    exactly target_count (or the full anchor pool if smaller).

    Allocates each stratum a proportional share of target_count (largest-
    remainder method, no per-stratum minimum-of-1 floor) so the total never
    overshoots target_count regardless of how many strata exist.
    """
    if target_count >= len(anchor_df):
        return anchor_df

    anchor_df = anchor_df.copy()
    anchor_df["_strata"] = anchor_df.apply(
        lambda r: _strata_key(r["corridor"], r["cause"], bool(r["is_peak_hour"]), bool(r["is_planned"])),
        axis=1,
    )

    sizes = anchor_df.groupby("_strata").size()
    frac = target_count / len(anchor_df)
    raw_quota = sizes * frac
    quota = raw_quota.apply(lambda x: int(x)).clip(upper=sizes)
    shortfall = target_count - int(quota.sum())
    if shortfall > 0:
        remainders = (raw_quota - quota).sort_values(ascending=False)
        for strata_key in remainders.index:
            if shortfall <= 0:
                break
            if quota[strata_key] < sizes[strata_key]:
                quota[strata_key] += 1
                shortfall -= 1

    parts = []
    for strata_key, n in quota.items():
        if n <= 0:
            continue
        group = anchor_df[anchor_df["_strata"] == strata_key]
        parts.append(group.sample(n=int(n), random_state=42))

    sampled = pd.concat(parts, ignore_index=True) if parts else anchor_df.iloc[0:0]
    return sampled.drop(columns="_strata").reset_index(drop=True)


async def build_buffer(
    session: AsyncSession,
    *,
    window_weeks: int = 4,
    anchor_min_records: int = 1500,
) -> BufferResult:
    recent_rows = await _load_recent_pool(session, window_weeks)
    recent_df = build_feature_rows(recent_rows) if recent_rows else pd.DataFrame()

    anchor_full = load_csv_frame(settings.astram_csv_path)

    recent_count = len(recent_df)
    status = "ready"

    if recent_count == 0:
        # No incidents closed yet through the live system — fall back to
        # 100% anchor rather than failing; nothing to retrain on beyond the
        # static corpus, but the endpoint must still succeed.
        anchor_count = max(anchor_min_records, len(anchor_full))
        anchor_sample = _stratified_anchor_sample(anchor_full, target_count=anchor_count)
        combined = anchor_sample
        recent_pct = 0.0
        anchor_pct = 100.0
        status = "anchor_only"
    else:
        # Size the anchor pool so it lands at ~20% of the combined buffer,
        # respecting the configured floor.
        target_anchor = max(anchor_min_records, round(recent_count * 0.25))
        anchor_sample = _stratified_anchor_sample(anchor_full, target_count=target_anchor)
        combined = pd.concat([recent_df, anchor_sample], ignore_index=True)
        anchor_count = len(anchor_sample)
        recent_pct = round(100.0 * recent_count / len(combined), 2)
        anchor_pct = round(100.0 * anchor_count / len(combined), 2)

    strata: dict[str, int] = {}
    for _, r in combined.iterrows():
        key = _strata_key(r["corridor"], r["cause"], bool(r["is_peak_hour"]), bool(r["is_planned"]))
        strata[key] = strata.get(key, 0) + 1

    reject_counts = await reject_reason_counts(session)

    return BufferResult(
        df=combined,
        recent_count=recent_count,
        anchor_count=anchor_count,
        recent_pct=recent_pct,
        anchor_pct=anchor_pct,
        strata=strata,
        status=status,
        reject_reason_counts=reject_counts,
    )
