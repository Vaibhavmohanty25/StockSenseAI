from apps.core.health import dependency_health
from apps.market.selectors import get_security, list_prices, list_securities
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    DailyPriceSerializer,
    HealthSerializer,
    PriceQuerySerializer,
    SecurityQuerySerializer,
    SecuritySerializer,
)


class StockPagination(LimitOffsetPagination):
    default_limit = 100
    max_limit = 1000


class HealthView(APIView):
    def get(self, request):
        health = dependency_health()
        return Response(
            HealthSerializer(health).data,
            status=200 if health["application"] == "ok" else 503,
        )


class StockListView(ListAPIView):
    serializer_class = SecuritySerializer
    pagination_class = StockPagination

    def get_queryset(self):
        query = SecurityQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        return list_securities(**query.validated_data)


class StockDetailView(APIView):
    def get(self, request, symbol: str):
        query = SecurityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        security = get_security(symbol, **query.validated_data)
        return Response(SecuritySerializer(security).data)


class StockPricesView(APIView):
    def get(self, request, symbol: str):
        query = PriceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = dict(query.validated_data)
        security = get_security(symbol, filters.pop("exchange", None))
        return Response(
            DailyPriceSerializer(list_prices(security, **filters), many=True).data
        )
