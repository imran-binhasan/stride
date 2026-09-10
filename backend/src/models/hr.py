"""HR domain — EmployeeProfile, LeaveRequest, PayrollRun, PayrollItem."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid, utc_now

if TYPE_CHECKING:
    from src.models.auth import Department, User


class EmploymentType(enum.StrEnum):
    FULL_TIME   = "FULL_TIME"
    PART_TIME   = "PART_TIME"
    CONTRACTOR  = "CONTRACTOR"
    INTERN      = "INTERN"


class LeaveType(enum.StrEnum):
    VACATION   = "VACATION"
    SICK       = "SICK"
    PERSONAL   = "PERSONAL"
    MATERNITY  = "MATERNITY"
    PATERNITY  = "PATERNITY"
    OTHER      = "OTHER"


class LeaveStatus(enum.StrEnum):
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PayrollStatus(enum.StrEnum):
    DRAFT      = "DRAFT"
    PROCESSING = "PROCESSING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"


class PayItemStatus(enum.StrEnum):
    PENDING = "PENDING"
    PAID    = "PAID"
    FAILED  = "FAILED"


# ── Employee Profile ───────────────────────────────────────────────────────────

class EmployeeProfile(Base, TimestampedModel, TenantScopedModel):
    __tablename__ = "employee_profiles"

    id              : Mapped[str]             = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id         : Mapped[str]             = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    department_id   : Mapped[str|None]        = mapped_column(String(36), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    manager_id      : Mapped[str|None]        = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    employee_id     : Mapped[str]             = mapped_column(String(50), nullable=False)
    job_title       : Mapped[str]             = mapped_column(String(255), nullable=False)
    employment_type : Mapped[EmploymentType]  = mapped_column(Enum(EmploymentType, native_enum=False, length=20), default=EmploymentType.FULL_TIME, nullable=False)
    hire_date       : Mapped[date]            = mapped_column(Date, nullable=False)
    termination_date: Mapped[date|None]       = mapped_column(Date, nullable=True)
    work_hours_per_week: Mapped[float]        = mapped_column(default=40.0, nullable=False)
    hourly_rate     : Mapped[float]           = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    currency        : Mapped[str]             = mapped_column(String(3), default="USD", nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "employee_id", name="uq_employee_id_per_org"),
        UniqueConstraint("org_id", "user_id",     name="uq_employee_profile_user"),
    )

    user      : Mapped[User]           = relationship("User", foreign_keys=[user_id], back_populates="employee_profile")
    manager   : Mapped[User|None]      = relationship("User", foreign_keys=[manager_id])
    department: Mapped[Department|None] = relationship("Department", foreign_keys=[department_id])
    leave_requests: Mapped[list[LeaveRequest]] = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    payroll_items : Mapped[list[PayrollItem]]  = relationship("PayrollItem",  back_populates="employee")


# ── Leave Requests ─────────────────────────────────────────────────────────────

class LeaveRequest(Base, TimestampedModel, TenantScopedModel):
    __tablename__ = "leave_requests"

    id               : Mapped[str]          = mapped_column(String(36), primary_key=True, default=generate_uuid)
    employee_id      : Mapped[str]          = mapped_column(String(36), ForeignKey("employee_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    type             : Mapped[LeaveType]    = mapped_column(Enum(LeaveType,   native_enum=False, length=20), nullable=False)
    status           : Mapped[LeaveStatus]  = mapped_column(Enum(LeaveStatus, native_enum=False, length=20), default=LeaveStatus.PENDING, nullable=False)
    start_date       : Mapped[date]         = mapped_column(Date, nullable=False)
    end_date         : Mapped[date]         = mapped_column(Date, nullable=False)
    days_count       : Mapped[float]        = mapped_column(nullable=False)
    reason           : Mapped[str|None]     = mapped_column(Text, nullable=True)
    rejection_reason : Mapped[str|None]     = mapped_column(Text, nullable=True)
    approved_by_id   : Mapped[str|None]     = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    employee   : Mapped[EmployeeProfile] = relationship("EmployeeProfile", back_populates="leave_requests")
    approved_by: Mapped[User|None]       = relationship("User", foreign_keys=[approved_by_id])


# ── Payroll ────────────────────────────────────────────────────────────────────

class PayrollRun(Base, TimestampedModel, TenantScopedModel):
    __tablename__ = "payroll_runs"

    id              : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    period_start    : Mapped[date]          = mapped_column(Date, nullable=False)
    period_end      : Mapped[date]          = mapped_column(Date, nullable=False)
    status          : Mapped[PayrollStatus] = mapped_column(Enum(PayrollStatus, native_enum=False, length=20), default=PayrollStatus.DRAFT, nullable=False)
    total_amount    : Mapped[float]         = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    currency        : Mapped[str]           = mapped_column(String(3), default="USD", nullable=False)
    notes           : Mapped[str|None]      = mapped_column(Text, nullable=True)
    processed_by_id : Mapped[str|None]      = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    items       : Mapped[list[PayrollItem]] = relationship("PayrollItem", back_populates="payroll_run", cascade="all, delete-orphan")
    processed_by: Mapped[User|None]         = relationship("User", foreign_keys=[processed_by_id])


class PayrollItem(Base, TimestampedModel):
    __tablename__ = "payroll_items"

    id                  : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    payroll_run_id      : Mapped[str]           = mapped_column(String(36), ForeignKey("payroll_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    employee_id         : Mapped[str]           = mapped_column(String(36), ForeignKey("employee_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    regular_hours       : Mapped[float]         = mapped_column(default=0.0, nullable=False)
    overtime_hours      : Mapped[float]         = mapped_column(default=0.0, nullable=False)
    gross_amount        : Mapped[float]         = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    deductions          : Mapped[float]         = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    net_amount          : Mapped[float]         = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    currency            : Mapped[str]           = mapped_column(String(3), default="USD", nullable=False)
    status              : Mapped[PayItemStatus] = mapped_column(Enum(PayItemStatus, native_enum=False, length=20), default=PayItemStatus.PENDING, nullable=False)
    payment_reference   : Mapped[str|None]      = mapped_column(String(255), nullable=True)

    payroll_run: Mapped[PayrollRun]     = relationship("PayrollRun", back_populates="items")
    employee   : Mapped[EmployeeProfile] = relationship("EmployeeProfile", back_populates="payroll_items")
