"""Central path configuration for the Aroogula backend."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = PROJECT_ROOT / "config"
TRADES_DIR = PROJECT_ROOT / "trades"
DATABASE_DIR = PROJECT_ROOT / "database"
LOGGER_DIR = DATABASE_DIR / "logger"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"

# Config files
BOTSTATE_PATH = str(CONFIG_DIR / "state.json")
SETTINGS_PATH = str(CONFIG_DIR / "settings.json")
WALLET_SIM_PATH = str(CONFIG_DIR / "wallet_sim_state.json")

# Trading files
DOSSIERS_PATH = str(TRADES_DIR / "dossiers.json")
COMPANY_PROFILE_PATH = str(TRADES_DIR / "company_profile.json")
PORTFOLIO_PATH = str(TRADES_DIR / "portfolio.csv")

# External/raw databases
MEMORY_DB_PATH = str(DATABASE_DIR / "chroma_db")
EDGAR_DB_PATH = str(DATABASE_DIR / "EDGAR filings.db")
FORBES_DB_PATH = str(DATABASE_DIR / "Forbes news.db")
BLOOMBERG_DB_PATH = str(DATABASE_DIR / "Bloomberg news.db")
YAHOO_DB_PATH = str(DATABASE_DIR / "Yahoo news.db")
REUTERS_DB_PATH = str(DATABASE_DIR / "Reuters.db")

# Central application database
LOGGER_DB_PATH = str(LOGGER_DIR / "aroogula_core.db")

# Data/model files
COMPANIES_CSV_PATH = str(PROJECT_ROOT / "Companies.csv")
FINBERT_PATH = str(MODELS_DIR / "best_model")
APP_LOG_PATH = str(LOGS_DIR / "app.log")


def ensure_directories() -> None:
    """Create folders that must exist before services write to disk."""
    for directory in (
        CONFIG_DIR,
        TRADES_DIR,
        DATABASE_DIR,
        LOGGER_DIR,
        LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
