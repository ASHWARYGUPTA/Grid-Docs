import json
from datetime import UTC, datetime

import h3

from grid_unlocked.features.constants import FEATURE_CACHE_TTL_SECONDS, NAMED_CORRIDORS
from grid_unlocked.features.graph_stub import corridor_centrality, corridor_to_node_id
from grid_unlocked.features.repository import FeatureRepository, veh_complexity_score
from grid_unlocked.features.schemas import FeatureVector
from grid_unlocked.features.temporal import cyclical_temporal
from grid_unlocked.ingestion.schemas import NormalizedEvent


async def materialize_features(
    event: NormalizedEvent,
    repo: FeatureRepository,
) -> FeatureVector:
    temporal = cyclical_temporal(event.start_datetime)
    bias_weight = await repo.get_bias_weight(temporal["hour_ist"])

    closure_rate, median_ict, _, low_conf = await repo.get_corridor_cause_prior(
        event.corridor, event.event_cause
    )
    cause_global = await repo.get_cause_global_median(event.event_cause)

    betweenness, degree_norm, _ = corridor_centrality(event.corridor)
    simultaneous = await repo.count_active_within_km(
        event.latitude, event.longitude, event.event_id
    )

    h3_res7 = h3.latlng_to_cell(event.latitude, event.longitude, 7)
    h3_res9 = h3.latlng_to_cell(event.latitude, event.longitude, 9)

    return FeatureVector(
        event_id=event.event_id,
        graph_node_id=corridor_to_node_id(event.corridor),
        hour_ist=temporal["hour_ist"],
        dow=temporal["dow"],
        hour_sin=temporal["hour_sin"],
        hour_cos=temporal["hour_cos"],
        dow_sin=temporal["dow_sin"],
        dow_cos=temporal["dow_cos"],
        is_peak_hour=temporal["is_peak_hour"],
        is_weekend=temporal["is_weekend"],
        reporting_bias_weight=bias_weight,
        betweenness_norm=betweenness,
        degree_norm=degree_norm,
        h3_res7=h3_res7,
        h3_res9=h3_res9,
        is_named_corridor=event.corridor in NAMED_CORRIDORS if event.corridor else False,
        corridor_cause_closure_rate=closure_rate,
        corridor_cause_median_ict_h=median_ict,
        duration_prior_h=median_ict,
        cause_median_resolution_global_h=cause_global,
        low_confidence_priors=low_conf,
        veh_complexity_score=veh_complexity_score(event.veh_type),
        simultaneous_events_2km=simultaneous,
        materialized_at=datetime.now(UTC),
        cache_hit=False,
    )
