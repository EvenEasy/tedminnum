from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from ted.domain.models import TimeEntry
from ted.domain.rules import effective_rate, hourly_amount, money


def test_exact_money_and_rate_precedence():
    assert effective_rate(Decimal(0), Decimal(50), Decimal(100)) == 0
    assert effective_rate(None, Decimal(50), Decimal(100)) == 50
    assert effective_rate(None, None, Decimal(100)) == 100
    assert hourly_amount(1, Decimal("18.00")) == Decimal("0.01")
    assert hourly_amount(3601, Decimal("120")) == Decimal("120.03")
    assert money(Decimal("1.005")) == Decimal("1.01")


def test_pauses_are_exact_before_rounding_to_whole_work_seconds():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    e = TimeEntry(
        user_id=uuid4(),
        billable=False,
        started_at=start,
        ended_at=start + timedelta(seconds=10, microseconds=500000),
        paused_microseconds=700000,
    )
    assert e.seconds() == 9
    e.ended_at = None
    e.paused_at = start + timedelta(seconds=4)
    assert e.seconds() == 3
