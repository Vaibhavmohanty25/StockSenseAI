"""Centralized market-data provider resolution."""

import os

from ..base import MarketDataProvider
from ..exceptions import MarketDataProviderError
from .bse_provider import BSEMarketDataProvider
from .mock import MockMarketDataProvider
from .nse_provider import NSEMarketDataProvider

PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "mock": MockMarketDataProvider,
    "nse": NSEMarketDataProvider,
    "bse": BSEMarketDataProvider,
}


def get_market_data_provider(name: str) -> MarketDataProvider:
    try:
        provider_name = name.strip().lower()
        options = _client_options() if provider_name in {"nse", "bse"} else {}
        return PROVIDERS[provider_name](**options)
    except (AttributeError, KeyError) as exc:
        raise MarketDataProviderError(
            f"Unknown market-data provider: {name!r}."
        ) from exc


def _client_options() -> dict[str, float | int]:
    return {
        "timeout_seconds": float(os.getenv("MARKET_DATA_HTTP_TIMEOUT_SECONDS", "10")),
        "retry_attempts": int(os.getenv("MARKET_DATA_RETRY_ATTEMPTS", "3")),
        "retry_backoff_seconds": float(
            os.getenv("MARKET_DATA_RETRY_BACKOFF_SECONDS", "0.25")
        ),
    }
