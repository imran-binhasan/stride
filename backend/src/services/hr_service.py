"""HR business logic — EmployeeProfile, LeaveRequest, Payroll."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from src.models.hr import LeaveStatus, PayrollStatus
from src.repositories.hr_repo import HRRepository
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


class HRService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = HRRepository(db)

    # ── Employee Profiles ─────────────────────────────────────────────────────

    async def create_profile(self, org_id: str, payload: EmployeeProfileCreate) -> EmployeeProfileResponse:
        existing = await self.repo.get_profile_by_user(org_id=org_id, user_id=payload.user_id)
        if existing:
            raise ConflictException("Employee profile already exists for this user")
        profile = await self.repo.create_profile(
            org_id=org_id,
            **payload.model_dump(),
        )
        return EmployeeProfileResponse.model_validate(profile)

    async def get_profile(self, profile_id: str, org_id: str) -> EmployeeProfileResponse:
        profile = await self.repo.get_profile_by_id(profile_id, org_id)
        if not profile:
            raise EntityNotFoundException("EmployeeProfile", profile_id)
        return EmployeeProfileResponse.model_validate(profile)

    async def list_profiles(self, org_id: str) -> list[EmployeeProfileResponse]:
        profiles = await self.repo.list_profiles(org_id)
        return [EmployeeProfileResponse.model_validate(p) for p in profiles]

    async def update_profile(
        self, profile_id: str, org_id: str, payload: EmployeeProfileUpdate
    ) -> EmployeeProfileResponse:
        profile = await self.repo.get_profile_by_id(profile_id, org_id)
        if not profile:
            raise EntityNotFoundException("EmployeeProfile", profile_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(profile, field, value)
        await self.db.flush()
        return EmployeeProfileResponse.model_validate(profile)

    # ── Leave Requests ────────────────────────────────────────────────────────

    async def request_leave(
        self, org_id: str, employee_id: str, payload: LeaveRequestCreate
    ) -> LeaveRequestResponse:
        if payload.end_date < payload.start_date:
            raise ValidationException("end_date must be on or after start_date")
        lr = await self.repo.create_leave_request(
            org_id=org_id,
            employee_id=employee_id,
            type=payload.type,
            status=LeaveStatus.PENDING,
            start_date=payload.start_date,
            end_date=payload.end_date,
            days_count=payload.days_count,
            reason=payload.reason,
        )
        return LeaveRequestResponse.model_validate(lr)

    async def review_leave(
        self, leave_id: str, org_id: str, reviewer_id: str, payload: LeaveRequestUpdate
    ) -> LeaveRequestResponse:
        lr = await self.repo.get_leave_request(leave_id, org_id)
        if not lr:
            raise EntityNotFoundException("LeaveRequest", leave_id)
        if lr.status != LeaveStatus.PENDING:
            raise ValidationException("Only PENDING leave requests can be reviewed")

        lr.status = payload.status
        lr.approved_by_id = reviewer_id
        if payload.rejection_reason:
            lr.rejection_reason = payload.rejection_reason
        await self.db.flush()
        return LeaveRequestResponse.model_validate(lr)

    async def list_leave_requests(
        self, org_id: str, employee_id: str | None = None, status: LeaveStatus | None = None
    ) -> list[LeaveRequestResponse]:
        requests = await self.repo.list_leave_requests(org_id, employee_id, status)
        return [LeaveRequestResponse.model_validate(r) for r in requests]

    # ── Payroll ────────────────────────────────────────────────────────────────

    async def create_payroll_run(
        self, org_id: str, processed_by_id: str, payload: PayrollRunCreate
    ) -> PayrollRunResponse:
        run = await self.repo.create_payroll_run(
            org_id=org_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            currency=payload.currency,
            notes=payload.notes,
            status=PayrollStatus.DRAFT,
            processed_by_id=processed_by_id,
        )
        return PayrollRunResponse.model_validate(run)

    async def get_payroll_run(self, run_id: str, org_id: str) -> PayrollRunResponse:
        run = await self.repo.get_payroll_run(run_id, org_id)
        if not run:
            raise EntityNotFoundException("PayrollRun", run_id)
        return PayrollRunResponse.model_validate(run)

    async def list_payroll_runs(self, org_id: str) -> list[PayrollRunResponse]:
        runs = await self.repo.list_payroll_runs(org_id)
        return [PayrollRunResponse.model_validate(r) for r in runs]
