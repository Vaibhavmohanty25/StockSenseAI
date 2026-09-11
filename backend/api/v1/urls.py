from django.urls import path

from .views import HealthView, StockDetailView, StockListView, StockPricesView

app_name = "v1"
urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("stocks/", StockListView.as_view(), name="stocks"),
    path("stocks/<str:symbol>/", StockDetailView.as_view(), name="stock-detail"),
    path("stocks/<str:symbol>/prices/", StockPricesView.as_view(), name="stock-prices"),
]
