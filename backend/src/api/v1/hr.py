"""HR — EmployeeProfile, LeaveRequest, Payroll API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.models.hr import LeaveStatus
from src.schemas.hr import (
    EmployeeProfileCreate,
    EmployeeProfileResponse,
    EmployeeProfileUpdate,
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveRequestUpdate,
    PayrollRunCreate,
    PayrollRunResponse,
)
from src.services.hr_service import HRService

router = APIRouter(prefix="/hr", tags=["HR"])


# ── Employee Profiles ─────────────────────────────────────────────────────────

@router.post("/employees", response_model=EmployeeProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_employee_profile(
    payload: EmployeeProfileCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmployeeProfileResponse:
    return await HRService(db).create_profile(org_id=ctx.org_id, payload=payload)


@router.get("/employees", response_model=list[EmployeeProfileResponse])
async def list_employee_profiles(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[EmployeeProfileResponse]:
    return await HRService(db).list_profiles(org_id=ctx.org_id)


@router.get("/employees/{profile_id}", response_model=EmployeeProfileResponse)
async def get_employee_profile(
    profile_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmployeeProfileResponse:
    return await HRService(db).get_profile(profile_id=profile_id, org_id=ctx.org_id)


@router.patch("/employees/{profile_id}", response_model=EmployeeProfileResponse)
async def update_employee_profile(
    profile_id: str,
    payload: EmployeeProfileUpdate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmployeeProfileResponse:
    return await HRService(db).update_profile(
        profile_id=profile_id, org_id=ctx.org_id, payload=payload
    )


# ── Leave Requests ────────────────────────────────────────────────────────────

@router.post("/leaves", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_leave(
    payload: LeaveRequestCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LeaveRequestResponse:
    """Submit a leave request for the acting employee."""
    service = HRService(db)
    from src.repositories.hr_repo import HRRepository
    profile = await HRRepository(db).get_profile_by_user(ctx.org_id, ctx.user.id)
    if not profile:
        from src.core.exceptions import EntityNotFoundException
        raise EntityNotFoundException("EmployeeProfile", ctx.user.id)
    return await service.request_leave(
        org_id=ctx.org_id, employee_id=profile.id, payload=payload
    )


@router.get("/leaves", response_model=list[LeaveRequestResponse])
async def list_leave_requests(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: Annotated[LeaveStatus | None, Query(alias="status")] = None,
) -> list[LeaveRequestResponse]:
    return await HRService(db).list_leave_requests(
        org_id=ctx.org_id, status=status_filter
    )


@router.patch("/leaves/{leave_id}", response_model=LeaveRequestResponse)
async def review_leave_request(
    leave_id: str,
    payload: LeaveRequestUpdate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LeaveRequestResponse:
    return await HRService(db).review_leave(
        leave_id=leave_id, org_id=ctx.org_id, reviewer_id=ctx.user.id, payload=payload
    )


# ── Payroll ────────────────────────────────────────────────────────────────────

@router.post("/payroll/runs", response_model=PayrollRunResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_run(
    payload: PayrollRunCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PAYROLL_RUN))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PayrollRunResponse:
    return await HRService(db).create_payroll_run(
        org_id=ctx.org_id, processed_by_id=ctx.user.id, payload=payload
    )


@router.get("/payroll/runs", response_model=list[PayrollRunResponse])
async def list_payroll_runs(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PayrollRunResponse]:
    return await HRService(db).list_payroll_runs(org_id=ctx.org_id)


@router.get("/payroll/runs/{run_id}", response_model=PayrollRunResponse)
async def get_payroll_run(
    run_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.HR_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PayrollRunResponse:
    return await HRService(db).get_payroll_run(run_id=run_id, org_id=ctx.org_id)
