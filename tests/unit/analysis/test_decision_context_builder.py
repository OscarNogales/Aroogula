from backend.analysis.decision_context import DecisionContextBuilder

import re
import pandas as pd
import pytest


# --------------
# Helpers
# --------------

def make_test_news_row(**overrides):
    news = {
        "ticker": "msft",
        "title": "TEST NEWS TITLE",
        "summary": "This is the test news row for pytest.",
        "id": "TEST_NEWS_001",
        "source": "Yahoo",
        "date": None,
    }

    news.update(overrides)
    return news


def make_settings_dict(**overrides):
    settings = {
        "strategy_version": "V1",
        "prompt_version": "V1",
        "LLM_model": "DeepSeek",
    }

    settings.update(overrides)
    return settings


def make_risk_profile(**overrides):
    risk_profile = {
        "REGIME": "MARKUP",
    }

    risk_profile.update(overrides)
    return risk_profile


def make_ticker_features(**overrides):
    features = {
        "price_at_decision": 600.0,
        "day_change_pct": 1.2,
        "volume": 1_600_000,
        "relative_volume": 1.1,
        "rsi_14": 55.0,
        "atr_14": 8.0,
    }

    features.update(overrides)
    return features


def make_index_snapshot(**overrides):
    snapshot = {
        "vix_level": 22.0,
        "interest_rate": 4.25,
        "vix_trend_pct": -3.5,
        "rates_trend_pct": 0.8,
        "sp500_trend_pct": 1.2,
        "tech_trend_pct": 1.8,
        "smallcap_trend_pct": 0.6,
    }

    snapshot.update(overrides)
    return snapshot


class FakeMarketData:
    def __init__(self):
        self.requested_tickers = []

    def get_index_snapshot(self):
        return make_index_snapshot()

    def get_ticker_decision_features(self, ticker):
        self.requested_tickers.append(ticker)
        return make_ticker_features()


# -----------
# Test build
# -----------

def test_build_returns_expected_context():
    news_row = make_test_news_row()
    settings = make_settings_dict()
    risk_profile = make_risk_profile()
    market_data = FakeMarketData()

    builder = DecisionContextBuilder(market_data)

    decision = builder.build(
        news_row=news_row,
        risk_profile=risk_profile,
        settings=settings,
    )

    assert isinstance(decision, dict)

    # Identity / news context
    assert decision["decision_id"].startswith("dec_")
    assert decision["news_id"] == "TEST_NEWS_001"
    assert decision["ticker"] == "MSFT"
    assert decision["news_source"] == "Yahoo"
    assert decision["news_title"] == "TEST NEWS TITLE"
    assert decision["news_age_minutes"] is None

    # Risk / session context
    assert decision["macro_regime"] == "MARKUP"
    assert decision["market_session"] in {"premarket", "regular", "afterhours"}
    assert decision["market_is_open"] in {0, 1}

    # Market index context
    assert decision["sp500_trend_pct"] == pytest.approx(1.2)
    assert decision["nasdaq_trend_pct"] == pytest.approx(1.8)
    assert decision["vix_level"] == pytest.approx(22.0)

    # Ticker decision features
    assert decision["price_at_decision"] == pytest.approx(600.0)
    assert decision["day_change_pct"] == pytest.approx(1.2)
    assert decision["volume"] == 1_600_000
    assert decision["relative_volume"] == pytest.approx(1.1)
    assert decision["rsi_14"] == pytest.approx(55.0)
    assert decision["atr_14"] == pytest.approx(8.0)

    # Versioning
    assert decision["strategy_version"] == "V1"
    assert decision["prompt_version"] == "V1"
    assert decision["model_version"] == "DeepSeek"

    # Verifies that build asks MarketDataService for the normalized ticker.
    assert market_data.requested_tickers == ["MSFT"]


# --------------------
# Test new_decision_id
# --------------------

def test_new_decision_id_is_unique_and_has_expected_format():
    id_1 = DecisionContextBuilder.new_decision_id()
    id_2 = DecisionContextBuilder.new_decision_id()

    assert id_1 != id_2
    assert re.fullmatch(r"dec_\d{8}_\d{6}_[a-f0-9]{8}", id_1)
    assert re.fullmatch(r"dec_\d{8}_\d{6}_[a-f0-9]{8}", id_2)


# ----------------------
# Test _news_age_minutes
# ----------------------

def test_news_age_minutes_returns_none_for_missing_or_invalid_date():
    builder = DecisionContextBuilder(market_data=None)

    assert builder._news_age_minutes(None) is None
    assert builder._news_age_minutes(pd.NaT) is None
    assert builder._news_age_minutes("not-a-real-date") is None


# -----------------------------------
# Test _news_age_minutes return none
# -----------------------------------
def test_news_age_minutes_returns_none_for_missing_date():
    builder = DecisionContextBuilder(market_data=None)

    result = builder._news_age_minutes(None)

    assert result is None
