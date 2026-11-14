"""Platform operator directory; never exposes password hashes or session tokens."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.exceptions import EntityNotFoundException, PermissionDeniedException
from src.core.rbac import get_current_user
from src.models.auth import Organization, OrgMember, User
from src.services.notification_service import NotificationService

router = APIRouter(prefix="/platform", tags=["Platform administration"])
DB = Annotated[AsyncSession, Depends(get_db_session)]


async def operator(user: Annotated[User, Depends(get_current_user)]):
    if not user.is_superadmin:
        raise PermissionDeniedException("Platform administrator access required")
    return user


Operator = Annotated[User, Depends(operator)]


@router.get("/summary")
async def summary(user: Operator, db: DB):
    return {
        "organizations": await db.scalar(select(func.count()).select_from(Organization)),
        "users": await db.scalar(select(func.count()).select_from(User)),
        "active_users": await db.scalar(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        ),
    }


@router.get("/organizations")
async def organizations(
    user: Operator,
    db: DB,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = list(
        await db.scalars(
            select(Organization)
            .order_by(Organization.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return [
        {
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "tier": o.subscription_tier,
            "created_at": o.created_at,
        }
        for o in rows
    ]


@router.get("/users")
async def users(
    user: Operator,
    db: DB,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = list(
        await db.scalars(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    )
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "is_superadmin": u.is_superadmin,
        }
        for u in rows
    ]


class UserState(BaseModel):
    is_active: bool
    reason: str = Field(min_length=5, max_length=1000)


@router.patch("/users/{user_id}")
async def set_user_state(user_id: str, payload: UserState, actor: Operator, db: DB):
    target = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not target:
        raise EntityNotFoundException("User", user_id)
    if target.is_superadmin:
        raise PermissionDeniedException("Platform administrator accounts require the operator CLI")
    target.is_active = payload.is_active
    orgs = list(await db.scalars(select(OrgMember.org_id).where(OrgMember.user_id == target.id)))
    from src.core.tenant_scope import set_tenant_scope

    for org_id in orgs:
        await set_tenant_scope(db, org_id)
        await NotificationService(db).log_audit(
            org_id,
            "platform.user_state",
            actor.id,
            "user",
            target.id,
            new_values={"is_active": payload.is_active, "reason": payload.reason},
        )
    await db.flush()
    return {"id": target.id, "is_active": target.is_active}
