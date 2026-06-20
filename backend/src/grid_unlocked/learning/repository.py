"""M13 — LearningRepository.

Handles DB reads/writes for replay_buffer_manifests, model_registry, and
learning_jobs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import (
    LearningJobRow,
    ModelRegistryRow,
    ReplayBufferManifestRow,
)


class LearningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # learning_jobs
    # ------------------------------------------------------------------

    async def create_job(self, job_id: str, trigger: str) -> LearningJobRow:
        row = LearningJobRow(job_id=job_id, trigger=trigger, status="running")
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_job(self, job_id: str) -> LearningJobRow | None:
        return await self.session.get(LearningJobRow, job_id)

    async def get_latest_job(self) -> LearningJobRow | None:
        return await self.session.scalar(
            select(LearningJobRow).order_by(LearningJobRow.created_at.desc()).limit(1)
        )

    async def update_job(
        self,
        job_id: str,
        *,
        status: str,
        model_version: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        row = await self.get_job(job_id)
        if not row:
            return
        row.status = status
        if model_version is not None:
            row.model_version = model_version
        if error_detail is not None:
            row.error_detail = error_detail
        if status in {"eval_complete", "promoted", "failed"}:
            row.completed_at = datetime.now(UTC)
        await self.session.commit()

    # ------------------------------------------------------------------
    # replay_buffer_manifests
    # ------------------------------------------------------------------

    async def save_manifest(
        self,
        job_id: str,
        *,
        recent_count: int,
        anchor_count: int,
        recent_pct: float,
        anchor_pct: float,
        strata: dict[str, int],
        window_weeks: int,
        status: str,
    ) -> ReplayBufferManifestRow:
        row = ReplayBufferManifestRow(
            job_id=job_id,
            recent_count=recent_count,
            anchor_count=anchor_count,
            recent_pct=recent_pct,
            anchor_pct=anchor_pct,
            strata_json=json.dumps(strata),
            window_weeks=window_weeks,
            status=status,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_manifest(self, job_id: str) -> ReplayBufferManifestRow | None:
        return await self.session.get(ReplayBufferManifestRow, job_id)

    # ------------------------------------------------------------------
    # model_registry
    # ------------------------------------------------------------------

    async def create_model(
        self,
        *,
        model_version: str,
        job_id: str,
        closure_version: str,
        ict_version: str,
        accuracy: float,
        anchor_accuracy: float,
        artifact_dir: str,
    ) -> ModelRegistryRow:
        row = ModelRegistryRow(
            model_version=model_version,
            job_id=job_id,
            closure_version=closure_version,
            ict_version=ict_version,
            stage="staged",
            accuracy=accuracy,
            anchor_accuracy=anchor_accuracy,
            artifact_dir=artifact_dir,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_model(self, model_version: str) -> ModelRegistryRow | None:
        return await self.session.get(ModelRegistryRow, model_version)

    async def get_production_model(self) -> ModelRegistryRow | None:
        return await self.session.scalar(
            select(ModelRegistryRow).where(ModelRegistryRow.stage == "production").limit(1)
        )

    async def latest_model_version_number(self) -> int:
        rows = (await self.session.scalars(select(ModelRegistryRow.model_version))).all()
        max_n = 1
        for v in rows:
            if v.startswith("v") and v[1:].isdigit():
                max_n = max(max_n, int(v[1:]))
        return max_n

    async def promote_model(self, model_version: str) -> ModelRegistryRow:
        incumbent = await self.get_production_model()
        if incumbent:
            incumbent.stage = "retired"
        row = await self.get_model(model_version)
        row.stage = "production"
        row.promoted_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(row)
        return row
