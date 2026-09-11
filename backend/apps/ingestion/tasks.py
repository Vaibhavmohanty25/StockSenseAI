from datetime import date

from celery import shared_task
from django.conf import settings

from src.data_ingestion.providers.registry import get_provider

from .services import ingest_historical_prices


@shared_task
def ingest_prices(
    symbol: str, exchange: str, start: str, end: str, provider: str | None = None
) -> dict[str, int | str]:
    """Task inputs and output are JSON-safe; service owns all ingestion behavior."""
    run = ingest_historical_prices(
        symbol=symbol,
        exchange=exchange,
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        provider=get_provider(provider or settings.MARKET_DATA_PROVIDER),
    )
    return {
        "run_id": run.pk,
        "status": run.status,
        "inserted": run.rows_inserted,
        "updated": run.rows_updated,
    }
