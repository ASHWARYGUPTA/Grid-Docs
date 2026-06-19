"""Pre-indexed planned event templates — MVP 5 causes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from grid_unlocked.features.temporal import cyclical_temporal
from grid_unlocked.planned.schemas import ChecklistItem, TemplateDefinition

MVP_CAUSES = frozenset({"construction", "public_event", "procession", "vip_movement", "protest"})


def _checklist(cause: str) -> list[ChecklistItem]:
    common = [
        ChecklistItem(id="perm-notify", category="compliance", description="Verify BBMP/BTP permit on file"),
        ChecklistItem(id="station-brief", category="ops", description="Brief jurisdictional police station"),
        ChecklistItem(id="vms-notify", category="comms", description="Pre-stage VMS advisory text (M11 stub)"),
    ]
    cause_specific = {
        "construction": [
            ChecklistItem(id="lane-mark", category="traffic", description="Mark lane closure geometry"),
            ChecklistItem(id="tow-standby", category="ops", description="Heavy tow on standby"),
        ],
        "vip_movement": [
            ChecklistItem(id="vip-route", category="security", description="Seal VIP route approaches"),
            ChecklistItem(id="escort-coord", category="security", description="Coordinate escort motorcade slots"),
        ],
        "procession": [
            ChecklistItem(id="crowd-mgmt", category="ops", description="Crowd management plan at halting points"),
        ],
        "public_event": [
            ChecklistItem(id="venue-access", category="ops", description="Venue ingress/egress traffic plan"),
        ],
        "protest": [
            ChecklistItem(id="de-escalation", category="ops", description="De-escalation liaison assigned"),
        ],
    }
    return common + cause_specific.get(cause, [])


@dataclass(frozen=True)
class TemplateSeed:
    template_id: str
    cause: str
    corridor: str | None
    dow_mask: tuple[int, ...]
    hour_bin: str
    duration_class: str
    staffing_min: int
    staffing_max: int
    barricade_count: int
    barricade_matrix_ref: str
    deployment_lead_time_hours: int


TEMPLATE_SEEDS: list[TemplateSeed] = [
    TemplateSeed(
        "construction_mysore_road_weekend",
        "construction",
        "Mysore Road",
        (5, 6),
        "morning",
        "24-48h",
        3,
        8,
        8,
        "dual_carriageway_full",
        12,
    ),
    TemplateSeed(
        "construction_generic",
        "construction",
        None,
        tuple(range(7)),
        "any",
        "24-48h",
        3,
        8,
        6,
        "dual_carriageway_partial",
        12,
    ),
    TemplateSeed(
        "vip_movement_generic",
        "vip_movement",
        None,
        tuple(range(7)),
        "any",
        "0-24h",
        8,
        20,
        16,
        "vip_route",
        24,
    ),
    TemplateSeed(
        "procession_generic",
        "procession",
        None,
        tuple(range(7)),
        "any",
        "4-12h",
        6,
        15,
        8,
        "single_carriageway_full",
        18,
    ),
    TemplateSeed(
        "public_event_generic",
        "public_event",
        None,
        tuple(range(7)),
        "any",
        "4-12h",
        4,
        12,
        6,
        "single_carriageway_partial",
        12,
    ),
    TemplateSeed(
        "protest_generic",
        "protest",
        None,
        tuple(range(7)),
        "any",
        "4-12h",
        6,
        15,
        10,
        "dual_carriageway_full",
        18,
    ),
]


def hour_bin(hour_ist: int) -> str:
    if 5 <= hour_ist < 12:
        return "morning"
    if 12 <= hour_ist < 17:
        return "afternoon"
    if 17 <= hour_ist < 22:
        return "evening"
    return "night"


def duration_class(hours: float | None) -> str:
    if hours is None:
        return "unknown"
    if hours <= 24:
        return "0-24h"
    if hours <= 48:
        return "24-48h"
    return "48-72h"


def _score_template(
    seed: TemplateSeed,
    *,
    cause: str,
    corridor: str | None,
    dow: int,
    hour: str,
    duration: str,
) -> float:
    if seed.cause != cause:
        return -1.0
    score = 10.0
    if seed.corridor and seed.corridor == corridor:
        score += 5.0
    elif seed.corridor is None:
        score += 1.0
    if dow in seed.dow_mask:
        score += 2.0
    if seed.hour_bin == hour or seed.hour_bin == "any":
        score += 1.5
    if seed.duration_class == duration or seed.duration_class == "unknown":
        score += 1.0
    return score


def match_template(
    *,
    cause: str,
    corridor: str | None,
    start_datetime: datetime,
    estimated_duration_h: float | None,
) -> tuple[TemplateSeed, bool]:
    temporal = cyclical_temporal(start_datetime)
    hour = hour_bin(temporal["hour_ist"])
    dur = duration_class(estimated_duration_h)

    best: TemplateSeed | None = None
    best_score = -1.0
    for seed in TEMPLATE_SEEDS:
        s = _score_template(
            seed,
            cause=cause,
            corridor=corridor,
            dow=temporal["dow"],
            hour=hour,
            duration=dur,
        )
        if s > best_score:
            best_score = s
            best = seed

    if best is None:
        fallback = TEMPLATE_SEEDS[1]  # construction_generic as last resort shape
        return fallback, True
    low_conf = best_score < 12.0 or cause not in MVP_CAUSES
    return best, low_conf


def seed_to_definition(seed: TemplateSeed) -> TemplateDefinition:
    return TemplateDefinition(
        template_id=seed.template_id,
        cause=seed.cause,
        corridor=seed.corridor,
        dow_mask=list(seed.dow_mask),
        hour_bin=seed.hour_bin,
        duration_class=seed.duration_class,
        staffing_min=seed.staffing_min,
        staffing_max=seed.staffing_max,
        barricade_count=seed.barricade_count,
        barricade_matrix_ref=seed.barricade_matrix_ref,
        deployment_lead_time_hours=seed.deployment_lead_time_hours,
        checklist=_checklist(seed.cause),
    )


def get_template_by_cause(cause: str) -> TemplateDefinition | None:
    for seed in TEMPLATE_SEEDS:
        if seed.cause == cause:
            return seed_to_definition(seed)
    return None
