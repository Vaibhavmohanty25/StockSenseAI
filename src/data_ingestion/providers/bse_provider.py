"""BSE adapter for an explicitly configured official BSE data service."""

import logging
import os
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from time import monotonic

from ..base import MarketDataProvider
from ..domain import HistoricalPrice, SecurityData, validate_range
from ..exceptions import (
    MalformedProviderResponseError,
    ProviderConfigurationError,
    SymbolNotFoundError,
)
from .http import JSONHTTPClient

logger = logging.getLogger(__name__)


class BSEMarketDataProvider(MarketDataProvider):
    name = "bse"
    source = "bse_eod"

    def __init__(self, **client_options) -> None:
        self.base_url = os.getenv("BSE_API_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("BSE_API_KEY", "")
        if not self.base_url or not self.api_key:
            raise ProviderConfigurationError(
                "BSE_API_BASE_URL and BSE_API_KEY are required for BSE."
            )
        self.client = JSONHTTPClient(**client_options)

    def get_security(
        self, symbol: str, exchange: str, identifier: str | None = None
    ) -> SecurityData:
        self._check_exchange(exchange)
        payload = self.client.get_json(
            f"{self.base_url}/security",
            params={"identifier": identifier or symbol},
            headers=self._headers(),
        )
        if not isinstance(payload, Mapping):
            raise MalformedProviderResponseError("BSE response must be an object.")
        data = payload.get("data", payload)
        if not isinstance(data, Mapping):
            raise SymbolNotFoundError("BSE security was not found.")
        name = data.get("company_name") or data.get("companyName")
        if not isinstance(name, str) or not name.strip():
            raise SymbolNotFoundError("BSE security was not found.")
        return SecurityData(
            symbol=symbol,
            exchange="BSE",
            company_name=name.strip(),
            isin=str(data.get("isin", "")),
        )

    def get_historical_prices(
        self,
        symbol: str,
        exchange: str,
        start: date,
        end: date,
        identifier: str | None = None,
    ) -> Iterable[HistoricalPrice]:
        started = monotonic()
        self._check_exchange(exchange)
        validate_range(start, end)
        try:
            payload = self.client.get_json(
                f"{self.base_url}/historical",
                params={
                    "identifier": identifier or symbol,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
                headers=self._headers(),
            )
            if not isinstance(payload, Mapping) or not isinstance(
                payload.get("data"), list
            ):
                raise MalformedProviderResponseError(
                    "BSE response has no price data list."
                )
            rows = payload["data"]
            normalized = [self._normalize_row(symbol, row) for row in rows]
        except Exception as exc:
            self._log(symbol, start, end, monotonic() - started, 0, 0, "failed", exc)
            raise
        self._log(
            symbol,
            start,
            end,
            monotonic() - started,
            len(rows),
            len(normalized),
            "success",
        )
        return normalized

    def health_check(self) -> None:
        self.client.get_json(f"{self.base_url}/health", headers=self._headers())

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    @staticmethod
    def _check_exchange(exchange: str) -> None:
        if exchange != "BSE":
            raise SymbolNotFoundError("BSE provider only supports BSE securities.")

    def _normalize_row(self, symbol: str, row: object) -> HistoricalPrice:
        if not isinstance(row, Mapping):
            raise MalformedProviderResponseError("BSE price row is malformed.")
        try:
            close = self._decimal(row, "close")
            adjusted = row.get("adjusted_close")
            return HistoricalPrice(
                symbol=symbol,
                exchange="BSE",
                date=date.fromisoformat(self._string(row, "date")),
                open=self._decimal(row, "open"),
                high=self._decimal(row, "high"),
                low=self._decimal(row, "low"),
                close=close,
                adjusted_close=self._decimal(row, "adjusted_close")
                if adjusted not in (None, "")
                else close,
                volume=int(self._string(row, "volume").replace(",", "")),
                source=self.source,
            )
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise MalformedProviderResponseError(
                "BSE price row cannot be normalized."
            ) from exc

    @staticmethod
    def _string(row: Mapping[str, object], field: str) -> str:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise MalformedProviderResponseError(f"BSE {field} is missing.")
        return value.strip()

    def _decimal(self, row: Mapping[str, object], field: str) -> Decimal:
        return Decimal(self._string(row, field).replace(",", "")).quantize(
            Decimal("0.000001")
        )

    def _log(
        self, symbol, start, end, duration, received, normalized, status, error=None
    ) -> None:
        logger.info(
            "provider_historical_prices_finished",
            extra={
                "provider": self.name,
                "exchange": "BSE",
                "symbol": symbol,
                "start": start,
                "end": end,
                "duration": round(duration, 3),
                "rows_received": received,
                "rows_normalized": normalized,
                "rows_rejected": received - normalized,
                "status": status,
                "error_type": type(error).__name__ if error else None,
            },
        )
