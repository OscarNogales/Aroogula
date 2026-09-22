from backend.analysis.trade_analyzer import TradeAnalyzer

import pandas as pd
from datetime import datetime
from types import SimpleNamespace


# --------------
# Helpers
# --------------

class FakeAILogger:
    table_name = "ai_decision_log"

    def __init__(self):
        self.entries = []

    def get_all(self):
        return pd.DataFrame([
            {
                "decision_id": "DEC-SEEN001",
                "news_id": "news_seen_001",
                "ticker": "AAPL",
                "timestamp": "2026-09-01T10:00:00-04:00",
                "ai_signal": "SKIP",
                "ai_confidence": 0.62,
                "decision_result": "skipped",
                "linked_trade_id": None,
            },
            {
                "decision_id": "DEC-SEEN002",
                "news_id": "news_seen_002",
                "ticker": "MSFT",
                "timestamp": "2026-09-01T11:15:00-04:00",
                "ai_signal": "BUY",
                "ai_confidence": 0.84,
                "decision_result": "executed",
                "linked_trade_id": "TRD-ABC12345",
            },
            {
                "decision_id": "DEC-SEEN003",
                "news_id": "news_seen_old",
                "ticker": "TSLA",
                "timestamp": "2026-08-25T09:30:00-04:00",
                "ai_signal": "SKIP",
                "ai_confidence": 0.40,
                "decision_result": "rejected",
                "linked_trade_id": None,
            },
        ])

    def save_entry(self, entry):
        self.entries.append(entry)
        return len(self.entries)

class FakeBotState:
    def __init__(self, consecutive_api_fails: int = 0):
        self.data = {
            "bot_status": "ACTIVE",
            "consecutive_api_fails": consecutive_api_fails,
            "last_crash_check": None,
        }

    def add_api_strike(self) -> int:
        self.data["consecutive_api_fails"] += 1
        self.data["last_crash_check"] = datetime.now().isoformat()
        return self.data["consecutive_api_fails"]

    def reset_api_strikes(self) -> bool:
        self.data["consecutive_api_fails"] = 0
        return True

    def is_blind(self) -> bool:
        return self.data["consecutive_api_fails"] >= 3

class FakeMemory:
    def __init__(self):
        self.saved_entries = []
        self.sell_updates = []

    def update_memory_sell(self, ticker, database_id, decision, macro_state):
        entry = {
            "ticker": ticker,
            "database_id": database_id,
            "decision": decision,
            "macro_state": macro_state,
        }

        self.sell_updates.append(entry)

        return {
            "status": "success",
            "message": "Fake memory updated.",
            "data": entry,
        }
    
    def vectorize_string(self, text):
        return text.split()

    def search_memory(self, ticker, vector):
        return []

    def format_memory_for_prompt(self, results, max_distance=0.6):
        return ""

    def save_memory(self, ticker, database_id, text, vector_array, macro_state, ai_decision):
        entry = {
            "ticker": ticker,
            "database_id": database_id,
            "text": text,
            "vector_array": vector_array,
            "macro_state": macro_state,
            "ai_decision": ai_decision,
        }

        self.saved_entries.append(entry)

        return {
            "status": "success",
            "message": f"Fake memory saved for {ticker}.",
            "data": entry,
        }

class FakeBroker:
    def __init__(self):
        self.mode = "local_sim"

        self.wallet = SimpleNamespace(
            get_balance=lambda: {
                "status": "success",
                "data": {
                    "equity": 10000.0
                }
            }
        )

    def buy(self,
            ticker: None,
            invest_amount: None,
            buy_reason: None,
            news_id: None,
            decision_id: None,
            ai_confidence: None,
            stop_loss_pct: None,
            take_profit_pct: None):

        return {
            "status": "success",
            "message": f"Fake bought {ticker}",
            "data": {
                "trade_id": "TRD-FAKE001",
                "decision_id": decision_id,
                "news_id": news_id,
                "ticker": ticker,
                "buy_price": 100.0,
                "shares": invest_amount / 100.0 if invest_amount else 0,
                "buy_reason": buy_reason,
                "ai_confidence": ai_confidence,
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct
            },
        }

class FakeDossier:
    def get(self, ticker):
        return f"This is a fake dossier for the ticker {ticker}"

class FakeSettings:
    def __init__(self, overrides=None):
        self.settings = {
            # Core bot settings
            "LLM_model": "deepseek-r1",
            "trading_mode": "local_sim",

            # News source toggles
            "Yahoo bot": True,
            "Bloomberg bot": True,
            "EDGAR bot": True,
            "Forbes bot": True,

            # Trade sizing / exits
            "trade_risk_per_trade_pct": 0.005,
            "trade_target_gain_pct": 0.05,
            "trade_stop_loss_pct": 0.03,

            # Useful risk defaults
            "max_open_positions": 10,
            "max_daily_buys": 5,
            "max_total_exposure_pct": 0.50,
            "max_single_ticker_exposure_pct": 0.10,

            # Strategy metadata
            "strategy_version": "test-v1",

            # Risk guard-ish defaults
            "panic_mode": False,
            "allow_new_buys": True,
            "market_crash_protection": True,
            "economic_calendar_protection": False,
            "panic_assets_protection": False,
        }

        if overrides:
            self.settings.update(overrides)

    def _load_settings(self):
        return self.settings

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        return {
            "status": "success",
            "message": f"Set {key} to {value}.",
            "data": {
                "key": key,
                "value": value,
            },
        }

    def save_settings(self):
        return {
            "status": "success",
            "message": "Fake settings saved.",
            "data": self.settings,
        }

now_utc = pd.Timestamp.now(tz="UTC")

test_news_df = pd.DataFrame([
    # ✅ Must pass: recent, not seen, ISO date
    {
        "id": "news_fresh_001",
        "title": "Apple announces stronger iPhone demand",
        "summary": "Analysts raise revenue expectations after supplier checks.",
        "ticker": "AAPL",
        "date": (now_utc - pd.Timedelta(hours=2)).isoformat(),
        "Source": "Yahoo",
    },

    # ❌ Must fail: already in FakeAILogger.seen_ids
    {
        "id": "news_seen_001",
        "title": "Apple expands AI features",
        "summary": "The company announced new on-device AI tools.",
        "ticker": "AAPL",
        "date": (now_utc - pd.Timedelta(hours=3)).isoformat(),
        "Source": "Yahoo",
    },

    # ❌ Must fail: old
    {
        "id": "news_old_001",
        "title": "Tesla delivered quarterly vehicles",
        "summary": "Old delivery report from several days ago.",
        "ticker": "TSLA",
        "date": (now_utc - pd.Timedelta(days=4)).isoformat(),
        "Source": "Bloomberg",
    },

    # ✅ Must pass: recent, not seen, format type Bloomberg/RSS
    {
        "id": "news_fresh_002",
        "title": "Nvidia rises after stronger data center outlook",
        "summary": "Investors react positively to AI infrastructure demand.",
        "ticker": "NVDA",
        "date": (now_utc - pd.Timedelta(hours=5)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "Source": "Bloomberg",
    },

    # ❌ Must fail: invalid date
    {
        "id": "news_bad_date",
        "title": "Bad date example",
        "summary": "This should be removed by date parsing.",
        "ticker": "META",
        "date": "not a real date",
        "Source": "Forbes",
    },

    # ❌ Must fail: already seen even if it's recent
    {
        "id": "news_seen_002",
        "title": "Microsoft announces new cloud contract",
        "summary": "This is recent but already processed by the AI logger.",
        "ticker": "MSFT",
        "date": (now_utc - pd.Timedelta(hours=1)).isoformat(),
        "Source": "Forbes",
    },

    # ❌ Must fail: old EDGAR
    {
        "id": "edgar_old_001",
        "title": "10-Q",
        "summary": "old_document.htm",
        "ticker": "AMZN",
        "date": (now_utc - pd.Timedelta(days=10)).date().isoformat(),
        "Source": "EDGAR",
    },
])

def make_trade_analyzer(news_df=None):
    analyzer = TradeAnalyzer.__new__(TradeAnalyzer)

    analyzer.ai_logger = FakeAILogger()
    analyzer.settings_dict = FakeSettings()._load_settings()
    analyzer.yahoo_db_path = "fake"
    analyzer.bloomberg_db_path = "fake"
    analyzer.edgar_db_path = "fake"
    analyzer.forbes_db_path = "fake"
    analyzer.fresh_news = pd.DataFrame()
    analyzer.seen_ids = analyzer._load_seen_news_ids()

    if news_df is None:
        news_df = test_news_df

    def fake_read_news_source(*, db_path, source, query, params):
        return news_df[news_df["Source"] == source].copy()

    analyzer._read_news_source = fake_read_news_source

    return analyzer

# ------------------------------------------------------------
# Test test_process_unred_news_filters_seen_old_and_bad_dates
# ------------------------------------------------------------

def test_process_unred_news_filters_seen_old_and_bad_dates():
    analyzer = make_trade_analyzer()

    fresh_news = analyzer._process_unred_news()

    assert set(fresh_news["id"]) == {"news_fresh_001", "news_fresh_002"}
    assert fresh_news["date_utc"].notna().all()
    assert (fresh_news["date_utc"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=24)).all()


# ----------------------------------------------
# Test test_process_unred_news_removes_seen_ids
# ----------------------------------------------

def test_process_unred_news_removes_seen_ids():
    analyzer = make_trade_analyzer()

    fresh_news = analyzer._process_unred_news()

    assert "news_seen_001" not in set(fresh_news["id"])
    assert "news_seen_002" not in set(fresh_news["id"])


# -----------------------------------------------
# Test test_process_unread_news_filters_old_news
# -----------------------------------------------

def test_process_unread_news_filters_old_news():
    analyzer = make_trade_analyzer()

    fresh_news = analyzer._process_unred_news()

    assert "edgar_old_001" not in set(fresh_news["id"])
    assert "news_old_001" not in set(fresh_news["id"])

# -----------------------------------------------
# Test test_process_unred_news_removes_bad_dates
# -----------------------------------------------

def test_process_unred_news_removes_bad_dates():
    analyzer = make_trade_analyzer()

    fresh_news = analyzer._process_unred_news()

    assert "news_bad_date" not in set(fresh_news["id"])


# --------------------------------------------
# Test test_load_seen_news_ids_from_ai_logger
# --------------------------------------------

def test_load_seen_news_ids_from_ai_logger():
    analyzer = make_trade_analyzer()

    news_ids = ["news_seen_001", "news_seen_002", "news_seen_old"]

    assert analyzer.seen_ids == set(news_ids)


# ----------------------------------------------
# Test test_process_unred_news_updates_seen_ids
# ----------------------------------------------


def test_process_unred_news_updates_seen_ids():
    analyzer = make_trade_analyzer()

    analyzer._process_unred_news()

    assert "news_fresh_001" in analyzer.seen_ids
    assert "news_fresh_002" in analyzer.seen_ids


# -----------------------------------------------------------
# Test test_process_unred_news_is_idempotent_in_same_runtime
# -----------------------------------------------------------

def test_process_unred_news_is_idempotent_in_same_runtime():
    analyzer = make_trade_analyzer()

    first_news_pull = analyzer._process_unred_news()
    second_news_pull = analyzer._process_unred_news()

    assert set(first_news_pull["id"]) == {"news_fresh_001", "news_fresh_002"}
    assert second_news_pull.empty == True

# --------------------------------------------------------
# Test test_process_unred_news_keeps_news_within_24_hours
# --------------------------------------------------------

def test_process_unred_news_keeps_news_within_24_hours():
    edge_news = pd.DataFrame([{
        "id": "news_almost_24h",
        "title": "Borderline fresh news",
        "summary": "This should still pass.",
        "ticker": "GOOG",
        "date": (now_utc - pd.Timedelta(hours=23)).isoformat(),
        "Source": "Yahoo",
    }])

    news_df = pd.concat([test_news_df, edge_news], ignore_index=True)

    analyzer = make_trade_analyzer(news_df=news_df)

    fresh_news = analyzer._process_unred_news()

    assert "news_almost_24h" in set(fresh_news["id"])

