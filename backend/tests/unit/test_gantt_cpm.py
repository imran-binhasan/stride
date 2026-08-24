"""Unit tests for Critical Path Method (CPM) calculation on task dependency networks."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.auth import OrgRole
from src.repositories.user_repo import UserRepository
from src.schemas.project import ProjectCreate
from src.schemas.task import DependencyCreate, TaskCreate
from src.services.project_service import ProjectService
from src.services.task_service import TaskService
from src.services.view_service import ViewService


@pytest.mark.asyncio
async def test_cpm_critical_path_calculation(db_session: AsyncSession):
    # Setup test org & project
    user_repo = UserRepository(db_session)
    user = await user_repo.create_user(
        email="cpm@lead.io", hashed_password="pw", full_name="CPM Lead"
    )
    org = await user_repo.create_organization(name="CPM Corp", slug="cpm-corp")
    await user_repo.add_org_member(org.id, user.id, OrgRole.ORG_OWNER)
    ws = await user_repo.create_workspace(org.id, "CPM WS")

    proj_service = ProjectService(db_session)
    project = await proj_service.create_project(
        org_id=org.id,
        payload=ProjectCreate(workspace_id=ws.id, name="CPM Project", key="CPM"),
    )

    task_service = TaskService(db_session)

    # Path 1: A (3 days) -> B (4 days) -> D (2 days) => Total = 9 days (CRITICAL)
    # Path 2: A (3 days) -> C (1 day)  -> D (2 days) => Total = 6 days (FLOAT = 3 on C)
    tA = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task A", story_points=3.0)
    )
    tB = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task B", story_points=4.0)
    )
    tC = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task C", story_points=1.0)
    )
    tD = await task_service.create_task(
        org.id, user.id, TaskCreate(project_id=project.id, title="Task D", story_points=2.0)
    )

    # Link dependencies:
    # A -> B
    await task_service.add_dependency(tA.id, org.id, DependencyCreate(successor_id=tB.id))
    # A -> C
    await task_service.add_dependency(tA.id, org.id, DependencyCreate(successor_id=tC.id))
    # B -> D
    await task_service.add_dependency(tB.id, org.id, DependencyCreate(successor_id=tD.id))
    # C -> D
    await task_service.add_dependency(tC.id, org.id, DependencyCreate(successor_id=tD.id))

    view_service = ViewService(db_session)
    gantt = await view_service.get_gantt_cpm(project.id, org.id)

    # Assertions
    assert gantt.project_duration_days == 9  # 3 + 4 + 2
    assert tA.id in gantt.critical_path
    assert tB.id in gantt.critical_path
    assert tD.id in gantt.critical_path
    assert tC.id not in gantt.critical_path  # C has float!

    # Verify nodes
    node_map = {n.id: n for n in gantt.nodes}
    assert node_map[tA.id].early_start == 0
    assert node_map[tA.id].early_finish == 3
    assert node_map[tA.id].is_critical is True

    assert node_map[tB.id].early_start == 3
    assert node_map[tB.id].early_finish == 7
    assert node_map[tB.id].is_critical is True

    assert node_map[tC.id].early_start == 3
    assert node_map[tC.id].early_finish == 4
    assert node_map[tC.id].total_float == 3  # LF (7) - EF (4) = 3
    assert node_map[tC.id].is_critical is False

    assert node_map[tD.id].early_start == 7
    assert node_map[tD.id].early_finish == 9
    assert node_map[tD.id].is_critical is True
