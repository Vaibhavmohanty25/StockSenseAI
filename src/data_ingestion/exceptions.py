"""Provider-boundary errors safe to expose to application layers."""


class MarketDataProviderError(ValueError):
    """Base class for expected market-data provider failures."""


class ProviderUnavailableError(MarketDataProviderError):
    """A provider could not be reached after bounded retries."""


class ProviderAuthenticationError(MarketDataProviderError):
    """Configured provider credentials were rejected."""


class ProviderConfigurationError(MarketDataProviderError):
    """Required provider configuration is absent or invalid."""


class SymbolNotFoundError(MarketDataProviderError):
    """The requested provider identifier does not identify a security."""


class ProviderRateLimitError(MarketDataProviderError):
    """The provider declined a request because its rate limit was exceeded."""


class MalformedProviderResponseError(MarketDataProviderError):
    """A provider response could not be normalized safely."""
