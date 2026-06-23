import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import NormalizedEventRow, PlannedPackageRow
from grid_unlocked.planned.schemas import PlannedEventPackage


def attributes_hash(
    cause: str,
    corridor: str | None,
    start: datetime,
    end: datetime | None,
) -> str:
    payload = f"{cause}|{corridor}|{start.isoformat()}|{end.isoformat() if end else ''}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class PlannedRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_event(self, event_id: str) -> NormalizedEventRow | None:
        return await self.session.get(NormalizedEventRow, event_id)

    async def get_cached_package(
        self, event_id: str, attr_hash: str
    ) -> PlannedEventPackage | None:
        row = await self.session.get(PlannedPackageRow, event_id)
        if not row or row.attributes_hash != attr_hash:
            return None
        data = json.loads(row.package_json)
        pkg = PlannedEventPackage.model_validate(data)
        pkg.cached = True
        return pkg

    async def save_package(
        self,
        package: PlannedEventPackage,
        attr_hash: str,
    ) -> None:
        payload = package.model_dump(mode="json")
        payload["cached"] = False
        row = await self.session.get(PlannedPackageRow, package.event_id)
        if row:
            row.template_id = package.template_id
            row.attributes_hash = attr_hash
            row.package_json = json.dumps(payload)
            row.generated_at = datetime.now(UTC)
        else:
            self.session.add(
                PlannedPackageRow(
                    event_id=package.event_id,
                    template_id=package.template_id,
                    attributes_hash=attr_hash,
                    package_json=json.dumps(payload),
                    generated_at=datetime.now(UTC),
                )
            )
        await self.session.commit()

    async def list_upcoming_planned(self, hours: int = 72) -> list[NormalizedEventRow]:
        now = datetime.now(UTC)
        horizon = now + timedelta(hours=hours)
        rows = (
            await self.session.scalars(
                select(NormalizedEventRow).where(
                    NormalizedEventRow.is_planned.is_(True),
                    NormalizedEventRow.status == "active",
                    or_(
                        # Case 1: Starts in the future, within the horizon
                        (NormalizedEventRow.start_datetime >= now) &
                        (NormalizedEventRow.start_datetime <= horizon),
                        # Case 2: Currently in progress (started in past, not yet ended)
                        (NormalizedEventRow.start_datetime < now) &
                        ((NormalizedEventRow.end_datetime.is_(None)) | (NormalizedEventRow.end_datetime >= now))
                    ),
                )
            )
        ).all()
        return list(rows)

    async def get_stored_package(self, event_id: str) -> PlannedEventPackage | None:
        row = await self.session.get(PlannedPackageRow, event_id)
        if not row:
            return None
        return PlannedEventPackage.model_validate(json.loads(row.package_json))
