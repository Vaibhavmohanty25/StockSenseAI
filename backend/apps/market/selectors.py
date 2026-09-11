from datetime import date

from django.db.models import QuerySet
from django.http import Http404
from rest_framework.exceptions import ValidationError

from .models import DailyPrice, Security


def list_securities(exchange: str | None = None) -> QuerySet[Security]:
    queryset = Security.objects.select_related("exchange").order_by(
        "exchange__code", "symbol"
    )
    return queryset.filter(exchange__code=exchange.upper()) if exchange else queryset


def get_security(symbol: str, exchange: str | None = None) -> Security:
    matches = list(list_securities(exchange).filter(symbol=symbol.upper())[:2])
    if not matches:
        raise Http404("Security not found.")
    if len(matches) > 1:
        raise ValidationError(
            {"exchange": "Symbol exists on multiple exchanges; supply exchange."}
        )
    return matches[0]


def list_prices(
    security: Security,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
) -> QuerySet[DailyPrice]:
    queryset = DailyPrice.objects.filter(security=security)
    if start:
        queryset = queryset.filter(date__gte=start)
    if end:
        queryset = queryset.filter(date__lte=end)
    return queryset.order_by("date")[:limit]
