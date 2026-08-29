"""Pydantic v2 schemas for the 5-Gate AI Loop Engineering Pipeline."""

from typing import Any

from pydantic import BaseModel, Field
from src.models.task import TaskPriority


class Gate1IngestRequest(BaseModel):
    project_id: str
    feature_prompt: str = Field(
        min_length=5, description="Natural language feature request or issue description"
    )


class Gate1IngestResponse(BaseModel):
    passed: bool = True
    feature_title: str
    summary: str
    suggested_priority: TaskPriority
    estimated_points: float
    acceptance_criteria: list[str]
    ambiguity_score: float = Field(ge=0.0, le=1.0)


class Gate2ContextRequest(BaseModel):
    project_id: str
    feature_title: str


class Gate2ContextResponse(BaseModel):
    passed: bool = True
    tenant_id: str
    project_key: str
    active_workflow_statuses: list[str]
    context_token_estimate: int
    context_payload: dict[str, Any]


class Gate3PlanRequest(BaseModel):
    project_id: str
    feature_title: str
    acceptance_criteria: list[str] = []


class PlannedTaskNode(BaseModel):
    step_number: int
    title: str
    layer: str  # e.g. "DATABASE", "REPOSITORY", "SERVICE", "ROUTER", "TEST"
    dependencies: list[int] = []


class Gate3PlanResponse(BaseModel):
    passed: bool = True
    plan_dag: list[PlannedTaskNode]
    is_acyclic: bool = True
    risk_assessment: str


class Gate4TDDRequest(BaseModel):
    feature_title: str
    plan_dag: list[PlannedTaskNode] = []
    acceptance_criteria: list[str] = []


class Gate4TDDResponse(BaseModel):
    passed: bool = True
    generated_test_module: str
    test_function_names: list[str]
    assertions_count: int


class Gate5ExecutionRequest(BaseModel):
    feature_title: str
    test_module_code: str


class Gate5ExecutionResponse(BaseModel):
    passed: bool = True
    static_analysis_passed: bool = True
    tests_executed: int
    tests_passed: int
    coverage_percent: float
    summary: str


class FullPipelineExecutionRequest(BaseModel):
    project_id: str
    feature_prompt: str


class FullPipelineExecutionResponse(BaseModel):
    pipeline_success: bool = True
    gate1_intent: Gate1IngestResponse
    gate2_context: Gate2ContextResponse
    gate3_plan: Gate3PlanResponse
    gate4_tdd: Gate4TDDResponse
    gate5_execution: Gate5ExecutionResponse
