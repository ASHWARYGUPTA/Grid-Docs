"""M11 — Mock VMS Board Registry.

Maps Bengaluru corridors and junctions to a set of VMS board IDs.
In the hackathon, boards are hardcoded here.

DEFERRED D-M11-03: Replace with `vms_board_registry` DB table loaded
from real BTP board data in Phase 1.5. The interface (get_boards_for_corridor)
stays the same — only the backing store changes.

DEFERRED D-M11-04: Commander-specified board_ids in ApproveRequest —
will override corridor-derived boards.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VmsBoard:
    board_id: str
    name: str
    location: str
    endpoint: str  # Phase 1.5: real webhook URL; for now a mock path
    region: str    # used for template formatting


# ---------------------------------------------------------------------------
# Hardcoded Bengaluru VMS board inventory
# Phase 1.5: load from DB table vms_board_registry
# ---------------------------------------------------------------------------
_BOARDS: dict[str, VmsBoard] = {
    "VMS-ORR-E1": VmsBoard("VMS-ORR-E1", "ORR East Entry", "Kadubeesanahalli",
                           "/mock/vms/receive", "orr_east"),
    "VMS-ORR-E2": VmsBoard("VMS-ORR-E2", "ORR East Mid", "Marathahalli Bridge",
                           "/mock/vms/receive", "orr_east"),
    "VMS-WHTFLD-1": VmsBoard("VMS-WHTFLD-1", "Whitefield Entry", "Hoodi Junction",
                              "/mock/vms/receive", "whitefield"),
    "VMS-WHTFLD-2": VmsBoard("VMS-WHTFLD-2", "Whitefield Inner", "ITPL Signal",
                              "/mock/vms/receive", "whitefield"),
    "VMS-KOR-1": VmsBoard("VMS-KOR-1", "Koramangala Inner Ring", "Sony World Jn",
                           "/mock/vms/receive", "koramangala"),
    "VMS-KOR-2": VmsBoard("VMS-KOR-2", "Koramangala Outer", "Agara Lake Jn",
                           "/mock/vms/receive", "koramangala"),
    "VMS-SARJ-1": VmsBoard("VMS-SARJ-1", "Sarjapur Entry", "Carmelaram",
                            "/mock/vms/receive", "sarjapur"),
    "VMS-HSR-1": VmsBoard("VMS-HSR-1", "HSR Layout 27th Main", "BDA Complex",
                           "/mock/vms/receive", "hsr"),
    "VMS-BTM-1": VmsBoard("VMS-BTM-1", "BTM Layout", "Forum Mall Jn",
                           "/mock/vms/receive", "btm"),
    "VMS-BSNK-1": VmsBoard("VMS-BSNK-1", "Banashankari Main", "Anavara Jn",
                            "/mock/vms/receive", "banashankari"),
}

# Corridor keyword → board IDs that should receive the alert
# Phase 1.5: replace with spatial lookup (board geo vs event geo)
_CORRIDOR_BOARDS: dict[str, list[str]] = {
    "ORR East 1": ["VMS-ORR-E1", "VMS-ORR-E2", "VMS-WHTFLD-1"],
    "ORR East 2": ["VMS-ORR-E1", "VMS-ORR-E2", "VMS-KOR-1"],
    "Whitefield": ["VMS-WHTFLD-1", "VMS-WHTFLD-2"],
    "Koramangala": ["VMS-KOR-1", "VMS-KOR-2", "VMS-HSR-1"],
    "Sarjapur": ["VMS-SARJ-1", "VMS-KOR-1"],
    "HSR": ["VMS-HSR-1", "VMS-BTM-1"],
    "Banashankari": ["VMS-BSNK-1", "VMS-BTM-1"],
    "Non-corridor": ["VMS-ORR-E1"],  # fallback
}

# Default boards used when corridor is unknown
_DEFAULT_BOARDS = ["VMS-ORR-E1", "VMS-KOR-1"]


def get_boards_for_corridor(corridor: str | None) -> list[VmsBoard]:
    """Return the VMS boards that should receive alerts for a given corridor."""
    if not corridor:
        board_ids = _DEFAULT_BOARDS
    else:
        # Partial-match to handle corridor suffixes like "ORR East 1", "ORR East 2"
        board_ids = _DEFAULT_BOARDS
        for key, ids in _CORRIDOR_BOARDS.items():
            if key.lower() in (corridor or "").lower() or (corridor or "").lower() in key.lower():
                board_ids = ids
                break

    return [_BOARDS[bid] for bid in board_ids if bid in _BOARDS]


def get_board(board_id: str) -> VmsBoard | None:
    return _BOARDS.get(board_id)


def all_boards() -> list[VmsBoard]:
    return list(_BOARDS.values())
