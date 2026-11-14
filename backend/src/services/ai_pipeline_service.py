"""5-Gate AI Context & Loop Engineering execution service."""

import ast
import json
import logging
import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.llm import complete_json
from src.models.task import TaskPriority
from src.repositories.project_repo import ProjectRepository
from src.repositories.task_repo import TaskRepository
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
    PlannedTaskNode,
)

logger = logging.getLogger("a3zen.ai")


class AIPipelineService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.task_repo = TaskRepository(db)

    # -------------------------------------------------------------
    # GATE 1: Intent & Scope Ingestion
    # -------------------------------------------------------------
    async def evaluate_gate1_intent(
        self, org_id: str, payload: Gate1IngestRequest
    ) -> Gate1IngestResponse:
        project = await self.project_repo.get_by_id(payload.project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", payload.project_id)

        prompt = payload.feature_prompt.strip()

        # Try a real LLM for genuine intent understanding; fall back to heuristics if every
        # configured provider fails / is rate-limited / is unset.
        llm_result = await self._gate1_llm(project.name, prompt)
        if llm_result is not None:
            return llm_result
        return self._gate1_heuristic(project.name, prompt)

    async def _gate1_llm(self, project_name: str, prompt: str) -> Gate1IngestResponse | None:
        system = (
            "You are a senior product manager. Convert a raw feature request into a "
            "structured task. Respond ONLY with a JSON object with keys: "
            "feature_title (string, <=8 words), suggested_priority "
            "(one of URGENT, HIGH, MEDIUM, LOW), estimated_points (number 1-13), "
            "acceptance_criteria (array of 2-5 Gherkin-style strings), "
            "ambiguity_score (number 0.0-1.0, higher = more ambiguous)."
        )
        user = f"Project: {project_name}\nFeature request: {prompt}"
        data = await complete_json(system, user)
        if not data:
            return None
        try:
            priority = TaskPriority(str(data["suggested_priority"]).upper())
            criteria = [str(c) for c in data.get("acceptance_criteria", []) if str(c).strip()]
            ambiguity = max(0.0, min(1.0, float(data.get("ambiguity_score", 0.1))))
            points = max(1.0, min(13.0, float(data.get("estimated_points", 3))))
            title = str(data["feature_title"]).strip()
            if not title or not criteria:
                return None
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Gate1 LLM output invalid, falling back to heuristic: %s", e)
            return None

        return Gate1IngestResponse(
            passed=ambiguity < 0.20,
            feature_title=title,
            summary=prompt,
            suggested_priority=priority,
            estimated_points=points,
            acceptance_criteria=criteria,
            ambiguity_score=ambiguity,
        )

    def _gate1_heuristic(self, project_name: str, prompt: str) -> Gate1IngestResponse:
        words = prompt.split()
        title = " ".join(words[:6]).title()

        # Priority extraction heuristic
        p_lower = prompt.lower()
        if "urgent" in p_lower or "blocker" in p_lower or "critical" in p_lower:
            priority = TaskPriority.URGENT
        elif "high" in p_lower or "important" in p_lower:
            priority = TaskPriority.HIGH
        elif "low" in p_lower or "nice to have" in p_lower:
            priority = TaskPriority.LOW
        else:
            priority = TaskPriority.MEDIUM

        # Story points estimation heuristic
        points = 5.0 if len(words) > 20 else 3.0

        # Structured Gherkin criteria
        criteria = [
            f"Given an authenticated user in project '{project_name}'",
            f"When the user interacts with the '{title}' feature",
            "Then the system validates input constraints and processes the request successfully",
            "And broadcasts state updates across real-time WebSockets if applicable",
        ]

        ambiguity_score = 0.05 if len(words) >= 5 else 0.40

        return Gate1IngestResponse(
            passed=ambiguity_score < 0.20,
            feature_title=title,
            summary=prompt,
            suggested_priority=priority,
            estimated_points=points,
            acceptance_criteria=criteria,
            ambiguity_score=ambiguity_score,
        )

    # -------------------------------------------------------------
    # GATE 2: Context Gathering & State Vectorization
    # -------------------------------------------------------------
    async def evaluate_gate2_context(
        self, org_id: str, payload: Gate2ContextRequest
    ) -> Gate2ContextResponse:
        project = await self.project_repo.get_by_id(payload.project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", payload.project_id)

        tasks = await self.task_repo.list_by_project(project.id, org_id=org_id)

        context_data = {
            "organization_id": org_id,
            "project_id": project.id,
            "project_key": project.key,
            "project_name": project.name,
            "workflow_statuses": [s.name for s in project.statuses],
            "existing_task_count": len(tasks),
            "target_feature": payload.feature_title,
            "supported_views": ["kanban", "calendar", "gantt", "table"],
            "security_context": {"tenant_scoped": True, "rbac_enabled": True},
        }

        # Estimate context token footprint
        json_str = str(context_data)
        token_estimate = max(100, int(len(json_str) / 4))

        return Gate2ContextResponse(
            passed=token_estimate < 32000,
            tenant_id=org_id,
            project_key=project.key,
            active_workflow_statuses=[s.name for s in project.statuses],
            context_token_estimate=token_estimate,
            context_payload=context_data,
        )

    # -------------------------------------------------------------
    # GATE 3: Task Decomposition & Plan Validation
    # -------------------------------------------------------------
    async def evaluate_gate3_plan(self, payload: Gate3PlanRequest) -> Gate3PlanResponse:
        nodes = [
            PlannedTaskNode(
                step_number=1,
                title=f"Define SQLAlchemy Model for {payload.feature_title}",
                layer="DATABASE",
                dependencies=[],
            ),
            PlannedTaskNode(
                step_number=2,
                title="Implement Repository & CRUD operations",
                layer="REPOSITORY",
                dependencies=[1],
            ),
            PlannedTaskNode(
                step_number=3,
                title="Implement Pure Business Logic Service Layer",
                layer="SERVICE",
                dependencies=[2],
            ),
            PlannedTaskNode(
                step_number=4,
                title="Create FastAPI APIRouter Endpoints & Pydantic Schemas",
                layer="ROUTER",
                dependencies=[3],
            ),
            PlannedTaskNode(
                step_number=5,
                title="Author Pytest Async Unit & Integration Test Suite",
                layer="TEST",
                dependencies=[4],
            ),
        ]

        return Gate3PlanResponse(
            passed=True,
            plan_dag=nodes,
            is_acyclic=True,
            risk_assessment="Low risk - standard domain-driven layered architecture",
        )

    # -------------------------------------------------------------
    # GATE 4: TDD Test Specification & Mock Suite Generation
    # -------------------------------------------------------------
    async def evaluate_gate4_tdd(self, payload: Gate4TDDRequest) -> Gate4TDDResponse:
        data = await complete_json(
            "Write a pytest module implementing the supplied acceptance criteria. "
            "Return JSON with generated_test_module (Python string). Do not claim tests ran. "
            "Tests must validate feature behavior, not just health endpoints.",
            json.dumps(
                {
                    "feature": payload.feature_title,
                    "criteria": payload.acceptance_criteria,
                    "plan": [n.model_dump() for n in payload.plan_dag],
                }
            ),
        )
        if data and isinstance(data.get("generated_test_module"), str):
            code = data["generated_test_module"]
        else:
            clean_name = re.sub(r"[^a-z0-9_]", "_", payload.feature_title.lower())[:80]
            code = (
                "import pytest\n\n"
                + f"def test_{clean_name}_lifecycle():\n"
                + "    pytest.fail('Acceptance tests require implementation or an LLM provider')\n"
            )
        try:
            tree = ast.parse(code)
            functions = [
                n.name
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name.startswith("test_")
            ]
            count = sum(isinstance(n, ast.Assert) for n in ast.walk(tree))
        except (SyntaxError, ValueError):
            functions, count = [], 0
        return Gate4TDDResponse(
            passed=bool(functions) and count > 0,
            generated_test_module=code,
            test_function_names=functions,
            assertions_count=count,
        )

    # -------------------------------------------------------------
    # GATE 5: Code Generation, Static Analysis & Automated Execution
    # -------------------------------------------------------------
    async def evaluate_gate5_execution(
        self, payload: Gate5ExecutionRequest
    ) -> Gate5ExecutionResponse:
        try:
            tree = ast.parse(payload.test_module_code)
            compile(
                tree, "generated_tests.py", "exec"
            )  # syntax validation only; never executes code
        except (SyntaxError, ValueError, TypeError) as error:
            return Gate5ExecutionResponse(
                passed=False,
                static_analysis_passed=False,
                tests_executed=0,
                tests_passed=0,
                execution_status="invalid_code",
                summary=f"Python syntax validation failed: {type(error).__name__}",
            )
        if not settings.AI_RUNNER_URL:
            return Gate5ExecutionResponse(
                passed=False,
                static_analysis_passed=True,
                tests_executed=0,
                tests_passed=0,
                execution_status="not_configured",
                summary="Syntax checked. No tests executed: configure an isolated AI_RUNNER_URL to verify generated code.",
            )
        if not payload.implementation_files:
            generated = await complete_json(
                "Implement the feature as typed standalone Python modules under the generated package. "
                "Return JSON implementation_files mapping relative .py paths to code. "
                "Do not edit tests, use network access, or claim execution results.",
                json.dumps({"feature": payload.feature_title, "tests": payload.test_module_code}),
            )
            if generated and isinstance(generated.get("implementation_files"), dict):
                payload.implementation_files = generated["implementation_files"]
        if (
            sum(
                len(k) + len(v)
                for k, v in payload.implementation_files.items()
                if isinstance(k, str) and isinstance(v, str)
            )
            > 50000
        ):
            raise ValidationException("Generated implementation exceeds runner input limit")
        try:
            headers = (
                {"Authorization": f"Bearer {settings.AI_RUNNER_TOKEN}"}
                if settings.AI_RUNNER_TOKEN
                else {}
            )
            async with httpx.AsyncClient(timeout=settings.AI_RUNNER_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    settings.AI_RUNNER_URL, json=payload.model_dump(), headers=headers
                )
                response.raise_for_status()
                result = Gate5ExecutionResponse.model_validate(response.json())
            if (
                result.execution_status != "completed"
                or result.tests_executed < 1
                or not 0 <= result.tests_passed <= result.tests_executed
            ):
                raise ValueError("Runner did not return completed test results")
            result.passed = (
                bool(payload.implementation_files)
                and result.static_analysis_passed
                and result.tests_passed == result.tests_executed
                and (result.coverage_percent or 0) >= 90
            )
            return result
        except (httpx.HTTPError, ValueError):
            return Gate5ExecutionResponse(
                passed=False,
                static_analysis_passed=True,
                tests_executed=0,
                tests_passed=0,
                execution_status="runner_failed",
                summary="The isolated runner did not return valid execution results.",
            )

    # -------------------------------------------------------------
    # FULL END-TO-END PIPELINE ORCHESTRATOR
    # -------------------------------------------------------------
    async def run_full_pipeline(
        self,
        org_id: str,
        payload: FullPipelineExecutionRequest,
    ) -> FullPipelineExecutionResponse:
        # Gate 1
        g1 = await self.evaluate_gate1_intent(
            org_id=org_id,
            payload=Gate1IngestRequest(
                project_id=payload.project_id, feature_prompt=payload.feature_prompt
            ),
        )
        if not g1.passed:
            raise ValidationException("Gate 1 Failed: Ambiguous feature prompt")

        # Gate 2
        g2 = await self.evaluate_gate2_context(
            org_id=org_id,
            payload=Gate2ContextRequest(
                project_id=payload.project_id, feature_title=g1.feature_title
            ),
        )

        # Gate 3
        g3 = await self.evaluate_gate3_plan(
            payload=Gate3PlanRequest(
                project_id=payload.project_id,
                feature_title=g1.feature_title,
                acceptance_criteria=g1.acceptance_criteria,
            )
        )

        # Gate 4
        g4 = await self.evaluate_gate4_tdd(
            payload=Gate4TDDRequest(
                feature_title=g1.feature_title,
                plan_dag=g3.plan_dag,
                acceptance_criteria=g1.acceptance_criteria,
            )
        )

        # Gate 5
        g5 = await self.evaluate_gate5_execution(
            payload=Gate5ExecutionRequest(
                feature_title=g1.feature_title,
                test_module_code=g4.generated_test_module,
            )
        )

        return FullPipelineExecutionResponse(
            pipeline_success=all((g1.passed, g2.passed, g3.passed, g4.passed, g5.passed)),
            gate1_intent=g1,
            gate2_context=g2,
            gate3_plan=g3,
            gate4_tdd=g4,
            gate5_execution=g5,
        )
