"""Pydantic v2 schemas for HR — EmployeeProfile, LeaveRequest, Payroll."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.hr import EmploymentType, LeaveStatus, LeaveType, PayItemStatus, PayrollStatus


class EmployeeProfileCreate(BaseModel):
    user_id: str
    department_id: str | None = None
    manager_id: str | None = None
    employee_id: str = Field(min_length=1, max_length=50)
    job_title: str = Field(min_length=1, max_length=255)
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    hire_date: date
    work_hours_per_week: float = 40.0
    hourly_rate: float = 0.0
    currency: str = "USD"


class EmployeeProfileUpdate(BaseModel):
    department_id: str | None = None
    manager_id: str | None = None
    job_title: str | None = None
    employment_type: EmploymentType | None = None
    work_hours_per_week: float | None = None
    hourly_rate: float | None = None
    currency: str | None = None
    termination_date: date | None = None


class EmployeeProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    user_id: str
    department_id: str | None
    manager_id: str | None
    employee_id: str
    job_title: str
    employment_type: EmploymentType
    hire_date: date
    termination_date: date | None
    work_hours_per_week: float
    hourly_rate: float
    currency: str
    created_at: datetime


class LeaveRequestCreate(BaseModel):
    type: LeaveType
    start_date: date
    end_date: date
    days_count: float = Field(gt=0)
    reason: str | None = None


class LeaveRequestUpdate(BaseModel):
    status: LeaveStatus
    rejection_reason: str | None = None


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    employee_id: str
    type: LeaveType
    status: LeaveStatus
    start_date: date
    end_date: date
    days_count: float
    reason: str | None
    rejection_reason: str | None
    approved_by_id: str | None
    created_at: datetime


class PayrollRunCreate(BaseModel):
    period_start: date
    period_end: date
    currency: str = "USD"
    notes: str | None = None


class PayrollItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payroll_run_id: str
    employee_id: str
    regular_hours: float
    overtime_hours: float
    gross_amount: float
    deductions: float
    net_amount: float
    currency: str
    status: PayItemStatus
    payment_reference: str | None


class PayrollRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    period_start: date
    period_end: date
    status: PayrollStatus
    total_amount: float
    currency: str
    notes: str | None
    processed_by_id: str | None
    created_at: datetime
    items: list[PayrollItemResponse] = []
