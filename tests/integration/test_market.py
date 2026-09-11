from datetime import date
from decimal import Decimal

import pytest
from apps.market.models import DailyPrice, Exchange, Security
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def security():
    exchange = Exchange.objects.create(code="NSE", name="National Stock Exchange")
    return Security.objects.create(exchange=exchange, symbol="TCS", company_name="TCS")


def test_exchange_code_unique(security):
    with pytest.raises(IntegrityError), transaction.atomic():
        Exchange.objects.create(code="NSE", name="Duplicate")


def test_security_unique_within_exchange_only(security):
    with pytest.raises(IntegrityError), transaction.atomic():
        Security.objects.create(
            exchange=security.exchange, symbol="TCS", company_name="TCS"
        )
    bse = Exchange.objects.create(code="BSE", name="Bombay")
    Security.objects.create(exchange=bse, symbol="TCS", company_name="TCS")
    assert Security.objects.count() == 2


def bar(security, **overrides):
    return DailyPrice(
        **(
            dict(
                security=security,
                date=date(2026, 1, 5),
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=10,
                source="mock",
            )
            | overrides
        )
    )


def test_daily_price_unique(security):
    bar(security).save()
    with pytest.raises(IntegrityError), transaction.atomic():
        bar(security).save()


@pytest.mark.parametrize(
    "values", [{"high": 80}, {"open": -1}, {"close": -1}, {"volume": -1}]
)
def test_price_validation_and_database_constraints(security, values):
    row = bar(security, **values)
    with pytest.raises(ValidationError):
        row.full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        row.save()


def test_seed_markets_repeatable():
    call_command("seed_markets")
    call_command("seed_markets")
    assert set(Exchange.objects.values_list("code", flat=True)) == {"NSE", "BSE"}


def test_identifiers_are_normalized_and_database_enforced(security):
    exchange = Exchange.objects.create(code=" bse ", name="Bombay")
    stock = Security.objects.create(
        exchange=exchange, symbol=" infy ", company_name="Infosys"
    )
    assert exchange.code == "BSE"
    assert stock.symbol == "INFY"
    with pytest.raises(IntegrityError), transaction.atomic():
        Security.objects.filter(pk=stock.pk).update(symbol="infy")
    with pytest.raises(IntegrityError), transaction.atomic():
        Exchange.objects.filter(pk=exchange.pk).update(code="bse")


def test_admin_clean_normalizes_identifiers():
    exchange = Exchange(code=" nse ", name="National")
    exchange.full_clean()
    assert exchange.code == "NSE"
