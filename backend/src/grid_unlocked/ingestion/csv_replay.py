import csv
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.ingestion.normalizer import astram_row_to_payload
from grid_unlocked.ingestion.schemas import IngestSource
from grid_unlocked.ingestion.service import IngestionService


async def replay_astram_csv(
    session: AsyncSession,
    csv_path: Path | None = None,
    limit: int | None = None,
    skip_test_demo: bool = True,
) -> dict[str, int]:
    """Replay historical ASTraM export through the ingestion pipeline (hackathon demo)."""
    path = csv_path or settings.astram_csv_path
    if not path.exists():
        raise FileNotFoundError(f"ASTraM CSV not found: {path}")

    service = IngestionService(session)
    accepted = 0
    rejected = 0

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            if limit is not None and idx >= limit:
                break
            if skip_test_demo and row.get("event_cause") == "test_demo":
                rejected += 1
                continue

            payload = astram_row_to_payload(row)
            result = await service.ingest(payload, source=IngestSource.ASTRAM)
            if isinstance(result, tuple):
                rejected += 1
            else:
                accepted += 1

    return {"accepted": accepted, "rejected": rejected, "source": str(path)}
