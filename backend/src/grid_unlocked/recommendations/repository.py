import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import ActionCardRow, ApprovalRecordRow, NormalizedEventRow
from grid_unlocked.recommendations.schemas import ActionCard, CardStatus


class RecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_card(self, card: ActionCard) -> None:
        existing = await self.session.get(ActionCardRow, card.card_id)
        payload = card.model_dump_json()
        if existing:
            existing.event_id = card.event_id
            existing.status = card.status.value
            existing.card_json = payload
            existing.skeleton_ms = card.skeleton_ms
            existing.latency_ms = card.latency_ms
            existing.updated_at = datetime.now(UTC)
        else:
            self.session.add(
                ActionCardRow(
                    card_id=card.card_id,
                    event_id=card.event_id,
                    status=card.status.value,
                    card_json=payload,
                    skeleton_ms=card.skeleton_ms,
                    latency_ms=card.latency_ms,
                )
            )
        await self.session.commit()

    async def get_card(self, card_id: str) -> ActionCard | None:
        row = await self.session.get(ActionCardRow, card_id)
        if not row:
            return None
        return ActionCard.model_validate(json.loads(row.card_json))

    async def get_card_by_event(self, event_id: str) -> ActionCard | None:
        row = await self.session.scalar(
            select(ActionCardRow)
            .where(ActionCardRow.event_id == event_id)
            .order_by(ActionCardRow.created_at.desc())
            .limit(1)
        )
        if not row:
            return None
        return ActionCard.model_validate(json.loads(row.card_json))

    async def list_active_events(self, limit: int = 50) -> list[NormalizedEventRow]:
        rows = (
            await self.session.scalars(
                select(NormalizedEventRow)
                .where(NormalizedEventRow.status == "active")
                .order_by(NormalizedEventRow.start_datetime.desc())
                .limit(limit)
            )
        ).all()
        return list(rows)

    async def save_approval(
        self,
        card_id: str,
        action: str,
        commander_id: str,
        *,
        reason_code: str | None = None,
        notes: str | None = None,
        override_codes: list[str] | None = None,
        shadow_mode: bool = False,
        execution_enqueued: bool = False,
    ) -> str:
        token = f"APPR-{card_id[-8:]}-{int(datetime.now(UTC).timestamp())}"
        self.session.add(
            ApprovalRecordRow(
                card_id=card_id,
                action=action,
                commander_id=commander_id,
                reason_code=reason_code,
                notes=notes,
                override_codes=json.dumps(override_codes or []),
                shadow_mode=shadow_mode,
                execution_enqueued=execution_enqueued,
                approval_token=token,
            )
        )
        await self.session.commit()
        return token

    async def update_status(self, card_id: str, status: CardStatus) -> ActionCard | None:
        row = await self.session.get(ActionCardRow, card_id)
        if not row:
            return None
        card = ActionCard.model_validate(json.loads(row.card_json))
        updated = card.model_copy(update={"status": status, "updated_at": datetime.now(UTC)})
        row.status = status.value
        row.card_json = updated.model_dump_json()
        row.updated_at = datetime.now(UTC)
        await self.session.commit()
        return updated
