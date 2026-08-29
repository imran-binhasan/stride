"""Unit tests for the 5-Gate AI Loop Engineering Pipeline."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.task import TaskPriority
from src.repositories.user_repo import UserRepository
from src.schemas.ai import (
    Gate1IngestRequest,
    Gate2ContextRequest,
    Gate3PlanRequest,
    Gate4TDDRequest,
    Gate5ExecutionRequest,
)
from src.schemas.project import ProjectCreate
from src.services.ai_pipeline_service import AIPipelineService
from src.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_gate1_intent_ingestion(db_session: AsyncSession):
    user_repo = UserRepository(db_session)
    await user_repo.create_user(email="ai@test.io", hashed_password="pw", full_name="AI Engineer")
    org = await user_repo.create_organization(name="AI Lab", slug="ai-lab")
    ws = await user_repo.create_workspace(org.id, "AI WS")

    proj_service = ProjectService(db_session)
    project = await proj_service.create_project(
        org_id=org.id,
        payload=ProjectCreate(workspace_id=ws.id, name="AI Project", key="AIP"),
    )

    ai_service = AIPipelineService(db_session)
    g1 = await ai_service.evaluate_gate1_intent(
        org_id=org.id,
        payload=Gate1IngestRequest(
            project_id=project.id,
            feature_prompt="URGENT: Implement OAuth2 Google Login with Refresh Token Rotation",
        ),
    )

    assert g1.passed is True
    assert g1.suggested_priority == TaskPriority.URGENT
    assert len(g1.acceptance_criteria) >= 3
    assert g1.ambiguity_score < 0.20


@pytest.mark.asyncio
async def test_gate2_to_gate5_sequence(db_session: AsyncSession):
    user_repo = UserRepository(db_session)
    await user_repo.create_user(email="ai2@test.io", hashed_password="pw", full_name="AI Dev")
    org = await user_repo.create_organization(name="AI Lab 2", slug="ai-lab-2")
    ws = await user_repo.create_workspace(org.id, "WS 2")

    proj_service = ProjectService(db_session)
    project = await proj_service.create_project(
        org_id=org.id,
        payload=ProjectCreate(workspace_id=ws.id, name="Core App", key="COR"),
    )

    ai_service = AIPipelineService(db_session)

    # Gate 2
    g2 = await ai_service.evaluate_gate2_context(
        org_id=org.id,
        payload=Gate2ContextRequest(project_id=project.id, feature_title="Webhooks Engine"),
    )
    assert g2.passed is True
    assert g2.project_key == "COR"
    assert g2.context_token_estimate < 32000

    # Gate 3
    g3 = await ai_service.evaluate_gate3_plan(
        payload=Gate3PlanRequest(project_id=project.id, feature_title="Webhooks Engine"),
    )
    assert g3.passed is True
    assert len(g3.plan_dag) == 5
    assert g3.is_acyclic is True

    # Gate 4
    g4 = await ai_service.evaluate_gate4_tdd(
        payload=Gate4TDDRequest(feature_title="Webhooks Engine", plan_dag=g3.plan_dag),
    )
    assert g4.passed is True
    assert "test_webhooks_engine_lifecycle" in g4.test_function_names

    # Gate 5
    g5 = await ai_service.evaluate_gate5_execution(
        payload=Gate5ExecutionRequest(
            feature_title="Webhooks Engine",
            test_module_code=g4.generated_test_module,
        )
    )
    assert g5.passed is True
    assert g5.coverage_percent >= 90.0
