from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ingestion.services import IngestionError, ingest_historical_prices
from src.data_ingestion.providers.registry import get_provider


class Command(BaseCommand):
    help = "Ingest inclusive historical daily prices through a configured provider."

    def add_arguments(self, parser):
        for name in ("symbol", "exchange", "start", "end"):
            parser.add_argument(f"--{name}", required=True)
        parser.add_argument("--provider", default=settings.MARKET_DATA_PROVIDER)

    def handle(self, *args, **options):
        try:
            run = ingest_historical_prices(
                symbol=options["symbol"],
                exchange=options["exchange"],
                start=date.fromisoformat(options["start"]),
                end=date.fromisoformat(options["end"]),
                provider=get_provider(options["provider"]),
            )
        except (ValueError, IngestionError) as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(
            self.style.SUCCESS(
                f"Run {run.pk}: received={run.rows_received} "
                f"inserted={run.rows_inserted} "
                f"updated={run.rows_updated} failed={run.rows_failed}"
            )
        )
