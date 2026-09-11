from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

from ..base import MarketDataProvider
from ..domain import HistoricalPrice, SecurityData, validate_range


class MockMarketDataProvider(MarketDataProvider):
    """Synthetic weekday bars, not real prices or an exchange holiday calendar."""

    name = "mock"
    companies = {
        "TCS": "Tata Consultancy Services",
        "INFY": "Infosys",
        "RELIANCE": "Reliance Industries",
    }

    def get_security(self, symbol: str, exchange: str) -> SecurityData:
        if exchange not in {"NSE", "BSE"} or symbol not in self.companies:
            raise ValueError("Unsupported mock security or exchange.")
        return SecurityData(
            symbol=symbol,
            exchange=exchange,
            company_name=f"{self.companies[symbol]} (synthetic fixture)",
        )

    def get_historical_prices(
        self,
        symbol: str,
        exchange: str,
        start: date,
        end: date,
    ) -> Iterable[HistoricalPrice]:
        self.get_security(symbol, exchange)
        validate_range(start, end)
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            opening = Decimal(100 + sum(map(ord, symbol)) + day.toordinal() % 100)
            yield HistoricalPrice(
                symbol=symbol,
                exchange=exchange,
                date=day,
                open=opening,
                high=opening + 3,
                low=opening - 2,
                close=opening + 1,
                adjusted_close=opening + 1,
                volume=1000 + day.toordinal() % 1000,
                source=self.name,
            )
