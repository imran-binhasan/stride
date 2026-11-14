"""Integration tests for Real-Time WebSockets (connection, room subscription, ping/pong, and broadcast)."""

import json

import pytest
from src.core.security import create_access_token
from src.main import create_app
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_websocket_realtime_connection(ws_identity):
    app = create_app()
    client = TestClient(app)

    token = create_access_token(
        subject=ws_identity["user_id"],
        claims={"org_id": ws_identity["org_id"]},
    )

    own_room = f"room:org:{ws_identity['org_id']}:project:{ws_identity['project']['id']}"
    with client.websocket_connect(f"/api/v1/ws/realtime?token={token}") as ws:
        # Test ping / pong
        ws.send_text(json.dumps({"action": "ping"}))
        response = json.loads(ws.receive_text())
        assert response.get("type") == "pong"

        # Test join room
        ws.send_text(json.dumps({"action": "join_room", "room": own_room}))
        join_resp = json.loads(ws.receive_text())
        assert join_resp.get("type") == "ROOM_JOINED"
        assert join_resp.get("room") == own_room

        # Test leave room
        ws.send_text(json.dumps({"action": "leave_room", "room": own_room}))
        leave_resp = json.loads(ws.receive_text())
        assert leave_resp.get("type") == "ROOM_LEFT"


def test_websocket_invalid_token_closed():
    app = create_app()
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws/realtime?token=invalid_token"):
            pass
