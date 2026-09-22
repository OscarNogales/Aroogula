"""Shared SQLite utilities for the trading bot storage layer.

These helpers keep every logger consistent:
- one connection policy
- WAL mode for better local-app concurrency
- parameterized values to avoid SQL injection
- validated table/column names for dynamic SQL fragments
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_sql_identifier(identifier: str) -> str:
    """Validate a SQLite table/column/index identifier used in dynamic SQL.

    Values should always be passed with placeholders. SQLite does not allow
    placeholders for identifiers, so any dynamic identifier must be validated.
    """
    if not _SQL_IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier!r}")
    return identifier


def validate_sql_identifiers(identifiers: Iterable[str]) -> list[str]:
    """Validate several SQLite identifiers and return them as a list."""
    return [validate_sql_identifier(identifier) for identifier in identifiers]


class SQLiteTableStore:
    """
    Subclasses define:
    - table_name
    - columns
    - schema_sql
    - indexes_sql

    The base class handles connection setup, insert helpers, validation, and
    common DataFrame reads. It intentionally does not keep a long-lived SQLite
    connection open; each operation opens a short transaction-safe connection.
    """

    table_name: str = ""
    columns: Sequence[str] = ()
    schema_sql: str = ""
    indexes_sql: Sequence[str] = ()

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.table_name = validate_sql_identifier(self.table_name)
        self.columns = tuple(validate_sql_identifiers(self.columns))
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        """Create a configured SQLite connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row

        # Useful defaults for a local desktop app where several backend tasks
        # may read while one task writes.
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _initialize_database(self) -> None:
        """Create the table and indexes if they do not exist."""
        if not self.schema_sql.strip():
            raise ValueError(f"{self.__class__.__name__} is missing schema_sql.")

        with self._connect() as conn:
            conn.execute(self.schema_sql)
            for index_sql in self.indexes_sql:
                conn.execute(index_sql)
            conn.commit()

    def _normalize_entry(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        """Reject unknown columns and fill missing known columns with None."""
        extra_columns = set(entry.keys()) - set(self.columns)
        if extra_columns:
            raise ValueError(
                f"{self.__class__.__name__} received unknown columns: "
                f"{sorted(extra_columns)}"
            )

        return {column: entry.get(column, None) for column in self.columns}

    def insert_row(
        self,
        entry: Mapping[str, Any],
        *,
        conflict_clause: str = "",
    ) -> int:
        """Insert one normalized row and return the SQLite row id.

        conflict_clause examples:
        - "" for normal INSERT
        - "OR IGNORE" for INSERT OR IGNORE
        - "OR REPLACE" for INSERT OR REPLACE
        """
        normalized = self._normalize_entry(entry)
        placeholders = ", ".join("?" for _ in self.columns)
        columns_sql = ", ".join(self.columns)
        conflict_sql = f" {conflict_clause.strip()}" if conflict_clause else ""

        sql = (
            f"INSERT{conflict_sql} INTO {self.table_name} "
            f"({columns_sql}) VALUES ({placeholders});"
        )
        values = tuple(normalized[column] for column in self.columns)

        with self._connect() as conn:
            cursor = conn.execute(sql, values)
            conn.commit()
            return int(cursor.lastrowid or 0)

    def to_json_records(self, df = pd.DataFrame) -> list[dict]:
        """Convert a DataFrame to JSON-safe records.

        Pandas uses NaN/NaT for missing values, but strict JSON responses
        require None so FastAPI can serialize them as null.
        """
        if df.empty:
            return []

        clean_df = df.copy()
        clean_df = clean_df.replace([float("inf"), float("-inf")], None)
        clean_df = clean_df.astype(object).where(pd.notna(clean_df), None)

        return clean_df.to_dict(orient="records")

    def execute(self, query: str, params: Sequence[Any] = ()) -> int:
        """Execute a write query and return affected row count."""
        with self._connect() as conn:
            cursor = conn.execute(query, tuple(params))
            conn.commit()
            return int(cursor.rowcount)

    def read_df(self, query: str, params: Sequence[Any] = ()) -> pd.DataFrame:
        """Read query results into a DataFrame."""
        with self._connect() as conn:
            return pd.read_sql_query(query, conn, params=tuple(params))

    def load_all(self, *, order_by: str = "timestamp", descending: bool = False) -> pd.DataFrame:
        """Return the complete table ordered by a validated column."""
        order_by = validate_sql_identifier(order_by)
        direction = "DESC" if descending else "ASC"
        return self.read_df(
            f"SELECT * FROM {self.table_name} ORDER BY {order_by} {direction};"
        )

    def get_recent(self, limit: int = 50, *, timestamp_column: str = "timestamp") -> pd.DataFrame:
        """Return the latest rows by timestamp."""
        timestamp_column = validate_sql_identifier(timestamp_column)
        limit = max(1, int(limit))
        return self.read_df(
            f"""
            SELECT *
            FROM {self.table_name}
            ORDER BY {timestamp_column} DESC
            LIMIT ?;
            """,
            (limit,),
        )

    def filter_equal(self, column: str, value: Any) -> pd.DataFrame:
        """Return rows where a validated column exactly equals a value."""
        column = validate_sql_identifier(column)
        return self.read_df(
            f"SELECT * FROM {self.table_name} WHERE {column} = ?;",
            (value,),
        )

    def search_text(self, columns: Sequence[str], query: str) -> pd.DataFrame:
        """Case-insensitive LIKE search across selected text columns."""
        if not columns:
            raise ValueError("At least one searchable column is required.")

        safe_columns = validate_sql_identifiers(columns)
        where_sql = " OR ".join(f"LOWER({column}) LIKE ?" for column in safe_columns)
        pattern = f"%{query.lower()}%"
        params = tuple(pattern for _ in safe_columns)

        return self.read_df(
            f"SELECT * FROM {self.table_name} WHERE {where_sql};",
            params,
        )
