from dataclasses import replace
from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from apps.ingestion.models import IngestionRun
from apps.ingestion.services import IngestionError, ingest_historical_prices
from apps.market.models import (
    DailyPrice,
    Exchange,
    Security,
    SecurityExternalIdentifier,
)
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
    def get_historical_prices(self, *args, identifier=None):
        for row in super().get_historical_prices(*args, identifier=identifier):
            yield replace(row, volume=777)


def test_changed_rows_are_updated():
    ingest()
    run = ingest(RevisedProvider())
    assert (run.rows_inserted, run.rows_updated) == (0, 3)
    assert set(DailyPrice.objects.values_list("volume", flat=True)) == {777}


class DuplicateProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args, identifier=None):
        rows = list(super().get_historical_prices(*args, identifier=identifier))
        return rows + rows


def test_identical_duplicates_collapsed():
    run = ingest(DuplicateProvider())
    assert (run.rows_received, run.rows_inserted) == (6, 3)


class ConflictProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args, identifier=None):
        rows = list(super().get_historical_prices(*args, identifier=identifier))
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
    def get_historical_prices(self, *args, identifier=None):
        for row in super().get_historical_prices(*args, identifier=identifier):
            yield replace(row, exchange="BSE")


def test_provider_cannot_contaminate_another_security():
    with pytest.raises(IngestionError):
        ingest(WrongSecurityProvider())
    assert not DailyPrice.objects.exists()


class BrokenProvider(MockMarketDataProvider):
    def get_historical_prices(self, *args, identifier=None):
        yield from super().get_historical_prices(*args, identifier=identifier)
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
        def get_historical_prices(self, *args, identifier=None):
            rows = list(super().get_historical_prices(*args, identifier=identifier))
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


def test_ingestion_uses_external_identifier_without_changing_security_symbol():
    captured = []

    class IdentifierProvider(MockMarketDataProvider):
        name = "nse"

        def get_security(self, symbol, exchange, identifier=None):
            captured.append(("security", symbol, identifier))
            return super().get_security(symbol, exchange, identifier)

        def get_historical_prices(self, symbol, exchange, start, end, identifier=None):
            captured.append(("prices", symbol, identifier))
            for row in super().get_historical_prices(
                symbol, exchange, start, end, identifier
            ):
                yield replace(row, source="nse_eod")

    stock = Security.objects.create(
        exchange=Exchange.objects.get(code="NSE"), symbol="TCS", company_name="TCS"
    )
    SecurityExternalIdentifier.objects.create(
        security=stock, provider="nse", identifier="TCS-EQ"
    )
    run = ingest(IdentifierProvider())
    assert run.rows_inserted == 3
    assert captured == [("security", "TCS", "TCS-EQ"), ("prices", "TCS", "TCS-EQ")]
    prices = DailyPrice.objects.filter(
        security=stock,
        date__range=(date(2026, 1, 5), date(2026, 1, 7)),
    ).order_by("date")
    assert prices.count() == 3
    assert [price.date for price in prices] == [
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
    ]
    assert all(price.security.symbol == "TCS" for price in prices)
    assert set(prices.values_list("source", flat=True)) == {"nse_eod"}


def test_real_provider_style_rows_are_idempotent():
    class NSEStyleProvider(MockMarketDataProvider):
        name = "nse"

        def get_historical_prices(self, *args, **kwargs):
            for row in super().get_historical_prices(*args, **kwargs):
                yield replace(row, source="nse_eod")

    first = ingest(NSEStyleProvider())
    second = ingest(NSEStyleProvider())
    assert (first.rows_inserted, second.rows_inserted, second.rows_updated) == (3, 0, 0)
    assert set(DailyPrice.objects.values_list("source", flat=True)) == {"nse_eod"}


def test_nse_bhavcopy_ingestion_is_idempotent(monkeypatch):
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    def report(rows):
        buffer = BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "pr05012026.csv",
                "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\n" + rows,
            )
        return buffer.getvalue()

    bhavcopy = report("TCS,EQ,4000,4050,3980,4025,12345\n")
    responses = iter([bhavcopy, bhavcopy, bhavcopy, bhavcopy])

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return self.payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: Response(next(responses)),
    )
    options = dict(
        symbol="TCS",
        exchange="NSE",
        start=date(2026, 1, 5),
        end=date(2026, 1, 5),
        provider=NSEMarketDataProvider(retry_attempts=1),
    )
    first = ingest_historical_prices(**options)
    second = ingest_historical_prices(**options)
    assert (first.rows_inserted, second.rows_inserted, second.rows_updated) == (1, 0, 0)
    assert DailyPrice.objects.get().source == "nse_eod"
    assert DailyPrice.objects.get().adjusted_close is None


def test_check_provider_command_reports_ready_and_not_ready(monkeypatch, capsys):
    from apps.ingestion.management.commands import check_market_provider

    from src.data_ingestion.exceptions import ProviderConfigurationError

    monkeypatch.setattr(
        check_market_provider,
        "get_market_data_provider",
        lambda name: MockMarketDataProvider(),
    )
    call_command("check_market_provider", provider="mock")
    assert "READY" in capsys.readouterr().out

    def unavailable(name):
        raise ProviderConfigurationError("missing BSE configuration")

    monkeypatch.setattr(check_market_provider, "get_market_data_provider", unavailable)
    call_command("check_market_provider", provider="bse")
    assert "NOT READY" in capsys.readouterr().out
