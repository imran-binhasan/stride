"""Calendar arithmetic independent of the API and database."""

import calendar
from datetime import datetime, time, timedelta

from croniter import croniter
from src.schemas.recurrence import RecurrenceRule


def next_due(rule: RecurrenceRule, current):
    if rule.frequency == "DAILY":
        value = current + timedelta(days=rule.interval)
    elif rule.frequency == "WEEKLY":
        if not rule.weekdays:
            value = current + timedelta(weeks=rule.interval)
        else:
            value = current + timedelta(days=1)
            anchor = current - timedelta(days=current.weekday())
            while (
                value.weekday() not in rule.weekdays or ((value - anchor).days // 7) % rule.interval
            ):
                value += timedelta(days=1)
    elif rule.frequency == "MONTHLY":
        month = current.year * 12 + current.month - 1 + rule.interval
        year, month = divmod(month, 12)
        month += 1
        value = current.replace(
            year=year, month=month, day=min(current.day, calendar.monthrange(year, month)[1])
        )
    else:
        # Task due dates have day precision: advance to the next calendar day matching cron.
        value = (
            croniter(rule.cron, datetime.combine(current, time.max), max_years_between_matches=8)
            .get_next(datetime)
            .date()
        )
    if rule.until and value > rule.until:
        return None
    return value
