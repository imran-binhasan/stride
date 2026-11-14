"""GitHub 2-way Webhook processor and repository sync service."""

import hashlib
import hmac
import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.events import record_change
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.models.integrations import GitHubIntegration, WebhookEventLog
from src.models.project import StatusCategory
from src.repositories.project_repo import ProjectRepository
from src.repositories.task_repo import TaskRepository
from src.schemas.integrations import GitHubIntegrationCreate, GitHubIntegrationResponse
from src.schemas.task import TaskUpdate
from src.services.task_service import TaskService

logger = logging.getLogger("a3zen.github")


def verify_github_signature(
    payload_bytes: bytes, secret: str, signature_header: str | None
) -> bool:
    """Verify GitHub webhook payload against HMAC-SHA256 signature."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_hash = signature_header[7:]
    mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), expected_hash)


def extract_task_keys_from_text(text: str) -> list[str]:
    """Extract task identifier keys (e.g. A3Z-101, ENG-42) from text."""
    if not text:
        return []
    matches = re.findall(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b", text)
    return list(dict.fromkeys(matches))  # deduplicate preserving order


class GitHubService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.task_repo = TaskRepository(db)

    async def connect_repository(
        self,
        org_id: str,
        project_id: str,
        payload: GitHubIntegrationCreate,
    ) -> GitHubIntegrationResponse:
        project = await self.project_repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        stmt = select(GitHubIntegration).where(
            GitHubIntegration.project_id == project_id,
            GitHubIntegration.repo_owner == payload.repo_owner,
            GitHubIntegration.repo_name == payload.repo_name,
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.auto_transition_pr_open = payload.auto_transition_pr_open
            existing.auto_transition_pr_merge = payload.auto_transition_pr_merge
            integration = existing
        else:
            integration = GitHubIntegration(
                org_id=org_id,
                project_id=project_id,
                repo_owner=payload.repo_owner,
                repo_name=payload.repo_name,
                auto_transition_pr_open=payload.auto_transition_pr_open,
                auto_transition_pr_merge=payload.auto_transition_pr_merge,
            )
            self.db.add(integration)

        await self.db.flush()
        return GitHubIntegrationResponse.model_validate(integration)

    async def process_webhook(
        self, event_type: str, payload: dict[str, Any], delivery_id: str | None = None
    ) -> dict[str, Any]:
        """Process incoming GitHub event payload."""
        if delivery_id:
            if self.db.bind.dialect.name == "postgresql":
                from sqlalchemy import text

                await self.db.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:delivery,0))"),
                    {"delivery": delivery_id},
                )
            if await self.db.get(WebhookEventLog, delivery_id):
                return {"status": "duplicate"}
        log = WebhookEventLog(
            **({"id": delivery_id} if delivery_id else {}),
            provider="github",
            event_type=event_type,
            payload_json=json.dumps(payload),
            processed_successfully=True,
        )
        self.db.add(log)

        repo_data = payload.get("repository", {})
        repo_owner = repo_data.get("owner", {}).get("login", "")
        repo_name = repo_data.get("name", "")

        stmt = select(GitHubIntegration).where(
            GitHubIntegration.repo_owner.ilike(repo_owner),
            GitHubIntegration.repo_name.ilike(repo_name),
        )
        integrations = list((await self.db.execute(stmt)).scalars().all())
        if not integrations:
            return {"status": "ignored", "reason": "No linked project found for repository"}

        affected_tasks = []

        if event_type == "push":
            commits = payload.get("commits", [])
            task_keys: list[str] = []
            for commit in commits:
                task_keys.extend(extract_task_keys_from_text(commit.get("message", "")))
            task_keys = list(dict.fromkeys(task_keys))  # dedupe preserving order

            for integration in integrations:
                from src.core.tenant_scope import set_tenant_scope

                await set_tenant_scope(self.db, integration.org_id)
                project = await self.project_repo.get_by_id(integration.project_id)
                if not project:
                    continue
                # Single batched query instead of one lookup per key.
                for task in await self.task_repo.get_many_by_short_ids(project.id, task_keys):
                    affected_tasks.append({"task_id": task.id, "linked_by": "commit"})

        elif event_type == "pull_request":
            pr = payload.get("pull_request", {})
            action = payload.get("action")
            branch_name = pr.get("head", {}).get("ref", "")
            pr_title = pr.get("title", "")
            merged = pr.get("merged", False)

            combined_text = f"{branch_name} {pr_title} {pr.get('body', '')}"
            task_keys = extract_task_keys_from_text(combined_text)

            for integration in integrations:
                from src.core.tenant_scope import set_tenant_scope

                await set_tenant_scope(self.db, integration.org_id)
                project = await self.project_repo.get_by_id(integration.project_id)
                if not project:
                    continue

                review_status = next(
                    (s for s in project.statuses if s.category == StatusCategory.IN_REVIEW),
                    None,
                )
                done_status = next(
                    (s for s in project.statuses if s.category == StatusCategory.DONE),
                    None,
                )

                # Single batched query instead of one lookup per key.
                for task in await self.task_repo.get_many_by_short_ids(project.id, task_keys):
                    if (
                        action in ("opened", "reopened", "ready_for_review")
                        and not pr.get("draft")
                        and integration.auto_transition_pr_open
                        and review_status
                    ):
                        await TaskService(self.db).update_task(
                            task.id, integration.org_id, TaskUpdate(status_id=review_status.id)
                        )
                        affected_tasks.append({"task_id": task.id, "status": "IN_REVIEW"})

                    elif (
                        action == "closed"
                        and merged
                        and integration.auto_transition_pr_merge
                        and done_status
                    ):
                        await TaskService(self.db).update_task(
                            task.id, integration.org_id, TaskUpdate(status_id=done_status.id)
                        )
                        affected_tasks.append({"task_id": task.id, "status": "DONE"})
                    if pr.get("draft") and action in {"opened", "reopened", "converted_to_draft"}:
                        progress = next(
                            (
                                s
                                for s in project.statuses
                                if s.category == StatusCategory.IN_PROGRESS
                            ),
                            None,
                        )
                        if progress:
                            await TaskService(self.db).update_task(
                                task.id, integration.org_id, TaskUpdate(status_id=progress.id)
                            )
                    task.custom_fields = {
                        **task.custom_fields,
                        "github_pr": {
                            "number": pr.get("number") or payload.get("number"),
                            "url": pr.get("html_url"),
                            "title": pr.get("title"),
                            "state": pr.get("state"),
                            "draft": bool(pr.get("draft")),
                            "merged": bool(merged),
                            "head_sha": pr.get("head", {}).get("sha"),
                        },
                    }
                    record_change(self.db, integration.org_id, project.id, "TASK_UPDATED", task.id)

        elif event_type in {"issue_comment", "workflow_run", "pull_request_review"}:
            obj = (
                payload.get("comment") or payload.get("workflow_run") or payload.get("review") or {}
            )
            source = (
                payload.get("issue")
                or payload.get("pull_request")
                or payload.get("workflow_run")
                or {}
            )
            text = " ".join(str(source.get(k) or "") for k in ("title", "body", "head_branch"))
            keys = extract_task_keys_from_text(text)
            for integration in integrations:
                from src.core.tenant_scope import set_tenant_scope

                await set_tenant_scope(self.db, integration.org_id)
                for task in await self.task_repo.get_many_by_short_ids(
                    integration.project_id, keys
                ):
                    task.custom_fields = {
                        **task.custom_fields,
                        "github_" + event_type: {
                            "url": obj.get("html_url"),
                            "state": obj.get("state"),
                            "status": obj.get("status"),
                            "conclusion": obj.get("conclusion"),
                            "author": obj.get("user", {}).get("login"),
                        },
                    }
                    record_change(
                        self.db, integration.org_id, integration.project_id, "TASK_UPDATED", task.id
                    )
                    affected_tasks.append({"task_id": task.id, "linked_by": event_type})
        await self.db.flush()
        return {"status": "processed", "affected_tasks": affected_tasks}

    async def publish_issue(self, org_id, task_id):
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)
        integration = await self.db.scalar(
            select(GitHubIntegration)
            .where(
                GitHubIntegration.project_id == task.project_id, GitHubIntegration.org_id == org_id
            )
            .limit(1)
        )
        if not integration or not settings.GITHUB_API_TOKEN:
            raise ValidationException(
                "Connect a repository and configure the GitHub API token first"
            )
        if task.custom_fields.get("github_issue", {}).get("url"):
            return task.custom_fields["github_issue"]
        from urllib.parse import quote

        url = f"https://api.github.com/repos/{quote(integration.repo_owner, safe='')}/{quote(integration.repo_name, safe='')}/issues"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.GITHUB_API_TOKEN}",
                    "Accept": "application/vnd.github+json",
                },
                json={"title": f"{task.short_id}: {task.title}", "body": task.description or ""},
            )
            if response.status_code != 201:
                raise ValidationException("GitHub rejected issue creation")
            data = response.json()
        link = {"number": data["number"], "url": data["html_url"]}
        task.custom_fields = {**task.custom_fields, "github_issue": link}
        record_change(self.db, org_id, task.project_id, "TASK_UPDATED", task.id)
        await self.db.flush()
        return link
