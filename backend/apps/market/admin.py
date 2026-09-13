from django.contrib import admin

from .models import DailyPrice, Exchange, Security, SecurityExternalIdentifier


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "country", "currency", "timezone", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active", "country")
    ordering = ("code",)


@admin.register(Security)
class SecurityAdmin(admin.ModelAdmin):
    list_display = (
        "symbol",
        "exchange",
        "company_name",
        "security_type",
        "sector",
        "is_active",
    )
    list_filter = ("exchange", "security_type", "is_active", "sector")
    search_fields = ("symbol", "company_name", "isin")
    list_select_related = ("exchange",)
    ordering = ("exchange__code", "symbol")


@admin.register(SecurityExternalIdentifier)
class SecurityExternalIdentifierAdmin(admin.ModelAdmin):
    list_display = ("provider", "identifier", "security", "updated_at")
    list_select_related = ("security", "security__exchange")
    search_fields = ("provider", "identifier", "security__symbol")
    list_filter = ("provider", "security__exchange")


@admin.register(DailyPrice)
class DailyPriceAdmin(admin.ModelAdmin):
    list_display = (
        "security",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
    )
    list_filter = ("source", "security__exchange", "date")
    search_fields = ("security__symbol", "security__company_name")
    list_select_related = ("security", "security__exchange")
    autocomplete_fields = ("security",)
    ordering = ("-date", "security_id")
    date_hierarchy = "date"
