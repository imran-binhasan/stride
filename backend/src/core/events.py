"""Transactional audit records and post-commit project notifications."""

from src.models.notifications import AuditLog


def record_change(db, org_id, project_id, event, resource_id, actor_id=None, values=None):
    db.add(
        AuditLog(
            org_id=org_id,
            action=event,
            actor_id=actor_id or db.info.get("actor_id"),
            resource_type="task",
            resource_id=resource_id,
            new_values=values,
        )
    )
    db.info.setdefault("project_events", []).append((org_id, project_id, event, resource_id))


async def publish_changes(db):
    import logging

    from src.core.websockets import ws_manager

    for org_id, project_id, event, resource_id in db.info.pop("project_events", []):
        try:
            await ws_manager.broadcast_to_room(
                f"room:org:{org_id}:project:{project_id}",
                event,
                {"resource_id": resource_id},
                org_id,
            )
        except Exception:
            logging.getLogger("stride.events").exception("Post-commit notification failed")
