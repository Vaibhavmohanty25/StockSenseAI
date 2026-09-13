from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Trim, Upper

from apps.core.models import TimestampedModel
from src.data_ingestion.domain import HistoricalPrice


class Exchange(TimestampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=2, default="IN")
    currency = models.CharField(max_length=3, default="INR")
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(code=Upper(Trim(F("code")))) & ~Q(code=""),
                name="exchange_code_canonical",
            )
        ]

    def clean(self) -> None:
        self.code = self.code.strip().upper()
        super().clean()

    def save(self, *args, **kwargs) -> None:
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.code


class Security(TimestampedModel):
    class Type(models.TextChoices):
        EQUITY = "equity", "Equity"
        ETF = "etf", "ETF"
        INDEX = "index", "Index"

    exchange = models.ForeignKey(
        Exchange, on_delete=models.PROTECT, related_name="securities"
    )
    symbol = models.CharField(max_length=32, db_index=True)
    company_name = models.CharField(max_length=255)
    isin = models.CharField(max_length=12, blank=True, db_index=True)
    sector = models.CharField(max_length=128, blank=True, db_index=True)
    industry = models.CharField(max_length=128, blank=True)
    security_type = models.CharField(max_length=16, choices=Type, default=Type.EQUITY)
    listing_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["exchange__code", "symbol"]
        constraints = [
            models.UniqueConstraint(
                fields=["exchange", "symbol"], name="security_exchange_symbol_uniq"
            ),
            models.CheckConstraint(
                condition=Q(symbol=Upper(Trim(F("symbol")))) & ~Q(symbol=""),
                name="security_symbol_canonical",
            ),
        ]
        indexes = [
            models.Index(
                fields=["exchange", "is_active"], name="security_exchange_active_idx"
            )
        ]

    def clean(self) -> None:
        self.symbol = self.symbol.strip().upper()
        super().clean()

    def save(self, *args, **kwargs) -> None:
        self.symbol = self.symbol.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.exchange.code}:{self.symbol}"


class SecurityExternalIdentifier(TimestampedModel):
    """Vendor identifier distinct from the internal security symbol."""

    security = models.ForeignKey(
        Security, on_delete=models.PROTECT, related_name="external_identifiers"
    )
    provider = models.CharField(max_length=64)
    identifier = models.CharField(max_length=128)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["security", "provider"],
                name="security_provider_identifier_uniq",
            ),
            models.UniqueConstraint(
                fields=["provider", "identifier"], name="provider_identifier_uniq"
            ),
        ]
        indexes = [
            models.Index(
                fields=["provider", "identifier"], name="provider_identifier_idx"
            )
        ]

    def clean(self) -> None:
        self.provider = self.provider.strip().lower()
        self.identifier = self.identifier.strip()
        if not self.provider or not self.identifier:
            raise ValidationError("Provider and external identifier are required.")
        super().clean()

    def save(self, *args, **kwargs) -> None:
        self.provider = self.provider.strip().lower()
        self.identifier = self.identifier.strip()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.provider}:{self.identifier} ({self.security})"


class DailyPrice(TimestampedModel):
    security = models.ForeignKey(
        Security, on_delete=models.PROTECT, related_name="prices"
    )
    date = models.DateField(db_index=True)
    open = models.DecimalField(
        max_digits=20, decimal_places=6, validators=[MinValueValidator(Decimal(0))]
    )
    high = models.DecimalField(
        max_digits=20, decimal_places=6, validators=[MinValueValidator(Decimal(0))]
    )
    low = models.DecimalField(
        max_digits=20, decimal_places=6, validators=[MinValueValidator(Decimal(0))]
    )
    close = models.DecimalField(
        max_digits=20, decimal_places=6, validators=[MinValueValidator(Decimal(0))]
    )
    adjusted_close = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal(0))],
    )
    volume = models.PositiveBigIntegerField()
    source = models.CharField(max_length=64)

    class Meta:
        ordering = ["date", "security_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["security", "date"], name="price_security_date_uniq"
            ),
            models.CheckConstraint(
                condition=Q(high__gte=F("low")), name="price_high_gte_low"
            ),
            models.CheckConstraint(
                condition=Q(open__gte=0) & Q(close__gte=0) & Q(low__gte=0),
                name="price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(open__gte=F("low"))
                & Q(open__lte=F("high"))
                & Q(close__gte=F("low"))
                & Q(close__lte=F("high")),
                name="price_ohlc_bounds",
            ),
            models.CheckConstraint(
                condition=Q(adjusted_close__isnull=True) | Q(adjusted_close__gte=0),
                name="price_adjusted_nonnegative",
            ),
        ]
        # The FK and date field provide individual indexes; the unique constraint
        # provides the composite B-tree for security + date range scans.

    def clean(self) -> None:
        super().clean()
        try:
            HistoricalPrice(
                symbol="validation",
                exchange="validation",
                date=self.date,
                open=self.open,
                high=self.high,
                low=self.low,
                close=self.close,
                adjusted_close=self.adjusted_close,
                volume=self.volume,
                source=self.source,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
