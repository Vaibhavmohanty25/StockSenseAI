# StockSense AI

**StockSense AI** is an AI-powered investment research and decision-support platform designed for the Indian equity market.

The system combines **market data, technical analysis, fundamental analysis, financial news sentiment, machine learning, portfolio optimization, risk analytics, explainable AI, and an LLM-powered investment assistant** to help investors evaluate NSE and BSE-listed stocks more intelligently.

Instead of attempting to predict an exact future stock price, StockSense focuses on questions that are more useful for investment decision-making:

> How likely is a stock to outperform the broader market over a given investment horizon, what factors are driving that prediction, and what level of risk does the opportunity carry?

---

## Vision

Traditional stock-analysis platforms often present investors with large amounts of disconnected information: price charts, financial ratios, analyst commentary, news articles, and technical indicators.

StockSense aims to connect these signals into a single research workflow.

The platform is designed to eventually provide:

- Technical and momentum analysis
- Fundamental company analysis
- Financial-news sentiment analysis
- Market-relative ML predictions
- Stock ranking and screening
- Risk analysis
- Explainable model predictions
- Historical strategy backtesting
- Portfolio optimization
- Investor risk profiling
- AI-assisted stock research
- Watchlists and portfolio monitoring
- NSE/BSE market coverage

The goal is not to replace human investment decisions, but to provide investors with a structured, explainable, data-driven research system.

---

# Core Architecture

```text
                           Investor
                               │
                               ▼
                    Next.js Web Application
                               │
                               ▼
                   Django REST Framework
                               │
       ┌───────────────────────┼────────────────────────┐
       │                       │                        │
       ▼                       ▼                        ▼

 Market Intelligence     ML Intelligence          AI Assistant

 ├─ Market Data          ├─ Feature Engine        ├─ Tool Calling
 ├─ Technical Analysis   ├─ Classification        ├─ Stock Research
 ├─ Fundamentals         ├─ Ranking               ├─ Comparisons
 ├─ Sentiment            ├─ Forecasting           └─ Explanations
 └─ Risk Analysis        └─ Ensemble Models

       │                       │
       └──────────────┬────────┘
                      ▼
              Stock Scoring Engine
                      │
             ┌────────┴─────────┐
             ▼                  ▼
       Backtesting         Portfolio Engine
             │                  │
             └────────┬─────────┘
                      ▼
                Explainable AI
                      │
                      ▼
                  PostgreSQL

                      │
                      ▼
                 Redis / Celery
                      │
                      ▼
             Background Pipelines
```

---

# Technology Stack

## Backend

- Python
- Django
- Django REST Framework
- Celery
- Redis
- PostgreSQL

Django acts as the main application backend responsible for API endpoints, authentication, portfolio data, stock data, model results, watchlists, user management, and application-level business logic.

Heavy jobs such as data ingestion, news processing, feature generation, model training, and stock ranking are handled asynchronously through Celery workers.

---

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS

The frontend will eventually provide dashboards for stock research, portfolio analysis, model predictions, explainability, backtesting, stock screening, and interaction with the StockSense AI assistant.

---

## Machine Learning

Initial models:

- Logistic Regression
- Random Forest
- XGBoost
- LightGBM

Advanced experimentation may later include:

- LSTM
- GRU
- Temporal neural networks
- Transformer-based time-series models
- Ensemble models
- Reinforcement-learning research

Model complexity will only be increased when it demonstrably improves out-of-sample performance.

---

## Natural Language Processing

Financial news will be processed using transformer-based NLP models such as **FinBERT**.

The sentiment pipeline will produce features including:

```text
Positive sentiment
Negative sentiment
Neutral sentiment
Sentiment intensity
News volume
Sentiment momentum
Recency-weighted sentiment
```

These features can then be incorporated into the ML prediction engine.

---

## Explainable AI

StockSense will use techniques such as:

- SHAP
- Feature importance
- Prediction contribution analysis

Instead of returning only:

```text
Outperformance probability: 71%
```

StockSense should be capable of explaining:

```text
Factors supporting prediction

+ Revenue growth
+ Positive earnings momentum
+ Relative strength
+ Improving market sentiment

Factors reducing prediction

- Elevated valuation
- High volatility
- Weak sector momentum
```

---

# Machine Learning Objective

StockSense does not initially attempt to predict the exact future share price.

The primary ML objective is **market-relative performance prediction**.

For a given future investment horizon:

```text
Relative Return =
Stock Future Return
-
Benchmark Future Return
```

For example, using NIFTY 50 as the benchmark:

```text
OUTPERFORM
NEUTRAL
UNDERPERFORM
```

A later model may estimate:

```text
Probability of positive return

Probability of NIFTY outperformance

Expected relative return

Prediction confidence
```

This provides a more realistic decision-support signal than exact price forecasting.

---

# Data Pipeline

The initial data pipeline will combine multiple data categories.

```text
Historical Prices
       │
       ├──────────────┐
       │              │
       ▼              ▼

Technical Data    Market Data

       │              │
       └──────┬───────┘
              │

Fundamental Data
              │
              ▼

Corporate / Financial Features
              │

News Data
              │
              ▼

Financial Sentiment
              │
              ▼

        Feature Pipeline
              │
              ▼

       ML Training Dataset
```

Initial coverage will focus on **NIFTY 50 companies** before expanding toward NIFTY 100, NIFTY 500, and broader NSE/BSE coverage.

---

# Feature Engineering

The system may use features from four major categories.

## Technical

Examples:

```text
RSI
MACD
Moving averages
ATR
Bollinger Bands
Rate of Change
Relative Strength
Volume Momentum
OBV
Historical Volatility
Price Momentum
```

## Fundamental

Examples:

```text
P/E
P/B
ROE
ROCE
Debt-to-Equity
Operating Margin
Net Profit Margin
Revenue Growth
Profit Growth
EPS Growth
Free Cash Flow
Interest Coverage
```

## Market

Examples:

```text
NIFTY returns
Sector returns
Market volatility
India VIX
Stock beta
Relative momentum
```

## Sentiment

Examples:

```text
7-day sentiment
30-day sentiment
News volume
Sentiment change
Negative-event intensity
Positive-event intensity
```

---

# Risk Engine

StockSense will evaluate opportunities using more than model confidence.

Risk metrics may include:

```text
Historical volatility
Beta
Sharpe ratio
Sortino ratio
Maximum drawdown
Value at Risk
Expected shortfall
Correlation
Portfolio concentration
```

This allows recommendations and rankings to consider both expected opportunity and downside risk.

---

# StockSense Score

The system will eventually combine multiple analysis components into a normalized score.

Conceptually:

```text
Technical Score
        +
Fundamental Score
        +
Sentiment Score
        +
ML Prediction Score
        +
Risk-Adjusted Score
        ↓
StockSense Score
```

The scoring system must remain explainable and configurable rather than functioning as an unexplained black box.

---

# Portfolio Intelligence

A later stage of the project will support portfolio-level decision making.

Features may include:

```text
Portfolio optimization
Diversification analysis
Sector exposure
Correlation analysis
Risk-adjusted allocation
Portfolio rebalancing
Position sizing
```

Initial optimization can use techniques such as **Modern Portfolio Theory / Markowitz optimization**, while later versions may experiment with additional optimization approaches.

---

# Backtesting

Every trading or investment signal must be evaluated historically before being considered useful.

The backtesting engine will simulate strategies using historical data while accounting for:

```text
Transaction costs
Slippage
Portfolio turnover
Rebalancing frequency
Position limits
Sector exposure
Benchmark performance
```

Performance metrics will include:

```text
CAGR
Sharpe Ratio
Sortino Ratio
Maximum Drawdown
Alpha
Beta
Win Rate
Volatility
Portfolio Turnover
```

StockSense will use time-based and walk-forward validation rather than random train/test splitting.

---

# AI Investment Assistant

The LLM will act primarily as an **interaction and reasoning interface**.

It should not invent financial numbers.

Instead, it will call internal StockSense tools such as:

```text
get_stock_data()

get_technical_analysis()

get_fundamentals()

get_sentiment()

predict_outperformance()

calculate_risk()

rank_stocks()

compare_stocks()

run_backtest()

optimize_portfolio()
```

The assistant can then synthesize structured results into natural-language analysis.

Example:

```text
User:

Compare TCS and Infosys for a six-month investment.

StockSense:

TCS currently shows stronger profitability and lower
volatility, while Infosys trades at a relatively more
attractive valuation.

The ML engine assigns TCS a higher probability of
market outperformance, although recent sentiment is
stronger for Infosys.

For a lower-risk portfolio, the current indicators favour
TCS, while investors prioritizing valuation may find
Infosys comparatively attractive.
```

---

# Project Structure

```text
StockSense-AI/
│
├── backend/
│   ├── manage.py
│   │
│   ├── stocksense/
│   │   ├── settings/
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── wsgi.py
│   │
│   ├── accounts/
│   ├── market/
│   ├── portfolio/
│   └── assistant/
│
├── src/
│   │
│   ├── data_ingestion/
│   │
│   ├── preprocessing/
│   │
│   ├── features/
│   │
│   ├── technical_analysis/
│   │
│   ├── fundamental_analysis/
│   │
│   ├── sentiment/
│   │
│   ├── models/
│   │
│   ├── training/
│   │
│   ├── scoring/
│   │
│   ├── risk/
│   │
│   ├── portfolio/
│   │
│   ├── explainability/
│   │
│   ├── agents/
│   │
│   ├── backtesting/
│   │
│   └── utils/
│
├── frontend/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── features/
│
├── models/
│   ├── trained/
│   └── checkpoints/
│
├── notebooks/
│
├── scripts/
│
├── tests/
│
├── config/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# Development Roadmap

## Phase 1 — Foundation and Data Infrastructure

Build the platform foundation.

Scope:

```text
Django project setup
Django REST Framework
PostgreSQL integration
Redis integration
Celery configuration
Environment configuration
Logging
Stock master model
Historical price model
Market data ingestion
NSE/BSE symbol handling
Basic API endpoints
Data validation
Automated tests
Docker development environment
```

Expected APIs:

```text
GET /api/stocks/

GET /api/stocks/{symbol}/

GET /api/stocks/{symbol}/prices/

GET /api/health/
```

---

## Phase 2 — Financial Analytics

Implement:

```text
Technical indicators
Fundamental ratios
Risk metrics
News ingestion
FinBERT sentiment
Feature generation
```

---

## Phase 3 — Machine Learning

Build:

```text
ML training dataset
Feature pipeline
Target generation
Logistic Regression baseline
Random Forest
XGBoost
LightGBM
Walk-forward validation
Model registry
Prediction API
```

---

## Phase 4 — Ranking and Backtesting

Build:

```text
Stock ranking
Historical strategy simulation
Benchmark comparison
Transaction-cost modelling
Performance analytics
```

---

## Phase 5 — Portfolio Intelligence and Explainability

Build:

```text
Portfolio optimization
Risk-aware allocation
Diversification analysis
SHAP explanations
Prediction reasoning
StockSense Score
```

---

## Phase 6 — AI Investment Agent

Build:

```text
LLM integration
Tool calling
Stock comparison
Research queries
Portfolio queries
Explainable recommendations
```

---

## Phase 7 — Product Interface

Build:

```text
Next.js frontend
Dashboard
Stock screener
Stock research pages
Portfolio dashboard
Backtesting interface
Explainability dashboard
AI assistant
Watchlist
```

---

## Phase 8 — Advanced Intelligence

Possible research extensions:

```text
Time-series deep learning
Model ensembles
Market regime detection
Sector-specific models
Macroeconomic features
Personalized investor profiles
Reinforcement learning
Paper trading
```

---


# Development Principles

StockSense follows several important engineering principles.

### No look-ahead bias

ML features must only contain information that was available at the time of prediction.

### Time-aware validation

Financial data must use chronological or walk-forward validation instead of randomly shuffled datasets.

### Provider independence

External market-data providers should sit behind reusable interfaces so that providers can be replaced without rewriting the application.

### Explainability before complexity

Complex ML models should only replace simpler models when they provide measurable improvements.

### Separation of concerns

Data ingestion, analytics, ML, application logic, and presentation should remain modular.

### Reproducibility

Model versions, features, training periods, and evaluation results should be traceable.

### Risk-aware recommendations

Predictions should never be presented without associated uncertainty and risk.

---

# Responsible Use

StockSense AI is an educational and research project.

The platform is intended to provide analytical and decision-support tools and **does not constitute financial, investment, legal, or trading advice**.

Predictions generated by machine-learning models may be incorrect. Historical performance does not guarantee future results.

Users should independently verify investment decisions and consult qualified professionals where appropriate.

---

# Current Status

```text
Phase 0
Architecture & Planning        ✅

Phase 1
Foundation & Data Layer        🚧

Phase 2
Analytics Engine               ⏳

Phase 3
Machine Learning               ⏳

Phase 4
Ranking & Backtesting          ⏳

Phase 5
Portfolio & Explainability     ⏳

Phase 6
AI Investment Agent            ⏳

Phase 7
Frontend                       ⏳

Phase 8
Advanced Intelligence          ⏳
```

---

# Author

**Vaibhav Mohanty**

B.Tech Computer Science & Engineering  
Artificial Intelligence & Machine Learning

---

## Project Goal

StockSense is ultimately intended to answer one question:

> **Can multiple forms of financial intelligence be combined into an explainable AI system that helps investors make better-informed decisions about Indian equities?**

That is what this project is being built to find out.