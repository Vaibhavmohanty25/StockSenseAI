# Phase 1: Foundation and Market Data Infrastructure

The original README describes the long-term platform and is unchanged. This implementation
is restricted to Phase 1. Python 3.13, Django 5.2, DRF, PostgreSQL 18, Redis 7.4 and Celery
run together as a modular monolith. Future architecture directories contain `.gitkeep` only.

The complete source tree is in [repository-tree.md](repository-tree.md).

## Verified result

Verified on September 12, 2026 (Asia/Kolkata): migrations applied, NSE/BSE seeded, all five
Compose services running, PostgreSQL/Redis connectivity and Celery execution confirmed.
The 56-test suite passed against real PostgreSQL and Redis. The smoke script persisted
five TCS/NSE prices, repeated ingestion with zero inserts/updates, and ingested three
INFY/BSE prices through a real worker. All four HTTP routes returned expected results.
Lint, Django system checks and migration consistency checks passed. The source review's
identifier-normalization and sanitized-error-diagnostic findings were fixed and retested.
No Phase 1 implementation or requested verification items remain unfinished.

## Start locally

Install Python 3.13 if using local tooling, and start Docker Desktop with Linux containers
(or Docker Engine with Compose on Linux). Run from the repository root:

```powershell
# First setup only; do not overwrite an existing .env.
Copy-Item .env.example .env
# Replace DJANGO_SECRET_KEY and POSTGRES_PASSWORD in .env with local random values.
python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up -d --build --wait
docker compose exec web python backend/manage.py migrate --noinput
docker compose exec web python backend/manage.py seed_markets
docker compose exec web pytest -q
docker compose exec web python scripts/verify_phase1.py
docker compose exec web pytest -q
```

On POSIX shells use `cp .env.example .env` for the first command. `.env` is ignored by Git
and excluded from Docker build context. The example contains placeholders only. Do not
change the database password after creating the volume without also changing that database
role's password. Existing PostgreSQL installations on the host are not used by Compose.

If Docker is not on Windows PATH, this installation can use:

```powershell
$env:Path += ';C:\Users\mohan\AppData\Local\Programs\DockerDesktop\resources\bin'
docker desktop start
```

The web service runs at http://127.0.0.1:8000. `WEB_PORT` can override the host port.
Only web is published, on loopback; PostgreSQL and Redis remain on the Compose network.
Containers run as a non-root application user. Named volumes preserve database and broker
state. `docker compose down` stops the stack and preserves those volumes.

## Services and configuration

| Service | Responsibility |
| --- | --- |
| `web` | Runs migrations, then Django development server; readiness calls the health API |
| `db` | PostgreSQL source of truth, persistent volume, `pg_isready` health check |
| `redis` | Cache DB 0, broker DB 1, result DB 2, AOF persistence, PING health check |
| `celery` | Worker; starts after web readiness; runs the shared ingestion service |
| `celery-beat` | Scheduler, starts after web readiness; no periodic imports configured yet |

Compose uses dependency health conditions, without arbitrary startup sleeps. The single
web service owns startup migrations; workers start only when it is ready. For a deployed
multi-instance environment, execute migrations as a release step rather than from each web
instance. The Dockerfile `base` target installs runtime dependencies and runs Gunicorn;
the `development` target adds tests/tooling and is used by Compose. Deployment must supply
TLS termination and static-file serving, and select `stocksense.settings.production`.

`base.py` reads `.env` without overriding process environment. `development.py` inherits
base; `test.py` uses PostgreSQL with eager tasks and a test-only signing key; `production.py`
disables debug, requires a strong secret and hosts, and enables secure cookies/HTTPS/HSTS.
`DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `POSTGRES_*`,
`REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `MARKET_DATA_PROVIDER` and
`LOG_LEVEL` configure the application. Compose overrides dependency hosts to its service
names. No external market API credentials are needed or configured in Phase 1.

## Schema

All model primary keys are bigint. Timestamp fields use timezone-aware timestamps.

| Table | Fields |
| --- | --- |
| `market_exchange` | id, code varchar(16), name varchar(255), country char-like varchar(2), currency varchar(3), timezone varchar(64), is_active, created_at, updated_at |
| `market_security` | id, exchange_id FK, symbol varchar(32), company_name varchar(255), isin varchar(12), sector/industry varchar(128), security_type varchar(16), nullable listing_date, is_active, created_at, updated_at |
| `market_dailyprice` | id, security_id FK, date, open/high/low/close numeric(20,6), nullable adjusted_close numeric(20,6), nonnegative bigint volume, source varchar(64), created_at, updated_at |
| `ingestion_ingestionrun` | id, provider/dataset varchar(64), symbol varchar(32), exchange varchar(16), nullable start_date/end_date, started_at, nullable finished_at, status varchar(16), rows_received/rows_inserted/rows_updated/rows_failed nonnegative integers, error_message text |

- Exchange code is unique, uppercase, trimmed and nonempty.
- Security `(exchange_id, symbol)` is unique; symbol is uppercase, trimmed and nonempty.
  ISIN is intentionally not globally unique because a security may be listed on both exchanges.
- DailyPrice `(security_id, date)` is unique. That unique B-tree supports date ranges per
  security; separate FK and date indexes support individual lookup dimensions.
- Database checks enforce nonnegative OHLC, high >= low, open/close within the daily range,
  nonnegative adjusted close when supplied, and nonnegative volume. Domain validation also
  rejects nonfinite decimals, floats, excessive precision and invalid dates.
- Security indexes include symbol, ISIN, sector, exchange and `(exchange, is_active)`.
  Ingestion indexes include `(status, started_at)` and `(provider, started_at)`.
- Exchange/security deletion is protected when dependent records exist.
- Django also creates its standard admin, auth, permissions, contenttypes and session tables.
  No custom authentication or account API is implemented.

Inspect exact SQL or applied migrations:

```powershell
docker compose exec web python backend/manage.py showmigrations
docker compose exec web python backend/manage.py sqlmigrate market 0001
docker compose exec web python backend/manage.py sqlmigrate market 0002
docker compose exec web python backend/manage.py sqlmigrate ingestion 0001
```

## APIs

All APIs are read-only and versioned through the `v1` namespace. Price decimals serialize
as strings to retain precision; dates use `YYYY-MM-DD`.

| Endpoint | Parameters / behavior |
| --- | --- |
| `GET /api/v1/health/` | `{application, database, redis}`; 200 when healthy, 503 when degraded; bounded DB/Redis connection timeouts |
| `GET /api/v1/stocks/` | Optional `exchange`, `limit` (default 100, cap 1000), `offset`; paginated `{count,next,previous,results}`, ordered by exchange then symbol |
| `GET /api/v1/stocks/{symbol}/` | Optional `exchange`; 404 if unknown; 400 if symbol is ambiguous without exchange |
| `GET /api/v1/stocks/{symbol}/prices/` | Optional `exchange`, inclusive `start`/`end`, `limit` (default 100, max 1000); array in ascending date order; invalid dates/ranges/limits return 400 |
| `/admin/` | Standard Django admin for Exchange, Security, DailyPrice and read-only ingestion diagnostics |

An empty price range returns `[]`. Lists include inactive securities and expose their
`is_active` flag. Ingestion rejects inactive exchanges/securities. Symbols are interpreted
within exchanges; a BSE adapter can later map vendor-specific scrip identifiers itself.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/
Invoke-RestMethod http://127.0.0.1:8000/api/v1/stocks/
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/stocks/TCS/?exchange=NSE'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/stocks/TCS/prices/?exchange=NSE&start=2026-01-05&end=2026-01-09&limit=5'
```

## Commands, providers and ingestion

Custom commands (standard Django commands such as `migrate`, `check`, `shell`,
`createsuperuser`, `runserver` and `showmigrations` also remain available):

```powershell
docker compose exec web python backend/manage.py seed_markets
docker compose exec web python backend/manage.py ingest_prices --symbol TCS --exchange NSE --start 2026-01-05 --end 2026-01-09 --provider mock
# Repeat exactly: unchanged rows are not counted as updates.
docker compose exec web python backend/manage.py ingest_prices --symbol TCS --exchange NSE --start 2026-01-05 --end 2026-01-09 --provider mock
docker compose exec web python backend/manage.py createsuperuser
```

`seed_markets` is repeatable and seeds National Stock Exchange of India and Bombay Stock
Exchange with IN/INR/Asia-Kolkata metadata. `ingest_prices` requires symbol, exchange and
inclusive start/end dates. Provider defaults to `MARKET_DATA_PROVIDER`, currently `mock`.

`MarketDataProvider` exposes `get_security` and `get_historical_prices`; implementations
return `SecurityData` and `HistoricalPrice` dataclasses. To add an adapter later, implement
these methods and register the class in `providers/registry.py`. Core ingestion and views
need no vendor-specific changes.

The NSE adapter retrieves daily historical OHLCV from NSE's official downloadable **CM-UDiFF
Common Bhavcopy Final** archive. For a requested day it first requests
`https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`.
If that dated archive returns 404, it explicitly falls back to the official press-file archive
using the documented `https://nsearchives.nseindia.com/content/cm/PRddmmyy.zip` convention.
It requests one report for each weekday in the requested interval; weekends and dated 404s are
treated as non-trading days. Provider readiness searches the preceding 14 calendar days,
skipping weekends, and is READY only after one official archive downloads and parses.
Bhavcopy provides EOD open, high, low, close and traded quantity but no adjusted close, so NSE
rows persist `adjusted_close` as `null` rather than inventing an adjusted value, and retain
`source="nse_eod"`.

The mock supports TCS, INFY and RELIANCE on NSE/BSE; company names explicitly identify
synthetic fixtures. Prices are stable across overlapping requests and skip weekends.
They are not actual market prices and do not model exchange holidays or corporate actions.

The service validates all returned rows before persisting a batch. Historical requests
are capped at 3660 days and provider responses at 20,000 rows. Identical duplicate dates
collapse; conflicting duplicates reject the whole batch. Metadata is used to create missing
securities, preserving existing curated metadata. Within a transaction, the service locks
the security, fetches existing prices once, then bulk inserts new dates and bulk updates
changed values. Unchanged prices retain timestamps. All service writers for a security
serialize on that lock, including concurrent first imports. Direct external SQL writers
are outside this locking contract; database uniqueness still prevents duplicate rows.

`IngestionRun` records running/success/failed states. `rows_received` includes duplicates;
inserted/updated count unique persisted rows, and unchanged/identical duplicates are neither.
Failed batches count all received rows as failed because none were committed. Provider
errors before yielding rows have zero received/failed rows but failed status. A failure
run is saved outside the price transaction. A database outage that prevents saving any run,
or a hard worker/process kill, cannot guarantee a finalized failure record; stale running
records are available for inspection. Ordinary provider, validation and database write
failures are recorded with sanitized exception types. Invocation errors (e.g. unknown
provider or malformed CLI dates) are rejected before a run begins.

The asynchronous task `apps.ingestion.tasks.ingest_prices` accepts JSON-safe symbol,
exchange, start/end ISO strings and an optional provider. It calls the same service.
Phase 1 has no automatic retry or periodic market schedule; failed requests may be safely
rerun. `verify_phase1.py` exercises a real queued task and its Redis result.

JSON logs include provider, symbol/exchange, date range, received/inserted/updated/failed
counts, run ID, status and duration. Exception diagnostics retain type and frame locations
without exception text or locals. Do not add raw vendor responses or credentials to logs.

## Verification and maintenance

```powershell
docker compose ps
docker compose exec db pg_isready -U stocksense -d stocksense
docker compose exec redis redis-cli ping
docker compose exec celery celery -A stocksense inspect ping
docker compose logs --tail=30 celery celery-beat
docker compose exec web python scripts/verify_phase1.py
docker compose exec web python backend/manage.py makemigrations --check --dry-run
docker compose exec web pytest -q
docker compose exec web ruff check backend src tests scripts
```

The smoke script checks PostgreSQL, actual Django Redis cache reads/writes, seeds exchanges,
ingests five TCS/NSE prices twice, confirms persisted counts and idempotency, dispatches
three INFY/BSE prices through a real Celery worker, retrieves its result, and verifies all
four API routes over HTTP. It intentionally leaves those synthetic database fixtures.
The test suite uses a separate PostgreSQL test database, which the test database role must
be permitted to create; it does not replace PostgreSQL with SQLite. Redis health tests
require live Redis. No upstream market API is called.

For local Python tooling:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format --check .
```

To run Django outside Docker, provide a reachable PostgreSQL database and Redis in `.env`;
set `PYTHONPATH` to include the repository and `backend` for Celery. Native Windows Celery
workers are not the supported execution path here; use the Linux Compose worker.

Dependency ranges live in `requirements.in` / `requirements-dev.in`; fully resolved runtime
and development pins are in the corresponding `.txt` files. Update deliberately with
`pip-compile --no-emit-index-url --output-file=requirements.txt requirements.in` and the
equivalent development command, then rebuild and rerun tests. No ML/NLP/LLM dependencies
are installed. Phase 2 and all later functionality remain unimplemented.
