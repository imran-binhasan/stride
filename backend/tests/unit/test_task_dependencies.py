"""Unit tests for task dependency DAG validation and cycle prevention."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import ConflictException
from src.models.auth import OrgRole
from src.repositories.user_repo import UserRepository
from src.schemas.project import ProjectCreate
from src.schemas.task import DependencyCreate, TaskCreate
from src.services.project_service import ProjectService
from src.services.task_service import TaskService


@pytest.mark.asyncio
async def test_dependency_cycle_detection(db_session: AsyncSession):
    # Setup test org and project
    user_repo = UserRepository(db_session)
    user = await user_repo.create_user(
        email="dev@dag.io", hashed_password="pw", full_name="DAG Dev"
    )
    org = await user_repo.create_organization(name="DAG Labs", slug="dag-labs")
    await user_repo.add_org_member(org.id, user.id, OrgRole.ORG_OWNER)
    ws = await user_repo.create_workspace(org.id, "Main")

    proj_service = ProjectService(db_session)
    project = await proj_service.create_project(
        org_id=org.id,
        payload=ProjectCreate(workspace_id=ws.id, name="Engine", key="ENG"),
    )

    task_service = TaskService(db_session)
    # Create 3 tasks: A, B, C
    tA = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task A")
    )
    tB = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task B")
    )
    tC = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task C")
    )

    # Link A -> B (A blocks B)
    await task_service.add_dependency(tA.id, org.id, DependencyCreate(successor_id=tB.id))

    # Link B -> C (B blocks C)
    await task_service.add_dependency(tB.id, org.id, DependencyCreate(successor_id=tC.id))

    # Attempting to link C -> A should trigger cycle detection and raise ConflictException!
    with pytest.raises(ConflictException) as exc_info:
        await task_service.add_dependency(tC.id, org.id, DependencyCreate(successor_id=tA.id))

    assert (
        "deadlock" in str(exc_info.value.message).lower()
        or "cycle" in str(exc_info.value.message).lower()
    )


@pytest.mark.asyncio
async def test_self_dependency_raises_conflict(db_session: AsyncSession):
    user_repo = UserRepository(db_session)
    user = await user_repo.create_user(
        email="self@dag.io", hashed_password="pw", full_name="Self Dev"
    )
    org = await user_repo.create_organization(name="Self Labs", slug="self-labs")
    ws = await user_repo.create_workspace(org.id, "Main")

    proj_service = ProjectService(db_session)
    project = await proj_service.create_project(
        org_id=org.id,
        payload=ProjectCreate(workspace_id=ws.id, name="Self", key="SLF"),
    )

    task_service = TaskService(db_session)
    t = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task 1")
    )

    with pytest.raises(ConflictException):
        await task_service.add_dependency(t.id, org.id, DependencyCreate(successor_id=t.id))
