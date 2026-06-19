from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GRID_", env_file=".env", extra="ignore")

    app_name: str = "Grid Unlocked"
    database_url: str = "sqlite+aiosqlite:///./grid_unlocked.db"
    redis_url: str = "redis://localhost:6379/0"
    astram_csv_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "data" / "astram_events.csv"
    )

    # Bengaluru bounding box (PRD / M01)
    bbox_lat_min: float = 12.8
    bbox_lat_max: float = 13.3
    bbox_lon_min: float = 77.3
    bbox_lon_max: float = 77.8

    planned_max_duration_hours: float = 72.0

    models_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "models" / "v1"
    )
    closure_alert_threshold: float = 0.35

    gcdh_lambda: float = 0.35
    gcdh_k: float = 0.15
    gcdh_epsilon: float = 0.02
    gcdh_max_hops: int = 5
    gcdh_tier2_max_hops: int = 2

    hotspot_dbscan_eps_rad: float = 0.005
    hotspot_dbscan_min_samples: int = 5
    hotspot_observed_cache_ttl: int = 300
    hotspot_forecast_cache_ttl: int = 21600
    hotspot_cusum_sigma: float = 3.0

    dispatch_milp_deadline_ms: int = 1500
    dispatch_total_deadline_ms: int = 1800
    dispatch_alpha_eta: float = 1.0
    dispatch_beta_rci: float = 0.4
    dispatch_gamma_centrality: float = 0.25
    dispatch_delta_cascade: float = 0.35
    dispatch_eta_heavy_tow: float = 0.5
    dispatch_alpha_uncovered_risk: float = 1.0
    dispatch_avg_speed_kmh: float = 30.0
    dispatch_roster_cache_ttl_s: int = 60
    dispatch_bias_hours: tuple[int, ...] = (14, 15, 16, 17, 18)
    dispatch_bias_max_multiplier: float = 3.0

    diversion_k_default: int = 3
    diversion_max_hops: int = 5

    governance_tier: str = "1"
    governance_shadow_mode: bool = True
    recommendation_skeleton_sla_ms: int = 350
    recommendation_complete_sla_ms: int = 1800

    @property
    def uses_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
