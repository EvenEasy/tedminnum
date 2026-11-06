from decimal import ROUND_HALF_UP, Decimal


class Problem(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status
        super().__init__(message)


def require(condition: bool, message: str, status: int = 400) -> None:
    if not condition:
        raise Problem(message, status)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def hourly_amount(seconds: int, rate: Decimal) -> Decimal:
    return money(Decimal(seconds) * rate / Decimal(3600))


def effective_rate(task: Decimal | None, project: Decimal | None, client: Decimal) -> Decimal:
    return task if task is not None else project if project is not None else client
