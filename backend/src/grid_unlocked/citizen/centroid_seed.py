import csv
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.db.models import CorridorCentroidRow


async def centroids_need_seed(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count()).select_from(CorridorCentroidRow))
    return (count or 0) == 0


async def seed_corridor_centroids_from_csv(session: AsyncSession, csv_path=None) -> dict[str, int]:
    path = csv_path or settings.astram_csv_path
    if not path.exists():
        raise FileNotFoundError(f"ASTraM CSV not found: {path}")

    points: dict[str, list[tuple[float, float]]] = defaultdict(list)

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lat_raw, lon_raw = row.get("latitude"), row.get("longitude")
            if not lat_raw or not lon_raw:
                continue
            try:
                lat, lon = float(lat_raw), float(lon_raw)
            except ValueError:
                continue

            corridor = row.get("corridor")
            if corridor in ("NULL", "", None):
                corridor = "Non-corridor"

            points[corridor].append((lat, lon))

    for corridor, coords in points.items():
        mean_lat = sum(c[0] for c in coords) / len(coords)
        mean_lon = sum(c[1] for c in coords) / len(coords)
        session.add(
            CorridorCentroidRow(
                corridor=corridor,
                lat=round(mean_lat, 6),
                lon=round(mean_lon, 6),
                sample_count=len(coords),
            )
        )

    await session.commit()
    return {
        "corridors_seeded": len(points),
        "source": str(path),
        "seeded_at": datetime.now(UTC).isoformat(),
    }
