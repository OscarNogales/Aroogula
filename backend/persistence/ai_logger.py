"""SQLite-backed AI decision logger.

This logger records every AI decision, not only executed trades. That makes it
possible to evaluate the model's behavior on BUY, SELL, HOLD, SKIP, rejected,
and error decisions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

try:
    from backend.persistence.database import SQLiteTableStore
except ImportError:  # Allows running this file directly during development.
    from database import SQLiteTableStore


class AILogger(SQLiteTableStore):
    """Stores AI decision events in the `ai_decision_log` SQLite table."""

    table_name = "ai_decision_log"

    columns = (
        # Identity
        "decision_id",
        "news_id",
        "ticker",
        "timestamp",
        # Decision
        "ai_signal",
        "ai_confidence",
        "ai_reasoning",
        "decision_result",
        "linked_trade_id",
        # FinBERT / NLP
        "finbert_sentiment",
        "finbert_sentiment_score",
        "finbert_tradeable",
        "finbert_tradeable_score",
        "finbert_direction",
        "finbert_direction_score",
        # News context
        "news_source",
        "news_title",
        "news_category",
        "news_age_minutes",
        # Market context
        "macro_regime",
        "market_session",
        "market_is_open",
        "sp500_trend_pct",
        "nasdaq_trend_pct",
        "vix_level",
        # Ticker context
        "price_at_decision",
        "day_change_pct",
        "volume",
        "relative_volume",
        "rsi_14",
        "atr_14",
        # Risk / filter result
        "risk_level",
        "rejected_by_risk_guard",
        "risk_guard_reason",
        # Future evaluation
        "future_return_15m_pct",
        "future_return_1h_pct",
        "future_return_1d_pct",
        "future_return_5d_pct",
        # Versioning
        "strategy_version",
        "prompt_version",
        "model_version",
    )

    schema_sql = """
        CREATE TABLE IF NOT EXISTS ai_decision_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            decision_id TEXT NOT NULL UNIQUE,
            news_id TEXT,
            ticker TEXT NOT NULL,
            timestamp TEXT NOT NULL,

            ai_signal TEXT,
            ai_confidence REAL,
            ai_reasoning TEXT,
            decision_result TEXT,
            linked_trade_id TEXT,

            finbert_sentiment TEXT,
            finbert_sentiment_score REAL,
            finbert_tradeable INTEGER,
            finbert_tradeable_score REAL,
            finbert_direction TEXT,
            finbert_direction_score REAL,

            news_source TEXT,
            news_title TEXT,
            news_category TEXT,
            news_age_minutes REAL,

            macro_regime TEXT,
            market_session TEXT,
            market_is_open INTEGER,
            sp500_trend_pct REAL,
            nasdaq_trend_pct REAL,
            vix_level REAL,

            price_at_decision REAL,
            day_change_pct REAL,
            volume REAL,
            relative_volume REAL,
            rsi_14 REAL,
            atr_14 REAL,

            risk_level TEXT,
            rejected_by_risk_guard INTEGER,
            risk_guard_reason TEXT,

            future_return_15m_pct REAL,
            future_return_1h_pct REAL,
            future_return_1d_pct REAL,
            future_return_5d_pct REAL,

            strategy_version TEXT,
            prompt_version TEXT,
            model_version TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """

    indexes_sql = (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_decision_log_decision_id ON ai_decision_log (decision_id);",
        "CREATE INDEX IF NOT EXISTS idx_ai_decision_log_timestamp ON ai_decision_log (timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_ai_decision_log_ticker_timestamp ON ai_decision_log (ticker, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_ai_decision_log_signal_timestamp ON ai_decision_log (ai_signal, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_ai_decision_log_result_timestamp ON ai_decision_log (decision_result, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_ai_decision_log_news_id ON ai_decision_log (news_id);",
        "CREATE INDEX IF NOT EXISTS idx_ai_decision_log_linked_trade_id ON ai_decision_log (linked_trade_id);",
    )

    def __init__(self, decision_db_path: str | Path):
        super().__init__(decision_db_path)
        self.log_df = self.get_all()

    def _normalize_entry(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        normalized = super()._normalize_entry(entry)

        if not normalized["decision_id"]:
            raise ValueError("decision_id is required for AILogger entries.")
        if not normalized["ticker"]:
            raise ValueError("ticker is required for AILogger entries.")

        normalized["ticker"] = str(normalized["ticker"]).upper()

        if normalized["timestamp"] is None:
            normalized["timestamp"] = datetime.now().isoformat(timespec="seconds")

        for boolean_column in (
            "finbert_tradeable",
            "market_is_open",
            "rejected_by_risk_guard",
        ):
            value = normalized[boolean_column]
            if isinstance(value, bool):
                normalized[boolean_column] = int(value)

        return normalized

    def save_entry(self, entry: Mapping[str, Any]) -> int:
        """Save one AI decision.

        Duplicate decision_id rows are ignored. This keeps decision logging
        idempotent if a pipeline step retries the same decision.
        """
        row_id = self.insert_row(entry, conflict_clause="OR IGNORE")
        self.log_df = self.get_all()
        return row_id

    def get_all(self) -> pd.DataFrame:
        """Return all AI decisions ordered by timestamp."""
        return self.load_all(order_by="timestamp")

    def get_recent(self, limit: int = 50) -> pd.DataFrame:
        """Return the latest AI decisions."""
        return super().get_recent(limit=limit, timestamp_column="timestamp")

    def filter_by_ticker(self, ticker: str) -> pd.DataFrame:
        """Return decisions for one ticker."""
        return self.read_df(
            f"SELECT * FROM {self.table_name} WHERE ticker = ? ORDER BY timestamp DESC;",
            (ticker.upper(),),
        )

    def filter_by_signal(self, signal: str) -> pd.DataFrame:
        """Return decisions by AI signal: BUY, SELL, HOLD, SKIP."""
        return self.read_df(
            f"SELECT * FROM {self.table_name} WHERE ai_signal = ? ORDER BY timestamp DESC;",
            (signal.upper(),),
        )

    def filter_by_result(self, result: str) -> pd.DataFrame:
        """Return decisions by result: executed, skipped, rejected, error."""
        return self.read_df(
            f"SELECT * FROM {self.table_name} WHERE decision_result = ? ORDER BY timestamp DESC;",
            (result.lower(),),
        )

    def search_reasoning(self, query: str) -> pd.DataFrame:
        """Search AI reasoning and news titles."""
        return self.search_text(("ai_reasoning", "news_title"), query)

    # Backward-compatible method name used by your earlier version.
    def search_text(self, query: str) -> pd.DataFrame:  # type: ignore[override]
        return self.search_reasoning(query)

    def update_future_returns(
        self,
        decision_id: str,
        *,
        return_15m_pct: float | None = None,
        return_1h_pct: float | None = None,
        return_1d_pct: float | None = None,
        return_5d_pct: float | None = None,
    ) -> int:
        """Update realized future returns for a previously logged decision."""
        affected = self.execute(
            f"""
            UPDATE {self.table_name}
            SET
                future_return_15m_pct = COALESCE(?, future_return_15m_pct),
                future_return_1h_pct = COALESCE(?, future_return_1h_pct),
                future_return_1d_pct = COALESCE(?, future_return_1d_pct),
                future_return_5d_pct = COALESCE(?, future_return_5d_pct)
            WHERE decision_id = ?;
            """,
            (
                return_15m_pct,
                return_1h_pct,
                return_1d_pct,
                return_5d_pct,
                decision_id,
            ),
        )
        self.log_df = self.get_all()
        return affected
