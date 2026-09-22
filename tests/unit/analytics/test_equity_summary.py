from backend.analytics.equity_summary import EquitySummaryService

import pandas as pd
from datetime import datetime

# ----- Dependencies -----

# --- Wallet ---
class FakeWallet():
    def get_balance(self):
        return {
                "status": "success", 
                "message": "Virtual cash loaded", 
                "data": {"equity": 1000, "mode": "local_sim"}
        }

# --- Portfolio ---
class FakePortfolio():
    def __init__(self, test_df: pd.DataFrame):
        self.df = test_df
    def get_positions(self):
        local_positions = self.df.to_dict(orient="records")
        return {
                "status": "success",
                "message": "Posiciones locales obtenidas.",
                "data": {"positions": local_positions}
            }


# --- Market Data ---
class FakeMarketData():
    def get_current_price(self, ticker: str):
        return 575


# --- Equity Logger ---
class FakeEquityLogger():
    def __init__(self):
        self.entries = []

    def save_entry(self, entry):
        self.entries.append(entry)

    def load_all(self):
        import pandas as pd
        return pd.DataFrame(self.entries)


def test_equity_summary():
    test_portfolio = pd.DataFrame([
        {
            "trade_id": "test_trade",
            "news_id": "Yahoo123456789",
            "ticker": "MSFT",
            "buy_price": 500,
            "max_price": 550,
            "take_profit": 600,
            "stop_loss": 450,
            "shares": 3,
            "buy_reason": "testing equity summary",
            "timestamp": datetime.now().isoformat(),
        }
    ])

    wallet = FakeWallet()
    portfolio = FakePortfolio(test_portfolio)
    market_data = FakeMarketData()
    equity_logger = FakeEquityLogger()

    equity_summary = EquitySummaryService(
        wallet=wallet,
        portfolio=portfolio,
        market_data=market_data,
        equity_logger=equity_logger,
    )

    summary = equity_summary.get_summary()

    assert summary["status"] == "success"
    assert summary["data"]["cash"] == 1000
    assert summary["data"]["portfolio_assets"] == 1725
    assert summary["data"]["total_equity"] == 2725
    assert summary["data"]["open_positions_count"] == 1

    assert len(equity_logger.entries) == 1

    saved_entry = equity_logger.entries[0]

    assert saved_entry["cash"] == 1000
    assert saved_entry["portfolio_assets"] == 1725
    assert saved_entry["equity"] == 2725
    assert saved_entry["open_positions_count"] == 1




def test_equity_summary_uses_buy_price_when_market_price_is_missing():
    test_portfolio = pd.DataFrame([
        {
            "trade_id": "test_trade",
            "news_id": "Yahoo123456789",
            "ticker": "MSFT",
            "buy_price": 500,
            "max_price": 550,
            "take_profit": 600,
            "stop_loss": 450,
            "shares": 3,
            "buy_reason": "testing equity summary",
            "timestamp": datetime.now().isoformat(),
        }
    ])

    class FakeMarketDataMissingPrice:
        def get_current_price(self, ticker: str):
            return None

    wallet = FakeWallet()
    portfolio = FakePortfolio(test_portfolio)
    market_data = FakeMarketDataMissingPrice()
    equity_logger = FakeEquityLogger()

    equity_summary = EquitySummaryService(
        wallet=wallet,
        portfolio=portfolio,
        market_data=market_data,
        equity_logger=equity_logger,
    )

    summary = equity_summary.get_summary()

    assert summary["status"] == "success"
    assert summary["data"]["cash"] == 1000
    assert summary["data"]["portfolio_assets"] == 1500
    assert summary["data"]["total_equity"] == 2500
    assert summary["data"]["open_positions_count"] == 1

    assert len(equity_logger.entries) == 1

    saved_entry = equity_logger.entries[0]

    assert saved_entry["cash"] == 1000
    assert saved_entry["portfolio_assets"] == 1500
    assert saved_entry["equity"] == 2500




def test_equity_summary_portfolio_empty():
    test_empty_portfolio = pd.DataFrame({})

    wallet = FakeWallet()
    market_data = FakeMarketData()
    empty_portfolio = FakePortfolio(test_empty_portfolio)
    equity_logger = FakeEquityLogger()

    equity_summary = EquitySummaryService(
        wallet=wallet,
        portfolio=empty_portfolio,
        market_data=market_data,
        equity_logger=equity_logger,
    )

    summary = equity_summary.get_summary()

    assert summary["status"] == "success"
    assert summary["data"]["cash"] == 1000
    assert summary["data"]["portfolio_assets"] == 0
    assert summary["data"]["total_equity"] == 1000
    assert summary["data"]["open_positions_count"] == 0

    assert len(equity_logger.entries) == 1

    saved_entry = equity_logger.entries[0]

    assert saved_entry["cash"] == 1000
    assert saved_entry["portfolio_assets"] == 0
    assert saved_entry["equity"] == 1000
    assert saved_entry["open_positions_count"] == 0