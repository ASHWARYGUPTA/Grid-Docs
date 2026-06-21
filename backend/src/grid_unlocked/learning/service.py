"""M13 — LearningService.

Orchestrates: build replay buffer -> train closure + Cox PH models ->
evaluate against the 94% accuracy gate + anchor-regression check -> stage a
new model_registry row -> (on promote) flip to production and reload M03's
registry.

D-M13-01: No MLflow — joblib + metadata.json sidecar, same as M03's existing
artifact convention. D-M13-02: training runs synchronously in-request (no
background job queue exists in the repo); measured ~3-5s for a full-corpus
retrain, well within request timeouts. D-M13-03: trigger=scheduled|drift is
accepted and recorded on the job row, but only an explicit API call actually
executes a retrain — no scheduler/drift-monitor exists (same precedent as
M14's on-demand-only cascade drills).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import joblib
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.learning.buffer import build_buffer
from grid_unlocked.learning.buffer import reject_reason_counts as buffer_reject_reason_counts
from grid_unlocked.learning.evaluation import evaluate
from grid_unlocked.learning.repository import LearningRepository
from grid_unlocked.learning.schemas import (
    BufferManifestResponse,
    EvalResponse,
    JobStatus,
    LatestJobResponse,
    PromoteResponse,
    RetrainResponse,
    RetrainTrigger,
)
from grid_unlocked.learning.training_core import (
    apply_encoders,
    build_encoders,
    train_closure_model,
    train_cox_model,
)
from grid_unlocked.recommendations.governance import get_governance


class LearningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LearningRepository(session)

    async def start_retrain(self, trigger: RetrainTrigger) -> RetrainResponse:
        gov = get_governance()
        if gov.tier == "3":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="M13 retrain disabled in Tier 3 continuity mode — model frozen until recovery.",
            )

        job_id = f"JOB-{uuid.uuid4().hex[:12].upper()}"
        await self.repo.create_job(job_id, trigger.value)

        try:
            buffer = await build_buffer(
                self.session,
                window_weeks=settings.learning_recent_window_weeks,
                anchor_min_records=settings.learning_anchor_min_records,
            )
            await self.repo.save_manifest(
                job_id,
                recent_count=buffer.recent_count,
                anchor_count=buffer.anchor_count,
                recent_pct=buffer.recent_pct,
                anchor_pct=buffer.anchor_pct,
                strata=buffer.strata,
                window_weeks=settings.learning_recent_window_weeks,
                status=buffer.status,
            )

            encoders = build_encoders(buffer.df)
            df = apply_encoders(buffer.df, encoders)

            closure_model, calibrator, importances, val_df, _train_df = train_closure_model(
                df, temporal_split=True
            )
            cox_model = train_cox_model(df)

            incumbent = await self.repo.get_production_model()
            incumbent_anchor_accuracy = incumbent.anchor_accuracy if incumbent else None

            eval_result = evaluate(
                closure_model,
                calibrator,
                val_df,
                df,
                incumbent_anchor_accuracy=incumbent_anchor_accuracy,
            )

            next_n = await self.repo.latest_model_version_number() + 1
            model_version = f"v{next_n}"
            artifact_dir = settings.models_dir.parent / model_version
            artifact_dir.mkdir(parents=True, exist_ok=True)

            joblib.dump(closure_model, artifact_dir / "closure_model.joblib")
            joblib.dump(calibrator, artifact_dir / "closure_calibrator.joblib")
            joblib.dump(cox_model, artifact_dir / "cox_model.joblib")
            joblib.dump(encoders, artifact_dir / "encoders.joblib")

            closure_version = f"lgbm-{model_version}"
            ict_version = f"cox-ph-{model_version}"
            metadata = {
                "closure_version": closure_version,
                "ict_version": ict_version,
                "source": "ml",
                "trained_at": datetime.now(UTC).isoformat(),
                "training_rows": len(df),
                "closure_positive_rate": round(float(df["closure"].mean()), 4),
                "job_id": job_id,
            }
            (artifact_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

            ranked = sorted(importances.items(), key=lambda x: x[1], reverse=True)
            fi = {k: round(v, 4) for k, v in ranked}
            (artifact_dir / "feature_importance.json").write_text(json.dumps(fi, indent=2))

            await self.repo.create_model(
                model_version=model_version,
                job_id=job_id,
                closure_version=closure_version,
                ict_version=ict_version,
                accuracy=eval_result.accuracy,
                anchor_accuracy=eval_result.anchor_accuracy,
                artifact_dir=str(artifact_dir),
            )
            await self.repo.update_job(
                job_id, status=JobStatus.EVAL_COMPLETE.value, model_version=model_version
            )

            return RetrainResponse(
                job_id=job_id,
                status=JobStatus.EVAL_COMPLETE,
                trigger=trigger,
                model_version=model_version,
                message=(
                    f"Retrain complete — model {model_version} staged "
                    f"(accuracy={eval_result.accuracy:.4f}, gate_passed={eval_result.gate_passed})"
                ),
            )
        except Exception as exc:
            await self.repo.update_job(job_id, status=JobStatus.FAILED.value, error_detail=str(exc))
            raise

    async def get_latest_job(self) -> LatestJobResponse:
        job = await self.repo.get_latest_job()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No retrain jobs have run yet"
            )
        return LatestJobResponse(
            job_id=job.job_id,
            status=JobStatus(job.status),
            trigger=RetrainTrigger(job.trigger),
            model_version=job.model_version,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    async def get_manifest(self, job_id: str) -> BufferManifestResponse:
        row = await self.repo.get_manifest(job_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Manifest for job {job_id} not found"
            )
        # Reject reason counts aren't persisted on the manifest row itself
        # (display-only signal, not training input) — re-derived live.
        reject_counts = await buffer_reject_reason_counts(self.session)

        return BufferManifestResponse(
            job_id=job_id,
            status=row.status,
            recent_count=row.recent_count,
            anchor_count=row.anchor_count,
            recent_pct=row.recent_pct,
            anchor_pct=row.anchor_pct,
            window_weeks=row.window_weeks,
            strata=json.loads(row.strata_json),
            reject_reason_counts=reject_counts,
            created_at=row.created_at,
        )

    async def get_eval(self, job_id: str) -> EvalResponse:
        job = await self.repo.get_job(job_id)
        if not job or not job.model_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No completed evaluation for job {job_id}",
            )
        model = await self.repo.get_model(job.model_version)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {job.model_version} not found",
            )

        incumbent = await self.repo.get_production_model()
        incumbent_anchor_accuracy = (
            incumbent.anchor_accuracy if incumbent and incumbent.model_version != model.model_version else None
        )
        anchor_regression = (
            round(incumbent_anchor_accuracy - model.anchor_accuracy, 4)
            if incumbent_anchor_accuracy is not None
            else None
        )
        anchor_stable = (
            anchor_regression <= settings.learning_anchor_epsilon
            if anchor_regression is not None
            else True
        )

        return EvalResponse(
            job_id=job_id,
            model_version=model.model_version,
            accuracy=model.accuracy,
            anchor_accuracy=model.anchor_accuracy,
            incumbent_anchor_accuracy=incumbent_anchor_accuracy,
            anchor_regression=anchor_regression,
            gate_passed=model.accuracy >= settings.learning_accuracy_gate,
            anchor_stable=anchor_stable,
            accuracy_gate=settings.learning_accuracy_gate,
            anchor_epsilon=settings.learning_anchor_epsilon,
        )

    async def promote(self, model_version: str, operator_id: str) -> PromoteResponse:
        gov = get_governance()
        if gov.tier in {"2", "3"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"M13 promotion disabled in Tier {gov.tier} — eval only, no promotion.",
            )

        model = await self.repo.get_model(model_version)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_version} not found"
            )
        if model.stage != "staged":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Model {model_version} is '{model.stage}' — only staged models can be promoted",
            )

        eval_result = await self.get_eval_for_model(model)
        if not eval_result.gate_passed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Promotion blocked: accuracy {eval_result.accuracy:.4f} "
                    f"< gate {settings.learning_accuracy_gate}"
                ),
            )
        if not eval_result.anchor_stable:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Promotion blocked: anchor slice regressed {eval_result.anchor_regression:.4f} "
                    f"> epsilon {settings.learning_anchor_epsilon} (anti-catastrophic-forgetting gate)"
                ),
            )

        promoted = await self.repo.promote_model(model_version)
        job = await self.repo.get_job(model.job_id)
        if job:
            await self.repo.update_job(job.job_id, status=JobStatus.PROMOTED.value)

        from grid_unlocked.impact.registry import registry

        registry.reload(models_dir=Path(promoted.artifact_dir))

        return PromoteResponse(
            model_version=model_version,
            promoted=True,
            closure_version=promoted.closure_version,
            ict_version=promoted.ict_version,
            message=f"Model {model_version} promoted to production by {operator_id}",
        )

    async def get_eval_for_model(self, model) -> EvalResponse:
        job = await self.repo.get_job(model.job_id)
        return await self.get_eval(job.job_id)

