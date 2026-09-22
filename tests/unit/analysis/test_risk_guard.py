from backend.analysis.risk_guard import RiskGuard

from datetime import datetime
from typing import Tuple

import pandas as pd

# -------------------
# Helpers
# -------------------

def make_hist(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": closes},
        index=pd.date_range("2026-07-20", periods=len(closes), freq="D"),
    )


def make_risk_settings(**overrides) -> dict:
    settings = {
        "cb_spy_hard_stop": -1.75,
        "cb_vix_high": 28.0,
        "cb_vix_spike": 10.0,
        "cb_tnx_spike": 2.5,
        "cb_breadth_drop": -1.0,
        "cb_min_warning_score": 3,
        "gold_spike": 1.5,
        "oil_spike": 2.5,
        "fmp_api_key": "",
        "cb_macro_buffer_minutes": 45,
    }

    settings.update(overrides)
    return settings


def make_market_snapshot(**overrides) -> dict:
    snapshot = {
        "SPY": {
            "closes": [500.0, 501.0],
            "change_pct": 0.20,
        },
        "QQQ": {
            "closes": [400.0, 401.0],
            "change_pct": 0.25,
        },
        "IWM": {
            "closes": [200.0, 201.0],
            "change_pct": 0.50,
        },
        "^VIX": {
            "closes": [15.0, 16.0],
            "change_pct": 1.00,
        },
        "^TNX": {
            "closes": [42.0, 42.2],
            "change_pct": 0.40,
        },
    }

    snapshot.update(overrides)
    return snapshot


def make_macro_warning_market_snapshot():
    return make_market_snapshot(
        SPY={
            "closes": [500.0, 496.0],
            "change_pct": -0.80,
        },
        QQQ={
            "closes": [400.0, 395.0],
            "change_pct": -1.25,
        },
        IWM={
            "closes": [200.0, 198.98],
            "change_pct": -0.51,
        },
        **{
            "^VIX": {
                "closes": [21.0, 23.0],
                "change_pct": 9.00,
            },
            "^TNX": {
                "closes": [42.0, 42.2],
                "change_pct": 0.40,
            },
        },
    )


def make_high_vix_market_snapshot() -> dict:
    return make_market_snapshot(
        SPY={
            "closes": [500.0, 498.0],
            "change_pct": -0.40,
        },
        **{
            "^VIX": {
                "closes": [27.0, 30.0],
                "change_pct": 8.00,
            },
        },
    )


def make_warning_score_market_snapshot() -> dict:
    return make_market_snapshot(
        SPY={
            "closes": [500.0, 496.0],
            "change_pct": -0.80,
        },
        QQQ={
            "closes": [400.0, 395.0],
            "change_pct": -1.25,
        },
        IWM={
            "closes": [200.0, 197.0],
            "change_pct": -1.50,
        },
        **{
            "^VIX": {
                "closes": [21.0, 23.0],
                "change_pct": 9.00,
            },
        },
    )


def make_panic_asset_df(open_price: float, close_price: float):
    return pd.DataFrame(
        {
            "Open": [open_price],
            "Close": [close_price],
        }
    )

# -------------------
# Fake Market Data
# -------------------

class FakeMarketData:
    def __init__(self, market_snapshot: dict | None = None):
        self.market_snapshot = market_snapshot or make_market_snapshot()
        self.calls = []

    def get_change_and_history(
        self,
        index: str,
        period: str = "10d",
    ) -> Tuple[pd.DataFrame | None, float | None]:
        self.calls.append(
            {
                "index": index,
                "period": period,
            }
        )

        data = self.market_snapshot.get(index)

        if data is None:
            return None, None

        hist = make_hist(data["closes"])
        pct_change = data["change_pct"]

        return hist, pct_change


class BrokenMarketData:
    def get_change_and_history(
        self,
        index: str,
        period: str = "10d",
    ) -> Tuple[pd.DataFrame | None, float | None]:
        raise RuntimeError("Fake market data failure.")


# -------------------
# Fake Bot State
# -------------------

class FakeBotState:
    def __init__(self, consecutive_api_fails: int = 0):
        self.default_state = {
            "bot_status": "ACTIVE",
            "consecutive_api_fails": consecutive_api_fails,
            "last_crash_check": None,
        }

    def add_api_strike(self) -> int:
        self.default_state["consecutive_api_fails"] += 1
        self.default_state["last_crash_check"] = datetime.now().isoformat()
        return self.default_state["consecutive_api_fails"]

    def reset_api_strikes(self) -> bool:
        self.default_state["consecutive_api_fails"] = 0
        return True

    def is_blind(self) -> bool:
        return self.default_state["consecutive_api_fails"] >= 3


# -------------------
# Factory
# -------------------

def make_risk_guard(
    market_snapshot: dict | None = None,
    bot_state: FakeBotState | None = None,
) -> RiskGuard:
    market_data = FakeMarketData(market_snapshot)
    bot_state = bot_state or FakeBotState()

    return RiskGuard(
        market_data=market_data,
        bot_state=bot_state,
    )


def disable_external_risk_checks(risk_guard: RiskGuard) -> None:
    risk_guard._check_panic_assets = lambda settings: {
        "rejected": False,
        "risk_level": "LOW",
        "reason": None,
    }

    risk_guard._check_economic_calendar = lambda settings: {
        "rejected": False,
        "risk_level": "LOW",
        "reason": None,
    }


# ---------------------------------
# Test _is_market_crashing_ Normal
# ---------------------------------

def test_risk_guard_allows_trading_when_market_is_normal():

    normal_market = make_market_snapshot()

    risk_guard = make_risk_guard(
        normal_market,
    )

    settings_dict = make_risk_settings()

    normal_result = risk_guard._is_market_crashing(settings_dict)

    assert normal_result["rejected"] is False
    assert normal_result["risk_level"] == "LOW"
    assert normal_result["reason"] is None

# -----------------------------------------
# Test _is_market_crashing_ SPY Hard Stop
# -----------------------------------------

def test_risk_guard_blocks_trading_when_spy_hits_hard_stop():

    spy_hard_stop = make_market_snapshot(
        SPY={
            "closes": [500, 400],
            "change_pct": -2.00,
        },
    )

    risk_guard = make_risk_guard(
        spy_hard_stop,
    )

    settings_dict = make_risk_settings()

    result = risk_guard._is_market_crashing(settings_dict)

    assert result["rejected"] is True
    assert result["risk_level"] == "HIGH"
    assert "SPY hard stop triggered" in result["reason"]
    assert "-2.00%" in result["reason"]


# ---------------------------------------------
# Test _is_market_crashing_ VIX level reached
# ---------------------------------------------

def test_risk_guard_blocks_trading_when_VIX_is_above_established_level():

    vix_stop = make_high_vix_market_snapshot()

    risk_guard = make_risk_guard(
        vix_stop,
    )

    settings_dict = make_risk_settings()

    result = risk_guard._is_market_crashing(settings_dict)

    assert result["rejected"] is True
    assert result["risk_level"] == "HIGH"
    assert "VIX elevated" in result["reason"]
    assert "30.00" in result["reason"]


# -----------------------------------------------------
# Test _is_market_crashing_ general market is crashing
# -----------------------------------------------------

def test_risk_guard_blocks_trading_when_the_general_market_is_crashing():

    market_crashing = make_macro_warning_market_snapshot()

    risk_guard = make_risk_guard(
        market_crashing,
    )

    settings_dict = make_risk_settings()

    result = risk_guard._is_market_crashing(settings_dict)

    assert result["rejected"] is True
    assert result["risk_level"] == "HIGH"
    assert "Macro warning score" in result["reason"]
    assert "4" in result["reason"]


# -----------------------------------
# Test _check_panic_assets high peak
# -----------------------------------

def test_risk_guard_blocks_when_panic_assets_spike(monkeypatch):
    risk_guard = make_risk_guard()
    settings = make_risk_settings(
        gold_spike=1.5,
        oil_spike=2.5,
    )

    def fake_download(ticker, period, interval, progress):
        if ticker == "GC=F":
            return make_panic_asset_df(open_price=100.0, close_price=102.0)  # +2%
        if ticker == "CL=F":
            return make_panic_asset_df(open_price=100.0, close_price=100.5)  # +0.5%

        raise ValueError(f"Unexpected ticker: {ticker}")

    monkeypatch.setattr("backend.analysis.risk_guard.yf.download", fake_download)

    result = risk_guard._check_panic_assets(settings)

    assert result["rejected"] is True
    assert result["risk_level"] == "HIGH"
    assert "Panic assets spike" in result["reason"]
    assert "gold=+2.00%" in result["reason"]


# -----------------------------------
# Test _check_panic_assets normal
# -----------------------------------

def test_risk_guard_allows_when_panic_assets_are_normal(monkeypatch):
    risk_guard = make_risk_guard()
    settings = make_risk_settings()

    def fake_download(ticker, period, interval, progress):
        if ticker == "GC=F":
            return make_panic_asset_df(open_price=100.0, close_price=100.5)
        if ticker == "CL=F":
            return make_panic_asset_df(open_price=100.0, close_price=101.0)

        raise ValueError(f"Unexpected ticker: {ticker}")

    monkeypatch.setattr("backend.analysis.risk_guard.yf.download", fake_download)

    result = risk_guard._check_panic_assets(settings)

    assert result["rejected"] is False
    assert result["risk_level"] == "LOW"
    assert result["reason"] is None


# -----------------------------------
# Test _check_economic_calendar when event is nearby
# -----------------------------------

def test_economic_calendar_blocks_when_high_impact_event_is_nearby(monkeypatch):
    risk_guard = make_risk_guard()
    monkeypatch.setattr(
        "backend.analysis.risk_guard.get_env",
        lambda name, default="": "fake_key" if name == "FMP_API_KEY" else default,
    )

    settings = make_risk_settings(
        fmp_api_key="fake_key",
        cb_macro_buffer_minutes=45,
    )
    class FakeResponse:
        status_code = 200

        def json(self):
            return [
                {
                    "country": "US",
                    "impact": "High",
                    "date": "2026-07-20 09:00:00",
                    "event": "CPI Inflation Rate",
                }
            ]

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr("backend.analysis.risk_guard.requests.get", fake_get)

    from datetime import datetime as RealDateTime

    class FrozenDateTime(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            naive_now = RealDateTime(2026, 7, 20, 8, 45, 0)

            if tz is not None:
                return tz.localize(naive_now)

            return naive_now

    monkeypatch.setattr("backend.analysis.risk_guard.datetime", FrozenDateTime)

    result = risk_guard._check_economic_calendar(settings)

    assert result["rejected"] is True
    assert result["risk_level"] == "HIGH"
    assert "High-impact macro event nearby" in result["reason"]
    assert "CPI Inflation Rate" in result["reason"]



# ------------------------------------------------
# Test _check_economic_calendar When event is far
# ------------------------------------------------

def test_economic_calendar_allows_when_event_is_outside_buffer(monkeypatch):
    risk_guard = make_risk_guard()
    monkeypatch.setattr(
        "backend.analysis.risk_guard.get_env",
        lambda name, default="": "fake_key" if name == "FMP_API_KEY" else default,
    )

    settings = make_risk_settings(
        fmp_api_key="fake_key",
        cb_macro_buffer_minutes=45,
    )
    class FakeResponse:
        status_code = 200

        def json(self):
            return [
                {
                    "country": "US",
                    "impact": "High",
                    "date": "2026-07-20 10:00:00",
                    "event": "CPI Inflation Rate",
                }
            ]

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr("backend.analysis.risk_guard.requests.get", fake_get)

    from datetime import datetime as RealDateTime

    class FrozenDateTime(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            naive_now = RealDateTime(2026, 7, 20, 8, 45, 0)

            if tz is not None:
                return tz.localize(naive_now)

            return naive_now

    monkeypatch.setattr("backend.analysis.risk_guard.datetime", FrozenDateTime)

    result = risk_guard._check_economic_calendar(settings)

    assert result["rejected"] is False
    assert result["risk_level"] == "LOW"
    assert result["reason"] is None

