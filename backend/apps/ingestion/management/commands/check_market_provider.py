from django.core.management.base import BaseCommand

from src.data_ingestion.exceptions import MarketDataProviderError
from src.data_ingestion.providers.factory import get_market_data_provider


class Command(BaseCommand):
    help = "Check configured market-data provider readiness without ingesting prices."

    def add_arguments(self, parser):
        parser.add_argument("--provider", required=True)

    def handle(self, *args, **options):
        provider_name = options["provider"]
        try:
            provider = get_market_data_provider(provider_name)
            provider.health_check()
        except MarketDataProviderError as exc:
            self.stdout.write(
                self.style.ERROR(f"NOT READY: {type(exc).__name__}: {exc}")
            )
            return
        self.stdout.write(self.style.SUCCESS(f"READY: {provider.name}"))
