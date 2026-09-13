from datetime import date
from decimal import Decimal
from io import BytesIO
from urllib.error import HTTPError, URLError
from zipfile import ZIP_DEFLATED, ZipFile

import pytest


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200, final_url: str | None = None):
        self.payload = payload
        self.status = status
        self.final_url = final_url

    def read(self) -> bytes:
        return self.payload

    def geturl(self) -> str:
        return self.final_url or ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


NSE_HISTORY = b"""{"data": [{
    "CH_TIMESTAMP": "05-Jan-2026",
    "CH_OPENING_PRICE": "1,400.00",
    "CH_TRADE_HIGH_PRICE": "1,420.50",
    "CH_TRADE_LOW_PRICE": "1,390.00",
    "CH_CLOSING_PRICE": "1,410.25",
    "CH_TOT_TRADED_QTY": "12,345"
}]}"""


def bhavcopy(rows: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "pr05012026.csv",
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\n" + rows,
        )
    return buffer.getvalue()


def udiff_bhavcopy(rows: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "BhavCopy_NSE_CM_0_0_0_20260105_F_0000.csv",
            "TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n" + rows,
        )
    return buffer.getvalue()


RELIANCE_BHAVCOPY = bhavcopy(
    "RELIANCE,EQ,1400.00,1420.50,1390.00,1410.25,12345\nOTHER,EQ,1,2,1,2,10\n"
)


def test_factory_resolves_real_providers_and_rejects_unknown_name():
    from src.data_ingestion.exceptions import MarketDataProviderError
    from src.data_ingestion.providers.factory import get_market_data_provider
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    assert isinstance(get_market_data_provider("nse"), NSEMarketDataProvider)
    with pytest.raises(MarketDataProviderError, match="Unknown market-data provider"):
        get_market_data_provider("not-a-provider")


def test_nse_provider_normalizes_official_structured_rows(monkeypatch):
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    responses = iter([FakeResponse(RELIANCE_BHAVCOPY), FakeResponse(RELIANCE_BHAVCOPY)])
    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: next(responses),
    )
    provider = NSEMarketDataProvider(retry_attempts=1)

    security = provider.get_security("RELIANCE", "NSE", identifier="RELIANCE")
    rows = list(
        provider.get_historical_prices(
            "RELIANCE",
            "NSE",
            date(2026, 1, 5),
            date(2026, 1, 5),
            identifier="RELIANCE",
        )
    )

    assert security.company_name == "RELIANCE"
    assert security.isin == ""
    assert rows == [
        rows[0].__class__(
            symbol="RELIANCE",
            exchange="NSE",
            date=date(2026, 1, 5),
            open=Decimal("1400.000000"),
            high=Decimal("1420.500000"),
            low=Decimal("1390.000000"),
            close=Decimal("1410.250000"),
            adjusted_close=None,
            volume=12345,
            source="nse_eod",
        )
    ]


def test_nse_bhavcopy_aggregates_trading_days_and_skips_missing_report(monkeypatch):
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    second_day = bhavcopy("RELIANCE,EQ,1410,1430,1400,1420,54321\n")

    def respond(request, timeout):
        if "20260106" in request.full_url or "060126" in request.full_url:
            raise HTTPError(request.full_url, 404, "missing", {}, BytesIO())
        if "20260107" in request.full_url or "070126" in request.full_url:
            return FakeResponse(second_day)
        return FakeResponse(RELIANCE_BHAVCOPY)

    monkeypatch.setattr("src.data_ingestion.providers.http.urlopen", respond)
    rows = list(
        NSEMarketDataProvider(retry_attempts=1).get_historical_prices(
            "RELIANCE", "NSE", date(2026, 1, 5), date(2026, 1, 7)
        )
    )
    assert [(row.date, row.close, row.source) for row in rows] == [
        (date(2026, 1, 5), Decimal("1410.250000"), "nse_eod"),
        (date(2026, 1, 7), Decimal("1420.000000"), "nse_eod"),
    ]
    assert all(row.adjusted_close is None for row in rows)


def test_nse_udiff_zip_is_primary_and_normalizes_its_schema(monkeypatch):
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    urls = []

    def respond(request, timeout):
        urls.append(request.full_url)
        return FakeResponse(udiff_bhavcopy("RELIANCE,EQ,1400,1420,1390,1410,12345\n"))

    monkeypatch.setattr("src.data_ingestion.providers.http.urlopen", respond)
    rows = list(
        NSEMarketDataProvider(retry_attempts=1).get_historical_prices(
            "RELIANCE", "NSE", date(2026, 1, 5), date(2026, 1, 5)
        )
    )

    assert urls == [
        "https://nsearchives.nseindia.com/content/cm/"
        "BhavCopy_NSE_CM_0_0_0_20260105_F_0000.csv.zip"
    ]
    assert [(row.symbol, row.close, row.volume, row.source) for row in rows] == [
        ("RELIANCE", Decimal("1410.000000"), 12345, "nse_eod")
    ]


def test_nse_udiff_url_uses_current_official_archive_path_and_filename():
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    assert NSEMarketDataProvider._bhavcopy_urls(date(2026, 9, 11))[0] == (
        "udiff",
        "https://nsearchives.nseindia.com/content/cm/"
        "BhavCopy_NSE_CM_0_0_0_20260911_F_0000.csv.zip",
    )


def test_shared_binary_client_accepts_redirected_official_archive(monkeypatch, caplog):
    from src.data_ingestion.providers.http import JSONHTTPClient

    requested_url = "https://www.nseindia.com/archive/report.zip"
    final_url = "https://nsearchives.nseindia.com/content/cm/report.zip"
    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(b"zip-bytes", final_url=final_url),
    )

    with caplog.at_level("DEBUG"):
        assert JSONHTTPClient(retry_attempts=1).get_bytes(requested_url) == b"zip-bytes"

    assert any(
        record.message == "provider_binary_response"
        and record.request_url == requested_url
        and record.final_url == final_url
        for record in caplog.records
    )


def test_shared_binary_client_logs_request_url_when_response_has_no_geturl(
    monkeypatch, caplog
):
    from src.data_ingestion.providers.http import JSONHTTPClient

    class ResponseWithoutGeturl:
        def read(self):
            return b"zip-bytes"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    requested_url = "https://nsearchives.nseindia.com/content/cm/report.zip"
    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: ResponseWithoutGeturl(),
    )

    with caplog.at_level("DEBUG"):
        assert JSONHTTPClient(retry_attempts=1).get_bytes(requested_url) == b"zip-bytes"

    assert any(
        record.message == "provider_binary_response"
        and record.request_url == requested_url
        and record.final_url == requested_url
        for record in caplog.records
    )


def test_nse_403_is_access_restriction_not_a_missing_report(monkeypatch):
    from src.data_ingestion.exceptions import ProviderAuthenticationError
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    def forbidden(request, timeout):
        raise HTTPError(request.full_url, 403, "forbidden", {}, BytesIO())

    monkeypatch.setattr("src.data_ingestion.providers.http.urlopen", forbidden)
    with pytest.raises(
        ProviderAuthenticationError, match="authentication was rejected"
    ):
        NSEMarketDataProvider(retry_attempts=1)._download_bhavcopy(date(2026, 9, 11))


@pytest.mark.parametrize(
    ("reference_date", "available_date", "expected_dates"),
    [
        (date(2026, 1, 13), date(2026, 1, 12), [date(2026, 1, 12)]),
        (date(2026, 1, 12), date(2026, 1, 9), [date(2026, 1, 9)]),
        (
            date(2026, 1, 15),
            date(2026, 1, 12),
            [date(2026, 1, 14), date(2026, 1, 13), date(2026, 1, 12)],
        ),
        (
            date(2026, 1, 16),
            date(2026, 1, 12),
            [
                date(2026, 1, 15),
                date(2026, 1, 14),
                date(2026, 1, 13),
                date(2026, 1, 12),
            ],
        ),
    ],
    ids=(
        "latest-weekday-missing",
        "weekend-fallback",
        "holiday-fallback",
        "several-days-back",
    ),
)
def test_nse_health_searches_recent_candidate_dates(
    monkeypatch, reference_date, available_date, expected_dates
):
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    tried = []

    def respond(request, timeout):
        for candidate in expected_dates:
            if (
                candidate.strftime("%Y%m%d") in request.full_url
                or candidate.strftime("%d%m%y") in request.full_url
            ):
                if "BhavCopy_NSE_CM" in request.full_url:
                    tried.append(candidate)
                if candidate == available_date:
                    return FakeResponse(RELIANCE_BHAVCOPY)
                raise HTTPError(request.full_url, 404, "missing", {}, BytesIO())
        raise AssertionError(f"unexpected candidate URL {request.full_url}")

    monkeypatch.setattr("src.data_ingestion.providers.http.urlopen", respond)
    NSEMarketDataProvider(retry_attempts=1)._recent_bhavcopy_rows(reference_date)

    assert tried == expected_dates


def test_nse_health_exhausts_candidates_when_all_reports_are_missing(monkeypatch):
    from src.data_ingestion.exceptions import ProviderUnavailableError
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    urls = []

    def missing(request, timeout):
        urls.append(request.full_url)
        raise HTTPError(request.full_url, 404, "missing", {}, BytesIO())

    monkeypatch.setattr("src.data_ingestion.providers.http.urlopen", missing)
    with pytest.raises(ProviderUnavailableError, match="No recent NSE Bhavcopy"):
        NSEMarketDataProvider(retry_attempts=1)._recent_bhavcopy_rows(date(2026, 1, 12))

    # Seven weekdays occur in the preceding ten calendar days; both official sources
    # are attempted for each missing date.
    assert len(urls) >= 14
    assert all("PR" in url or "BhavCopy_NSE_CM" in url for url in urls)


def test_nse_bhavcopy_rejects_empty_or_malformed_reports(monkeypatch):
    from src.data_ingestion.exceptions import MalformedProviderResponseError
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(b""),
    )
    provider = NSEMarketDataProvider(retry_attempts=1)
    with pytest.raises(MalformedProviderResponseError):
        list(
            provider.get_historical_prices(
                "RELIANCE", "NSE", date(2026, 1, 5), date(2026, 1, 5)
            )
        )

    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(b"not a zip"),
    )
    with pytest.raises(MalformedProviderResponseError):
        list(
            provider.get_historical_prices(
                "RELIANCE", "NSE", date(2026, 1, 5), date(2026, 1, 5)
            )
        )


def test_nse_bhavcopy_translates_unavailable_daily_report(monkeypatch):
    from src.data_ingestion.exceptions import ProviderUnavailableError
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    unavailable = HTTPError("https://example.test", 503, "unavailable", {}, BytesIO())
    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(unavailable),
    )
    with pytest.raises(ProviderUnavailableError):
        list(
            NSEMarketDataProvider(retry_attempts=1).get_historical_prices(
                "RELIANCE", "NSE", date(2026, 1, 5), date(2026, 1, 5)
            )
        )


def test_nse_health_check_parses_a_recent_bhavcopy(monkeypatch):
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(RELIANCE_BHAVCOPY),
    )
    NSEMarketDataProvider(retry_attempts=1).health_check()


def test_nse_provider_rejects_empty_and_malformed_payloads(monkeypatch):
    from src.data_ingestion.exceptions import (
        MalformedProviderResponseError,
    )
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(bhavcopy("OTHER,EQ,1,2,1,2,10\n")),
    )
    provider = NSEMarketDataProvider(retry_attempts=1)
    assert (
        list(
            provider.get_historical_prices(
                "RELIANCE", "NSE", date(2026, 1, 5), date(2026, 1, 5)
            )
        )
        == []
    )

    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(b'{"data": [{}]}'),
    )
    with pytest.raises(MalformedProviderResponseError):
        list(
            provider.get_historical_prices(
                "RELIANCE", "NSE", date(2026, 1, 5), date(2026, 1, 5)
            )
        )


def test_nse_provider_translates_missing_symbol_and_transient_failures(monkeypatch):
    from src.data_ingestion.exceptions import (
        ProviderUnavailableError,
        SymbolNotFoundError,
    )
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(bhavcopy("OTHER,EQ,1,2,1,2,10\n")),
    )
    with pytest.raises(SymbolNotFoundError):
        NSEMarketDataProvider(retry_attempts=1).get_security("MISSING", "NSE")

    attempts = []

    def unavailable(request, timeout):
        attempts.append(request)
        raise URLError("temporary")

    monkeypatch.setattr("src.data_ingestion.providers.http.urlopen", unavailable)
    with pytest.raises(ProviderUnavailableError):
        NSEMarketDataProvider(retry_attempts=2, retry_backoff_seconds=0).get_security(
            "RELIANCE", "NSE"
        )
    # Each official archive receives its independently bounded two attempts.
    assert len(attempts) == 4
    attempted_urls = [request.full_url for request in attempts]
    assert len(set(attempted_urls)) == 2
    assert all(attempted_urls.count(url) == 2 for url in set(attempted_urls))


def test_nse_provider_retries_temporary_http_failure(monkeypatch):
    from src.data_ingestion.providers.nse_provider import NSEMarketDataProvider

    temporary_failure = HTTPError(
        "https://example.test", 503, "unavailable", {}, BytesIO()
    )
    responses = iter([temporary_failure, FakeResponse(RELIANCE_BHAVCOPY)])

    def respond(request, timeout):
        response = next(responses)
        if isinstance(response, HTTPError):
            raise response
        return response

    monkeypatch.setattr("src.data_ingestion.providers.http.urlopen", respond)
    security = NSEMarketDataProvider(
        retry_attempts=2, retry_backoff_seconds=0
    ).get_security("RELIANCE", "NSE")
    assert security.symbol == "RELIANCE"


def test_bse_provider_requires_config_and_normalizes_configured_response(monkeypatch):
    from src.data_ingestion.exceptions import ProviderConfigurationError
    from src.data_ingestion.providers.bse_provider import BSEMarketDataProvider

    monkeypatch.delenv("BSE_API_BASE_URL", raising=False)
    monkeypatch.delenv("BSE_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError):
        BSEMarketDataProvider()

    monkeypatch.setenv("BSE_API_BASE_URL", "https://official.bse.example/api")
    monkeypatch.setenv("BSE_API_KEY", "test-key")
    payload = b"""{
        "data": [{
            "date": "2026-01-05", "open": "100", "high": "110",
            "low": "90", "close": "105", "volume": "123"
        }]
    }"""
    monkeypatch.setattr(
        "src.data_ingestion.providers.http.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )
    rows = list(
        BSEMarketDataProvider(retry_attempts=1).get_historical_prices(
            "TCS", "BSE", date(2026, 1, 5), date(2026, 1, 5), identifier="532540"
        )
    )
    assert rows[0].symbol == "TCS"
    assert rows[0].source == "bse_eod"
    assert rows[0].adjusted_close == Decimal("105.000000")
