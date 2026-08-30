"""WebSocket room authorization — a client may only join rooms in its own org (H3)."""

import json

from src.core.security import create_access_token
from src.main import create_app
from starlette.testclient import TestClient


def test_ws_rejects_foreign_org_room():
    app = create_app()
    client = TestClient(app)
    token = create_access_token(subject="u1", claims={"org_id": "my-org", "email": "u@test.io"})

    with client.websocket_connect(f"/api/v1/ws/realtime?token={token}") as ws:
        # Foreign org room -> ERROR
        ws.send_text(json.dumps({"action": "join_room", "room": "room:org:other-org:project:p1"}))
        resp = json.loads(ws.receive_text())
        assert resp.get("type") == "ERROR"

        # Own org room -> ROOM_JOINED
        ws.send_text(json.dumps({"action": "join_room", "room": "room:org:my-org:project:p1"}))
        resp = json.loads(ws.receive_text())
        assert resp.get("type") == "ROOM_JOINED"
