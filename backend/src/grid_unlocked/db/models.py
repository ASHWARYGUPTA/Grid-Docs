from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String, Text, func
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
