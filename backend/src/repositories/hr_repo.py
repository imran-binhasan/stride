"""Database repository for HR — EmployeeProfile, LeaveRequest, Payroll."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.hr import (
    EmployeeProfile,
    LeaveRequest,
    LeaveStatus,
    PayrollItem,
    PayrollRun,
    PayrollStatus,
)


class HRRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Employee Profiles ─────────────────────────────────────────────────────

    async def get_profile_by_user(self, org_id: str, user_id: str) -> EmployeeProfile | None:
        stmt = select(EmployeeProfile).where(
            EmployeeProfile.org_id == org_id, EmployeeProfile.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_profile_by_id(self, profile_id: str, org_id: str) -> EmployeeProfile | None:
        stmt = select(EmployeeProfile).where(
            EmployeeProfile.id == profile_id, EmployeeProfile.org_id == org_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_profiles(self, org_id: str) -> list[EmployeeProfile]:
        stmt = (
            select(EmployeeProfile)
            .where(EmployeeProfile.org_id == org_id)
            .order_by(EmployeeProfile.employee_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_profile(self, **fields) -> EmployeeProfile:
        profile = EmployeeProfile(**fields)
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    # ── Leave Requests ────────────────────────────────────────────────────────

    async def create_leave_request(self, **fields) -> LeaveRequest:
        lr = LeaveRequest(**fields)
        self.db.add(lr)
        await self.db.flush()
        await self.db.refresh(lr)
        return lr

    async def get_leave_request(self, leave_id: str, org_id: str) -> LeaveRequest | None:
        stmt = select(LeaveRequest).where(
            LeaveRequest.id == leave_id, LeaveRequest.org_id == org_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_leave_requests(
        self, org_id: str, employee_id: str | None = None, status: LeaveStatus | None = None
    ) -> list[LeaveRequest]:
        stmt = select(LeaveRequest).where(LeaveRequest.org_id == org_id)
        if employee_id:
            stmt = stmt.where(LeaveRequest.employee_id == employee_id)
        if status:
            stmt = stmt.where(LeaveRequest.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Payroll ────────────────────────────────────────────────────────────────

    async def create_payroll_run(self, **fields) -> PayrollRun:
        run = PayrollRun(**fields)
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def get_payroll_run(self, run_id: str, org_id: str) -> PayrollRun | None:
        stmt = (
            select(PayrollRun)
            .where(PayrollRun.id == run_id, PayrollRun.org_id == org_id)
            .options(selectinload(PayrollRun.items))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_payroll_runs(self, org_id: str) -> list[PayrollRun]:
        stmt = (
            select(PayrollRun)
            .where(PayrollRun.org_id == org_id)
            .order_by(PayrollRun.period_start.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_payroll_item(self, **fields) -> PayrollItem:
        item = PayrollItem(**fields)
        self.db.add(item)
        await self.db.flush()
        return item
