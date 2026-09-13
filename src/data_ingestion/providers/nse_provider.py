"""NSE adapter using the exchange's official downloadable daily Bhavcopy reports."""

import logging
from collections.abc import Iterable, Mapping
from csv import DictReader
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from time import monotonic
from zipfile import BadZipFile, ZipFile

from ..base import MarketDataProvider
from ..domain import HistoricalPrice, SecurityData, validate_range
from ..exceptions import (
    MalformedProviderResponseError,
    ProviderUnavailableError,
    SymbolNotFoundError,
)
from .http import JSONHTTPClient

logger = logging.getLogger(__name__)


class NSEMarketDataProvider(MarketDataProvider):
    name = "nse"
    source = "nse_eod"
    recent_report_window_days = 14
    udiff_bhavcopy_url_template = (
        "https://nsearchives.nseindia.com/content/cm/"
        "BhavCopy_NSE_CM_0_0_0_{date:%Y%m%d}_F_0000.csv.zip"
    )
    press_bhavcopy_url_template = (
        "https://nsearchives.nseindia.com/content/cm/PR{date:%d%m%y}.zip"
    )

    def __init__(self, **client_options) -> None:
        self.client = JSONHTTPClient(**client_options)

    def get_security(
        self, symbol: str, exchange: str, identifier: str | None = None
    ) -> SecurityData:
        self._check_exchange(exchange)
        report_symbol = (identifier or symbol).upper()
        for row in self._recent_bhavcopy_rows():
            if row["SYMBOL"] == report_symbol and row["SERIES"] == "EQ":
                return SecurityData(
                    symbol=symbol,
                    exchange="NSE",
                    company_name=row.get("NAME OF COMPANY") or symbol,
                    isin=row.get("ISIN", ""),
                )
        raise SymbolNotFoundError("NSE security was not found in a recent Bhavcopy.")

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
            normalized = self._historical_rows(symbol, start, end, identifier)
        except Exception as exc:
            self._log(symbol, start, end, monotonic() - started, 0, 0, "failed", exc)
            raise
        self._log(
            symbol,
            start,
            end,
            monotonic() - started,
            len(normalized),
            len(normalized),
            "success",
        )
        return normalized

    def health_check(self) -> None:
        self._recent_bhavcopy_rows()

    def _recent_bhavcopy_rows(
        self, reference_date: date | None = None
    ) -> list[dict[str, str]]:
        reference_date = reference_date or date.today()
        for offset in range(1, self.recent_report_window_days + 1):
            day = reference_date - timedelta(days=offset)
            if day.weekday() >= 5:
                self._log_candidate(day, "none", "weekend")
                continue
            rows = self._download_bhavcopy(day)
            if rows is None:
                continue
            return rows
        raise ProviderUnavailableError("No recent NSE Bhavcopy report is available.")

    @staticmethod
    def _check_exchange(exchange: str) -> None:
        if exchange != "NSE":
            raise SymbolNotFoundError("NSE provider only supports NSE securities.")

    @staticmethod
    def _string(row: Mapping[str, object], field: str) -> str:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise MalformedProviderResponseError(f"NSE {field} is missing.")
        return value.strip()

    def _historical_rows(
        self, symbol: str, start: date, end: date, identifier: str | None
    ) -> list[HistoricalPrice]:
        normalized = []
        report_symbol = (identifier or symbol).upper()
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            report_rows = self._download_bhavcopy(day)
            if report_rows is None:
                continue
            for row in report_rows:
                if row["SYMBOL"] != report_symbol or row["SERIES"] != "EQ":
                    continue
                normalized.append(self._normalize_bhavcopy_row(symbol, day, row))
        return normalized

    def _download_bhavcopy(self, day: date) -> list[dict[str, str]] | None:
        """Try the current UDiFF archive, then NSE's documented PR archive."""
        unavailable_error = None
        for report_source, url in self._bhavcopy_urls(day):
            try:
                report = self.client.get_bytes(url)
            except SymbolNotFoundError:
                # A dated archive 404 is a normal non-trading-day outcome.  The
                # HTTP client intentionally does not retry this permanent response.
                self._log_candidate(day, report_source, "missing")
                continue
            except ProviderUnavailableError as exc:
                # The client has completed bounded retries for a transient source
                # failure. The other official archive may still be available.
                unavailable_error = exc
                self._log_candidate(day, report_source, "unavailable")
                continue
            rows = self._read_bhavcopy(report)
            self._log_candidate(day, report_source, "ready")
            return rows
        if unavailable_error is not None:
            raise unavailable_error
        return None

    @classmethod
    def _bhavcopy_urls(cls, day: date) -> tuple[tuple[str, str], ...]:
        return (
            ("udiff", cls.udiff_bhavcopy_url_template.format(date=day)),
            ("press", cls.press_bhavcopy_url_template.format(date=day)),
        )

    def _read_bhavcopy(self, report: bytes) -> list[dict[str, str]]:
        if not report:
            raise MalformedProviderResponseError("NSE Bhavcopy report is empty.")
        try:
            with ZipFile(BytesIO(report)) as archive:
                candidates = [
                    name for name in archive.namelist() if name.lower().endswith(".csv")
                ]
                for name in candidates:
                    content = archive.read(name).decode("utf-8-sig")
                    reader = DictReader(StringIO(content))
                    if reader.fieldnames is None:
                        continue
                    fieldnames = {
                        field.strip().upper(): field for field in reader.fieldnames
                    }
                    legacy_required = {
                        "SYMBOL",
                        "SERIES",
                        "OPEN",
                        "HIGH",
                        "LOW",
                        "CLOSE",
                        "TOTTRDQTY",
                    }
                    udiff_fields = {
                        "TCKRSYMB": "SYMBOL",
                        "SCTYSRS": "SERIES",
                        "OPNPRIC": "OPEN",
                        "HGHPRIC": "HIGH",
                        "LWPRIC": "LOW",
                        "CLSPRIC": "CLOSE",
                        "TTLTRADGVOL": "TOTTRDQTY",
                    }
                    if legacy_required.issubset(fieldnames):
                        aliases = {field: field for field in legacy_required}
                        aliases.update(
                            {
                                field: field
                                for field in ("ISIN", "NAME OF COMPANY")
                                if field in fieldnames
                            }
                        )
                    elif set(udiff_fields).issubset(fieldnames):
                        aliases = dict(udiff_fields)
                        if "ISIN" in fieldnames:
                            aliases["ISIN"] = "ISIN"
                    else:
                        continue
                    rows = []
                    for row in reader:
                        if any(value is None for value in row.values()):
                            continue
                        normalized_row = {
                            target: (row[fieldnames[source]] or "").strip()
                            for source, target in aliases.items()
                        }
                        rows.append(normalized_row)
                    return rows
        except (BadZipFile, UnicodeDecodeError, OSError) as exc:
            raise MalformedProviderResponseError(
                "NSE Bhavcopy report cannot be parsed."
            ) from exc
        raise MalformedProviderResponseError(
            "NSE Bhavcopy does not contain an OHLCV CSV file."
        )

    def _normalize_bhavcopy_row(
        self, symbol: str, day: date, row: Mapping[str, str]
    ) -> HistoricalPrice:
        try:
            closing = self._decimal(row, "CLOSE")
            return HistoricalPrice(
                symbol=symbol,
                exchange="NSE",
                date=day,
                open=self._decimal(row, "OPEN"),
                high=self._decimal(row, "HIGH"),
                low=self._decimal(row, "LOW"),
                close=closing,
                adjusted_close=None,
                volume=int(self._string(row, "TOTTRDQTY").replace(",", "")),
                source=self.source,
            )
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise MalformedProviderResponseError(
                "NSE price row cannot be normalized."
            ) from exc

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
                "exchange": "NSE",
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

    def _log_candidate(self, day: date, report_source: str, status: str) -> None:
        logger.info(
            "nse_bhavcopy_candidate",
            extra={
                "provider": self.name,
                "exchange": "NSE",
                "candidate_date": day,
                "report_source": report_source,
                "status": status,
            },
        )
