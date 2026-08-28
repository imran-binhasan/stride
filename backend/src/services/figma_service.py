"""Figma Design Frame linking and oEmbed preview resolver."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.models.integrations import FigmaLink
from src.repositories.task_repo import TaskRepository
from src.schemas.integrations import FigmaLinkCreate, FigmaLinkResponse


def parse_figma_url(url: str) -> tuple[str, str | None]:
    """Extract Figma file_key and optional node_id from Figma web URL."""
    pattern = r"https?://(?:www\.)?figma\.com/(?:file|design)/([a-zA-Z0-9]+)(?:/[^?#]*)?(?:\?[^#]*node-id=([^&#]+))?"
    match = re.search(pattern, url)
    if not match:
        raise ValidationException(
            "Invalid Figma URL format. Expected 'https://figma.com/file/... or /design/...'"
        )

    file_key = match.group(1)
    node_id = match.group(2)
    if node_id:
        node_id = node_id.replace("%3A", ":").replace("-", ":")

    return file_key, node_id


class FigmaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.task_repo = TaskRepository(db)

    async def attach_figma_link(
        self,
        org_id: str,
        task_id: str,
        payload: FigmaLinkCreate,
    ) -> FigmaLinkResponse:
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        file_key, node_id = parse_figma_url(payload.figma_url)
        mock_thumbnail = f"https://api.figma.com/v1/images/{file_key}?ids={node_id or '0:1'}"

        figma_link = FigmaLink(
            task_id=task.id,
            figma_url=payload.figma_url,
            file_key=file_key,
            node_id=node_id,
            file_name=payload.file_name or f"Figma Frame {node_id or file_key}",
            thumbnail_url=mock_thumbnail,
        )
        self.db.add(figma_link)
        await self.db.flush()
        return FigmaLinkResponse.model_validate(figma_link)

    async def list_task_figma_links(self, org_id: str, task_id: str) -> list[FigmaLinkResponse]:
        task = await self.task_repo.get_by_id(task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)

        stmt = select(FigmaLink).where(FigmaLink.task_id == task_id)
        links = list((await self.db.execute(stmt)).scalars().all())
        return [FigmaLinkResponse.model_validate(link_item) for link_item in links]
