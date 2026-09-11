from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date

from .domain import HistoricalPrice, SecurityData


class MarketDataProvider(ABC):
    """Adapters normalize vendor responses before crossing this boundary."""

    name: str

    @abstractmethod
    def get_security(self, symbol: str, exchange: str) -> SecurityData:
        """Return metadata or raise ValueError for an unsupported security."""

    @abstractmethod
    def get_historical_prices(
        self,
        symbol: str,
        exchange: str,
        start: date,
        end: date,
    ) -> Iterable[HistoricalPrice]:
        """Return normalized daily bars for the inclusive interval."""
