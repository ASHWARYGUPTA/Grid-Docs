"""BTP station roster proxy — 54-station footprint, MVP active units."""

from __future__ import annotations

import time

from grid_unlocked.dispatch.schemas import DispatchUnit, EquipType, UnitOverride

# Representative Bengaluru stations (subset of 54) with patrol + tow coverage.
_DEFAULT_ROSTER: list[DispatchUnit] = [
    DispatchUnit(
        unit_id="TOW-7",
        station_id="ST-ORR-E",
        station_name="ORR East Traffic",
        equip_type=EquipType.HEAVY_TOW,
        latitude=12.935,
        longitude=77.678,
    ),
    DispatchUnit(
        unit_id="TOW-3",
        station_id="ST-MYS",
        station_name="Mysore Road",
        equip_type=EquipType.HEAVY_TOW,
        latitude=12.914,
        longitude=77.512,
    ),
    DispatchUnit(
        unit_id="PATROL-12",
        station_id="ST-BEL",
        station_name="Bellandur",
        equip_type=EquipType.PATROL,
        latitude=12.926,
        longitude=77.676,
    ),
    DispatchUnit(
        unit_id="PATROL-3",
        station_id="ST-ORR-E",
        station_name="ORR East Traffic",
        equip_type=EquipType.PATROL,
        latitude=12.938,
        longitude=77.682,
    ),
    DispatchUnit(
        unit_id="PATROL-8",
        station_id="ST-CBD",
        station_name="CBD Traffic",
        equip_type=EquipType.PATROL,
        latitude=12.971,
        longitude=77.594,
    ),
    DispatchUnit(
        unit_id="PATROL-21",
        station_id="ST-HOS",
        station_name="Hosur Road",
        equip_type=EquipType.PATROL,
        latitude=12.892,
        longitude=77.608,
    ),
    DispatchUnit(
        unit_id="TRAFFIC-5",
        station_id="ST-MAG",
        station_name="Magadi Road",
        equip_type=EquipType.TRAFFIC,
        latitude=12.987,
        longitude=77.534,
    ),
    DispatchUnit(
        unit_id="TRAFFIC-11",
        station_id="ST-TUM",
        station_name="Tumkur Road",
        equip_type=EquipType.TRAFFIC,
        latitude=13.028,
        longitude=77.548,
    ),
    DispatchUnit(
        unit_id="PATROL-15",
        station_id="ST-BAN",
        station_name="Bannerghata Road",
        equip_type=EquipType.PATROL,
        latitude=12.887,
        longitude=77.597,
    ),
    DispatchUnit(
        unit_id="PATROL-19",
        station_id="ST-OLD-AIR",
        station_name="Old Airport Road",
        equip_type=EquipType.PATROL,
        latitude=12.960,
        longitude=77.647,
    ),
    DispatchUnit(
        unit_id="TOW-11",
        station_id="ST-HOS",
        station_name="Hosur Road",
        equip_type=EquipType.HEAVY_TOW,
        latitude=12.898,
        longitude=77.612,
    ),
    DispatchUnit(
        unit_id="PATROL-27",
        station_id="ST-VAR",
        station_name="Varthur Road",
        equip_type=EquipType.PATROL,
        latitude=12.939,
        longitude=77.749,
    ),
]

_cache: tuple[float, list[DispatchUnit]] | None = None


def default_roster(ttl_s: int = 60) -> tuple[list[DispatchUnit], bool]:
    """Return cached roster; stale=True if TTL exceeded (still served)."""
    global _cache
    now = time.monotonic()
    if _cache is None or now - _cache[0] > ttl_s:
        units = [u.model_copy() for u in _DEFAULT_ROSTER]
        stale = _cache is not None
        _cache = (now, units)
        return units, stale
    return [u.model_copy() for u in _cache[1]], False


def resolve_units(
    overrides: list[UnitOverride] | None,
    ttl_s: int = 60,
) -> tuple[list[DispatchUnit], bool]:
    if overrides:
        units = [
            DispatchUnit(
                unit_id=o.unit_id,
                station_id=o.station_id,
                station_name=o.station_name,
                equip_type=o.equip_type,
                latitude=o.latitude,
                longitude=o.longitude,
            )
            for o in overrides
        ]
        return units, False
    return default_roster(ttl_s)


def reset_roster_cache() -> None:
    global _cache
    _cache = None
