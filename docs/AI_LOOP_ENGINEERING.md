# 5-Gate AI Loop Engineering & Context Engineering Architecture

## 1. Overview
The **A3Zen AI Loop Engineering Architecture** establishes a rigorous, deterministic, multi-stage pipeline for transforming ambiguous user intent into verified, tested, and deployed software features and project deliverables.

Each phase of development is guarded by an automated or interactive **Quality Gate** to guarantee zero hallucination, strict context alignment, schema validity, and 100% test coverage.

---

## 2. The 5-Gate Architecture Workflow

```mermaid
graph TD
    subgraph "Gate 1: Ingestion & Intent Parse"
        UInput["User Prompt / Feature Spec / Issue Description"] --> G1Parser["Intent Extraction & Scope Boundary Parser"]
        G1Parser --> G1Validation{"Gate 1: Scope & Ambiguity Check"}
        G1Validation -->|Ambiguous| Clarify["Clarification Sub-loop"]
        G1Validation -->|Passed| G1Spec["Structured Feature Specification"]
    end

    subgraph "Gate 2: Context Retrieval & State Vectorization"
        G1Spec --> G2Engine["Context Assembly Engine"]
        G2Engine --> DBState["Project Schema & Entity Graph"]
        G2Engine --> HistoryContext["Past Sprints & Bug Transcripts"]
        G2Engine --> CodeContext["Target Codebase AST & Types"]
        G2Engine --> G2Validation{"Gate 2: Context Sufficiency Check"}
        G2Validation -->|Passed| ContextVector["Vectorized Context Payload (<32k tokens)"]
    end

    subgraph "Gate 3: Task Decomposition & Plan Validation"
        ContextVector --> G3Planner["Planner Agent (Hierarchical Decomposition)"]
        G3Planner --> TaskTree["Atomic Task Tree & Dependency Graph"]
        G3Planner --> G3Validation{"Gate 3: Plan & Invariant Validation"}
        G3Validation -->|Passed| ExecutionPlan["Deterministic Execution Plan"]
    end

    subgraph "Gate 4: TDD Test Specification & Mock Suite"
        ExecutionPlan --> G4TDDGen["TDD Spec & Fixture Generator"]
        G4TDDGen --> PytestSuite["Async Pytest Suite (Unit + Integration)"]
        G4TDDGen --> G4Validation{"Gate 4: Test Assertion Quality Gate"}
        G4Validation -->|Passed| RedSuite["Failing Test Suite (RED phase)"]
    end

    subgraph "Gate 5: Code Generation, Static Analysis & Execution"
        RedSuite --> G5Coder["Coder Agent (Implementation)"]
        G5Coder --> StaticLint["Ruff / Mypy / Pyright Static Analysis"]
        StaticLint --> TestRunner["Automated Pytest Execution Runner"]
        TestRunner --> G5Validation{"Gate 5: All Tests Passing & Coverage > 90%?"}
        G5Validation -->|Fail| G5Repair["Self-Correction Loop (Max 3 iterations)"]
        G5Repair --> G5Coder
        G5Validation -->|Passed (GREEN)| ProductionDiff["Verified Code Diff + Changelog"]
    end
```

---

## 3. Detailed Gate Specifications

### Gate 1: Ingestion & Intent Parsing
* **Objective:** Parse raw user input (e.g. natural language issue, PRD, or Slack prompt) into structured domain attributes.
* **Input:** Unstructured prompt text, user attachments, Figma links, GitHub issues.
* **Processing:**
  - Entity extraction: Target Project, Target Milestones, Priority, Assignee suggestions, Estimated story points.
  - Acceptance Criteria Generation: Given/When/Then formatted Gherkin specifications.
* **Gate 1 Pass Criteria:**
  - No missing mandatory domain fields (Project ID, Title, Primary Actor).
  - Ambiguity score $< 0.15$ (if ambiguous, fires automated clarification prompt).

---

### Gate 2: Context Gathering & State Vectorization
* **Objective:** Assemble a deterministic, minimal-token context window containing all relevant database schemas, service interfaces, type definitions, and relational dependencies.
* **Context Layers:**
  1. **Schema Context:** Pydantic models, SQLAlchemy tables, Alembic migrations.
  2. **Dependency Context:** Upstream and downstream task blockers, GitHub PR status.
  3. **Role & Permission Context:** Tenant ID, actor role permissions, workspace limits.
* **Gate 2 Pass Criteria:**
  - Context size within token budget ($< 32,000$ tokens).
  - All foreign keys, model imports, and enum references resolved without dangling symbols.

---

### Gate 3: Task Breakdown & Plan Validation
* **Objective:** Break complex requirements into topological DAG (Directed Acyclic Graph) subtasks.
* **Output Artifacts:**
  - Atomic steps (Database schema change $\to$ Repository CRUD $\to$ Service business logic $\to$ API Router $\to$ WebSocket event broadcast).
  - Pre-flight risk assessment and rollback strategy.
* **Gate 3 Pass Criteria:**
  - Dependency acyclicity check passes (no circular dependencies).
  - Every subtask has concrete, measurable verification criteria.

---

### Gate 4: Test-Driven Development (TDD) Test & Mock Generation
* **Objective:** Write comprehensive failing test cases (`RED` phase) before any production code is written.
* **Test Suite Layers:**
  - **Unit Tests:** Business domain rules, permission checks, calculation algorithms (e.g., CPM in Gantt, activity indices).
  - **Integration Tests:** Async HTTP endpoints (`httpx.AsyncClient`), Database transactions with automatic rollback fixtures.
  - **WebSocket / Event Tests:** Pub/Sub message serialization, room subscription filtering.
* **Gate 4 Pass Criteria:**
  - Test suite compiles cleanly and fails as expected on missing implementation (`RED`).
  - Fixtures and mocks correctly isolate external services (S3, GitHub API, Figma API).

---

### Gate 5: Code Generation, Static Analysis & Automated Execution
* **Objective:** Implement the minimum code required to turn all test cases green (`GREEN` phase), followed by static linting, typing, and refactoring (`REFACTOR` phase).
* **Automated Guardrails:**
  1. **Static Analysis:** `ruff check --fix` and `ruff format` (PEP 8 compliance).
  2. **Strict Typing:** `mypy --strict` (Zero `Any` leaks in domain interfaces).
  3. **Test Execution:** `pytest -v --cov=src --cov-report=term-missing`.
* **Gate 5 Pass Criteria:**
  - 100% of test cases pass with exit code `0`.
  - Code coverage $\ge 90\%$ on all modified service modules.
  - Zero high/critical static analysis warnings.

---

## 4. Context Engineering & Memory State Template

```json
{
  "trace_id": "a3zen-ctx-20260827-001",
  "tenant_id": "org_9841aef2",
  "actor": {
    "user_id": "usr_c398df1",
    "role": "ProjectManager",
    "permissions": ["project:write", "task:create", "timesheet:approve"]
  },
  "project_context": {
    "project_id": "prj_e9801",
    "key": "A3Z",
    "current_sprint": "sprint_04",
    "active_workflow_states": ["BACKLOG", "TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"]
  },
  "target_spec": {
    "feature_title": "WebSocket Real-Time Kanban Card Sync",
    "acceptance_criteria": [
      "When a task's status changes via REST or WebSocket, a broadcast is published to Redis channel `org:{org_id}:project:{prj_id}`.",
      "All active clients subscribed to the project channel receive a `TASK_MOVED` payload within 50ms.",
      "The client that initiated the change receives an acknowledgment and is omitted from redundant echo broadcasts."
    ]
  },
  "code_references": [
    "src/core/websocket_manager.py",
    "src/services/task_service.py",
    "src/schemas/events.py"
  ]
}
```
