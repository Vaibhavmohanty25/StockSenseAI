"""Vendor-neutral data contracts. Prices are exact, finite decimal values."""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal


def validate_range(start: Date, end: Date) -> None:
    if type(start) is not Date or type(end) is not Date:
        raise ValueError("Start and end must be dates.")
    if start > end or (end - start).days > 3660:
        raise ValueError("Date range must be ordered and at most 3660 days.")


def validate_identifier(value: str, name: str, max_length: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"Invalid {name}.")
    if value != value.strip():
        raise ValueError(f"{name} must not contain surrounding whitespace.")


def validate_decimal(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a nonnegative finite Decimal.")
    if value >= Decimal("100000000000000"):
        raise ValueError(f"{name} exceeds supported precision.")
    if value != value.quantize(Decimal("0.000001")):
        raise ValueError(f"{name} supports at most six decimal places.")


@dataclass(frozen=True, slots=True)
class SecurityData:
    symbol: str
    exchange: str
    company_name: str
    isin: str = ""
    sector: str = ""
    industry: str = ""
    security_type: str = "equity"
    listing_date: Date | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.symbol, "symbol", 32)
        validate_identifier(self.exchange, "exchange", 16)
        validate_identifier(self.company_name, "company_name", 255)
        if self.listing_date is not None and type(self.listing_date) is not Date:
            raise ValueError("listing_date must be a date.")


@dataclass(frozen=True, slots=True)
class HistoricalPrice:
    symbol: str
    exchange: str
    date: Date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int
    source: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        validate_identifier(self.symbol, "symbol", 32)
        validate_identifier(self.exchange, "exchange", 16)
        validate_identifier(self.source, "source", 64)
        if type(self.date) is not Date:
            raise ValueError("Price date must be a date, not a string or datetime.")
        for name in ("open", "high", "low", "close", "adjusted_close"):
            value = getattr(self, name)
            if name == "adjusted_close" and value is None:
                continue
            validate_decimal(value, name)
        if self.high < self.low:
            raise ValueError("High must be greater than or equal to low.")
        if (
            not self.low <= self.open <= self.high
            or not self.low <= self.close <= self.high
        ):
            raise ValueError("Open and close must be within low and high.")
        if type(self.volume) is not int or not 0 <= self.volume <= 9223372036854775807:
            raise ValueError("Volume must be a nonnegative 64-bit integer.")
