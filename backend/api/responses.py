"""Small helpers for consistent API responses."""

from __future__ import annotations

from typing import Any


def error_response(message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "data": data or {},
    }
