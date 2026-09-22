"""SQLite-backed equity snapshot logger."""

from __future__ import annotations

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

try:
    from backend.persistence.database import SQLiteTableStore
except ImportError:  # Allows running this file directly during development.
    from database import SQLiteTableStore


class EquityLogger(SQLiteTableStore):
    """Stores portfolio equity snapshots for dashboard and performance charts."""

    table_name = "equity_log"

    columns = (
        "timestamp",
        "cash",
        "portfolio_assets",
        "equity",
        "open_positions_count",
        "daily_pnl",
        "daily_pnl_pct",
        "total_exposure_pct",
        "max_position_weight_pct",
        "execution_mode",
    )

    schema_sql = """
        CREATE TABLE IF NOT EXISTS equity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cash REAL,
            portfolio_assets REAL,
            equity REAL,
            open_positions_count INTEGER,
            daily_pnl REAL,
            daily_pnl_pct REAL,
            total_exposure_pct REAL,
            max_position_weight_pct REAL,
            execution_mode TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """

    indexes_sql = (
        "CREATE INDEX IF NOT EXISTS idx_equity_log_timestamp ON equity_log (timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_equity_log_mode_timestamp ON equity_log (execution_mode, timestamp);",
    )

    def __init__(self, equity_db_path: str | Path):
        super().__init__(equity_db_path)
        # Compatibility with older code. New methods read from SQLite directly.
        self.equity_df = self.get_all()

    def _normalize_entry(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        normalized = super()._normalize_entry(entry)

        if normalized["timestamp"] is None:
            normalized["timestamp"] = datetime.now().isoformat(timespec="seconds")

        return normalized

    def save_entry(self, entry: Mapping[str, Any]) -> int:
        """Save one equity snapshot and return its SQLite row id."""
        row_id = self.insert_row(entry)
        self.equity_df = self.get_all()
        return row_id

    def get_all(self) -> pd.DataFrame:
        """Return all equity snapshots ordered by timestamp."""
        return self.load_all(order_by="timestamp")

    def get_latest(self) -> pd.DataFrame:
        """Return the latest equity snapshot as a one-row DataFrame."""
        return self.get_recent(limit=1)

    def get_recent(self, limit: int = 50) -> pd.DataFrame:
        """Return the latest equity snapshots."""
        return super().get_recent(limit=limit, timestamp_column="timestamp")

    def _time_cutoff(self, timeframe: str) -> str | None:
        valid_timeframes = {
            "1d", "5d", "1mo", "3mo", "6mo",
            "1y", "2y", "5y", "10y", "ytd", "max",
        }

        if timeframe not in valid_timeframes:
            raise ValueError("Time selected is not inside the established timeframes.")

        ny_now = datetime.now(ZoneInfo("America/New_York"))

        if timeframe == "max":
            return None

        if timeframe == "ytd":
            cutoff = ny_now.replace(
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            return cutoff.isoformat(timespec="seconds")

        if timeframe == "1d":
            cutoff = ny_now.replace(
                hour=9,
                minute=30,
                second=0,
                microsecond=0,
            )
            return cutoff.isoformat(timespec="seconds")

        days_by_timeframe = {
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 365 * 2,
            "5y": 365 * 5,
            "10y": 365 * 10,
        }

        cutoff = ny_now - timedelta(days=days_by_timeframe[timeframe])
        cutoff = cutoff.replace(
            hour=9,
            minute=30,
            second=0,
            microsecond=0,
        )

        return cutoff.isoformat(timespec="seconds")

    def get_range(self, timeframe: str = "max") -> pd.DataFrame:
        """Return equity snapshots filtered by a timeframe."""
        cutoff = self._time_cutoff(timeframe)

        if cutoff is None:
            return self.get_all()

        return self.read_df(
            f"""
            SELECT *
            FROM {self.table_name}
            WHERE timestamp >= ?
            ORDER BY timestamp ASC;
            """,
            (cutoff,),
        )

    def equity_graph(self, time: str = "max") -> dict[str, Any]:
        """Return frontend-ready equity history for chart rendering."""
        equity_log = self.get_range(time)

        if equity_log.empty:
            return {
                "status": "error",
                "message": f"El historial de rendimiento está vacío para el rango '{time}'.",
            }

        return {
            "status": "success",
            **equity_log.to_dict(orient="list"),
        }
