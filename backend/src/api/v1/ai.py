"""5-Gate AI Loop Engineering API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.schemas.ai import (
    FullPipelineExecutionRequest,
    FullPipelineExecutionResponse,
    Gate1IngestRequest,
    Gate1IngestResponse,
    Gate2ContextRequest,
    Gate2ContextResponse,
    Gate3PlanRequest,
    Gate3PlanResponse,
    Gate4TDDRequest,
    Gate4TDDResponse,
    Gate5ExecutionRequest,
    Gate5ExecutionResponse,
)
from src.services.ai_pipeline_service import AIPipelineService

router = APIRouter(prefix="/ai", tags=["AI Engineering Pipeline"])


@router.post("/pipeline/gate1-intent", response_model=Gate1IngestResponse)
async def evaluate_gate1_intent(
    payload: Gate1IngestRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.AI_USE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Gate1IngestResponse:
    return await AIPipelineService(db).evaluate_gate1_intent(org_id=ctx.org_id, payload=payload)


@router.post("/pipeline/gate2-context", response_model=Gate2ContextResponse)
async def evaluate_gate2_context(
    payload: Gate2ContextRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.AI_USE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Gate2ContextResponse:
    return await AIPipelineService(db).evaluate_gate2_context(org_id=ctx.org_id, payload=payload)


@router.post("/pipeline/gate3-plan", response_model=Gate3PlanResponse)
async def evaluate_gate3_plan(
    payload: Gate3PlanRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.AI_USE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Gate3PlanResponse:
    return await AIPipelineService(db).evaluate_gate3_plan(payload=payload)


@router.post("/pipeline/gate4-tdd", response_model=Gate4TDDResponse)
async def evaluate_gate4_tdd(
    payload: Gate4TDDRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.AI_USE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Gate4TDDResponse:
    return await AIPipelineService(db).evaluate_gate4_tdd(payload=payload)


@router.post("/pipeline/gate5-execute", response_model=Gate5ExecutionResponse)
async def evaluate_gate5_execution(
    payload: Gate5ExecutionRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.AI_USE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Gate5ExecutionResponse:
    return await AIPipelineService(db).evaluate_gate5_execution(payload=payload)


@router.post("/pipeline/run-all", response_model=FullPipelineExecutionResponse)
async def run_full_ai_pipeline(
    payload: FullPipelineExecutionRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.AI_PIPELINE_FULL))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FullPipelineExecutionResponse:
    return await AIPipelineService(db).run_full_pipeline(org_id=ctx.org_id, payload=payload)
