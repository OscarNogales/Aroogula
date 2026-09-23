# Aroogula

Aroogula is a personal research and software-engineering project for building an event-driven trading system around financial news, market context, risk controls, and explicit order execution.

The project started as a local trading simulator and is currently being refactored into a cleaner execution architecture that can support **local simulation**, **Alpaca paper trading**, and eventually **Alpaca live trading** without changing the higher-level trading workflow.

> **Status:** active development. Local simulation is the default execution path. Alpaca order execution and reconciliation are being integrated and are **not production-ready**.

## Why I built it

The goal is not simply to generate BUY/SELL signals. Aroogula is an exercise in building a stateful backend that has to coordinate asynchronous external systems, market data, NLP models, persistence, risk controls, and a UI while remaining testable and auditable.

The project is intentionally structured around separation of responsibilities rather than one large trading script.

## Current architecture

```text
News / filings / market data
          |
          v
   Decision pipeline
  FinBERT + local LLM
          |
          v
      Risk guard
          |
          v
        Broker
   workflow coordinator
          |
          v
       Executor
   +------+-------+
   |              |
LocalExecutor  AlpacaExecutor
(simulated)    (in progress)
   |              |
   +------+-------+
          |
          v
   ExecutionResult
          |
   +------+-------+
   |              |
Portfolio       Ledger
```

### Execution abstraction

A recent refactor moves order mechanics out of `Broker` and into dedicated executors:

- `LocalExecutor` performs immediate simulated fills and updates the local wallet.
- `AlpacaExecutor` submits market orders and tracks the real order lifecycle through Alpaca trade-update events.
- `ExecutionResult` normalizes requested notional/quantity, actual fill quantity and price, execution mode, and client/broker order IDs.

The purpose is to let `Broker` coordinate the workflow without knowing *how* an order is executed.

## Main components

- **FastAPI backend** — route layer and service composition.
- **Broker / Portfolio / Wallet** — trading workflow and local state.
- **Execution layer** — normalized local and Alpaca order execution.
- **Market data** — current prices and market context using Alpaca and Yahoo Finance.
- **News ingestion** — Yahoo, Bloomberg RSS, Forbes, and SEC EDGAR ingestion pipelines.
- **FinBERT filter** — fine-tuned multitask classifier used as a fast NLP filter.
- **Local LLM analysis** — Ollama-backed deeper decision analysis.
- **RiskGuard** — macro/market safety checks before new buys.
- **SQLite persistence** — trade ledger, decision records, equity snapshots, and news data.
- **Desktop/web UI** — FastAPI-served frontend with a pywebview desktop wrapper.
- **Tests** — unit tests for trading, risk, market-data, portfolio, and analysis components.

## Preliminary evaluation

Aroogula has been evaluated across **two development test windows totaling 32 active trading days**. These runs were used to test the trading workflow, inspect capital utilization, identify implementation problems, and iterate on the strategy and risk logic. They are **not intended to establish expected future returns**.

### Logged simulation window

The most recent test window was recorded through Aroogula's structured equity logger and contained **12 active trading days**, spanning July 28 through August 28, 2026.

| Metric                   | Observed value |
| ------------------------ | -------------: |
| Initial equity           |     $10,000.00 |
| Final equity             |     $10,146.19 |
| Observed profit          |       +$146.19 |
| Return on total account  |         +1.46% |
| Active trading days      |             12 |
| Average deployed capital |      $2,431.99 |

Because the bot frequently had only a fraction of the account exposed to the market, the analysis also tracks **capital-days**: the sum of average deployed capital across active trading days.

For this logged window, profit relative to deployed capital corresponded to approximately **0.50% per capital-day**.

### Earlier development window

An earlier test covered **20 active trading days** and produced an observed profit of **$84.44**. The structured equity logger had not yet been implemented during this period, so average deployed capital was recorded manually at approximately **$1,300**.

This earlier window is retained as historical development evidence, but its exposure measurements are less reproducible than those from the structured logger.

### Combined capital-efficiency analysis

Across both development windows:

| Metric                                                   |     Value |
| -------------------------------------------------------- | --------: |
| Active trading days                                      |        32 |
| Combined observed profit                                 |   $230.63 |
| Combined capital-days                                    | 55,183.88 |
| Return per capital-day                                   |     0.42% |
| Annualized capital-efficiency extrapolation — simple     |   105.32% |
| Annualized capital-efficiency extrapolation — compounded |   186.05% |

The annualized figures are **mathematical extrapolations of short-window capital efficiency**, not observed annual returns or forecasts. They answer the hypothetical question of what the measured return per unit of deployed capital would imply if it remained unchanged across 252 trading days.

That assumption is intentionally strong and is not supported by the current sample size.

These results should therefore be interpreted only as **preliminary local-simulation evidence**. The evaluation covers a short development period, the first window relies partly on manually recorded exposure data, strategy parameters were still evolving, and local simulation does not reproduce all effects of real execution such as slippage, latency, partial fills, or broker-side order behavior.

The next validation stage is Alpaca paper execution with broker-reported fills, reconciliation, and a substantially longer out-of-sample evaluation period.

The detailed analysis is available in `notebooks/03_strategy_performance_analysis.ipynb`. The private runtime trading database is intentionally excluded from the repository.


## Current engineering work

The current refactor focuses on making execution safe enough for paper trading:

- normalize all executions through `ExecutionResult`;
- separate local execution from Alpaca execution;
- track Alpaca orders with application-generated `client_order_id` values;
- consume `TradingStream` order events without making the entire Broker asynchronous;
- correctly handle partial fills, terminal states, timeouts, and reconciliation;
- persist execution/audit information separately from strategy accounting;
- support safe runtime transitions between `local_sim`, `alpaca_paper`, and eventually `alpaca_live`.

## Security / credentials

No API credentials are committed to this repository.

Local development uses environment variables loaded from `.env`:

```bash
cp .env.example .env
```

Then configure:

```dotenv
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
GROQ_API_KEY=
FMP_API_KEY=
SEC_EDGAR_IDENTITY=Your Name you@example.com
OLLAMA_APP_PATH=
```

`.env`, browser profiles, logs, SQLite databases, local portfolio state, and model weights are excluded by `.gitignore`.

**Never commit real credentials.** If a credential has ever been committed to Git history, removing it from the latest file is not enough; rotate the credential as well.

## Local setup

Python 3.12 is recommended.

```bash
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

Copy the environment template:

```bash
cp .env.example .env
```

Aroogula also expects:

1. **Ollama** installed locally with the configured LLM model (currently `deepseek-r1:8b` in the development settings).
2. The fine-tuned FinBERT artifacts under `models/best_model/` or an equivalent configured model path.
3. Alpaca and Groq credentials for the current service wiring. FMP is optional and only enables the economic-calendar guard.

Run the FastAPI application:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

or launch the desktop wrapper:

```bash
python desktop_app.py
```

## Tests

Run the test suite with:

```bash
python -m pytest -q
```

Individual subsystems can also be tested independently while refactors are in progress, for example:

```bash
python -m pytest tests/unit/trading/test_local_executor.py -q
```

## Repository layout

```text
backend/
├── analysis/       # decision context, FinBERT, LLM, risk logic
├── analytics/      # portfolio/equity analytics
├── api/            # FastAPI routes and schemas
├── app/            # service wiring and runtime coordination
├── config/         # paths, settings, logging, environment loading
├── market/         # market data and regime analysis
├── news/           # news/dossier aggregation
├── persistence/    # SQLite logs, ledger, memory
└── trading/
    ├── broker.py
    ├── portfolio.py
    ├── wallet.py
    └── execution/
        ├── local_lexecutor.py
        ├── alpaca_executor.py
        └── order_template.py

scrappers/           # external news/filing ingestion
dist/                # frontend
tests/               # unit tests
Companies.csv        # tracked ticker universe
main.py              # FastAPI entrypoint
desktop_app.py       # desktop wrapper
```

## Disclaimer

Aroogula is an experimental software/research project. It is not investment advice and should not be considered production trading infrastructure. Paper trading, reconciliation, failure recovery, authentication, and live-trading safeguards require further validation before any real-money deployment.
