"""Task, Comment, Dependency, and Attachment business logic."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.events import record_change
from src.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from src.models.auth import MemberStatus
from src.models.project import StatusCategory, WorkflowStatus
from src.models.task import DependencyType, Task, TaskDependency
from src.repositories.project_repo import ProjectRepository
from src.repositories.task_repo import TaskRepository
from src.repositories.user_repo import UserRepository
from src.schemas.recurrence import RecurrenceRule
from src.schemas.task import (
    CommentCreate,
    CommentResponse,
    DependencyCreate,
    DependencyResponse,
    SubtaskCreate,
    TaskChildResponse,
    TaskCreate,
    TaskMoveRequest,
    TaskResponse,
    TaskUpdate,
)
from src.services.recurrence_service import next_due


class TaskService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.task_repo = TaskRepository(db)
        self.project_repo = ProjectRepository(db)
        self.user_repo = UserRepository(db)

    async def _validate_assignee(self, org_id: str, assignee_id: str | None) -> None:
        if assignee_id is None:
            return
        membership = await self.user_repo.get_org_membership(org_id=org_id, user_id=assignee_id)
        if not membership or membership.status != MemberStatus.ACTIVE:
            raise ValidationException("Assignee is not a member of this organization")

    async def create_task(self, org_id: str, creator_id: str, payload: TaskCreate) -> TaskResponse:
        project = await self.project_repo.get_by_id(payload.project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", payload.project_id)

        from src.services.custom_field_service import validate_values

        await validate_values(
            self.db, org_id, payload.custom_fields, project.custom_field_definitions
        )
        target_status_id = payload.status_id
        if not target_status_id:
            if not project.statuses:
                raise ValidationException("Project has no configured workflow statuses")
            target_status_id = project.statuses[0].id
        else:
            status_obj = await self.project_repo.get_status_by_id(target_status_id)
            if not status_obj or status_obj.project_id != project.id:
                raise ValidationException("Invalid status ID for this project")

        await self._validate_assignee(org_id, payload.assignee_id)

        await self._validate_links(org_id, project.id, payload.sprint_id, payload.parent_task_id)
        self._validate_dates(payload.start_date, payload.due_date)
        if payload.recurrence and not payload.due_date:
            raise ValidationException("Recurring tasks require a due date")
        new_counter = await self.project_repo.increment_task_counter(project.id)
        short_id = f"{project.key}-{new_counter}"

        task = await self.task_repo.create_task(
            org_id=org_id,
            project_id=project.id,
            short_id=short_id,
            title=payload.title,
            status_id=target_status_id,
            creator_id=creator_id,
            task_type=payload.type,
            description=payload.description,
            sprint_id=payload.sprint_id,
            parent_task_id=payload.parent_task_id,
            priority=payload.priority,
            story_points=payload.story_points,
            estimated_hours=payload.estimated_hours,
            start_date=payload.start_date,
            due_date=payload.due_date,
            assignee_id=payload.assignee_id,
            is_client_ticket=payload.is_client_ticket,
            custom_fields=payload.custom_fields,
            recurrence=payload.recurrence.model_dump(mode="json") if payload.recurrence else None,
        )
        record_change(self.db, org_id, project.id, "TASK_CREATED", task.id, creator_id)
        if payload.assignee_id:
            await self.task_repo.add_assignee(task.id, payload.assignee_id)
        fresh_task = await self.task_repo.get_by_id(task.id, org_id=org_id)
        return TaskResponse.model_validate(fresh_task)

    async def get_task(self, task_id: str, org_id: str) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)
        return TaskResponse.model_validate(task)

    async def list_tasks(
        self,
        project_id: str,
        org_id: str,
        sprint_id: str | None = None,
        status_id: str | None = None,
        assignee_id: str | None = None,
        priority=None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskResponse]:
        tasks = await self.task_repo.list_by_project(
            project_id=project_id,
            org_id=org_id,
            sprint_id=sprint_id,
            status_id=status_id,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
            top_level=True,
            priority=priority,
            search=search,
        )
        return [
            TaskResponse.model_validate(t).model_copy(update={"comments": [], "attachments": []})
            for t in tasks
        ]

    async def update_task(self, task_id: str, org_id: str, payload: TaskUpdate) -> TaskResponse:
        await self.db.execute(
            select(Task.id).where(Task.id == task_id, Task.org_id == org_id).with_for_update()
        )
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        if payload.status_id is not None:
            status_obj = await self.project_repo.get_status_by_id(payload.status_id)
            if not status_obj or status_obj.project_id != task.project_id:
                raise ValidationException("Target status does not belong to this project")
        await self._validate_assignee(org_id, payload.assignee_id)

        if payload.custom_fields is not None:
            from src.services.custom_field_service import validate_values

            project = await self.project_repo.get_by_id(task.project_id, org_id=org_id)
            await validate_values(
                self.db, org_id, payload.custom_fields, project.custom_field_definitions
            )
        changes = payload.model_dump(exclude_unset=True)
        for required in (
            "title",
            "status_id",
            "type",
            "priority",
            "is_client_ticket",
            "custom_fields",
        ):
            if required in changes and changes[required] is None:
                raise ValidationException(f"{required} cannot be null")
        await self._validate_links(
            org_id,
            task.project_id,
            changes.get("sprint_id", task.sprint_id),
            changes.get("parent_task_id", task.parent_task_id),
            task.id,
        )
        self._validate_dates(
            changes.get("start_date", task.start_date), changes.get("due_date", task.due_date)
        )
        if changes.get("recurrence", task.recurrence) and not changes.get(
            "due_date", task.due_date
        ):
            raise ValidationException("Recurring tasks require a due date")
        if payload.recurrence is not None:
            changes["recurrence"] = payload.recurrence.model_dump(mode="json")
        for field, value in changes.items():
            if field == "custom_fields" and value is not None:
                task.custom_fields = {**task.custom_fields, **value}
            else:
                setattr(task, field, value)

        await self.db.flush()
        await self._spawn_recurrence(task)
        record_change(self.db, org_id, task.project_id, "TASK_UPDATED", task_id)
        fresh = await self.task_repo.get_by_id(task_id, org_id=org_id)
        return TaskResponse.model_validate(fresh)

    async def move_task(self, task_id: str, org_id: str, payload: TaskMoveRequest) -> TaskResponse:
        await self.db.execute(
            select(Task.id).where(Task.id == task_id, Task.org_id == org_id).with_for_update()
        )
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        status_obj = await self.project_repo.get_status_by_id(payload.status_id)
        if not status_obj or status_obj.project_id != task.project_id:
            raise ValidationException("Target status does not belong to this project")

        task.status_id = payload.status_id
        task.position = payload.new_position
        await self.db.flush()

        await self._spawn_recurrence(task)
        record_change(self.db, org_id, task.project_id, "TASK_UPDATED", task_id)
        fresh = await self.task_repo.get_by_id(task_id, org_id=org_id)
        return TaskResponse.model_validate(fresh)

    # ── Comments ──────────────────────────────────────────────────────────────

    async def add_comment(
        self, task_id: str, org_id: str, author_id: str, payload: CommentCreate
    ) -> CommentResponse:
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        if payload.parent_comment_id:
            parent = await self.task_repo.get_comment_by_id(payload.parent_comment_id)
            if not parent or parent.task_id != task_id:
                raise ValidationException("Parent comment must belong to this task")
        comment = await self.task_repo.add_comment(
            task_id=task_id,
            author_id=author_id,
            content=payload.content,
            is_internal=payload.is_internal,
            parent_comment_id=payload.parent_comment_id,
        )
        record_change(self.db, org_id, task.project_id, "COMMENT_ADDED", task.id, author_id)
        await self.db.refresh(comment, ["author"])
        return CommentResponse.model_validate(comment)

    async def delete_comment(
        self, comment_id: str, org_id: str, user_id: str, can_delete_any: bool
    ) -> dict:
        comment = await self.task_repo.get_comment_by_id(comment_id)
        if not comment or not await self.task_repo.get_by_id(comment.task_id, org_id=org_id):
            raise EntityNotFoundException("Comment", comment_id)
        if not can_delete_any and comment.author_id != user_id:
            raise ValidationException("You can only delete your own comments")
        await self.task_repo.delete_comment(comment_id)
        return {"success": True, "deleted_comment_id": comment_id}

    # ── Dependencies ──────────────────────────────────────────────────────────

    async def add_dependency(
        self, task_id: str, org_id: str, payload: DependencyCreate
    ) -> DependencyResponse:
        if task_id == payload.successor_id:
            raise ConflictException("A task cannot depend on itself")

        predecessor = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not predecessor:
            raise EntityNotFoundException("Task", task_id)

        successor = await self.task_repo.get_by_id(payload.successor_id, org_id=org_id)
        if not successor:
            raise EntityNotFoundException("Task", payload.successor_id)

        if predecessor.project_id != successor.project_id:
            raise ValidationException("Cross-project dependencies are not supported")

        pred_id, succ_id = task_id, payload.successor_id
        if payload.dependency_type == DependencyType.BLOCKED_BY:
            pred_id, succ_id = succ_id, pred_id
        existing = await self.db.scalar(
            select(TaskDependency).where(
                TaskDependency.predecessor_id == pred_id, TaskDependency.successor_id == succ_id
            )
        )
        if existing:
            raise ConflictException("Dependency already exists")
        if payload.dependency_type != DependencyType.RELATES_TO:
            await self._verify_no_cycles(
                project_id=predecessor.project_id,
                new_pred_id=pred_id,
                new_succ_id=succ_id,
            )

        dep = await self.task_repo.add_dependency(
            predecessor_id=pred_id,
            successor_id=succ_id,
            dependency_type=DependencyType.RELATES_TO
            if payload.dependency_type == DependencyType.RELATES_TO
            else DependencyType.BLOCKS,
            lag_days=payload.lag_days,
        )
        return DependencyResponse.model_validate(dep)

    async def _verify_no_cycles(self, project_id: str, new_pred_id: str, new_succ_id: str) -> None:
        existing_deps = await self.task_repo.get_dependency_graph(project_id)
        graph: dict[str, list[str]] = defaultdict(list)
        for dep in existing_deps:
            if dep.dependency_type == DependencyType.BLOCKS:
                graph[dep.predecessor_id].append(dep.successor_id)
        graph[new_pred_id].append(new_succ_id)

        visited: set[str] = set()

        def dfs(current: str) -> bool:
            if current == new_pred_id:
                return True
            visited.add(current)
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
            return False

        if dfs(new_succ_id):
            raise ConflictException("Adding this dependency creates a circular blocking cycle")

    async def get_project_or_raise(self, project_id, org_id):
        project = await self.project_repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)
        return project

    @staticmethod
    def _validate_dates(start, end):
        if start and end and end < start:
            raise ValidationException("Due date must not precede start date")

    async def _validate_links(self, org_id, project_id, sprint_id, parent_id, task_id=None):
        if sprint_id:
            sprint = await self.project_repo.get_sprint_by_id(sprint_id)
            if not sprint or sprint.project_id != project_id:
                raise ValidationException("Sprint must belong to this project")
        seen = {task_id} if task_id else set()
        while parent_id:
            if parent_id in seen:
                raise ConflictException("Task parent relationship would create a cycle")
            seen.add(parent_id)
            parent = await self.task_repo.get_by_id(parent_id, org_id=org_id)
            if not parent or parent.project_id != project_id:
                raise ValidationException("Parent must belong to this project")
            parent_id = parent.parent_task_id

    async def add_subtask(self, task_id, org_id, creator_id, payload: SubtaskCreate):
        parent = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not parent:
            raise EntityNotFoundException("Task", task_id)
        child = await self.create_task(
            org_id,
            creator_id,
            TaskCreate(
                project_id=parent.project_id,
                parent_task_id=task_id,
                title=payload.title,
                sprint_id=parent.sprint_id,
            ),
        )
        task = await self.task_repo.get_by_id(child.id, org_id=org_id)
        task.position = payload.position
        await self.db.flush()
        return TaskChildResponse.model_validate(task)

    async def delete_task(self, task_id, org_id):
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)
        record_change(self.db, org_id, task.project_id, "TASK_DELETED", task.id)
        await self.db.delete(task)
        await self.db.flush()

    async def delete_dependency(self, task_id, dependency_id, org_id):
        if not await self.task_repo.get_by_id(task_id, org_id=org_id):
            raise EntityNotFoundException("Task", task_id)
        dep = await self.db.scalar(
            select(TaskDependency).where(
                TaskDependency.id == dependency_id,
                (TaskDependency.predecessor_id == task_id)
                | (TaskDependency.successor_id == task_id),
            )
        )
        if not dep:
            raise EntityNotFoundException("Dependency", dependency_id)
        await self.db.delete(dep)
        await self.db.flush()

    async def _spawn_recurrence(self, task):
        if not task.recurrence or task.recurrence_generated or not task.due_date:
            return
        status = await self.project_repo.get_status_by_id(task.status_id)
        if status.category != StatusCategory.DONE:
            return
        rule = RecurrenceRule.model_validate(task.recurrence)
        due = next_due(rule, task.due_date)
        task.recurrence_generated = True
        if due is None:
            return
        first = await self.db.scalar(
            select(WorkflowStatus.id)
            .where(
                WorkflowStatus.project_id == task.project_id,
                WorkflowStatus.category != StatusCategory.DONE,
            )
            .order_by(WorkflowStatus.position)
            .limit(1)
        )
        if not first:
            raise ValidationException("Recurrence requires an unfinished workflow status")
        await self.create_task(
            task.org_id,
            task.creator_id,
            TaskCreate(
                project_id=task.project_id,
                title=task.title,
                description=task.description,
                type=task.type,
                status_id=first,
                priority=task.priority,
                story_points=task.story_points,
                estimated_hours=task.estimated_hours,
                start_date=task.start_date + (due - task.due_date) if task.start_date else None,
                due_date=due,
                assignee_id=task.assignee_id,
                custom_fields=task.custom_fields,
                recurrence=rule,
            ),
        )
