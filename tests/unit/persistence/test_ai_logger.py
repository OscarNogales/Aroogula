from backend.persistence.ai_logger import AILogger

import pandas as pd
import sqlite3 as sql
import pytest

# ---------------------
# Helpers
# ---------------------

def get_table_from_sql(table_name: str, db_path: str):
    with sql.connect(db_path) as conn:
        df = pd.read_sql_query(
            f"SELECT * FROM {table_name};",
            con=conn,
        )

    return df

def make_ai_entry(**overrides):
    entry = {
        "decision_id": "DEC_TEST_001",
        "news_id": "NEWS_TEST_001",
        "ticker": "MSFT",
        "timestamp": "2026-07-20T12:00:00",
        "ai_signal": "BUY",
        "ai_confidence": 0.87,
        "ai_reasoning": "Strong positive earnings news with favorable market context.",
        "decision_result": "executed",
        "linked_trade_id": "TRD_TEST_001",
        "finbert_sentiment": "positive",
        "finbert_sentiment_score": 0.91,
        "finbert_tradeable": 1,
        "finbert_tradeable_score": 0.84,
        "news_source": "Yahoo Finance",
        "news_title": "Microsoft reports strong quarterly earnings",
        "news_age_minutes": 12,
        "macro_regime": "MARKUP",
        "market_session": "regular",
        "market_is_open": 1,
        "sp500_trend_pct": 0.45,
        "nasdaq_trend_pct": 0.72,
        "vix_level": 14.8,
        "price_at_decision": 500.0,
        "day_change_pct": 1.25,
        "volume": 25000000,
        "relative_volume": 1.35,
        "rsi_14": 58.2,
        "atr_14": 7.4,
        "risk_level": "normal",
        "rejected_by_risk_guard": 0,
        "risk_guard_reason": None,
        "strategy_version": "test_strategy_v1",
        "prompt_version": "test_prompt_v1",
        "model_version": "llama3.1:test",
    }

    entry.update(overrides)
    return entry

# ---------------------
# AILogger.save_entry
# ---------------------

def test_ailogger_save_entry(tmp_path):
    logger_db_path = tmp_path / "logger.db"

    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    test_entry = make_ai_entry()

    result = ai_logger.save_entry(test_entry)

    assert result > 0

    # Asserts with pandas

    ai_table_name = ai_logger.table_name
    ai_logger_df = get_table_from_sql(ai_table_name, str(logger_db_path))

    assert len(ai_logger_df) == 1

    row = ai_logger_df.iloc[0]

    assert row["decision_id"] == "DEC_TEST_001"
    assert row["ticker"] == "MSFT"
    assert row["ai_signal"] == "BUY"
    assert row["decision_result"] == "executed"
    assert row["finbert_sentiment"] == "positive"
    assert row["price_at_decision"] == 500.0



# ----------------------------------------------
# AILogger.save_entry when there is a duplicate
# ----------------------------------------------

def test_ailogger_duplicate_decision_id_is_ignored(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    msft_entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        ticker="MSFT"
    )

    aapl_entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        ticker="AAPL"
    )

    ai_logger.save_entry(msft_entry)
    ai_logger.save_entry(aapl_entry)

    df = ai_logger.get_all()

    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "MSFT"



# -------------------------------------------------
# AILogger.save_entry when decision id is missing
# -------------------------------------------------

def test_ailogger_decision_id_missing_raises_value_error(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    entry = make_ai_entry(
        decision_id=None,
        ticker="MSFT"
    )
    with pytest.raises(ValueError):
        ai_logger.save_entry(entry)


# -------------------------------------------
# AILogger.save_entry when ticker is missing
# -------------------------------------------

def test_ailogger_ticker_missing_raises_value_error(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        ticker=None
    )
    with pytest.raises(ValueError):
        ai_logger.save_entry(entry)


# ---------------------------------------------------
# AILogger.save_entry normalizes ticker to uppercase
# ---------------------------------------------------

def test_ailogger_save_entry_normalizes_the_ticker_to_upper_case(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        ticker="msft"
    )

    ai_logger.save_entry(entry)

    saved_entry = ai_logger.get_all()

    assert saved_entry.loc[0, "ticker"] == "MSFT"


# -----------------
# AILogger.get_all
# -----------------

def test_ailogger_get_all(tmp_path):
    logger_db_path = tmp_path / "logger.db"

    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    test_entry = make_ai_entry()

    send_result = ai_logger.save_entry(test_entry)

    assert send_result > 0

    retrieve_result = ai_logger.get_all()

    # Asserts with pandas
    table_name = ai_logger.table_name
    db_data_df = get_table_from_sql(table_name, str(logger_db_path))

    pd.testing.assert_frame_equal(
    retrieve_result.reset_index(drop=True),
    db_data_df.reset_index(drop=True),
    check_dtype=False,
    )

    
# --------------------------
# AILogger.filter_by_ticker
# --------------------------

def test_ailogger_filter_by_ticker_returns_only_matching_rows(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    msft_entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        ticker="MSFT",
        news_id="NEWS_MSFT_001",
    )

    aapl_entry = make_ai_entry(
        decision_id="DEC_TEST_002",
        ticker="AAPL",
        news_id="NEWS_AAPL_001",
    )

    ai_logger.save_entry(msft_entry)
    ai_logger.save_entry(aapl_entry)

    result_df = ai_logger.filter_by_ticker("MSFT")

    assert len(result_df) == 1
    assert result_df.iloc[0]["ticker"] == "MSFT"
    assert result_df.iloc[0]["decision_id"] == "DEC_TEST_001"




# --------------------------
# AILogger.filter_by_signal
# --------------------------

def test_ailogger_filter_by_signal_returns_only_matching_rows(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    buy_entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        ai_signal="BUY"
    )

    sell_entry = make_ai_entry(
        decision_id="DEC_TEST_002",
        ai_signal="SELL"
    )

    hold_entry = make_ai_entry(
        decision_id="DEC_TEST_003",
        ai_signal="HOLD"
    )

    ai_logger.save_entry(buy_entry)
    ai_logger.save_entry(sell_entry)
    ai_logger.save_entry(hold_entry)

    result_df = ai_logger.filter_by_signal("buy")

    assert len(result_df) == 1
    assert result_df.iloc[0]["ai_signal"] == "BUY"
    assert result_df.iloc[0]["decision_id"] == "DEC_TEST_001"



# -------------------------------
# AILogger.update_future_returns
# -------------------------------


def test_ailogger_update_future_returns_updates_existing_row(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        ticker="msft"
    )

    ai_logger.save_entry(entry)

    ai_logger.update_future_returns(
        decision_id="DEC_TEST_001",
        return_15m_pct=0.15,
        return_1h_pct=0.50,
        return_1d_pct=0.65,
        return_5d_pct=0.75
    )

    saved_entry = ai_logger.get_all()

    row = saved_entry.iloc[0]

    assert row["future_return_15m_pct"] == pytest.approx(0.15)
    assert row["future_return_1h_pct"] == pytest.approx(0.50)
    assert row["future_return_1d_pct"] == pytest.approx(0.65)
    assert row["future_return_5d_pct"] == pytest.approx(0.75)


# ---------------------------
# AILogger.filter_by_results
# ---------------------------



def test_ailogger_filter_by_result_returns_only_matching_rows(tmp_path):
    logger_db_path = tmp_path / "logger.db"
    ai_logger = AILogger(decision_db_path=str(logger_db_path))

    executed_entry = make_ai_entry(
        decision_id="DEC_TEST_001",
        decision_result="executed",
    )

    rejected_entry = make_ai_entry(
        decision_id="DEC_TEST_002",
        decision_result="rejected",
    )

    ai_logger.save_entry(executed_entry)
    ai_logger.save_entry(rejected_entry)

    result_df = ai_logger.filter_by_result("executed")

    assert len(result_df) == 1
    assert result_df.iloc[0]["decision_result"] == "executed"
    assert result_df.iloc[0]["decision_id"] == "DEC_TEST_001"