"""Transactional historical ingestion shared by commands and background tasks."""

import logging
from dataclasses import asdict
from datetime import date
from time import monotonic

from django.db import transaction
from django.utils import timezone

from apps.market.models import (
    DailyPrice,
    Exchange,
    Security,
    SecurityExternalIdentifier,
)
from src.data_ingestion.base import MarketDataProvider
from src.data_ingestion.domain import HistoricalPrice, SecurityData, validate_range

from .models import IngestionRun

logger = logging.getLogger(__name__)
PRICE_FIELDS = ("open", "high", "low", "close", "adjusted_close", "volume", "source")
MAX_PROVIDER_ROWS = 20000


class IngestionError(Exception):
    """A failed batch whose diagnostic record is stored separately from prices."""


def _validate_rows(
    rows: list[HistoricalPrice], symbol: str, exchange: str, start: date, end: date
) -> dict[date, HistoricalPrice]:
    unique: dict[date, HistoricalPrice] = {}
    for row in rows:
        if not isinstance(row, HistoricalPrice):
            raise ValueError("Provider must return normalized HistoricalPrice records.")
        row.validate()
        if (row.symbol, row.exchange) != (
            symbol,
            exchange,
        ) or not start <= row.date <= end:
            raise ValueError("Provider returned a different security or date range.")
        if row.date in unique and unique[row.date] != row:
            raise ValueError("Conflicting duplicate dates in provider response.")
        unique[row.date] = row
    return unique


def _persist(
    metadata: SecurityData, rows: dict[date, HistoricalPrice]
) -> tuple[int, int]:
    exchange = Exchange.objects.get(code=metadata.exchange, is_active=True)
    defaults = asdict(metadata)
    defaults.pop("exchange")
    defaults.pop("symbol")
    candidate = Security(exchange=exchange, symbol=metadata.symbol, **defaults)
    candidate.full_clean(
        exclude=["exchange"], validate_unique=False, validate_constraints=False
    )
    security, _ = Security.objects.get_or_create(
        exchange=exchange, symbol=metadata.symbol, defaults=defaults
    )
    # PostgreSQL READ COMMITTED + this row lock serializes all service writers
    # for the same security, including concurrent first-time imports.
    security = Security.objects.select_for_update().get(pk=security.pk)
    if not security.is_active:
        raise ValueError("Security is inactive.")
    if not rows:
        return 0, 0
    existing = {
        row.date: row
        for row in DailyPrice.objects.filter(
            security=security, date__gte=min(rows), date__lte=max(rows)
        )
    }
    inserts, updates = [], []
    now = timezone.now()
    for day, bar in sorted(rows.items()):
        values = {field: getattr(bar, field) for field in PRICE_FIELDS}
        current = existing.get(day)
        if current is None:
            inserts.append(DailyPrice(security=security, date=day, **values))
        elif any(getattr(current, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(current, key, value)
            current.updated_at = now
            updates.append(current)
    DailyPrice.objects.bulk_create(inserts, batch_size=500)
    DailyPrice.objects.bulk_update(
        updates, [*PRICE_FIELDS, "updated_at"], batch_size=500
    )
    return len(inserts), len(updates)


def _external_identifier(symbol: str, exchange: str, provider_name: str) -> str | None:
    """Use a configured vendor identifier when the internal security already exists."""
    return (
        SecurityExternalIdentifier.objects.filter(
            security__exchange__code=exchange,
            security__symbol=symbol,
            provider=provider_name.lower(),
        )
        .values_list("identifier", flat=True)
        .first()
    )


def ingest_historical_prices(
    *, symbol: str, exchange: str, start: date, end: date, provider: MarketDataProvider
) -> IngestionRun:
    symbol, exchange = symbol.strip().upper(), exchange.strip().upper()
    run = IngestionRun.objects.create(
        provider=provider.name,
        symbol=symbol,
        exchange=exchange,
        start_date=start,
        end_date=end,
    )
    started = monotonic()
    rows: list[HistoricalPrice] = []
    try:
        validate_range(start, end)
        identifier = _external_identifier(symbol, exchange, provider.name)
        if identifier is None:
            metadata = provider.get_security(symbol, exchange)
        else:
            metadata = provider.get_security(symbol, exchange, identifier=identifier)
        if not isinstance(metadata, SecurityData) or (
            metadata.symbol,
            metadata.exchange,
        ) != (symbol, exchange):
            raise ValueError("Provider returned incorrect security metadata.")
        if identifier is None:
            provider_rows = provider.get_historical_prices(symbol, exchange, start, end)
        else:
            provider_rows = provider.get_historical_prices(
                symbol, exchange, start, end, identifier=identifier
            )
        for row in provider_rows:
            rows.append(row)
            if len(rows) > MAX_PROVIDER_ROWS:
                raise ValueError("Provider response exceeds the batch row limit.")
        unique = _validate_rows(rows, symbol, exchange, start, end)
        with transaction.atomic():
            run.rows_inserted, run.rows_updated = _persist(metadata, unique)
            run.rows_received = len(rows)
            run.status = IngestionRun.Status.SUCCESS
            run.finished_at = timezone.now()
            run.save()
    except Exception as exc:
        # Boundary-level catch ensures provider and database failures are observable.
        # Raw exception strings may contain vendor credentials, URLs or SQL values.
        run.rows_received = run.rows_failed = len(rows)
        run.rows_inserted = run.rows_updated = 0
        run.status = IngestionRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = (
            f"{type(exc).__name__}: historical ingestion failed; batch rolled back."
        )
        run.save()
        raise IngestionError(
            f"Ingestion run {run.pk} failed ({type(exc).__name__})."
        ) from exc
    finally:
        logger.info(
            "historical_ingestion_finished",
            extra={
                "run_id": run.pk,
                "provider": provider.name,
                "symbol": symbol,
                "exchange": exchange,
                "start": start,
                "end": end,
                "rows_received": run.rows_received,
                "rows_inserted": run.rows_inserted,
                "rows_updated": run.rows_updated,
                "rows_failed": run.rows_failed,
                "duration": round(monotonic() - started, 3),
                "status": run.status,
            },
        )
    return run
