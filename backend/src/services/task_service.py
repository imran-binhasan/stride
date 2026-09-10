"""Task, Comment, Dependency, and Attachment business logic."""

from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from src.repositories.project_repo import ProjectRepository
from src.repositories.task_repo import TaskRepository
from src.repositories.user_repo import UserRepository
from src.schemas.task import (
    AttachmentResponse,
    CommentCreate,
    CommentResponse,
    DependencyCreate,
    DependencyResponse,
    TaskCreate,
    TaskMoveRequest,
    TaskResponse,
    TaskUpdate,
)


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
        if not membership:
            raise ValidationException("Assignee is not a member of this organization")

    async def create_task(self, org_id: str, creator_id: str, payload: TaskCreate) -> TaskResponse:
        project = await self.project_repo.get_by_id(payload.project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", payload.project_id)

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
        )
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
        )
        return [TaskResponse.model_validate(t) for t in tasks]

    async def update_task(self, task_id: str, org_id: str, payload: TaskUpdate) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        if payload.status_id is not None:
            status_obj = await self.project_repo.get_status_by_id(payload.status_id)
            if not status_obj or status_obj.project_id != task.project_id:
                raise ValidationException("Target status does not belong to this project")
        await self._validate_assignee(org_id, payload.assignee_id)

        for field, value in payload.model_dump(exclude_none=True).items():
            if field == "custom_fields" and value is not None:
                task.custom_fields = {**task.custom_fields, **value}
            else:
                setattr(task, field, value)

        await self.db.flush()
        fresh = await self.task_repo.get_by_id(task_id, org_id=org_id)
        return TaskResponse.model_validate(fresh)

    async def move_task(self, task_id: str, org_id: str, payload: TaskMoveRequest) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        status_obj = await self.project_repo.get_status_by_id(payload.status_id)
        if not status_obj or status_obj.project_id != task.project_id:
            raise ValidationException("Target status does not belong to this project")

        task.status_id = payload.status_id
        task.position = payload.new_position
        await self.db.flush()

        fresh = await self.task_repo.get_by_id(task_id, org_id=org_id)
        return TaskResponse.model_validate(fresh)

    # ── Comments ──────────────────────────────────────────────────────────────

    async def add_comment(
        self, task_id: str, org_id: str, author_id: str, payload: CommentCreate
    ) -> CommentResponse:
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        comment = await self.task_repo.add_comment(
            task_id=task_id,
            author_id=author_id,
            content=payload.content,
            is_internal=payload.is_internal,
            parent_comment_id=payload.parent_comment_id,
        )
        return CommentResponse.model_validate(comment)

    async def delete_comment(self, comment_id: str, org_id: str, user_id: str, can_delete_any: bool) -> dict:
        comment = await self.task_repo.get_comment_by_id(comment_id)
        if not comment:
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

        await self._verify_no_cycles(
            project_id=predecessor.project_id,
            new_pred_id=task_id,
            new_succ_id=payload.successor_id,
        )

        dep = await self.task_repo.add_dependency(
            predecessor_id=task_id,
            successor_id=payload.successor_id,
            dependency_type=payload.dependency_type,
            lag_days=payload.lag_days,
        )
        return DependencyResponse.model_validate(dep)

    async def _verify_no_cycles(self, project_id: str, new_pred_id: str, new_succ_id: str) -> None:
        existing_deps = await self.task_repo.get_dependency_graph(project_id)
        graph: dict[str, list[str]] = defaultdict(list)
        for dep in existing_deps:
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
