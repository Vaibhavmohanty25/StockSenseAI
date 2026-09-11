"""Run inside the web container after Compose is healthy; leaves synthetic fixtures."""

import json
import os
from urllib.request import urlopen
from uuid import uuid4

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stocksense.settings.development")
django.setup()

from apps.ingestion.models import IngestionRun  # noqa: E402
from apps.ingestion.tasks import ingest_prices  # noqa: E402
from apps.market.models import DailyPrice, Exchange  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402


def verify() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        print("Database:", cursor.fetchone()[0])
    cache_key = f"verification:{uuid4().hex}"
    try:
        cache.set(cache_key, "connected", timeout=30)
        assert cache.get(cache_key) == "connected"
    finally:
        cache.delete(cache_key)
    print("Redis cache: write/read verified")

    call_command("seed_markets")
    assert set(Exchange.objects.values_list("code", flat=True)) >= {"NSE", "BSE"}
    options = dict(
        symbol="TCS",
        exchange="NSE",
        start="2026-01-05",
        end="2026-01-09",
        provider="mock",
    )
    call_command("ingest_prices", **options)
    prices = DailyPrice.objects.filter(
        security__symbol="TCS",
        security__exchange__code="NSE",
        date__range=(options["start"], options["end"]),
    )
    assert prices.count() == 5
    call_command("ingest_prices", **options)
    second = IngestionRun.objects.filter(symbol="TCS", exchange="NSE").first()
    assert (second.rows_inserted, second.rows_updated, second.rows_failed) == (0, 0, 0)
    assert prices.count() == 5
    print("Synchronous ingestion: 5 persisted prices; repeated import changed 0 rows")

    result = ingest_prices.delay("INFY", "BSE", "2026-01-05", "2026-01-07", "mock")
    task = result.get(timeout=30)
    assert task["status"] == "success"
    assert IngestionRun.objects.get(pk=task["run_id"]).status == "success"
    assert (
        DailyPrice.objects.filter(
            security__symbol="INFY",
            security__exchange__code="BSE",
            date__range=("2026-01-05", "2026-01-07"),
        ).count()
        == 3
    )
    print("Celery/Redis: asynchronous ingestion and result retrieval verified")

    base = os.environ.get("VERIFY_API_URL", "http://127.0.0.1:8000/api/v1")
    responses = {}
    for path in (
        "health/",
        "stocks/",
        "stocks/TCS/?exchange=NSE",
        "stocks/TCS/prices/?exchange=NSE&start=2026-01-05&end=2026-01-09",
    ):
        with urlopen(f"{base}/{path}", timeout=10) as response:
            assert response.status == 200
            responses[path] = json.load(response)
    assert responses["health/"] == {
        "application": "ok",
        "database": "ok",
        "redis": "ok",
    }
    assert responses["stocks/TCS/?exchange=NSE"]["exchange"] == "NSE"
    assert (
        len(
            responses["stocks/TCS/prices/?exchange=NSE&start=2026-01-05&end=2026-01-09"]
        )
        == 5
    )
    print("HTTP: health, list, detail and persisted price responses verified")


if __name__ == "__main__":
    verify()
