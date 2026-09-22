"""Environment-backed configuration for external credentials.

Secrets are loaded from a local .env file during development and from the
process environment in deployed environments. The .env file is intentionally
excluded from version control.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable {name!r} is not configured. "
            "Copy .env.example to .env and provide the credential locally."
        )
    return value
