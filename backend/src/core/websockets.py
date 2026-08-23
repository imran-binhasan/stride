"""Real-Time WebSocket Connection Manager and Redis Pub/Sub Multiplexer.

Scalability note: cross-worker fan-out is sharded by organization. A worker subscribes
only to the Redis channels (``ws:org:{org_id}``) for orgs it currently holds sockets for,
so a broadcast is only deserialized by workers that can actually deliver it — instead of
every worker receiving every message (the old ``ws:*`` pattern). All Redis pub/sub
operations run on a single listener task; connect/disconnect enqueue subscription changes
rather than touching the shared pubsub concurrently.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import WebSocket
from src.core.redis import RedisPubSubManager, get_redis

logger = logging.getLogger("a3zen.websockets")

# A channel that always has at least one subscriber so the poll loop stays live.
WS_CONTROL_CHANNEL = "ws:__control__"


def org_channel(org_id: str) -> str:
    return f"ws:org:{org_id}"


def room_authorized(room_name: str, org_id: str) -> bool:
    """A client may only join/broadcast to rooms scoped to its own organization.

    Rooms follow the convention ``...:org:{org_id}:...`` (e.g. ``room:org:<id>:project:<id>``).
    The org id must appear as a whole ``:``-delimited segment — a substring match would let
    org ``abc`` reach a room of org ``abcd``.
    """
    if not room_name or not org_id:
        return False
    return f":org:{org_id}:" in f":{room_name}:"


class ConnectionManager:
    """Manages active WebSocket connections, room subscriptions, and Redis message distribution."""

    def __init__(self) -> None:
        # Map: room_name -> set of WebSocket instances
        self.rooms: dict[str, set[WebSocket]] = {}
        # Map: WebSocket -> user info & subscribed rooms
        self.client_meta: dict[WebSocket, dict[str, Any]] = {}
        self.pubsub_task: asyncio.Task | None = None
        self.redis_manager = RedisPubSubManager()
        # Unique id per worker process, used to drop echoes of our own published messages.
        self.worker_id = uuid.uuid4().hex
        # Per-org local socket ref-counts; subscribe on 0->1, unsubscribe on 1->0.
        self._org_refcounts: dict[str, int] = {}
        # Subscription-change requests processed by the (single) listener task.
        self._sub_queue: asyncio.Queue[tuple[str, str]] | None = None
        self._pubsub = None

    async def connect(self, websocket: WebSocket, user_id: str, org_id: str) -> None:
        await websocket.accept()
        self.client_meta[websocket] = {
            "user_id": user_id,
            "org_id": org_id,
            "rooms": set(),
        }
        self._retain_org(org_id)
        logger.info("WebSocket connected: user=%s org=%s", user_id, org_id)

    async def disconnect(self, websocket: WebSocket) -> None:
        meta = self.client_meta.pop(websocket, None)
        if meta:
            for room in meta.get("rooms", set()):
                if room in self.rooms:
                    self.rooms[room].discard(websocket)
                    if not self.rooms[room]:
                        del self.rooms[room]
            org_id = meta.get("org_id")
            if org_id:
                self._release_org(org_id)
        logger.info("WebSocket disconnected")

    def _retain_org(self, org_id: str) -> None:
        count = self._org_refcounts.get(org_id, 0) + 1
        self._org_refcounts[org_id] = count
        if count == 1 and self._sub_queue is not None:
            self._sub_queue.put_nowait(("subscribe", org_channel(org_id)))

    def _release_org(self, org_id: str) -> None:
        count = self._org_refcounts.get(org_id, 0) - 1
        if count <= 0:
            self._org_refcounts.pop(org_id, None)
            if self._sub_queue is not None:
                self._sub_queue.put_nowait(("unsubscribe", org_channel(org_id)))
        else:
            self._org_refcounts[org_id] = count

    def join_room(self, websocket: WebSocket, room_name: str) -> None:
        if websocket not in self.client_meta:
            return
        if room_name not in self.rooms:
            self.rooms[room_name] = set()
        self.rooms[room_name].add(websocket)
        self.client_meta[websocket]["rooms"].add(room_name)

    def leave_room(self, websocket: WebSocket, room_name: str) -> None:
        if room_name in self.rooms:
            self.rooms[room_name].discard(websocket)
            if not self.rooms[room_name]:
                del self.rooms[room_name]
        if websocket in self.client_meta:
            self.client_meta[websocket]["rooms"].discard(room_name)

    async def _local_deliver(
        self, room_name: str, json_str: str, exclude: WebSocket | None = None
    ) -> None:
        """Deliver a serialized message to all sockets in a room within this process.

        Sends run concurrently so one slow client cannot stall delivery to the rest.
        """
        if room_name not in self.rooms:
            return
        targets = [ws for ws in list(self.rooms[room_name]) if ws != exclude]
        if not targets:
            return

        results = await asyncio.gather(
            *(ws.send_text(json_str) for ws in targets), return_exceptions=True
        )
        for ws, result in zip(targets, results, strict=True):
            if isinstance(result, Exception):
                await self.disconnect(ws)

    async def broadcast_to_room(
        self,
        room_name: str,
        event_type: str,
        payload: dict[str, Any],
        org_id: str,
        sender_ws: WebSocket | None = None,
    ) -> None:
        """Broadcast an event to all clients in a room (excluding an optional sender)."""
        client_message = json.dumps(
            {"room": room_name, "event": event_type, "data": payload}
        )

        # 1. Local delivery to active sockets in this process.
        await self._local_deliver(room_name, client_message, exclude=sender_ws)

        # 2. Publish to this org's channel so other workers holding the org deliver locally.
        #    The origin worker id lets subscribers drop the echo of their own message.
        try:
            envelope = json.dumps(
                {
                    "origin": self.worker_id,
                    "room": room_name,
                    "event": event_type,
                    "data": payload,
                }
            )
            await self.redis_manager.publish(org_channel(org_id), envelope)
        except Exception as e:
            logger.debug("Redis pub/sub publish skipped: %s", e)

    async def _drain_subscription_changes(self) -> None:
        assert self._sub_queue is not None and self._pubsub is not None
        while not self._sub_queue.empty():
            op, channel = self._sub_queue.get_nowait()
            try:
                if op == "subscribe":
                    await self._pubsub.subscribe(channel)
                else:
                    await self._pubsub.unsubscribe(channel)
            except Exception as e:
                logger.debug("Pub/sub %s %s failed: %s", op, channel, e)

    async def _pubsub_listener(self) -> None:
        """Single task owning all pub/sub ops: apply subscription changes, then poll messages."""
        try:
            while True:
                await self._drain_subscription_changes()
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.5
                )
                if not message or message.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(message["data"])
                except (ValueError, TypeError):
                    continue
                # Echo prevention: skip messages this worker itself published.
                if envelope.get("origin") == self.worker_id:
                    continue
                room_name = envelope.get("room")
                if not room_name:
                    continue
                client_message = json.dumps(
                    {
                        "room": room_name,
                        "event": envelope.get("event", "GENERIC_EVENT"),
                        "data": envelope.get("data", {}),
                    }
                )
                await self._local_deliver(room_name, client_message)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("WebSocket pub/sub listener stopped: %s", e)

    async def start(self) -> None:
        """Start the background Redis pub/sub listener (idempotent)."""
        if self.pubsub_task is not None and not self.pubsub_task.done():
            return
        self._sub_queue = asyncio.Queue()
        client = await get_redis()
        self._pubsub = client.pubsub()
        await self._pubsub.subscribe(WS_CONTROL_CHANNEL)
        # Re-subscribe to any orgs already held (e.g. after a restart of the listener).
        for org_id in self._org_refcounts:
            self._sub_queue.put_nowait(("subscribe", org_channel(org_id)))
        self.pubsub_task = asyncio.create_task(self._pubsub_listener())

    async def stop(self) -> None:
        """Cancel the background Redis pub/sub listener."""
        if self.pubsub_task is not None:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except (asyncio.CancelledError, Exception):
                pass
            self.pubsub_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None


ws_manager = ConnectionManager()
