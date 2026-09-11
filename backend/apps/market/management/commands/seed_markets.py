from django.core.management.base import BaseCommand
from django.db import transaction

from apps.market.models import Exchange


class Command(BaseCommand):
    help = "Idempotently seed NSE and BSE exchange reference metadata."

    @transaction.atomic
    def handle(self, *args, **options):
        for code, name in (
            ("NSE", "National Stock Exchange of India"),
            ("BSE", "Bombay Stock Exchange"),
        ):
            Exchange.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "country": "IN",
                    "currency": "INR",
                    "timezone": "Asia/Kolkata",
                },
            )
        self.stdout.write(self.style.SUCCESS("Seeded NSE and BSE."))
