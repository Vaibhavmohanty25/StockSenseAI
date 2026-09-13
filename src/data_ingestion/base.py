from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date

from .domain import HistoricalPrice, SecurityData


class MarketDataProvider(ABC):
    """Adapters normalize vendor responses before crossing this boundary."""

    name: str

    @abstractmethod
    def get_security(
        self, symbol: str, exchange: str, identifier: str | None = None
    ) -> SecurityData:
        """Return metadata or raise ValueError for an unsupported security."""

    @abstractmethod
    def get_historical_prices(
        self,
        symbol: str,
        exchange: str,
        start: date,
        end: date,
        identifier: str | None = None,
    ) -> Iterable[HistoricalPrice]:
        """Return normalized daily bars for the inclusive interval."""

    def health_check(self) -> None:
        """Perform a lightweight provider readiness check when supported."""
        return None
