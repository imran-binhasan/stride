"""Authenticated project-scoped realtime collaboration."""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.core.database import async_session_factory
from src.core.exceptions import AuthenticationError
from src.core.rbac import AuthContext, explicit_project_ids
from src.core.security import decode_access_token
from src.core.tenant_scope import set_tenant_scope
from src.core.websockets import room_authorized, ws_manager
from src.models.auth import MemberStatus, OrgMember, OrgRole, User, Workspace
from src.models.client import ClientContact
from src.models.project import Project
from src.models.task import Task

logger = logging.getLogger("a3zen.ws")
router = APIRouter(prefix="/ws", tags=["RealTime WebSockets"])


async def socket_identity(token, selected_org=None):
    payload = decode_access_token(token)
    org_id = selected_org or payload.get("org_id")
    async with async_session_factory() as db:
        user = await db.scalar(
            select(User).where(User.id == payload.get("sub"), User.is_active.is_(True))
        )
        member = await db.scalar(
            select(OrgMember).where(
                OrgMember.user_id == payload.get("sub"),
                OrgMember.org_id == org_id,
                OrgMember.status == MemberStatus.ACTIVE,
            )
        )
        if not user or not org_id or not (member or user.is_superadmin):
            raise AuthenticationError("Active organization membership is required")
        await set_tenant_scope(db, org_id)
        ctx = AuthContext(
            user=user,
            org_id=org_id,
            role=member.role if member else OrgRole.ORG_OWNER,
            is_superadmin=user.is_superadmin,
        )
        if ctx.role == OrgRole.CLIENT:
            contact = await db.scalar(
                select(ClientContact)
                .where(
                    ClientContact.user_id == user.id,
                    ClientContact.org_id == org_id,
                    ClientContact.is_active.is_(True),
                )
                .options(selectinload(ClientContact.project_access))
            )
            ctx.project_ids = (
                frozenset(a.project_id for a in contact.project_access) if contact else frozenset()
            )
        if ctx.role == OrgRole.CLIENT:
            ctx.project_ids = ctx.project_ids | await explicit_project_ids(db, user.id, org_id)
        return ctx


async def can_join(room, ctx):
    if not isinstance(room, str) or not room_authorized(room, ctx.org_id):
        return False
    prefix = f"room:org:{ctx.org_id}:"
    if not room.startswith(prefix):
        return False
    parts = room[len(prefix) :].split(":")
    if len(parts) != 2:
        return False
    kind, identifier = parts
    async with async_session_factory() as db:
        await set_tenant_scope(db, ctx.org_id)
        if kind == "project":
            exists = await db.scalar(
                select(Project.id).where(Project.id == identifier, Project.org_id == ctx.org_id)
            )
            return bool(exists) and ctx.can_access_project(identifier)
        if kind == "task":
            project_id = await db.scalar(
                select(Task.project_id).where(Task.id == identifier, Task.org_id == ctx.org_id)
            )
            return bool(project_id) and ctx.can_access_project(project_id)
        if kind == "workspace" and ctx.role != OrgRole.CLIENT:
            return bool(
                await db.scalar(
                    select(Workspace.id).where(
                        Workspace.id == identifier, Workspace.org_id == ctx.org_id
                    )
                )
            )
    return False


@router.websocket("/realtime")
async def websocket_endpoint(
    websocket: WebSocket, token: str = Query(...), org_id: str | None = None
):
    try:
        ctx = await socket_identity(token, org_id)
    except AuthenticationError as error:
        await websocket.close(code=4001, reason=error.message)
        return
    await ws_manager.connect(websocket, ctx.user.id, ctx.org_id)
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode()) > 65536:
                await websocket.close(code=1009, reason="Message too large")
                break
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError("Message must be an object")
            except ValueError:
                await websocket.send_json({"type": "ERROR", "error": "Invalid JSON object"})
                continue
            # Recheck expiration, membership and grants so suspension/revocation is honored.
            try:
                ctx = await socket_identity(token, org_id)
            except AuthenticationError as error:
                await websocket.close(code=4001, reason=error.message)
                break
            action, room = msg.get("action"), msg.get("room")
            if action == "ping":
                await websocket.send_json({"type": "pong"})
            elif action in {"join_room", "broadcast"}:
                if not await can_join(room, ctx):
                    await websocket.send_json({"type": "ERROR", "error": "Room not authorized"})
                    continue
                if action == "join_room":
                    ws_manager.join_room(websocket, room)
                    await websocket.send_json({"type": "ROOM_JOINED", "room": room})
                elif room not in ws_manager.client_meta[websocket]["rooms"]:
                    await websocket.send_json(
                        {"type": "ERROR", "error": "Join the room before broadcasting"}
                    )
                elif msg.get("event") not in {
                    "TASK_UPDATED",
                    "TASK_MOVED",
                    "USER_PRESENCE",
                    "CURSOR_MOVED",
                } or not isinstance(msg.get("data", {}), dict):
                    await websocket.send_json({"type": "ERROR", "error": "Unsupported event"})
                else:
                    data = msg.get("data", {})
                    if msg["event"] == "USER_PRESENCE":
                        data = {
                            "user_id": ctx.user.id,
                            "full_name": ctx.user.full_name,
                            "state": "away" if data.get("state") == "away" else "viewing",
                        }
                    await ws_manager.broadcast_to_room(
                        room, msg["event"], data, ctx.org_id, websocket
                    )
            elif action == "leave_room" and isinstance(room, str):
                ws_manager.leave_room(websocket, room)
                await websocket.send_json({"type": "ROOM_LEFT", "room": room})
            else:
                await websocket.send_json({"type": "ERROR", "error": "Unknown action"})
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)
