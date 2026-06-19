"""Barricade and staffing rule helpers."""

VIP_CAUSES = frozenset({"vip_movement"})


def barricade_staging_required(cause: str, p_closure: float, *, threshold: float = 0.35) -> bool:
    if cause in VIP_CAUSES:
        return True
    return p_closure >= threshold


def apply_vip_barricade_floor(cause: str, barricade_count: int) -> int:
    if cause in VIP_CAUSES:
        return max(barricade_count, 12)
    return barricade_count


def severity_ordinal(band: str) -> int:
    return {"Green": 1, "Yellow": 2, "Orange": 3, "Red": 4}.get(band, 2)
