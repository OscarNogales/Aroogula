"""Builds normalized AI decision log contexts."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pandas as pd
import pytz

from backend.market.market_data import MarketDataService


class DecisionContextBuilder:
    """Collects all stable context fields before FinBERT/LLM decisions."""

    def __init__(self, market_data: MarketDataService):
        self.market_data = market_data
        self.ny_tz = pytz.timezone("America/New_York")

    def build(self, *, news_row: pd.Series | dict, risk_profile: dict, settings: dict) -> dict:
        ticker = str(news_row.get("ticker", "")).upper()
        title = news_row.get("title")
        summary = news_row.get("summary")
        news_id = str(news_row.get("id"))
        news_source = news_row.get("Source") or news_row.get("source")
        news_date = news_row.get("date")

        market_indices = self.market_data.get_index_snapshot()
        ticker_features = self.market_data.get_ticker_decision_features(ticker)

        timestamp = datetime.now().isoformat(timespec="seconds")

        return {
            "decision_id": self.new_decision_id(),
            "news_id": news_id,
            "ticker": ticker,
            "timestamp": timestamp,
            "news_source": news_source,
            "news_title": title,
            "news_age_minutes": self._news_age_minutes(news_date),
            "macro_regime": risk_profile.get("REGIME"),
            "market_session": self.get_market_session(),
            "market_is_open": int(self.is_market_open()),
            "sp500_trend_pct": market_indices.get("sp500_trend_pct"),
            "nasdaq_trend_pct": market_indices.get("tech_trend_pct"),
            "vix_level": market_indices.get("vix_level"),
            "price_at_decision": ticker_features.get("price_at_decision"),
            "day_change_pct": ticker_features.get("day_change_pct"),
            "volume": ticker_features.get("volume"),
            "relative_volume": ticker_features.get("relative_volume"),
            "rsi_14": ticker_features.get("rsi_14"),
            "atr_14": ticker_features.get("atr_14"),
            "strategy_version": settings.get("strategy_version", "v1"),
            "prompt_version": settings.get("prompt_version", "v1"),
            "model_version": settings.get("LLM_model"),
        }

    @staticmethod
    def new_decision_id() -> str:
        return f"dec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

    def get_market_session(self) -> str:
        now = datetime.now(self.ny_tz)
        open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
        close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)

        if now < open_time:
            return "premarket"
        if now <= close_time:
            return "regular"
        return "afterhours"

    def is_market_open(self) -> bool:
        now = datetime.now(self.ny_tz)
        if now.weekday() >= 5:
            return False
        open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
        close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return open_time <= now <= close_time

    def _news_age_minutes(self, news_date) -> float | None:
        if news_date is None or pd.isna(news_date):
            return None
        try:
            parsed = pd.to_datetime(news_date)
            if parsed.tzinfo is None:
                parsed = self.ny_tz.localize(parsed.to_pydatetime())
            else:
                parsed = parsed.to_pydatetime().astimezone(self.ny_tz)
            now = datetime.now(self.ny_tz)
            return round((now - parsed).total_seconds() / 60, 2)
        except Exception:
            return None
