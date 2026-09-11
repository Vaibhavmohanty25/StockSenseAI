from ..base import MarketDataProvider
from .mock import MockMarketDataProvider

PROVIDERS: dict[str, type[MarketDataProvider]] = {"mock": MockMarketDataProvider}


def get_provider(name: str) -> MarketDataProvider:
    try:
        factory = PROVIDERS[name]
    except KeyError as exc:
        raise ValueError("Unknown market-data provider.") from exc
    return factory()
