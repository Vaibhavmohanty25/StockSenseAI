from datetime import date

import pytest
from apps.ingestion.services import ingest_historical_prices
from apps.market.models import Exchange, Security
from django.core.management import call_command
from django.db import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError

from src.data_ingestion.providers.mock import MockMarketDataProvider

pytestmark = pytest.mark.django_db


@pytest.fixture
def populated():
    call_command("seed_markets")
    ingest_historical_prices(
        symbol="TCS",
        exchange="NSE",
        start=date(2026, 1, 5),
        end=date(2026, 1, 9),
        provider=MockMarketDataProvider(),
    )


def test_stock_list_is_database_backed(client, populated):
    response = client.get("/api/v1/stocks/")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["symbol"] == "TCS"
    assert response.json()["results"][0]["exchange"] == "NSE"


def test_detail_and_exchange_ambiguity(client, populated):
    assert client.get("/api/v1/stocks/TCS/").json()["symbol"] == "TCS"
    Security.objects.create(
        exchange=Exchange.objects.get(code="BSE"), symbol="TCS", company_name="BSE TCS"
    )
    assert client.get("/api/v1/stocks/TCS/").status_code == 400
    response = client.get("/api/v1/stocks/TCS/?exchange=BSE")
    assert response.json()["company_name"] == "BSE TCS"
    assert client.get("/api/v1/stocks/?exchange=BSE").json()["count"] == 1


def test_prices_filter_and_order(client, populated):
    response = client.get(
        "/api/v1/stocks/TCS/prices/?start=2026-01-06&end=2026-01-08&limit=2"
    )
    assert response.status_code == 200
    assert [r["date"] for r in response.json()] == ["2026-01-06", "2026-01-07"]
    assert isinstance(response.json()[0]["close"], str)
    assert response.json()[0]["source"] == "mock"


@pytest.mark.parametrize(
    "query",
    [
        "start=invalid",
        "end=2026-02-30",
        "limit=0",
        "limit=1001",
        "limit=abc",
        "start=2026-02-01&end=2026-01-01",
    ],
)
def test_invalid_price_queries_are_400(client, populated, query):
    assert client.get(f"/api/v1/stocks/TCS/prices/?{query}").status_code == 400


@pytest.mark.parametrize(
    "path", ["/api/v1/stocks/UNKNOWN/", "/api/v1/stocks/UNKNOWN/prices/"]
)
def test_unknown_symbol_is_404(client, path):
    assert client.get(path).status_code == 404


def test_empty_price_range(client, populated):
    assert client.get("/api/v1/stocks/TCS/prices/?start=2027-01-01").json() == []


def test_health_dependency_failures_are_503(client, monkeypatch):
    def db_failure(*args, **kwargs):
        raise OperationalError("private database credentials")

    def redis_failure(*args, **kwargs):
        raise RedisConnectionError("private redis credentials")

    monkeypatch.setattr("django.db.backends.utils.CursorWrapper.execute", db_failure)
    monkeypatch.setattr("redis.Redis.ping", redis_failure)
    response = client.get("/api/v1/health/")
    assert response.status_code == 503
    assert response.json() == {
        "application": "degraded",
        "database": "unavailable",
        "redis": "unavailable",
    }
    assert b"credentials" not in response.content


@pytest.mark.infrastructure
def test_health_checks_live_dependencies(client):
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"application": "ok", "database": "ok", "redis": "ok"}
