"""Unit test for per-org cross-worker WebSocket broadcasting via Redis pub/sub."""

import asyncio
import json

import pytest
from src.core.websockets import ConnectionManager

ROOM = "room:org:acme:project:p1"
OTHER_ROOM = "room:org:evilcorp:project:p9"


class StubWebSocket:
    """Minimal websocket stub that records text frames sent to it."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def accept(self) -> None:
        return None

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


async def _wait_for(condition, timeout: float = 3.0) -> None:
    elapsed = 0.0
    while elapsed < timeout:
        if condition():
            return
        await asyncio.sleep(0.05)
        elapsed += 0.05


@pytest.mark.asyncio
async def test_broadcast_fans_out_across_workers_without_echo():
    worker_a = ConnectionManager()
    worker_b = ConnectionManager()
    await worker_a.start()
    await worker_b.start()

    ws_a = StubWebSocket()
    ws_b = StubWebSocket()
    await worker_a.connect(ws_a, user_id="ua", org_id="acme")
    await worker_b.connect(ws_b, user_id="ub", org_id="acme")
    worker_a.join_room(ws_a, ROOM)
    worker_b.join_room(ws_b, ROOM)

    # Give both listeners time to apply their org subscriptions.
    await asyncio.sleep(0.7)

    try:
        await worker_a.broadcast_to_room(ROOM, "TASK_UPDATED", {"id": "T-1"}, org_id="acme")

        await _wait_for(lambda: len(ws_b.sent) >= 1)
        assert len(ws_b.sent) == 1
        msg = json.loads(ws_b.sent[0])
        assert msg["event"] == "TASK_UPDATED"
        assert msg["data"] == {"id": "T-1"}

        # No echo back to the originating worker's own socket beyond the single local send.
        await asyncio.sleep(0.3)
        assert len(ws_a.sent) == 1
        assert len(ws_b.sent) == 1
    finally:
        await worker_a.stop()
        await worker_b.stop()


@pytest.mark.asyncio
async def test_worker_does_not_receive_other_orgs_broadcasts():
    """A worker holding only org 'acme' must not receive org 'evilcorp' broadcasts."""
    worker_a = ConnectionManager()  # publishes for evilcorp
    worker_b = ConnectionManager()  # only holds acme sockets
    await worker_a.start()
    await worker_b.start()

    ws_b = StubWebSocket()
    await worker_b.connect(ws_b, user_id="ub", org_id="acme")
    worker_b.join_room(ws_b, ROOM)
    await asyncio.sleep(0.7)

    try:
        # Broadcast for a different org entirely.
        await worker_a.broadcast_to_room(
            OTHER_ROOM, "TASK_UPDATED", {"id": "X"}, org_id="evilcorp"
        )
        await asyncio.sleep(0.7)
        assert ws_b.sent == []  # never delivered cross-org
    finally:
        await worker_a.stop()
        await worker_b.stop()
