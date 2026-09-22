from backend.trading.portfolio import Portfolio

import pandas as pd
import pytest

# --------------------
# Make Test DataFrame
# -------------------=

def make_test_portfolio_dataframe(**overrides) -> pd.DataFrame:
    test_dict = {
        "trade_id": "TRD_TEST_001",
        "news_id": "NEWS_TEST_001",
        "ticker": "MSFT",
        "buy_price": 500.0,
        "max_price": 550.0,
        "take_profit": 600.0,
        "stop_loss": 450.0,
        "shares": 3.0,
        "buy_reason": "Test buy reason.",
        "timestamp": "2026-07-20T12:00:00",
    }

    test_dict.update(overrides)

    return pd.DataFrame([test_dict])


# -------------------
# Test get_positions
# -------------------

def test_get_positions_returns_all_positions_as_a_dataframe(tmp_path):
    portfolio_path = tmp_path / "temp_portfolio.csv"

    portfolio = Portfolio(
        portfolio_path=portfolio_path
    )

    test_df = make_test_portfolio_dataframe()

    portfolio.df = test_df

    result = portfolio.get_positions()

    assert result["status"] == "success"
    
    positions = positions = pd.DataFrame(result["data"]["positions"])

    pd.testing.assert_frame_equal(test_df, positions, check_dtype=False)


# -------------------
# Test add_trade
# -------------------

def test_add_trade_adds_the_right_trade(tmp_path):
    portfolio_path = tmp_path / "temp_portfolio.csv"

    portfolio = Portfolio(
        portfolio_path=portfolio_path
    )

    test_df = make_test_portfolio_dataframe().iloc[0].to_dict()
    result = portfolio.add_trade(test_df)

    assert result["status"] == "success"
    assert result["data"]["trade_id"] == "TRD_TEST_001"

    positions = portfolio.get_positions()["data"]["positions"]
    positions_df = pd.DataFrame(positions)

    assert len(positions_df) == 1
    assert positions_df.iloc[0]["trade_id"] == "TRD_TEST_001"


# -------------------
# Test remove_trade
# -------------------

def test_remove_trade_removes_the_right_trade(tmp_path):
    portfolio_path = tmp_path / "temp_portfolio.csv"

    portfolio = Portfolio(
        portfolio_path=portfolio_path
    )

    test_trade  = make_test_portfolio_dataframe().iloc[0].to_dict()
    _ = portfolio.add_trade(test_trade)

    result = portfolio.remove_trade("TRD_TEST_001")

    assert result["status"] == "success"

    positions = portfolio.get_positions()["data"]["positions"]
    
    assert positions == []

# ----------------------
# Test update_max_price
# ----------------------

def test_update_max_price(tmp_path):

    portfolio_path = tmp_path / "temp_portfolio.csv"

    portfolio = Portfolio(
        portfolio_path=portfolio_path
    )

    test_trade  = make_test_portfolio_dataframe().iloc[0].to_dict()
    _ = portfolio.add_trade(test_trade)

    result = portfolio.update_max_price("TRD_TEST_001", 580)

    assert result["status"] == "success"

    positions = portfolio.get_positions()["data"]["positions"]
    
    assert positions[0]["max_price"] == pytest.approx(580)



# ----------------------
# Test get_buy_reasons
# ----------------------

def test_get_shares_owned(tmp_path):
    portfolio_path = tmp_path / "temp_portfolio.csv"
    portfolio = Portfolio(
        portfolio_path=portfolio_path
    )

    trade_1 = {
        "trade_id": "TRD_TEST_001",
        "news_id": "NEWS_TEST_001",
        "ticker": "MSFT",
        "buy_price": 500.0,
        "max_price": 550.0,
        "take_profit": 600.0,
        "stop_loss": 450.0,
        "shares": 3.0,
        "buy_reason": "Test buy reason for MSFT.",
        "timestamp": "2026-07-20T12:00:00",
    }

    trade_2 = {
        **trade_1,
        "trade_id": "TRD_TEST_002",
        "news_id": "NEWS_TEST_002",
        "shares": 2.0,
    }

    portfolio.add_trade(trade_1)
    portfolio.add_trade(trade_2)

    result = portfolio.get_shares_owned("MSFT")

    assert result == pytest.approx(5.0)


# ----------------------
# Test get_buy_reasons
# ----------------------

def test_get_buy_reasons(tmp_path):
    portfolio_path = tmp_path / "temp_portfolio.csv"
    portfolio = Portfolio(
        portfolio_path=portfolio_path
    )

    trade_1 = {
        "trade_id": "TRD_TEST_001",
        "news_id": "NEWS_TEST_001",
        "ticker": "MSFT",
        "buy_price": 500.0,
        "max_price": 550.0,
        "take_profit": 600.0,
        "stop_loss": 450.0,
        "shares": 3.0,
        "buy_reason": "Test buy reason for MSFT.",
        "timestamp": "2026-07-20T12:00:00",
    }

    trade_2 = {
        **trade_1,
        "trade_id": "TRD_TEST_002",
        "news_id": "NEWS_TEST_002",
        "shares": 2.0,
        "buy_reason": "Test buy reason for MSFT #2."
    }

    trade_3 = {
        **trade_1,
        "trade_id": "TRD_TEST_003",
        "news_id": "NEWS_TEST_003",
        "ticker": "AAPL",
        "shares": 5.0,
        "buy_reason": "Test buy reason for AAPL.",
    }

    portfolio.add_trade(trade_1)
    portfolio.add_trade(trade_2)
    portfolio.add_trade(trade_3)

    result = portfolio.get_buy_reasons("MSFT")

    assert result == [
        "Test buy reason for MSFT.",
        "Test buy reason for MSFT #2.",
    ]   