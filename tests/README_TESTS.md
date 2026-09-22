# Aroogula Test Suite

This folder contains the unit-test suite for the trading bot.

## Recommended command

```bash
python -m pytest
```

The bundled `pytest.ini` already enables clear verbose output, short tracebacks,
strict marker/config validation, and colored terminal output when supported.

## Structure

```text
tests/
  unit/
    core/       # RiskGuard, MarketDataService, DecisionContextBuilder, LLMDecisionEngine
    trading/    # Broker, Portfolio, Wallet
    utils/      # AILogger, EquityLogger, Ledger
    services/   # EquitySummaryService
```

## Testing policy

These are unit tests. They should not call real external services:

- no real Alpaca orders
- no real yfinance network calls
- no real Ollama server startup
- no writes to production databases or JSON files

Use `tmp_path`, fakes, and `monkeypatch` for anything with I/O.
