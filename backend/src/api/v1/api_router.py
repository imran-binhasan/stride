"""Master API v1 Router aggregation."""

from fastapi import APIRouter

from src.api.v1.ai import router as ai_router
from src.api.v1.auth import router as auth_router
from src.api.v1.clients import router as client_router
from src.api.v1.hr import router as hr_router
from src.api.v1.integrations import router as integration_router
from src.api.v1.notifications import router as notification_router
from src.api.v1.organizations import router as org_router
from src.api.v1.projects import router as project_router
from src.api.v1.tasks import router as task_router
from src.api.v1.time_tracking import router as time_router
from src.api.v1.views import router as view_router
from src.api.v1.ws import router as ws_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(org_router)
api_v1_router.include_router(project_router)
api_v1_router.include_router(task_router)
api_v1_router.include_router(view_router)
api_v1_router.include_router(time_router)
api_v1_router.include_router(integration_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(hr_router)
api_v1_router.include_router(client_router)
api_v1_router.include_router(notification_router)
api_v1_router.include_router(ws_router)
