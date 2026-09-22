"""Risk guard for market-wide buy halts."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pytz
import requests
import yfinance as yf

from backend.market.market_data import MarketDataService
from backend.config.environment import get_env

logger = logging.getLogger(__name__)


class RiskGuard:
    """Evaluates conditions that should halt new buy decisions."""

    def __init__(self, market_data: MarketDataService, bot_state: Any):
        self.market_data = market_data
        self.bot_state = bot_state

    def evaluate_global_buy_halt(self, settings: dict) -> dict:
        """Return a risk decision for whether new buys should be halted."""
        checks = [
            self._check_panic_assets(settings),
            self._check_economic_calendar(settings),
            self._is_market_crashing(settings),
        ]
        for result in checks:
            if result["rejected"]:
                return result
        return {"rejected": False, "risk_level": "LOW", "reason": None}

    def _is_market_crashing(self, settings: dict) -> dict:
        spy_hard_stop = settings.get("cb_spy_hard_stop", -1.75)
        vix_high = settings.get("cb_vix_high", 28.0)
        vix_spike = settings.get("cb_vix_spike", 10.0)
        tnx_spike = settings.get("cb_tnx_spike", 2.5)
        breadth_drop = settings.get("cb_breadth_drop", -1.0)
        min_warning_score = settings.get("cb_min_warning_score", 3)

        try:
            spy_hist, spy_change = self.market_data.get_change_and_history("SPY", period="10d")
            _, qqq_change = self.market_data.get_change_and_history("QQQ", period="10d")
            _, iwm_change = self.market_data.get_change_and_history("IWM", period="10d")
            vix_hist, vix_change = self.market_data.get_change_and_history("^VIX", period="10d")
            _, tnx_change = self.market_data.get_change_and_history("^TNX", period="10d")

            if spy_hist is None or spy_change is None:
                logger.warning("SPY data unavailable. Halting buys for safety.")
                return {"rejected": True, "risk_level": "HIGH", "reason": "SPY data unavailable"}

            if spy_change <= spy_hard_stop:
                reason = f"SPY hard stop triggered: {spy_change:.2f}%"
                logger.warning(reason)
                return {"rejected": True, "risk_level": "HIGH", "reason": reason}

            if hasattr(self.bot_state, "reset_api_strikes"):
                self.bot_state.reset_api_strikes()

            if vix_hist is not None:
                vix_level = float(vix_hist["Close"].iloc[-1])
                if vix_level >= vix_high and spy_change < 0:
                    reason = f"VIX elevated at {vix_level:.2f} with market weakness"
                    logger.warning(reason)
                    return {"rejected": True, "risk_level": "HIGH", "reason": reason}

            warning_score = 0
            if spy_change <= -0.75:
                warning_score += 1
            if qqq_change is not None and qqq_change <= breadth_drop:
                warning_score += 1
            if iwm_change is not None and iwm_change <= breadth_drop:
                warning_score += 1
            if vix_hist is not None:
                vix_level = float(vix_hist["Close"].iloc[-1])
                if vix_level >= 22:
                    warning_score += 1
                if vix_change is not None and vix_change >= vix_spike:
                    warning_score += 1
            if tnx_change is not None and tnx_change >= tnx_spike:
                warning_score += 1
            if (
                qqq_change is not None and iwm_change is not None and
                spy_change < -0.3 and qqq_change < -0.5 and iwm_change < -0.5
            ):
                warning_score += 1

            if warning_score >= min_warning_score:
                reason = f"Macro warning score={warning_score}. Halting buys."
                logger.warning(reason)
                return {"rejected": True, "risk_level": "HIGH", "reason": reason}

            return {"rejected": False, "risk_level": "LOW", "reason": None}

        except Exception:
            logger.exception("Failed to evaluate market crash guard. Halting buys defensively.")
            if hasattr(self.bot_state, "is_blind") and self.bot_state.is_blind():
                return {"rejected": True, "risk_level": "HIGH", "reason": "Market data blind mode"}
            if hasattr(self.bot_state, "add_api_strike"):
                self.bot_state.add_api_strike()
            return {"rejected": True, "risk_level": "HIGH", "reason": "Market crash guard error"}

    def _check_panic_assets(self, settings: dict) -> dict:
        gold_spike_limit = settings.get("gold_spike", 1.5)
        oil_spike_limit = settings.get("oil_spike", 2.5)

        try:
            gold = yf.download("GC=F", period="1d", interval="15m", progress=False)
            oil = yf.download("CL=F", period="1d", interval="15m", progress=False)

            if gold.empty or oil.empty:
                return {"rejected": False, "risk_level": "LOW", "reason": None}

            gold_open = float(gold["Open"].iloc[0].item())
            gold_current = float(gold["Close"].iloc[-1].item())
            oil_open = float(oil["Open"].iloc[0].item())
            oil_current = float(oil["Close"].iloc[-1].item())

            gold_spike_pct = ((gold_current - gold_open) / gold_open) * 100 if gold_open else 0
            oil_spike_pct = ((oil_current - oil_open) / oil_open) * 100 if oil_open else 0

            if gold_spike_pct >= gold_spike_limit or oil_spike_pct >= oil_spike_limit:
                reason = f"Panic assets spike: gold={gold_spike_pct:+.2f}%, oil={oil_spike_pct:+.2f}%"
                logger.warning(reason)
                return {"rejected": True, "risk_level": "HIGH", "reason": reason}

            return {"rejected": False, "risk_level": "LOW", "reason": None}

        except Exception:
            logger.exception("Failed to evaluate panic assets guard.")
            return {"rejected": False, "risk_level": "MEDIUM", "reason": "Panic assets check failed"}

    def _check_economic_calendar(self, settings: dict) -> dict:
        api_key = get_env("FMP_API_KEY", "")
        if not api_key:
            logger.warning("FMP API key not configured. Economic calendar guard disabled.")
            return {"rejected": False, "risk_level": "LOW", "reason": None}

        buffer_minutes = settings.get("cb_macro_buffer_minutes", 45)

        try:
            ny_tz = pytz.timezone("America/New_York")
            now_ny = datetime.now(ny_tz)
            today = now_ny.strftime("%Y-%m-%d")

            url = (
                "https://financialmodelingprep.com/api/v3/economic_calendar"
                f"?from={today}&to={today}&apikey={api_key}"
            )
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                logger.error("Economic calendar API returned status %s.", response.status_code)
                return {"rejected": False, "risk_level": "MEDIUM", "reason": "Economic calendar API error"}

            for event in response.json():
                if event.get("country") != "US" or event.get("impact") != "High":
                    continue

                event_time_raw = event.get("date")
                if not event_time_raw:
                    continue

                event_time = datetime.strptime(event_time_raw, "%Y-%m-%d %H:%M:%S")
                event_time = ny_tz.localize(event_time)
                block_start = event_time - timedelta(minutes=buffer_minutes)
                block_end = event_time + timedelta(minutes=15)

                if block_start <= now_ny <= block_end:
                    reason = f"High-impact macro event nearby: {event.get('event')}"
                    logger.warning(reason)
                    return {"rejected": True, "risk_level": "HIGH", "reason": reason}

            return {"rejected": False, "risk_level": "LOW", "reason": None}

        except Exception:
            logger.exception("Failed to evaluate economic calendar guard.")
            return {"rejected": False, "risk_level": "MEDIUM", "reason": "Economic calendar check failed"}
