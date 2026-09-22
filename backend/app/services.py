"""Application service wiring for the Aroogula backend.

This module is the composition root: it creates the objects used by the API,
but it does not define routes and it does not contain trading logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from alpaca.data.historical import StockHistoricalDataClient

from backend.config import paths
from backend.config.environment import get_env, require_env

from backend.market.market_data import MarketDataService
from backend.persistence.market_memory import MarketMemory
from backend.news.feeder import NewsFeeder
from backend.analysis.trade_analyzer import TradeAnalyzer

from scrappers.BloombergBot import BloombergBot
from scrappers.EdgarBot import EdgarBot
from scrappers.Forbes.ForbesBot import ForbesBot
from scrappers.YahooBot import YahooNewsBot

from backend.trading.broker import Broker
from backend.analytics.charts import ChartEngine
from backend.trading.portfolio import Portfolio
from backend.trading.wallet import Wallet
from backend.trading.execution.local_lexecutor import LocalExecutor

from backend.persistence.ai_logger import AILogger
from backend.news.dossiers import Dossiers
from backend.persistence.equity_logger import EquityLogger
from backend.analytics.equity_summary import EquitySummaryService
from backend.persistence.ledger import Ledger
from backend.config.settings import Settings
from backend.config.state import BotState

logger = logging.getLogger(__name__)

EDGAR_IDENTITY = get_env("SEC_EDGAR_IDENTITY", "Aroogula Developer developer@example.com")

BLOOMBERG_RSS_SITES = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.bloomberg.com/politics/news.rss",
    "https://feeds.bloomberg.com/technology/news.rss",
    "https://feeds.bloomberg.com/wealth/news.rss",
]

@dataclass(slots=True)
class AppServices:
    settings: Settings
    state: BotState
    dossiers: Dossiers
    memory: MarketMemory
    ledger: Ledger
    ai_logger: AILogger
    equity_logger: EquityLogger
    alpaca_client: StockHistoricalDataClient
    market_data: MarketDataService
    news_feeder: NewsFeeder
    wallet: Wallet
    portfolio: Portfolio
    broker: Broker
    trade_analyzer: TradeAnalyzer
    equity_summary: EquitySummaryService
    chart_engine: ChartEngine


def initialize_alpaca() -> StockHistoricalDataClient:
    """Create the Alpaca historical data client from environment credentials."""
    return StockHistoricalDataClient(
        require_env("ALPACA_API_KEY"),
        require_env("ALPACA_SECRET_KEY"),
    )


def create_services() -> AppServices:
    """Build all long-lived backend services in dependency order."""
    paths.ensure_directories()

    settings = Settings(paths.SETTINGS_PATH)
    state = BotState(paths.BOTSTATE_PATH)
    memory = MarketMemory(paths.MEMORY_DB_PATH)

    dossiers = Dossiers(
        dossier_path=paths.DOSSIERS_PATH,
        company_profile_path=paths.COMPANY_PROFILE_PATH,
        forbes_db_path=paths.FORBES_DB_PATH,
        edgar_db_path=paths.EDGAR_DB_PATH,
        yahoo_db_path=paths.YAHOO_DB_PATH,
        bloomberg_db_path=paths.BLOOMBERG_DB_PATH,
        companies_csv_path=paths.COMPANIES_CSV_PATH,
        reuters_db_path=paths.REUTERS_DB_PATH
        )

    ledger = Ledger(paths.LOGGER_DB_PATH)
    ai_logger = AILogger(paths.LOGGER_DB_PATH)
    equity_logger = EquityLogger(paths.LOGGER_DB_PATH)

    alpaca_client = initialize_alpaca()
    market_data = MarketDataService(alpaca_client=alpaca_client)

    edgar_bot = EdgarBot(
        db_path=paths.EDGAR_DB_PATH,
        companies_csv=paths.COMPANIES_CSV_PATH,
        identity=EDGAR_IDENTITY,
    )
    yahoo_bot = YahooNewsBot(
        db_path=paths.YAHOO_DB_PATH,
        companies_csv=paths.COMPANIES_CSV_PATH,
    )
    bloomberg_bot = BloombergBot(
        db_path=paths.BLOOMBERG_DB_PATH,
        companies_csv=paths.COMPANIES_CSV_PATH,
        sites=BLOOMBERG_RSS_SITES,
    )
    forbes_bot = ForbesBot(
        db_path=paths.FORBES_DB_PATH,
        groq_api_key=require_env("GROQ_API_KEY"),
        companies_csv=paths.COMPANIES_CSV_PATH,
    )

    news_feeder = NewsFeeder(
        settings=settings,
        bloomberg_bot=bloomberg_bot,
        yahoo_bot=yahoo_bot,
        forbes_bot=forbes_bot,
        edgar_bot=edgar_bot,
    )

    wallet = Wallet(
        wallet_state=paths.WALLET_SIM_PATH,
        config_path=paths.SETTINGS_PATH,
        alpaca_client=alpaca_client,
    )
    portfolio = Portfolio(
        mode="local_sim",
        alpaca_client=alpaca_client,
        portfolio_path=paths.PORTFOLIO_PATH,
    )
    local_executor = LocalExecutor(
        wallet=wallet,
        market_data=market_data,
    )
    broker = Broker(
        wallet=wallet,
        ledger=ledger,
        portfolio=portfolio,
        memory=memory,
        market_data=market_data,
        executor=local_executor,
        settings_path=paths.SETTINGS_PATH,
        alpaca_client=alpaca_client,
        mode="local_sim",
    )

    trade_analyzer = TradeAnalyzer(
        broker=broker,
        dossier=dossiers,
        memory=memory,
        settings=settings,
        bot_state=state,
        ai_logger=ai_logger,
        edgar_db_path=paths.EDGAR_DB_PATH,
        yahoo_db_path=paths.YAHOO_DB_PATH,
        bloomberg_db_path=paths.BLOOMBERG_DB_PATH,
        forbes_db_path=paths.FORBES_DB_PATH,
        finbert_model_path=paths.FINBERT_PATH,
    )

    equity_summary = EquitySummaryService(
        wallet=wallet,
        portfolio=portfolio,
        equity_logger=equity_logger,
        market_data=market_data,
    )
    chart_engine = ChartEngine(ledger=ledger)

    logger.info("Application services created successfully.")

    return AppServices(
        settings=settings,
        state=state,
        dossiers=dossiers,
        memory=memory,
        ledger=ledger,
        ai_logger=ai_logger,
        equity_logger=equity_logger,
        alpaca_client=alpaca_client,
        market_data=market_data,
        news_feeder=news_feeder,
        wallet=wallet,
        portfolio=portfolio,
        broker=broker,
        trade_analyzer=trade_analyzer,
        equity_summary=equity_summary,
        chart_engine=chart_engine,
    )
