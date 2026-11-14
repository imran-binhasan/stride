"""HR business logic — EmployeeProfile, LeaveRequest, Payroll."""

from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from src.models.auth import Department, MemberStatus, Organization
from src.models.hr import LeaveStatus, PayrollItem, PayrollRun, PayrollStatus
from src.models.time_tracking import TimeEntry, TimeEntryStatus
from src.repositories.hr_repo import HRRepository
from src.repositories.user_repo import UserRepository
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
from src.services.notification_service import NotificationService
from src.services.time_service import ensure_utc


class HRService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = HRRepository(db)

    # ── Employee Profiles ─────────────────────────────────────────────────────

    async def create_profile(
        self, org_id: str, payload: EmployeeProfileCreate
    ) -> EmployeeProfileResponse:
        await self._validate_profile_links(org_id, payload)
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
        await self._validate_profile_links(org_id, payload)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is None and field not in {"department_id", "manager_id", "termination_date"}:
                raise ValidationException(f"{field} cannot be null")
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

        if payload.status not in {LeaveStatus.APPROVED, LeaveStatus.REJECTED}:
            raise ValidationException("Review must approve or reject a leave request")
        employee = await self.repo.get_profile_by_id(lr.employee_id, org_id)
        if employee.user_id == reviewer_id:
            raise ValidationException("You cannot review your own leave request")
        if payload.status == LeaveStatus.REJECTED and not (payload.rejection_reason or "").strip():
            raise ValidationException("A rejection reason is required")
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
        if payload.period_end < payload.period_start:
            raise ValidationException("Payroll end must be on or after start")
        await self.db.execute(
            select(Organization.id).where(Organization.id == org_id).with_for_update()
        )
        overlap = await self.db.scalar(
            select(PayrollItem.id)
            .join(PayrollItem.payroll_run)
            .where(
                PayrollRun.org_id == org_id,
                PayrollRun.period_start <= payload.period_end,
                PayrollRun.period_end >= payload.period_start,
            )
            .limit(1)
        )
        if overlap:
            raise ConflictException("Payroll period overlaps an existing calculated run")
        run = await self.repo.create_payroll_run(
            org_id=org_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            currency=payload.currency,
            notes=payload.notes,
            status=PayrollStatus.DRAFT,
            processed_by_id=processed_by_id,
        )
        profiles = await self.repo.list_profiles(org_id)
        start = datetime.combine(payload.period_start, time.min, tzinfo=UTC)
        end = datetime.combine(payload.period_end + timedelta(days=1), time.min, tzinfo=UTC)
        total = Decimal("0")
        for profile in profiles:
            if profile.currency != payload.currency:
                continue
            entries = list(
                await self.db.scalars(
                    select(TimeEntry).where(
                        TimeEntry.org_id == org_id,
                        TimeEntry.user_id == profile.user_id,
                        TimeEntry.status == TimeEntryStatus.APPROVED,
                        TimeEntry.start_time < end,
                        TimeEntry.end_time > start,
                    )
                )
            )
            seconds = 0
            for entry in entries:
                entry_start, entry_end = ensure_utc(entry.start_time), ensure_utc(entry.end_time)
                duration = max(1, (entry_end - entry_start).total_seconds())
                overlap_seconds = max(
                    0, (min(end, entry_end) - max(start, entry_start)).total_seconds()
                )
                seconds += (
                    max(0, entry.total_seconds - entry.idle_seconds) * overlap_seconds / duration
                )
            hours = Decimal(str(seconds)) / Decimal(3600)
            gross = (hours * Decimal(str(profile.hourly_rate))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            self.db.add(
                PayrollItem(
                    payroll_run_id=run.id,
                    employee_id=profile.id,
                    regular_hours=float(hours),
                    overtime_hours=0,
                    gross_amount=gross,
                    deductions=0,
                    net_amount=gross,
                    currency=payload.currency,
                )
            )
            total += gross
        run.total_amount = total
        await self.db.flush()
        await NotificationService(self.db).log_audit(
            org_id, "payroll.calculated", processed_by_id, "payroll_run", run.id
        )
        run = await self.repo.get_payroll_run(run.id, org_id)
        return PayrollRunResponse.model_validate(run)

    async def get_payroll_run(self, run_id: str, org_id: str) -> PayrollRunResponse:
        run = await self.repo.get_payroll_run(run_id, org_id)
        if not run:
            raise EntityNotFoundException("PayrollRun", run_id)
        return PayrollRunResponse.model_validate(run)

    async def list_payroll_runs(self, org_id: str) -> list[PayrollRunResponse]:
        runs = await self.repo.list_payroll_runs(org_id)
        return [PayrollRunResponse.model_validate(r) for r in runs]

    async def _validate_profile_links(self, org_id, payload):
        repo = UserRepository(self.db)
        for key in ("user_id", "manager_id"):
            value = getattr(payload, key, None)
            if value:
                membership = await repo.get_org_membership(org_id, value)
                if not membership or membership.status != MemberStatus.ACTIVE:
                    raise ValidationException(
                        f"{key} must be an active member of this organization"
                    )
        if payload.department_id and not await self.db.scalar(
            select(Department.id).where(
                Department.id == payload.department_id, Department.org_id == org_id
            )
        ):
            raise ValidationException("Department must belong to this organization")
