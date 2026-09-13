"""Small shared JSON client for provider adapters."""

import json
import logging
from collections.abc import Mapping
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ..exceptions import (
    MalformedProviderResponseError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)


class JSONHTTPClient:
    """Bounded-retry client; urllib follows standard HTTP redirects by default."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.25,
        user_agent: str = "StockSenseAI/1.5 market-data ingestion",
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = max(1, retry_attempts)
        self.retry_backoff_seconds = max(0, retry_backoff_seconds)
        self.user_agent = user_agent

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> object:
        payload = self.get_bytes(url, params=params, headers=headers)
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedProviderResponseError(
                "Provider returned invalid JSON."
            ) from exc

    def get_bytes(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        query = urlencode(params or {}, doseq=True)
        request_url = f"{url}?{query}" if query else url
        request_headers = {"Accept": "*/*", "User-Agent": self.user_agent}
        request_headers.update(headers or {})
        request = Request(request_url, headers=request_headers)
        logger.debug(
            "provider_binary_request",
            extra={"request_url": self._safe_url(request.full_url)},
        )
        for attempt in range(self.retry_attempts):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    logger.debug(
                        "provider_binary_response",
                        extra={
                            "request_url": self._safe_url(request.full_url),
                            "final_url": self._safe_url(
                                self._response_url(response, request.full_url)
                            ),
                        },
                    )
                    return response.read()
            except HTTPError as exc:
                if exc.code == 404:
                    raise SymbolNotFoundError(
                        "Provider security was not found."
                    ) from exc
                if exc.code in {401, 403}:
                    raise ProviderAuthenticationError(
                        "Provider authentication was rejected."
                    ) from exc
                if exc.code == 429:
                    raise ProviderRateLimitError(
                        "Provider rate limit was exceeded."
                    ) from exc
                if exc.code not in {500, 502, 503, 504}:
                    raise ProviderUnavailableError(
                        "Provider request was rejected."
                    ) from exc
            except (URLError, TimeoutError, OSError) as exc:
                if attempt == self.retry_attempts - 1:
                    raise ProviderUnavailableError("Provider is unavailable.") from exc
            if attempt < self.retry_attempts - 1:
                sleep(self.retry_backoff_seconds * (2**attempt))
        raise ProviderUnavailableError("Provider is unavailable.")

    @staticmethod
    def _safe_url(url: str) -> str:
        """Keep debug URLs useful without exposing query-string credentials."""
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    @staticmethod
    def _response_url(response: object, request_url: str) -> str:
        """Use urllib's redirected URL when available, including test doubles."""
        geturl = getattr(response, "geturl", None)
        if not callable(geturl):
            return request_url
        final_url = geturl()
        return final_url if isinstance(final_url, str) else request_url
