import logging

from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from app.core.device_registry import registry

logger = logging.getLogger(__name__)
ws_router = APIRouter()


@ws_router.websocket("/ws/{serial:path}")
async def device_websocket(websocket: WebSocket, serial: str) -> None:
    # Accept first — closing before accept violates the WebSocket handshake protocol
    await websocket.accept()

    if registry.get_device(serial) is None:
        await websocket.close(code=4004, reason="Device not found")
        return

    logger.info("[%s] WebSocket client connected", serial)

    try:
        session = await registry.get_or_create_session(serial)
    except KeyError:
        await websocket.close(code=4004, reason="Device not found")
        return
    except Exception as exc:
        logger.error("[%s] Failed to start session: %s", serial, exc)
        await websocket.close(code=4500, reason="Failed to start scrcpy session")
        return

    await session.add_client(websocket)

    try:
        while True:
            data = await websocket.receive_bytes()
            await session.send_control(data)
    except WebSocketDisconnect:
        logger.info("[%s] WebSocket client disconnected", serial)
    except Exception as exc:
        logger.warning("[%s] WebSocket error: %s", serial, exc)
    finally:
        await session.remove_client(websocket)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
