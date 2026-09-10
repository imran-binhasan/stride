"""External Integrations (GitHub Webhooks & Figma) API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.schemas.integrations import (
    FigmaLinkCreate,
    FigmaLinkResponse,
    GitHubIntegrationCreate,
    GitHubIntegrationResponse,
)
from src.services.figma_service import FigmaService
from src.services.github_service import GitHubService, verify_github_signature

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.post("/github/webhook", status_code=status.HTTP_200_OK)
async def github_webhook_receiver(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    x_hub_signature_256: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict:
    """Public webhook endpoint receiving GitHub events (push, pull_request, etc.)."""
    raw_body = await request.body()
    if settings.ENVIRONMENT != "test":
        if not verify_github_signature(raw_body, settings.GITHUB_WEBHOOK_SECRET, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid GitHub HMAC signature")
    payload = await request.json()
    result = await GitHubService(db).process_webhook(
        event_type=x_github_event or "generic", payload=payload
    )
    return {"success": True, "result": result}


@router.post(
    "/projects/{project_id}/github",
    response_model=GitHubIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_github_repo(
    project_id: str,
    payload: GitHubIntegrationCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GitHubIntegrationResponse:
    return await GitHubService(db).connect_repository(
        org_id=ctx.org_id, project_id=project_id, payload=payload
    )


@router.post(
    "/tasks/{task_id}/figma", response_model=FigmaLinkResponse, status_code=status.HTTP_201_CREATED
)
async def attach_figma_frame(
    task_id: str,
    payload: FigmaLinkCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FigmaLinkResponse:
    return await FigmaService(db).attach_figma_link(
        org_id=ctx.org_id, task_id=task_id, payload=payload
    )


@router.get("/tasks/{task_id}/figma", response_model=list[FigmaLinkResponse])
async def list_task_figma_frames(
    task_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[FigmaLinkResponse]:
    return await FigmaService(db).list_task_figma_links(org_id=ctx.org_id, task_id=task_id)
