"""M08 diversion atlas — delegates to DiversionService (backward compat for M06 imports)."""

from grid_unlocked.diversions.service import DiversionService
from grid_unlocked.planned.schemas import DiversionRef


def diversion_refs_for_corridor(corridor: str | None, *, limit: int = 3) -> list[DiversionRef]:
    return DiversionService.refs_for_corridor(corridor, limit=limit)
