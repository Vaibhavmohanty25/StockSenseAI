from django.contrib import admin

from .models import IngestionRun


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "symbol",
        "exchange",
        "status",
        "started_at",
        "finished_at",
        "rows_received",
        "rows_inserted",
        "rows_updated",
        "rows_failed",
    )
    search_fields = ("symbol", "exchange", "provider", "error_message")
    list_filter = ("status", "provider", "dataset", "exchange")
    ordering = ("-started_at", "-pk")
    readonly_fields = tuple(field.name for field in IngestionRun._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
