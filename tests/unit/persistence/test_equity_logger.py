from backend.persistence.equity_logger import EquityLogger

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sqlite3 as sql

import pandas as pd
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


def make_equity_entry(**overrides):
    entry = {
        "timestamp": "2026-07-20T12:00:00",
        "cash": 1000.0,
        "portfolio_assets": 1500.0,
        "equity": 2500.0,
        "open_positions_count": 3,
        "daily_pnl": 125.0,
        "daily_pnl_pct": 5.0,
        "total_exposure_pct": 60.0,
        "max_position_weight_pct": 25.0,
        "execution_mode": "local_sim",
    }

    entry.update(overrides)
    return entry


# ---------------------
# EquityLogger.save_entry
# ---------------------

def test_equity_logger_save_entry_writes_snapshot_to_database(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    entry = make_equity_entry()

    row_id = equity_logger.save_entry(entry)

    assert row_id > 0

    table_df = get_table_from_sql(
        table_name=equity_logger.table_name,
        db_path=str(equity_db_path),
    )

    assert len(table_df) == 1

    row = table_df.iloc[0]

    assert row["timestamp"] == "2026-07-20T12:00:00"
    assert row["cash"] == pytest.approx(1000.0)
    assert row["portfolio_assets"] == pytest.approx(1500.0)
    assert row["equity"] == pytest.approx(2500.0)
    assert row["open_positions_count"] == 3
    assert row["execution_mode"] == "local_sim"


def test_equity_logger_save_entry_fills_missing_timestamp(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    entry = make_equity_entry(timestamp=None)

    equity_logger.save_entry(entry)

    saved_df = equity_logger.get_all()

    assert len(saved_df) == 1
    assert isinstance(saved_df.iloc[0]["timestamp"], str)
    assert saved_df.iloc[0]["timestamp"] != ""


def test_equity_logger_save_entry_rejects_unknown_columns(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    entry = make_equity_entry(
        fake_column="this should not exist",
    )

    with pytest.raises(ValueError):
        equity_logger.save_entry(entry)


# ---------------------
# EquityLogger.get_all
# ---------------------

def test_equity_logger_get_all_returns_rows_ordered_by_timestamp(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    later_entry = make_equity_entry(
        timestamp="2026-07-20T12:00:00",
        equity=2500.0,
    )

    earlier_entry = make_equity_entry(
        timestamp="2026-07-20T09:30:00",
        equity=2000.0,
    )

    equity_logger.save_entry(later_entry)
    equity_logger.save_entry(earlier_entry)

    saved_df = equity_logger.get_all()

    assert len(saved_df) == 2
    assert saved_df.iloc[0]["timestamp"] == "2026-07-20T09:30:00"
    assert saved_df.iloc[1]["timestamp"] == "2026-07-20T12:00:00"
    assert saved_df.iloc[0]["equity"] == pytest.approx(2000.0)
    assert saved_df.iloc[1]["equity"] == pytest.approx(2500.0)


# ---------------------
# EquityLogger.get_latest
# ---------------------

def test_equity_logger_get_latest_returns_latest_snapshot(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    old_entry = make_equity_entry(
        timestamp="2026-07-20T09:30:00",
        equity=2000.0,
    )

    latest_entry = make_equity_entry(
        timestamp="2026-07-20T12:00:00",
        equity=2500.0,
    )

    equity_logger.save_entry(old_entry)
    equity_logger.save_entry(latest_entry)

    latest_df = equity_logger.get_latest()

    assert len(latest_df) == 1
    assert latest_df.iloc[0]["timestamp"] == "2026-07-20T12:00:00"
    assert latest_df.iloc[0]["equity"] == pytest.approx(2500.0)


# ---------------------
# EquityLogger.get_recent
# ---------------------

def test_equity_logger_get_recent_respects_limit_and_orders_latest_first(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    entry_1 = make_equity_entry(
        timestamp="2026-07-20T09:30:00",
        equity=2000.0,
    )

    entry_2 = make_equity_entry(
        timestamp="2026-07-20T10:30:00",
        equity=2200.0,
    )

    entry_3 = make_equity_entry(
        timestamp="2026-07-20T11:30:00",
        equity=2500.0,
    )

    equity_logger.save_entry(entry_1)
    equity_logger.save_entry(entry_2)
    equity_logger.save_entry(entry_3)

    recent_df = equity_logger.get_recent(limit=2)

    assert len(recent_df) == 2
    assert recent_df.iloc[0]["timestamp"] == "2026-07-20T11:30:00"
    assert recent_df.iloc[1]["timestamp"] == "2026-07-20T10:30:00"


# ---------------------
# EquityLogger.get_range
# ---------------------

def test_equity_logger_get_range_max_returns_all_rows(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    entry_1 = make_equity_entry(
        timestamp="2026-07-20T09:30:00",
        equity=2000.0,
    )

    entry_2 = make_equity_entry(
        timestamp="2026-07-20T10:30:00",
        equity=2200.0,
    )

    equity_logger.save_entry(entry_1)
    equity_logger.save_entry(entry_2)

    range_df = equity_logger.get_range("max")

    assert len(range_df) == 2
    assert set(range_df["equity"]) == {2000.0, 2200.0}


def test_equity_logger_get_range_1d_filters_old_rows(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    ny_now = datetime.now(ZoneInfo("America/New_York"))
    market_open = ny_now.replace(
        hour=9,
        minute=30,
        second=0,
        microsecond=0,
    )

    old_timestamp = (market_open - timedelta(seconds=1)).isoformat(timespec="seconds")
    recent_timestamp = (market_open + timedelta(hours=1)).isoformat(timespec="seconds")

    old_entry = make_equity_entry(
        timestamp=old_timestamp,
        equity=1000.0,
    )

    recent_entry = make_equity_entry(
        timestamp=recent_timestamp,
        equity=2500.0,
    )

    equity_logger.save_entry(old_entry)
    equity_logger.save_entry(recent_entry)

    range_df = equity_logger.get_range("1d")

    assert len(range_df) == 1
    assert range_df.iloc[0]["equity"] == pytest.approx(2500.0)


def test_equity_logger_get_range_invalid_timeframe_raises_value_error(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    with pytest.raises(ValueError):
        equity_logger.get_range("bad_timeframe")


# ---------------------
# EquityLogger.equity_graph
# ---------------------

def test_equity_logger_equity_graph_returns_success_with_frontend_lists(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    entry_1 = make_equity_entry(
        timestamp="2026-07-20T09:30:00",
        cash=1000.0,
        portfolio_assets=1000.0,
        equity=2000.0,
    )

    entry_2 = make_equity_entry(
        timestamp="2026-07-20T10:30:00",
        cash=900.0,
        portfolio_assets=1300.0,
        equity=2200.0,
    )

    equity_logger.save_entry(entry_1)
    equity_logger.save_entry(entry_2)

    graph = equity_logger.equity_graph(time="max")

    assert graph["status"] == "success"
    assert graph["timestamp"] == [
        "2026-07-20T09:30:00",
        "2026-07-20T10:30:00",
    ]
    assert graph["cash"] == [1000.0, 900.0]
    assert graph["portfolio_assets"] == [1000.0, 1300.0]
    assert graph["equity"] == [2000.0, 2200.0]


def test_equity_logger_equity_graph_returns_error_when_empty(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    graph = equity_logger.equity_graph(time="max")

    assert graph["status"] == "error"
    assert "historial" in graph["message"].lower()


def test_equity_logger_equity_graph_invalid_timeframe_raises_value_error(tmp_path):
    equity_db_path = tmp_path / "logger.db"
    equity_logger = EquityLogger(equity_db_path=str(equity_db_path))

    with pytest.raises(ValueError):
        equity_logger.equity_graph(time="bad_timeframe")