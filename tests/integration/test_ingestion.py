from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from apps.ingestion.models import IngestionRun
from apps.ingestion.services import IngestionError, ingest_historical_prices
from apps.market.models import DailyPrice
from django.core.management import call_command

from src.data_ingestion.providers.mock import MockMarketDataProvider

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def exchanges():
    call_command("seed_markets")


def ingest(provider=None):
    return ingest_historical_prices(
        symbol="TCS",
        exchange="NSE",
        start=date(2026, 1, 5),
        end=date(2026, 1, 7),
        provider=provider or MockMarketDataProvider(),
    )


def test_ingestion_persists_and_is_idempotent():
    first = ingest()
    second = ingest()
    assert (first.rows_received, first.rows_inserted, first.rows_updated) == (3, 3, 0)
    assert (second.rows_inserted, second.rows_updated, second.rows_failed) == (0, 0, 0)
    assert DailyPrice.objects.count() == 3
    assert second.status == IngestionRun.Status.SUCCESS
    assert second.finished_at >= second.started_at


class RevisedProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args):
        for row in super().get_historical_prices(*args):
            yield replace(row, volume=777)


def test_changed_rows_are_updated():
    ingest()
    run = ingest(RevisedProvider())
    assert (run.rows_inserted, run.rows_updated) == (0, 3)
    assert set(DailyPrice.objects.values_list("volume", flat=True)) == {777}


class DuplicateProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args):
        rows = list(super().get_historical_prices(*args))
        return rows + rows


def test_identical_duplicates_collapsed():
    run = ingest(DuplicateProvider())
    assert (run.rows_received, run.rows_inserted) == (6, 3)


class ConflictProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args):
        rows = list(super().get_historical_prices(*args))
        return rows + [replace(rows[0], volume=999)]


def test_conflicting_duplicates_fail_without_partial_writes():
    with pytest.raises(IngestionError):
        ingest(ConflictProvider())
    run = IngestionRun.objects.get()
    assert run.status == IngestionRun.Status.FAILED
    assert run.rows_received == run.rows_failed == 4
    assert run.rows_inserted == run.rows_updated == 0
    assert not DailyPrice.objects.exists()


class WrongSecurityProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args):
        for row in super().get_historical_prices(*args):
            yield replace(row, exchange="BSE")


def test_provider_cannot_contaminate_another_security():
    with pytest.raises(IngestionError):
        ingest(WrongSecurityProvider())
    assert not DailyPrice.objects.exists()


class BrokenProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args):
        yield from super().get_historical_prices(*args)
        raise RuntimeError("vendor error containing secret-key")


def test_provider_failure_is_observed_without_leaking_secrets():
    with pytest.raises(IngestionError):
        ingest(BrokenProvider())
    run = IngestionRun.objects.get()
    assert run.rows_failed == 3
    assert run.finished_at is not None
    assert "secret-key" not in run.error_message
    assert not DailyPrice.objects.exists()


def test_ingestion_command_uses_service():
    call_command(
        "ingest_prices",
        symbol="TCS",
        exchange="NSE",
        start="2026-01-05",
        end="2026-01-07",
        provider="mock",
    )
    assert DailyPrice.objects.count() == 3
    assert isinstance(DailyPrice.objects.first().close, Decimal)


def test_eager_celery_task_persists_through_service():
    from apps.ingestion.tasks import ingest_prices

    result = ingest_prices.apply(
        kwargs=dict(
            symbol="INFY",
            exchange="BSE",
            start="2026-01-05",
            end="2026-01-07",
            provider="mock",
        )
    ).get()
    assert result["inserted"] == 3
    assert IngestionRun.objects.get(pk=result["run_id"]).status == "success"
    assert DailyPrice.objects.filter(security__exchange__code="BSE").count() == 3


def test_bulk_import_does_not_issue_queries_per_price():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as queries:
        run = ingest_historical_prices(
            symbol="TCS",
            exchange="NSE",
            start=date(2025, 1, 1),
            end=date(2025, 12, 31),
            provider=MockMarketDataProvider(),
        )
    assert run.rows_inserted == 261
    assert len(queries) < 20


def test_database_failure_rolls_back_prices_but_preserves_run(monkeypatch):
    from django.db import IntegrityError
    from django.db.models.query import QuerySet

    ingest()
    before = list(DailyPrice.objects.order_by("date").values_list("date", "volume"))

    def fail_update(*args, **kwargs):
        raise IntegrityError("simulated failure after bulk inserts")

    monkeypatch.setattr(QuerySet, "bulk_update", fail_update)
    with pytest.raises(IngestionError):
        ingest_historical_prices(
            symbol="TCS",
            exchange="NSE",
            start=date(2026, 1, 5),
            end=date(2026, 1, 9),
            provider=RevisedProvider(),
        )
    assert (
        list(DailyPrice.objects.order_by("date").values_list("date", "volume"))
        == before
    )
    run = IngestionRun.objects.first()
    assert run.status == "failed"
    assert (
        run.rows_received,
        run.rows_failed,
        run.rows_inserted,
        run.rows_updated,
    ) == (5, 5, 0, 0)


@pytest.mark.django_db(transaction=True)
def test_concurrent_initial_imports_have_accurate_counts():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import connections

    barrier = Barrier(2)

    class ConcurrentProvider(MockMarketDataProvider):
        def get_historical_prices(self, *args):
            rows = list(super().get_historical_prices(*args))
            barrier.wait(timeout=10)
            return rows

    def import_in_thread():
        try:
            run = ingest(ConcurrentProvider())
            return run.rows_inserted, run.rows_updated
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(import_in_thread) for _ in range(2)]
        results = [job.result(timeout=30) for job in jobs]
    assert sorted(results) == [(0, 0), (3, 0)]
    assert DailyPrice.objects.count() == 3


def test_empty_weekend_is_successful():
    run = ingest_historical_prices(
        symbol="TCS",
        exchange="NSE",
        start=date(2026, 1, 3),
        end=date(2026, 1, 4),
        provider=MockMarketDataProvider(),
    )
    assert run.status == "success"
    assert run.rows_received == run.rows_inserted == 0


def test_inactive_exchange_rejected():
    from apps.market.models import Exchange

    Exchange.objects.filter(code="NSE").update(is_active=False)
    with pytest.raises(IngestionError):
        ingest()
    assert not DailyPrice.objects.exists()
