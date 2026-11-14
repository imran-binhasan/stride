"""Serialize quota-consuming operations per organization."""

from sqlalchemy import func, select
from src.core.exceptions import ConflictException, EntityNotFoundException
from src.models.auth import MemberStatus, Organization, OrgMember
from src.models.project import Project, ProjectStatus


async def reserve_capacity(db, org_id, resource):
    org = await db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
    if not org:
        raise EntityNotFoundException("Organization", org_id)
    if resource == "members":
        count = await db.scalar(
            select(func.count())
            .select_from(OrgMember)
            .where(
                OrgMember.org_id == org_id,
                OrgMember.status.in_(
                    [MemberStatus.ACTIVE, MemberStatus.PENDING, MemberStatus.SUSPENDED]
                ),
            )
        )
        maximum = org.max_members
    else:
        count = await db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.org_id == org_id, Project.status != ProjectStatus.ARCHIVED)
        )
        maximum = org.max_projects
    if count >= maximum:
        raise ConflictException(f"This organization has reached its {resource} limit ({maximum})")
