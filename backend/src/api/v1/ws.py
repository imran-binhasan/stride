"""Real-Time WebSocket Collaboration Endpoints."""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from src.core.exceptions import AuthenticationError
from src.core.security import decode_access_token
from src.core.websockets import room_authorized, ws_manager

logger = logging.getLogger("a3zen.ws")
router = APIRouter(prefix="/ws", tags=["RealTime WebSockets"])


@router.websocket("/realtime")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Bearer access token"),
) -> None:
    """Real-time bi-directional WebSocket connection for Kanban/Cursor sync and Presence."""
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        org_id = payload.get("org_id", "default")
        if not user_id:
            await websocket.close(code=4001, reason="Missing user identity in token")
            return
    except AuthenticationError as e:
        await websocket.close(code=4001, reason=e.message)
        return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(websocket, user_id=user_id, org_id=org_id)

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                action = msg.get("action")

                if action == "join_room":
                    room_name = msg.get("room")
                    if room_name and not room_authorized(room_name, org_id):
                        await websocket.send_text(
                            json.dumps({"type": "ERROR", "error": "Room not authorized for your organization"})
                        )
                    elif room_name:
                        ws_manager.join_room(websocket, room_name)
                        await websocket.send_text(
                            json.dumps({"type": "ROOM_JOINED", "room": room_name})
                        )

                elif action == "leave_room":
                    room_name = msg.get("room")
                    if room_name:
                        ws_manager.leave_room(websocket, room_name)
                        await websocket.send_text(
                            json.dumps({"type": "ROOM_LEFT", "room": room_name})
                        )

                elif action == "broadcast":
                    room_name = msg.get("room")
                    event_type = msg.get("event", "GENERIC_EVENT")
                    data = msg.get("data", {})
                    if room_name and not room_authorized(room_name, org_id):
                        await websocket.send_text(
                            json.dumps({"type": "ERROR", "error": "Room not authorized for your organization"})
                        )
                    elif room_name:
                        await ws_manager.broadcast_to_room(
                            room_name=room_name,
                            event_type=event_type,
                            payload=data,
                            org_id=org_id,
                            sender_ws=websocket,
                        )

                elif action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON frame"}))

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket unhandled exception: %s", e)
        await ws_manager.disconnect(websocket)
