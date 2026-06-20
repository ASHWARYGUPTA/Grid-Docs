"""M13 — ReplayLearningService schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RetrainTrigger(StrEnum):
    SCHEDULED = "scheduled"
    DRIFT = "drift"
    MANUAL = "manual"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    EVAL_COMPLETE = "eval_complete"
    PROMOTED = "promoted"
    FAILED = "failed"


class ModelStage(StrEnum):
    STAGED = "staged"
    PRODUCTION = "production"
    RETIRED = "retired"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RetrainRequest(BaseModel):
    trigger: RetrainTrigger = RetrainTrigger.MANUAL


class PromoteRequest(BaseModel):
    operator_id: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RetrainResponse(BaseModel):
    job_id: str
    status: JobStatus
    trigger: RetrainTrigger
    model_version: str | None = None
    message: str


class LatestJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    trigger: RetrainTrigger
    model_version: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class BufferManifestResponse(BaseModel):
    job_id: str
    status: str  # building | ready | anchor_only | failed
    recent_count: int
    anchor_count: int
    recent_pct: float
    anchor_pct: float
    window_weeks: int
    strata: dict[str, int] = Field(default_factory=dict)
    reject_reason_counts: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class EvalResponse(BaseModel):
    job_id: str
    model_version: str
    accuracy: float
    anchor_accuracy: float
    incumbent_anchor_accuracy: float | None
    anchor_regression: float | None
    gate_passed: bool
    anchor_stable: bool
    accuracy_gate: float
    anchor_epsilon: float


class PromoteResponse(BaseModel):
    model_version: str
    promoted: bool
    closure_version: str
    ict_version: str
    message: str
