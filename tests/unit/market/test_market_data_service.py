from backend.market.market_data import MarketDataService

import pytest
import pandas as pd

# -----------------
# Helpers
# -----------------


def make_hist(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": closes},
        index=pd.date_range("2026-07-20", periods=len(closes), freq="D"),
    )


def make_index_histories():
    return {
        "SPY": make_hist([500.0, 550.0]),    # +10.00%
        "QQQ": make_hist([400.0, 420.0]),    # +5.00%
        "IWM": make_hist([200.0, 190.0]),    # -5.00%
        "^VIX": make_hist([20.0, 25.0]),     # +25.00%
        "^TNX": make_hist([40.0, 42.0]),     # +5.00%
    }

def make_ticker_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [
                500, 505, 508, 510, 512,
                515, 518, 520, 522, 525,
                528, 530, 535, 540, 545,
                550, 555, 560, 570, 600,
            ],
            "High": [
                510, 512, 515, 518, 520,
                523, 526, 528, 530, 533,
                536, 538, 543, 548, 553,
                558, 563, 568, 578, 626,
            ],
            "Low": [
                490, 498, 500, 503, 505,
                508, 511, 513, 515, 518,
                521, 523, 528, 533, 538,
                543, 548, 553, 563, 575,
            ],
            "Volume": [
                1000, 1050, 1100, 1080, 1120,
                1150, 1180, 1190, 1210, 1230,
                1250, 1280, 1300, 1320, 1350,
                1380, 1400, 1450, 1500, 1600,
            ],
        },
        index=pd.date_range("2026-07-01", periods=20, freq="D"),
    )

# -----------------------
# Test get_current_price
# -----------------------

def test_get_current_price(monkeypatch):
    market_data = MarketDataService()

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker
            self.fast_info = {
                "last_price": 500
            }

    monkeypatch.setattr("backend.market.market_data.yf.Ticker", FakeTicker)

    price = market_data.get_current_price("MSFT")

    assert price == pytest.approx(500)

# ----------------------------
# Test get_change_and_history
# ----------------------------

def test_get_change_and_history(monkeypatch):
    market_data = MarketDataService()

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, period, *args, **kwargs):
            return pd.DataFrame({
                    "Close": [550, 600],
                })

    monkeypatch.setattr("backend.market.market_data.yf.Ticker", FakeTicker)

    hist, pct_change = market_data.get_change_and_history("MSFT")

    assert isinstance(hist, pd.DataFrame)

    assert pct_change == pytest.approx(9.09, rel=1e-2)



# --------------------
# Test index_snapshot
# --------------------

def test_index_snapshot(monkeypatch):
    market_data = MarketDataService()

    class FakeTicker:
        histories = make_index_histories()

        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, period, *args, **kwargs):
            return self.histories[self.ticker]

    monkeypatch.setattr("backend.market.market_data.yf.Ticker", FakeTicker)

    snapshot = market_data.get_index_snapshot()

    assert snapshot["sp500_trend_pct"] == pytest.approx(10.0)
    assert snapshot["tech_trend_pct"] == pytest.approx(5.0)
    assert snapshot["smallcap_trend_pct"] == pytest.approx(-5.0)
    assert snapshot["vix_level"] == pytest.approx(25.0)
    assert snapshot["vix_trend_pct"] == pytest.approx(25.0)
    assert snapshot["interest_rate"] == pytest.approx(42.0)
    assert snapshot["rates_trend_pct"] == pytest.approx(5.0)


# ----------------------------------
# Test get_ticker_decision_features
# ----------------------------------

def test_get_ticker_decision_features(monkeypatch):
    market_data = MarketDataService()

    class FakeTicker:
            def __init__(self, ticker):
                self.ticker = ticker
    
            def history(self, period, *args, **kwargs):
                return make_ticker_history()

    monkeypatch.setattr("backend.market.market_data.yf.Ticker", FakeTicker)

    features = market_data.get_ticker_decision_features("MSFT")

    assert isinstance(features, dict)
    assert features["price_at_decision"] == pytest.approx(600)
    assert features["day_change_pct"] == pytest.approx((600 - 570) / 570 * 100)
    assert features["volume"] == pytest.approx(1600)
    assert features["rsi_14"] is not None
    assert features["atr_14"] is not None
    assert features["relative_volume"] is not None

# -----------------------------------------------------
# Test get_ticker_decision_features with empty history
# -----------------------------------------------------


def test_get_ticker_decision_features_handles_empty_history(monkeypatch):
    market_data = MarketDataService()

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, period, *args, **kwargs):
            return pd.DataFrame(columns=["Close", "High", "Low", "Volume"])

    monkeypatch.setattr("backend.market.market_data.yf.Ticker", FakeTicker)

    features = market_data.get_ticker_decision_features("MSFT")

    assert isinstance(features, dict)

    assert features["price_at_decision"] is None
    assert features["day_change_pct"] is None
    assert features["volume"] is None
    assert features["relative_volume"] is None
    assert features["rsi_14"] is None
    assert features["atr_14"] is None

# -------------------
# Test calculate_rsi
# -------------------

def test_calculate_rsi():
    market_data = MarketDataService()

    closes = make_ticker_history()["Close"]

    rsi = market_data.calculate_rsi(closes)

    assert rsi == pytest.approx(100.0)


# -------------------
# Test calculate_atr
# -------------------

def test_calculate_atr():
    market_data = MarketDataService()

    ticker_history = make_ticker_history()

    closes = ticker_history["Close"]
    highs = ticker_history["High"]
    lows = ticker_history["Low"]

    atr = market_data.calculate_atr(high=highs,
                                    low=lows,
                                    close=closes
                                    )

    assert atr == pytest.approx(18.14, rel=1e-2)