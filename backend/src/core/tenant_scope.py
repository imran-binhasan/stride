"""Transaction-local tenant context for Postgres RLS; never stored on pooled connections."""

from sqlalchemy import event, text
from sqlalchemy.orm import Session


async def set_tenant_scope(db, org_id):
    # A trusted worker may process several organizations in one transaction.
    # Flush pending writes under the previous scope before switching policies.
    if db.info.get("tenant_org_id") and db.info["tenant_org_id"] != (org_id or ""):
        await db.flush()
    db.info["tenant_org_id"] = org_id or ""
    if db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('stride.org_id', :org_id, true)"), {"org_id": org_id or ""}
        )


@event.listens_for(Session, "after_begin")
def restore_scope(session, transaction, connection):
    # Explicit commits (e.g. OAuth) begin a fresh transaction, so reapply scoped context.
    if connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT set_config('stride.org_id', :org_id, true)"),
            {"org_id": session.info.get("tenant_org_id", "")},
        )
