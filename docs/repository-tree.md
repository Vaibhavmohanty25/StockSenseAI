# Repository tree

Source tree after Phase 1; ignored local environments, caches and .env are omitted.
Directories reserved for later phases contain only .gitkeep.

```text
StockSenseAI/
├── .dockerignore
├── .env.example
├── .gitattributes
├── .gitignore
├── Dockerfile
├── README.md
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── serializers.py
│   │       ├── urls.py
│   │       └── views.py
│   ├── apps/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── logging.py
│   │   │   └── models.py
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── admin.py
│   │   │   ├── management/
│   │   │   │   ├── __init__.py
│   │   │   │   └── commands/
│   │   │   │       ├── __init__.py
│   │   │   │       └── ingest_prices.py
│   │   │   ├── migrations/
│   │   │   │   ├── 0001_initial.py
│   │   │   │   └── __init__.py
│   │   │   ├── models.py
│   │   │   ├── services.py
│   │   │   └── tasks.py
│   │   └── market/
│   │       ├── __init__.py
│   │       ├── admin.py
│   │       ├── management/
│   │       │   ├── __init__.py
│   │       │   └── commands/
│   │       │       ├── __init__.py
│   │       │       └── seed_markets.py
│   │       ├── migrations/
│   │       │   ├── 0001_initial.py
│   │       │   ├── 0002_exchange_exchange_code_canonical_and_more.py
│   │       │   └── __init__.py
│   │       ├── models.py
│   │       └── selectors.py
│   ├── manage.py
│   └── stocksense/
│       ├── __init__.py
│       ├── celery.py
│       ├── settings/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── development.py
│       │   ├── production.py
│       │   └── test.py
│       ├── urls.py
│       └── wsgi.py
├── config/
│   └── .gitkeep
├── data/
│   ├── features/
│   │   └── .gitkeep
│   ├── processed/
│   │   └── .gitkeep
│   └── raw/
│       └── .gitkeep
├── docker-compose.yml
├── docs/
│   ├── phase-1.md
│   ├── repository-tree.md
│   └── superpowers/
│       └── plans/
│           └── 2026-09-12-phase-1.md
├── frontend/
│   └── .gitkeep
├── models/
│   ├── checkpoints/
│   │   └── .gitkeep
│   └── trained/
│       └── .gitkeep
├── notebooks/
│   └── .gitkeep
├── pyproject.toml
├── requirements-dev.in
├── requirements-dev.txt
├── requirements.in
├── requirements.txt
├── scripts/
│   ├── .gitkeep
│   └── verify_phase1.py
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   └── .gitkeep
│   ├── backtesting/
│   │   └── .gitkeep
│   ├── data_ingestion/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── domain.py
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── mock.py
│   │       └── registry.py
│   ├── explainability/
│   │   └── .gitkeep
│   ├── features/
│   │   └── .gitkeep
│   ├── fundamental_analysis/
│   │   └── .gitkeep
│   ├── models/
│   │   └── .gitkeep
│   ├── portfolio/
│   │   └── .gitkeep
│   ├── preprocessing/
│   │   └── .gitkeep
│   ├── risk/
│   │   └── .gitkeep
│   ├── scoring/
│   │   └── .gitkeep
│   ├── sentiment/
│   │   └── .gitkeep
│   ├── technical_analysis/
│   │   └── .gitkeep
│   ├── training/
│   │   └── .gitkeep
│   └── utils/
│       └── .gitkeep
└── tests/
    ├── integration/
    │   ├── test_api.py
    │   ├── test_ingestion.py
    │   └── test_market.py
    └── unit/
        ├── test_logging.py
        └── test_providers.py
```

