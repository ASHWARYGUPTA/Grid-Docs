"""Shared geo helpers for M05."""

from __future__ import annotations

import math

import h3


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def h3_res7(lat: float, lon: float) -> str:
    return h3.latlng_to_cell(lat, lon, 7)


def h3_centroid(h3_cell: str) -> tuple[float, float]:
    lat, lon = h3.cell_to_latlng(h3_cell)
    return lat, lon


def count_within_km(
    lat: float,
    lon: float,
    points: list[tuple[float, float]],
    radius_km: float = 2.0,
) -> int:
    return sum(1 for plat, plon in points if haversine_km(lat, lon, plat, plon) <= radius_km)
