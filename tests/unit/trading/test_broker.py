from datetime import datetime

import pandas as pd
import pytest

from backend.trading.broker import Broker
from backend.trading.execution.local_lexecutor import LocalExecutor
from backend.trading.execution.order_template import ExecutionResult

# ---------------------
# Fakes
# ---------------------

class FakeWallet:
    def __init__(self, cash: float = 1000):
        self.cash = cash

    def get_balance(self):
        return {
            "status": "success",
            "message": "Virtual cash loaded",
            "data": {
                "cash": self.cash,
                "mode": "local_sim",
            },
        }

    def update_balance(self, amount: float):
        new_balance = self.cash + amount

        if new_balance < 0:
            return {
                "status": "error",
                "message": "Insufficient cash.",
                "data": {"current_cash": self.cash},
            }

        self.cash = new_balance
        return {
            "status": "success",
            "message": "Balance updated.",
            "data": {"new_cash": self.cash},
        }


class FakePortfolio:
    def __init__(self, test_df: pd.DataFrame | None = None):
        if test_df is None:
            test_df = pd.DataFrame(
                columns=[
                    "trade_id",
                    "news_id",
                    "ticker",
                    "buy_price",
                    "max_price",
                    "take_profit",
                    "stop_loss",
                    "shares",
                    "buy_reason",
                    "timestamp",
                ]
            )

        self.df = test_df.copy()

    def get_positions(self):
        return {
            "status": "success",
            "message": "Local positions retrieved.",
            "data": {
                "positions": self.df.to_dict(orient="records"),
            },
        }

    def get_open_trades(self) -> list[dict]:
        return self.df.to_dict(orient="records")

    def has_open_trades(self) -> bool:
        return not self.df.empty

    def get_trade(self, trade_id: str) -> dict | None:
        trade = self.df[self.df["trade_id"] == trade_id]
        if trade.empty:
            return None
        return trade.iloc[0].to_dict()

    def get_trade_ids(self) -> list[str]:
        if self.df.empty:
            return []
        return self.df["trade_id"].astype(str).tolist()

    def add_trade(self, buy_entry: dict):
        row = pd.DataFrame([buy_entry])
        self.df = pd.concat([self.df, row], ignore_index=True)
        return {
            "status": "success",
            "message": "Trade added.",
        }

    def remove_trade(self, trade_id: str):
        idx = self.df["trade_id"] == trade_id
        if not idx.any():
            return {
                "status": "error",
                "message": f"Trade {trade_id} not found.",
            }

        self.df = self.df[~idx].reset_index(drop=True)
        return {
            "status": "success",
            "message": "Trade removed.",
        }

    def update_shares(self, trade_id: str, new_shares: float):
        idx = self.df["trade_id"] == trade_id
        if not idx.any():
            return {
                "status": "error",
                "message": f"Trade {trade_id} not found.",
            }
        if new_shares <= 0:
            return {
                "status": "error",
                "message": "New share quantity must be greater than zero.",
            }

        self.df.loc[idx, "shares"] = new_shares
        return {
            "status": "success",
            "message": "Share quantity updated.",
            "data": {"new_shares_hold": new_shares},
        }

    def update_max_price(self, trade_id: str, current_price: float):
        idx = self.df["trade_id"] == trade_id

        if not idx.any():
            return {
                "status": "error",
                "message": f"Trade {trade_id} not found.",
            }

        current_max = float(self.df.loc[idx, "max_price"].iloc[0])
        self.df.loc[idx, "max_price"] = max(current_price, current_max)
        return {
            "status": "success",
            "message": "Max price updated.",
        }


class FakeLedger:
    def __init__(self, df: pd.DataFrame | None = None, equity_logger=None):
        if df is None:
            df = pd.DataFrame()

        self.ledger = df.copy()
        self.equity_logger = equity_logger

    def seen_ids(self):
        return []

    def get_all(self):
        return self.ledger.copy()

    def add_event(self, event: dict):
        row = pd.DataFrame([event])
        self.ledger = pd.concat([self.ledger, row], ignore_index=True)

        return {
            "status": "success",
            "message": "Added an event to the ledger.",
        }

    def add_equity_log(self, snapshot: dict):
        if self.equity_logger is not None:
            self.equity_logger.save_entry(snapshot)


class FakeEquityLogger:
    def __init__(self):
        self.entries = []

    def save_entry(self, entry):
        self.entries.append(entry)

    def load_all(self):
        return pd.DataFrame(self.entries)


class FakeMemory:
    def update_memory_sell(self, ticker, database_id, decision, macro_state):
        return {
            "status": "success",
            "message": "Fake memory updated.",
        }

class FakeMarketData:
    def __init__(self, prices: dict[str, float] | None = None):
        self.prices = prices or {"MSFT": 500}

    def get_current_price(self, ticker: str) -> float:
        return self.prices[ticker.upper()]


# ---------------------
# Helpers
# ---------------------

def make_settings_file(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        '{"strategy_version": "test_v1"}',
        encoding="utf-8",
    )
    return settings_path


def make_position(
    *,
    trade_id: str = "test_trade",
    news_id: str = "Yahoo123456789",
    ticker: str = "MSFT",
    buy_price: float = 500,
    max_price: float = 550,
    take_profit: float = 600,
    stop_loss: float = 450,
    shares: float = 3,
):
    return {
        "trade_id": trade_id,
        "news_id": news_id,
        "ticker": ticker,
        "buy_price": buy_price,
        "max_price": max_price,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "shares": shares,
        "buy_reason": "test buy",
        "timestamp": datetime.now().isoformat(),
    }


def make_test_broker(
    tmp_path,
    *,
    cash: float = 1000,
    portfolio_df: pd.DataFrame | None = None,
    prices: dict[str, float] | None = None,
):
    settings_path = make_settings_file(tmp_path)

    if prices is None:
        prices = {"MSFT": 500}

    wallet = FakeWallet(cash=cash)
    portfolio = FakePortfolio(portfolio_df)
    equity_logger = FakeEquityLogger()
    ledger = FakeLedger(equity_logger=equity_logger)
    memory = FakeMemory()
    market_data = FakeMarketData(prices)

    executor = LocalExecutor(wallet, market_data)

    broker = Broker(
        wallet=wallet,
        ledger=ledger,
        portfolio=portfolio,
        memory=memory,
        market_data=market_data,
        alpaca_client=None,
        executor=executor,
        settings_path=str(settings_path),
        equity_logger=equity_logger,
        mode="local_sim",
    )

    return broker, wallet, portfolio, ledger, equity_logger


# ---------------------
# Broker.buy
# ---------------------

def test_broker_buy_order(tmp_path):
    # Arrange
    broker, wallet, portfolio, ledger, _ = make_test_broker(
        tmp_path,
        cash=1000,
        prices={"MSFT": 500},
    )

    # Act
    buy_order = broker.buy(
        ticker="MSFT",
        invest_amount=1000,
        buy_reason="Test buy.",
        news_id="TEST_NEWS_1",
        stop_loss_pct=0.15,
        take_profit_pct=0.15,
    )

    # Assert
    assert buy_order["status"] == "success"

    trade_data = buy_order["data"]
    assert trade_data["ticker"] == "MSFT"
    assert trade_data["news_id"] == "TEST_NEWS_1"
    assert trade_data["buy_price"] == 500
    assert trade_data["max_price"] == 500
    assert trade_data["shares"] == 2

    assert wallet.cash == 0

    positions = portfolio.get_positions()["data"]["positions"]
    assert len(positions) == 1

    position = positions[0]
    assert position["ticker"] == "MSFT"
    assert position["news_id"] == "TEST_NEWS_1"
    assert position["buy_price"] == 500
    assert position["max_price"] == 500
    assert position["shares"] == 2

    ledger_df = ledger.get_all()
    assert len(ledger_df) == 1

    ledger_entry = ledger_df.iloc[0]
    assert ledger_entry["ticker"] == "MSFT"
    assert ledger_entry["news_id"] == "TEST_NEWS_1"
    assert ledger_entry["action"] == "BUY"
    assert ledger_entry["entry_price"] == 500
    assert ledger_entry["shares"] == 2


def test_broker_buy_rejects_when_cash_is_insufficient(tmp_path):
    # Arrange
    broker, wallet, portfolio, ledger, _ = make_test_broker(
        tmp_path,
        cash=100,
        prices={"MSFT": 500},
    )

    # Act
    buy_order = broker.buy(
        ticker="MSFT",
        invest_amount=1000,
        buy_reason="Test buy.",
        news_id="TEST_NEWS_1",
    )

    # Assert
    assert buy_order["status"] == "error"
    assert wallet.cash == 100
    assert len(portfolio.get_positions()["data"]["positions"]) == 0
    assert len(ledger.get_all()) == 0


# ---------------------
# Broker.sell
# ---------------------

def test_broker_sell_order(tmp_path):
    # Arrange
    portfolio_df = pd.DataFrame([make_position()])
    broker, wallet, portfolio, ledger, _ = make_test_broker(
        tmp_path,
        cash=1000,
        portfolio_df=portfolio_df,
        prices={"MSFT": 610},
    )

    # Act
    sell_order = broker.sell(
        t_id="test_trade",
        sell_reason="Test sell.",
    )

    # Assert
    assert sell_order["status"] == "success"

    sell_data = sell_order["data"]
    assert sell_data["action"] == "SELL"
    assert sell_data["position_value"] == 1830
    assert sell_data["cash_before"] == 1000
    assert sell_data["cash_after"] == 2830
    assert sell_data["pnl_dollars"] == 330

    positions = portfolio.get_positions()["data"]["positions"]
    assert len(positions) == 0

    ledger_df = ledger.get_all()
    assert len(ledger_df) == 1

    ledger_entry = ledger_df.iloc[0]
    assert ledger_entry["action"] == "SELL"
    assert ledger_entry["ticker"] == "MSFT"
    assert ledger_entry["news_id"] == "Yahoo123456789"
    assert ledger_entry["exit_price"] == 610
    assert ledger_entry["shares"] == 3
    assert ledger_entry["pnl_dollars"] == 330


def test_broker_sell_returns_error_when_trade_id_is_missing(tmp_path):
    # Arrange
    broker, wallet, portfolio, ledger, _ = make_test_broker(tmp_path, cash=1000)

    # Act
    sell_order = broker.sell(
        t_id="missing_trade",
        sell_reason="Test sell.",
    )

    # Assert
    assert sell_order["status"] == "error"
    assert wallet.cash == 1000
    assert len(portfolio.get_positions()["data"]["positions"]) == 0
    assert len(ledger.get_all()) == 0


# ---------------------
# Broker.check_stock
# ---------------------

def test_check_stock_sells_when_take_profit_is_reached(tmp_path):
    # Arrange
    portfolio_df = pd.DataFrame([make_position(take_profit=600, stop_loss=450, max_price=550)])
    broker, _, portfolio, ledger, _ = make_test_broker(
        tmp_path,
        portfolio_df=portfolio_df,
        prices={"MSFT": 650},
    )

    # Act
    check_stock_result = broker.check_stock()

    # Assert
    assert check_stock_result["status"] == "success"

    check_stock_data = check_stock_result["data"]
    assert len(check_stock_data["actions_taken"]) == 1

    first_action_sold = check_stock_data["actions_taken"][0]
    assert first_action_sold["status"] == "success"

    sold_data = first_action_sold["data"]
    assert sold_data["sell_reason"] == "Take Profit Reached"
    assert sold_data["pnl_dollars"] == (650 - 500) * 3

    positions = portfolio.get_positions()["data"]["positions"]
    assert len(positions) == 0

    ledger_entry = ledger.get_all().iloc[0]
    assert ledger_entry["action"] == "SELL"
    assert ledger_entry["ticker"] == "MSFT"
    assert ledger_entry["exit_price"] == 650
    assert ledger_entry["pnl_dollars"] == (650 - 500) * 3


def test_check_stock_sells_when_stop_loss_is_reached(tmp_path):
    # Arrange
    portfolio_df = pd.DataFrame([
        make_position(max_price=500, take_profit=600, stop_loss=450)
    ])
    broker, wallet, portfolio, ledger, _ = make_test_broker(
        tmp_path,
        cash=1000,
        portfolio_df=portfolio_df,
        prices={"MSFT": 400},
    )

    # Act
    check_stock_result = broker.check_stock()

    # Assert
    assert check_stock_result["status"] == "success"

    check_stock_data = check_stock_result["data"]
    assert len(check_stock_data["actions_taken"]) == 1

    first_action_sold = check_stock_data["actions_taken"][0]
    assert first_action_sold["status"] == "success"

    sold_data = first_action_sold["data"]
    assert sold_data["sell_reason"] == "Stop Loss Triggered"
    assert sold_data["pnl_dollars"] == (400 - 500) * 3

    assert wallet.get_balance()["data"]["cash"] == 2200
    assert len(portfolio.get_positions()["data"]["positions"]) == 0

    ledger_entry = ledger.get_all().iloc[0]
    assert ledger_entry["action"] == "SELL"
    assert ledger_entry["ticker"] == "MSFT"
    assert ledger_entry["news_id"] == "Yahoo123456789"
    assert ledger_entry["exit_price"] == 400
    assert ledger_entry["shares"] == 3
    assert ledger_entry["pnl_dollars"] == (400 - 500) * 3


def test_check_stock_sells_when_trailing_stop_is_triggered(tmp_path):
    # Arrange
    portfolio_df = pd.DataFrame([
        make_position(max_price=575, take_profit=600, stop_loss=450)
    ])
    broker, wallet, portfolio, ledger, _ = make_test_broker(
        tmp_path,
        cash=1000,
        portfolio_df=portfolio_df,
        prices={"MSFT": 490},
    )

    # Act
    check_stock_result = broker.check_stock()

    # Assert
    assert check_stock_result["status"] == "success"

    check_stock_data = check_stock_result["data"]
    assert len(check_stock_data["actions_taken"]) == 1

    first_action_sold = check_stock_data["actions_taken"][0]
    assert first_action_sold["status"] == "success"

    sold_data = first_action_sold["data"]
    assert sold_data["sell_reason"] == "Price dropped 1% from peak"
    assert sold_data["pnl_dollars"] == (490 - 500) * 3

    assert wallet.get_balance()["data"]["cash"] == 2470
    assert len(portfolio.get_positions()["data"]["positions"]) == 0

    ledger_entry = ledger.get_all().iloc[0]
    assert ledger_entry["action"] == "SELL"
    assert ledger_entry["ticker"] == "MSFT"
    assert ledger_entry["news_id"] == "Yahoo123456789"
    assert ledger_entry["exit_price"] == 490
    assert ledger_entry["shares"] == 3
    assert ledger_entry["pnl_dollars"] == (490 - 500) * 3


def test_check_stock_does_not_sell_and_updates_max_price(tmp_path):
    # Arrange
    portfolio_df = pd.DataFrame([
        make_position(max_price=520, take_profit=600, stop_loss=450)
    ])
    broker, wallet, portfolio, ledger, equity_logger = make_test_broker(
        tmp_path,
        cash=1000,
        portfolio_df=portfolio_df,
        prices={"MSFT": 550},
    )

    # Act
    check_stock_result = broker.check_stock()

    # Assert
    assert check_stock_result["status"] == "success"
    assert check_stock_result["data"]["actions_taken"] == []

    positions = portfolio.get_positions()["data"]["positions"]
    assert len(positions) == 1
    assert positions[0]["max_price"] == 550

    assert wallet.get_balance()["data"]["cash"] == 1000
    assert len(ledger.get_all()) == 0
    assert len(equity_logger.entries) == 1


# ---------------------
# Broker.liquidate_all
# ---------------------

def test_liquidate_all_sells_all_positions(tmp_path):
    # Arrange
    portfolio_df = pd.DataFrame([
        make_position(
            trade_id="trade_msft",
            news_id="NEWS_MSFT",
            ticker="MSFT",
            buy_price=500,
            max_price=575,
            take_profit=600,
            stop_loss=450,
            shares=3,
        ),
        make_position(
            trade_id="trade_aapl",
            news_id="NEWS_AAPL",
            ticker="AAPL",
            buy_price=100,
            max_price=110,
            take_profit=130,
            stop_loss=90,
            shares=5,
        ),
    ])

    broker, wallet, portfolio, ledger, _ = make_test_broker(
        tmp_path,
        cash=1000,
        portfolio_df=portfolio_df,
        prices={"MSFT": 550, "AAPL": 120},
    )

    # Act
    liquidate_all_result = broker.liquidate_all()

    # Assert
    assert liquidate_all_result["status"] == "success"

    liquidate_all_data = liquidate_all_result["data"]
    assert liquidate_all_data["total_pnl"] == ((550 - 500) * 3) + ((120 - 100) * 5)
    assert len(liquidate_all_data["actions"]) == 2

    assert wallet.get_balance()["data"]["cash"] == 3250
    assert len(portfolio.get_positions()["data"]["positions"]) == 0

    ledger_df = ledger.get_all()
    assert len(ledger_df) == 2
    assert list(ledger_df["action"]) == ["SELL", "SELL"]
    assert set(ledger_df["ticker"]) == {"MSFT", "AAPL"}


def test_liquidate_all_returns_success_when_portfolio_is_empty(tmp_path):
    # Arrange
    broker, wallet, portfolio, ledger, _ = make_test_broker(tmp_path, cash=1000)

    # Act
    liquidate_all_result = broker.liquidate_all()

    # Assert
    assert liquidate_all_result["status"] == "success"
    assert liquidate_all_result["data"]["total_pnl"] == 0.0
    assert liquidate_all_result["data"]["actions"] == []

    assert wallet.get_balance()["data"]["cash"] == 1000
    assert len(portfolio.get_positions()["data"]["positions"]) == 0
    assert len(ledger.get_all()) == 0