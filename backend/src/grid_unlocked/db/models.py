from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class NormalizedEventRow(Base):
    __tablename__ = "normalized_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    is_planned: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_cause: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    authenticated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    corridor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    junction: Mapped[str | None] = mapped_column(String(256), nullable=True)
    police_station: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)

    requires_road_closure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reporting_lag_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    veh_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    anomaly_flags: Mapped[str | None] = mapped_column(Text, nullable=True)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_normalized_events_corridor", "corridor"),
        Index("ix_normalized_events_status", "status"),
        Index("ix_normalized_events_start_datetime", "start_datetime"),
    )


class IngestRejectRow(Base):
    __tablename__ = "ingest_rejects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HourBiasWeightRow(Base):
    __tablename__ = "hour_bias_weights"

    hour_ist: Mapped[int] = mapped_column(primary_key=True)
    logged_count: Mapped[int] = mapped_column(nullable=False)
    bias_weight: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CorridorCausePriorRow(Base):
    __tablename__ = "corridor_cause_priors"

    corridor: Mapped[str] = mapped_column(String(128), primary_key=True)
    cause: Mapped[str] = mapped_column(String(64), primary_key=True)
    closure_rate: Mapped[float] = mapped_column(Float, nullable=False)
    median_ict_h: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CausePriorRow(Base):
    __tablename__ = "cause_priors"

    cause: Mapped[str] = mapped_column(String(64), primary_key=True)
    global_median_ict_h: Mapped[float] = mapped_column(Float, nullable=False)
    global_closure_rate: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FeatureSnapshotRow(Base):
    __tablename__ = "feature_snapshots"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature_json: Mapped[str] = mapped_column(Text, nullable=False)
    materialized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ImpactScoreRow(Base):
    __tablename__ = "impact_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    p_closure: Mapped[float] = mapped_column(Float, nullable=False)
    ict_p20_h: Mapped[float] = mapped_column(Float, nullable=False)
    ict_p50_h: Mapped[float] = mapped_column(Float, nullable=False)
    ict_p80_h: Mapped[float] = mapped_column(Float, nullable=False)
    rci: Mapped[float] = mapped_column(Float, nullable=False)
    severity_band: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    closure_model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ict_model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    staging_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlannedPackageRow(Base):
    __tablename__ = "planned_packages"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attributes_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    package_json: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DispatchRecommendationRow(Base):
    __tablename__ = "dispatch_recommendations"

    recommendation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    tier_at_decision: Mapped[str] = mapped_column(String(8), nullable=False)
    recommendation_json: Mapped[str] = mapped_column(Text, nullable=False)
    solver_ms: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ActionCardRow(Base):
    __tablename__ = "action_cards"

    card_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    card_json: Mapped[str] = mapped_column(Text, nullable=False)
    skeleton_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApprovalRecordRow(Base):
    __tablename__ = "approval_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    commander_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_codes: Mapped[str | None] = mapped_column(Text, nullable=True)
    shadow_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    execution_enqueued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# M10 — AgenticExecutionBroker tables
# ---------------------------------------------------------------------------


class ExecutionQueueRow(Base):
    """Mutable state-machine row for a pending / in-flight execution command."""

    __tablename__ = "execution_queue"

    execution_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    approval_token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    card_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(String(32), nullable=False)  # dispatch | barricade
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending"
    )  # pending | processing | acknowledged | failed | retrying | dead_letter
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_execution_queue_status", "status"),
        # approval_token index auto-created by column-level index=True
    )


class ExecutionAuditRow(Base):
    """Immutable per-attempt audit record — 7-year retention per spec."""

    __tablename__ = "execution_audit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    approval_token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    card_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    station_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    outcome: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # acknowledged | failed | dead_letter
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # event_id and card_id indexes auto-created by column-level index=True
    )


# ---------------------------------------------------------------------------
# M11 — VMSRouter table
# ---------------------------------------------------------------------------


class VmsDeliveryRow(Base):
    """Per-board delivery state machine row for M11 VMS fanout."""

    __tablename__ = "vms_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    push_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    card_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    board_id: Mapped[str] = mapped_column(String(32), nullable=False)
    board_name: Mapped[str] = mapped_column(String(128), nullable=False)
    board_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending"
    )  # pending | processing | delivered | failed | retrying | dead_letter
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dead_letter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ack_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_vms_deliveries_push_status", "push_id", "status"),
    )


# ---------------------------------------------------------------------------
# M14 — GovernanceConsole tables
# ---------------------------------------------------------------------------


class GovernanceStateRow(Base):
    """Singleton (id=1) — current tier + shadow mode, the durable source of
    truth backing the in-process cache read by get_governance()."""

    __tablename__ = "governance_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, default=1)
    tier: Mapped[str] = mapped_column(String(8), nullable=False, default="1")
    shadow_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TierTransitionRow(Base):
    """Immutable audit log — every tier change, automatic or manual."""

    __tablename__ = "tier_transitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_tier: Mapped[str] = mapped_column(String(8), nullable=False)
    to_tier: Mapped[str] = mapped_column(String(8), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # null = automatic
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_tier_transitions_created_at", "created_at"),
    )


class DrillResultRow(Base):
    """Nightly synthetic cascade drill outcomes."""

    __tablename__ = "drill_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    drill_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# M13 — ReplayLearningService tables
# ---------------------------------------------------------------------------


class ReplayBufferManifestRow(Base):
    """80/20 replay buffer composition report for one retrain job."""

    __tablename__ = "replay_buffer_manifests"

    job_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    recent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anchor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recent_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    anchor_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    strata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    window_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="building"
    )  # building | ready | anchor_only | failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModelRegistryRow(Base):
    """Staged -> production -> retired lifecycle for trained model artifacts."""

    __tablename__ = "model_registry"

    model_version: Mapped[str] = mapped_column(String(48), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    closure_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ict_version: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(
        String(16), nullable=False, default="staged"
    )  # staged | production | retired
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    anchor_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    artifact_dir: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_model_registry_stage", "stage"),
    )


class LearningJobRow(Base):
    """One retrain job — buffer -> train -> eval -> (promote) lifecycle."""

    __tablename__ = "learning_jobs"

    job_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)  # scheduled | drift | manual
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )  # pending | running | eval_complete | promoted | failed
    model_version: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# M17 — CitizenReportService tables
# ---------------------------------------------------------------------------


class CorridorCentroidRow(Base):
    """One mean lat/lon per corridor, seeded once from astram_events.csv."""

    __tablename__ = "corridor_centroids"

    corridor: Mapped[str] = mapped_column(String(128), primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CitizenReportRow(Base):
    """Citizen-submitted report — snap result, ICT quote snapshot, verification state."""

    __tablename__ = "citizen_reports"

    report_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_source: Mapped[str] = mapped_column(String(16), nullable=False)  # device | exif
    h3_cell: Mapped[str] = mapped_column(String(16), nullable=False)
    corridor: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    junction: Mapped[str | None] = mapped_column(String(256), nullable=True)

    cause_hint: Mapped[str] = mapped_column(String(64), nullable=False)
    cause_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    ict_p50: Mapped[float] = mapped_column(Float, nullable=False)
    ict_p80: Mapped[float] = mapped_column(Float, nullable=False)
    p_closure: Mapped[float] = mapped_column(Float, nullable=False)
    ict_quote_source: Mapped[str] = mapped_column(String(24), nullable=False)  # m03_live | corridor_prior_fallback

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    reject_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_citizen_reports_status", "status"),
        Index("ix_citizen_reports_h3_cell", "h3_cell"),
    )


class CorridorSubscriptionRow(Base):
    """user_ref subscribed to a set of corridors and/or H3 cells for pre-alerts."""

    __tablename__ = "corridor_subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    corridors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    h3_cells_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_corridor_subscriptions_active", "active"),
    )


# ---------------------------------------------------------------------------
# M16 — FieldOfficerApp tables
# ---------------------------------------------------------------------------


class FieldClosureRow(Base):
    """Officer-submitted closure resource labels — report of record for M13."""

    __tablename__ = "field_closures"

    closure_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    barricades_used: Mapped[int] = mapped_column(Integer, nullable=False)
    officers_used: Mapped[int] = mapped_column(Integer, nullable=False)
    diversion_activated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    officer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FieldAcknowledgementRow(Base):
    """One ack per dispatch recommendation — upsert keyed by recommendation_id."""

    __tablename__ = "field_acknowledgements"

    recommendation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    officer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# M12 — TransitImpactService tables
# ---------------------------------------------------------------------------


class TransitImpactCacheRow(Base):
    """Per-event cached TransitImpactIndex payload, TTL checked at read-time."""

    __tablename__ = "transit_impact_cache"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
