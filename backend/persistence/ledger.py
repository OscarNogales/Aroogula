"""SQLite-backed trade ledger.

The ledger records executed trade events. It intentionally does not replace
AILogger: AILogger stores all model decisions, while Ledger stores actions that
actually became broker/portfolio events.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

try:
    from backend.persistence.database import SQLiteTableStore
except ImportError:
    from database import SQLiteTableStore


class Ledger(SQLiteTableStore):
    """Stores executed trade events in the `trade_ledger` table."""

    table_name = "trade_ledger"

    columns = (
        "trade_id",
        "decision_id",
        "news_id",
        "ticker",
        "action",
        "status",
        "timestamp",
        "entry_price",
        "exit_price",
        "shares",
        "position_value",
        "cash_before",
        "cash_after",
        "equity_before",
        "equity_after",
        "buy_reason",
        "sell_reason",
        "ai_confidence",
        "pnl_dollars",
        "pnl_pct",
        "holding_minutes",
        "exit_trigger",
        "was_profitable",
        "execution_mode",
        "strategy_version",
    )

    schema_sql = """
        CREATE TABLE IF NOT EXISTS trade_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            trade_id TEXT,
            decision_id TEXT,
            news_id TEXT,
            ticker TEXT,
            action TEXT NOT NULL,
            status TEXT,
            timestamp TEXT NOT NULL,

            entry_price REAL,
            exit_price REAL,
            shares REAL,
            position_value REAL,

            cash_before REAL,
            cash_after REAL,
            equity_before REAL,
            equity_after REAL,

            buy_reason TEXT,
            sell_reason TEXT,
            ai_confidence REAL,

            pnl_dollars REAL,
            pnl_pct REAL,
            holding_minutes REAL,
            exit_trigger TEXT,
            was_profitable INTEGER,

            execution_mode TEXT,
            strategy_version TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """

    indexes_sql = (
        "CREATE INDEX IF NOT EXISTS idx_trade_ledger_timestamp ON trade_ledger (timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_trade_ledger_trade_id ON trade_ledger (trade_id);",
        "CREATE INDEX IF NOT EXISTS idx_trade_ledger_ticker_timestamp ON trade_ledger (ticker, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_trade_ledger_action_timestamp ON trade_ledger (action, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_trade_ledger_news_id ON trade_ledger (news_id);",
        "CREATE INDEX IF NOT EXISTS idx_trade_ledger_decision_id ON trade_ledger (decision_id);",
    )

    def __init__(self, ledger_db_path: str | Path):
        super().__init__(ledger_db_path)
        self.ledger = self.get_all()

    def _normalize_entry(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        normalized = super()._normalize_entry(entry)

        if not normalized["action"]:
            raise ValueError("action is required for Ledger events.")

        normalized["action"] = str(normalized["action"]).upper()

        if normalized["ticker"] is not None:
            normalized["ticker"] = str(normalized["ticker"]).upper()

        if normalized["timestamp"] is None:
            normalized["timestamp"] = datetime.now().isoformat(timespec="seconds")

        if isinstance(normalized["was_profitable"], bool):
            normalized["was_profitable"] = int(normalized["was_profitable"])

        return normalized

    def add_event(self, event_data: Mapping[str, Any]) -> bool:
        """Add an executed trade event.

        Returns True for backward compatibility with the previous CSV version.
        Raises ValueError for invalid/unknown columns instead of printing.
        """
        self.insert_row(event_data)
        self.ledger = self.get_all()
        return True

    def get_all(self) -> pd.DataFrame:
        """Return all trade events ordered by timestamp."""
        return self.load_all(order_by="timestamp")

    def get_recent(self, limit: int = 50) -> pd.DataFrame:
        """Return recent trade events."""
        return super().get_recent(limit=limit, timestamp_column="timestamp")

    def filter_by_ticker(self, ticker: str) -> pd.DataFrame:
        """Return trade events for one ticker."""
        return self.read_df(
            f"SELECT * FROM {self.table_name} WHERE ticker = ? ORDER BY timestamp DESC;",
            (ticker.upper(),),
        )

    def filter_by_trade_id(self, trade_id: str) -> pd.DataFrame:
        """Return all events for one trade id."""
        return self.read_df(
            f"SELECT * FROM {self.table_name} WHERE trade_id = ? ORDER BY timestamp ASC;",
            (trade_id,),
        )

    def seen_ids(self) -> list[str]:
        """Return news IDs already represented in the trade ledger."""
        df = self.read_df(
            f"""
            SELECT DISTINCT news_id
            FROM {self.table_name}
            WHERE news_id IS NOT NULL AND news_id != '';
            """
        )
        return df["news_id"].dropna().astype(str).tolist()


# Clearer name for future imports, while keeping Ledger for compatibility.
TradeLedger = Ledger
