from django.db import models
from django.utils import timezone


class IngestionRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    provider = models.CharField(max_length=64)
    dataset = models.CharField(max_length=64, default="daily_prices")
    symbol = models.CharField(max_length=32)
    exchange = models.CharField(max_length=16)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status, default=Status.RUNNING)
    rows_received = models.PositiveIntegerField(default=0)
    rows_inserted = models.PositiveIntegerField(default=0)
    rows_updated = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        indexes = [
            models.Index(
                fields=["status", "started_at"], name="run_status_started_idx"
            ),
            models.Index(
                fields=["provider", "started_at"], name="run_provider_started_idx"
            ),
        ]
