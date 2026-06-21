from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from grid_unlocked.dashboard.bus import dashboard_bus

router = APIRouter(tags=["dashboard"])


@router.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    dashboard_bus.register(websocket)
    try:
        while True:
            # Clients only receive deltas; any inbound message is ignored
            # (kept open so the server can detect disconnects).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        dashboard_bus.unregister(websocket)
