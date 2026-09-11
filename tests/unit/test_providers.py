from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.data_ingestion.base import MarketDataProvider
from src.data_ingestion.domain import HistoricalPrice
from src.data_ingestion.providers.mock import MockMarketDataProvider


def price(**overrides):
    values = dict(
        symbol="TCS",
        exchange="NSE",
        date=date(2026, 1, 5),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        adjusted_close=None,
        volume=100,
        source="mock",
    )
    return HistoricalPrice(**(values | overrides))


def test_provider_requires_both_operations():
    with pytest.raises(TypeError):
        MarketDataProvider()


@pytest.mark.parametrize(
    "values",
    [
        {"high": Decimal("80")},
        {"open": Decimal("-1")},
        {"close": Decimal("-1")},
        {"volume": -1},
        {"date": "2026-02-30"},
        {"open": 1.2},
        {"close": Decimal("NaN")},
        {"volume": 1.5},
        {"low": Decimal("-1")},
        {"adjusted_close": Decimal("-1")},
        {"close": Decimal("1.1234567")},
        {"source": ""},
    ],
)
def test_price_rejects_invalid_domain_data(values):
    with pytest.raises(ValueError):
        price(**values)


def test_price_preserves_decimal_and_optional_adjustment():
    row = price()
    assert row.close == Decimal("105")
    assert row.adjusted_close is None


def test_mock_has_stable_values_across_overlapping_requests():
    provider = MockMarketDataProvider()
    rows = list(
        provider.get_historical_prices("TCS", "NSE", date(2026, 1, 2), date(2026, 1, 6))
    )
    assert [r.date for r in rows] == [
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 6),
    ]
    subset = list(
        provider.get_historical_prices("TCS", "NSE", date(2026, 1, 5), date(2026, 1, 6))
    )
    assert rows[1:] == subset
    assert provider.get_security("TCS", "BSE").exchange == "BSE"
    assert rows[0].source == "mock"
    assert replace(rows[0], volume=0).volume == 0


def test_mock_rejects_unknown_security_and_reversed_range():
    provider = MockMarketDataProvider()
    with pytest.raises(ValueError):
        provider.get_security("UNKNOWN", "NSE")
    with pytest.raises(ValueError):
        list(
            provider.get_historical_prices(
                "TCS", "NSE", date(2026, 2, 1), date(2026, 1, 1)
            )
        )


def test_unknown_provider_rejected():
    from src.data_ingestion.providers.registry import get_provider

    with pytest.raises(ValueError):
        get_provider("unconfigured-vendor")


def test_historical_request_is_bounded():
    from src.data_ingestion.domain import validate_range

    with pytest.raises(ValueError):
        validate_range(date(2000, 1, 1), date(2026, 1, 1))
