"""Figma Design Frame linking and oEmbed preview resolver."""

import re
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.redis import get_redis
from src.models.integrations import FigmaLink
from src.repositories.task_repo import TaskRepository
from src.schemas.integrations import FigmaLinkCreate, FigmaLinkResponse


def parse_figma_url(url: str) -> tuple[str, str | None]:
    """Extract Figma file_key and optional node_id from Figma web URL."""
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"figma.com", "www.figma.com"}
        or len(parts) < 2
        or parts[0] not in {"file", "design"}
        or not re.fullmatch(r"[a-zA-Z0-9]+", parts[1])
    ):
        raise ValidationException("Invalid Figma URL")
    file_key = parts[1]
    node_id = parse_qs(parsed.query).get("node-id", [None])[0]
    if node_id:
        node_id = node_id.replace("-", ":")

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
        thumbnail = None
        if settings.FIGMA_API_ACCESS_TOKEN:
            redis = await get_redis()
            cache_key = f"figma:{org_id}:{file_key}:{node_id or '0:1'}"
            thumbnail = await redis.get(cache_key)
            if not thumbnail:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        response = await client.get(
                            f"https://api.figma.com/v1/images/{file_key}",
                            headers={"X-Figma-Token": settings.FIGMA_API_ACCESS_TOKEN},
                            params={"ids": node_id or "0:1", "format": "png"},
                        )
                        response.raise_for_status()
                        thumbnail = response.json().get("images", {}).get(node_id or "0:1")
                    if thumbnail:
                        await redis.set(cache_key, thumbnail, ex=3600)
                except (httpx.HTTPError, ValueError):
                    thumbnail = None

        figma_link = FigmaLink(
            task_id=task.id,
            figma_url=payload.figma_url,
            file_key=file_key,
            node_id=node_id,
            file_name=payload.file_name or f"Figma Frame {node_id or file_key}",
            thumbnail_url=thumbnail,
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
