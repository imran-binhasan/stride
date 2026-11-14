"""Bounded calendar recurrence rules. Weekdays use ISO Monday=0 conventions."""

from datetime import date
from typing import Literal

from croniter import croniter
from pydantic import BaseModel, Field, model_validator


class RecurrenceRule(BaseModel):
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY", "CRON"]
    interval: int = Field(default=1, ge=1, le=365)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    until: date | None = None
    cron: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def valid_rule(self):
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("Weekdays must be between 0 (Monday) and 6 (Sunday)")
        if self.frequency == "CRON" and (
            not self.cron or len(self.cron.split()) != 5 or not croniter.is_valid(self.cron)
        ):
            raise ValueError("A valid five-field cron expression is required")
        return self
