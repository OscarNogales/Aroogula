from backend.persistence.ledger import Ledger

import pandas as pd
import sqlite3 as sql
import pytest

# ---------------------
# Helpers
# ---------------------

def make_ledger_event(**overrides):
    event = {
        "trade_id": "TRD_TEST_001",
        "decision_id": "DEC_TEST_001",
        "news_id": "NEWS_TEST_001",
        "ticker": "MSFT",
        "action": "BUY",
        "status": "success",
        "timestamp": "2026-07-20T12:00:00",

        "entry_price": 500.0,
        "exit_price": None,
        "shares": 2.0,
        "position_value": 1000.0,

        "cash_before": 1000.0,
        "cash_after": 0.0,
        "equity_before": 1000.0,
        "equity_after": 1000.0,

        "buy_reason": "Test buy reason.",
        "sell_reason": None,
        "ai_confidence": 0.87,

        "pnl_dollars": None,
        "pnl_pct": None,
        "holding_minutes": None,
        "exit_trigger": None,
        "was_profitable": None,

        "execution_mode": "local_sim",
        "strategy_version": "test_strategy_v1",
    }

    event.update(overrides)
    return event

def make_buy_ledger_event(**overrides):
    return make_ledger_event(
        action="BUY",
        exit_price=None,
        sell_reason=None,
        pnl_dollars=None,
        pnl_pct=None,
        holding_minutes=None,
        exit_trigger=None,
        was_profitable=None,
        **overrides,
    )

def make_sell_ledger_event(**overrides):
    return make_ledger_event(
        action="SELL",
        exit_price=650.0,
        position_value=1300.0,
        cash_before=0.0,
        cash_after=1300.0,
        sell_reason="Take Profit Reached",
        pnl_dollars=300.0,
        pnl_pct=30.0,
        holding_minutes=45.0,
        exit_trigger="Take Profit Reached",
        was_profitable=1,
        **overrides,
    )

# ---------------------
# Ledger.add_buy_event
# ---------------------

def test_ledger_add_buy_event(tmp_path):
    ledger_db_path = tmp_path / "logger.db"

    ledger = Ledger(ledger_db_path=str(ledger_db_path))

    buy_event = make_buy_ledger_event()
    
    ledger.add_event(buy_event)

    saved_entry = ledger.get_all()

    assert saved_entry.loc[0, "trade_id"] == buy_event["trade_id"]
    assert saved_entry.loc[0, "decision_id"] == buy_event["decision_id"]
    assert saved_entry.loc[0, "ticker"] == buy_event["ticker"]
    assert saved_entry.loc[0, "status"] == buy_event["status"]
    assert saved_entry.loc[0, "action"] == "BUY"
    assert saved_entry.loc[0, "entry_price"] == pytest.approx(500.0)
    assert pd.isna(saved_entry.loc[0, "exit_price"])
    assert pd.isna(saved_entry.loc[0, "pnl_dollars"])


# ---------------------
# Ledger.add_sell_event
# ---------------------

def test_ledger_add_sell_event(tmp_path):
    ledger_db_path = tmp_path / "logger.db"

    ledger = Ledger(ledger_db_path=str(ledger_db_path))

    sell_event = make_sell_ledger_event()
    
    ledger.add_event(sell_event)

    saved_entry = ledger.get_all()

    assert saved_entry.loc[0, "trade_id"] == sell_event["trade_id"]
    assert saved_entry.loc[0, "decision_id"] == sell_event["decision_id"]
    assert saved_entry.loc[0, "ticker"] == sell_event["ticker"]
    assert saved_entry.loc[0, "status"] == sell_event["status"]
    assert saved_entry.loc[0, "action"] == "SELL"
    assert saved_entry.loc[0, "entry_price"] == pytest.approx(500.0)
    assert saved_entry.loc[0, "exit_price"] == pytest.approx(650.0)
    assert saved_entry.loc[0, "pnl_dollars"] == pytest.approx(300.0)
    assert saved_entry.loc[0, "sell_reason"] == "Take Profit Reached"



# ---------------------
# Ledger.seen_ids
# ---------------------

def test_ledger_seen_ids(tmp_path):
    ledger_db_path = tmp_path / "logger.db"

    ledger = Ledger(ledger_db_path=str(ledger_db_path))

    entry_1 = make_sell_ledger_event(
        trade_id="TRD_TEST_001",
        decision_id="DEC_TEST_001",
        news_id="NEWS_TEST_001",
    )

    entry_2 = make_sell_ledger_event(
        trade_id="TRD_TEST_002",
        decision_id="DEC_TEST_002",
        news_id="NEWS_TEST_002",
    )
    
    ledger.add_event(entry_1)
    ledger.add_event(entry_2)

    seen_ids = ledger.seen_ids()

    assert set(seen_ids) == {"NEWS_TEST_001", "NEWS_TEST_002"}


# ---------------------
# Ledger.get_all
# ---------------------

def test_ledger_get_all(tmp_path):
    ledger_db_path = tmp_path / "logger.db"

    ledger = Ledger(ledger_db_path=str(ledger_db_path))

    entry = make_ledger_event()

    ledger.add_event(entry)

    saved_entry = ledger.get_all()

    expected_df = pd.DataFrame([entry])

    columns_to_compare = list(entry.keys())

    pd.testing.assert_frame_equal(
        expected_df[columns_to_compare].reset_index(drop=True),
        saved_entry[columns_to_compare].reset_index(drop=True),
        check_dtype=False,
    )

# -----------------------------------------------------
# Ledger.save_entry without action return a ValueError
# -----------------------------------------------------

def test_ledger_missing_action_raises_value_error(tmp_path):
    ledger_db_path = tmp_path / "logger.db"

    ledger = Ledger(ledger_db_path=str(ledger_db_path))

    entry = make_ledger_event(
        action=None
    )

    with pytest.raises(ValueError):
        ledger.add_event(entry)