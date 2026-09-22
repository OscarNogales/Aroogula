"""Market regime classifier for the trading bot."""

from __future__ import annotations

import logging

import pandas as pd

from backend.market.market_data import MarketDataService

logger = logging.getLogger(__name__)


RISK_PROFILES = {
    "MARKUP": {
        "REGIME": "MARKUP",
        "BUY_CONF": 0.65,
        "SELL_CONF": 0.85,
        "FINBERT_SENT": 0.50,
        "FINBERT_TRAD": 0.50,
    },
    "DISTRIBUTION": {
        "REGIME": "DISTRIBUTION",
        "BUY_CONF": 0.82,
        "SELL_CONF": 0.65,
        "FINBERT_SENT": 0.60,
        "FINBERT_TRAD": 0.60,
    },
    "MARKDOWN": {
        "REGIME": "MARKDOWN",
        "BUY_CONF": 0.97,
        "SELL_CONF": 0.52,
        "FINBERT_SENT": 0.78,
        "FINBERT_TRAD": 0.78,
    },
    "ACCUMULATION": {
        "REGIME": "ACCUMULATION",
        "BUY_CONF": 0.75,
        "SELL_CONF": 0.75,
        "FINBERT_SENT": 0.55,
        "FINBERT_TRAD": 0.55,
    },
}


class MarketRegimeAnalyzer:
    """Classifies the broad market into a strategy regime."""

    def __init__(self, market_data: MarketDataService):
        self.market_data = market_data

    def analyze(self) -> dict:
        """Return the active risk profile for the current market regime."""
        try:
            spy_hist, spy_change = self.market_data.get_change_and_history("SPY", period="120d")
            qqq_hist, qqq_change = self.market_data.get_change_and_history("QQQ", period="120d")
            iwm_hist, iwm_change = self.market_data.get_change_and_history("IWM", period="120d")
            vix_hist, _ = self.market_data.get_change_and_history("^VIX", period="30d")
            _, tnx_change = self.market_data.get_change_and_history("^TNX", period="30d")

            if spy_hist is None or qqq_hist is None or iwm_hist is None:
                logger.warning("Not enough index data. Defaulting to ACCUMULATION.")
                return RISK_PROFILES["ACCUMULATION"].copy()

            spy_hist = self._add_features(spy_hist)
            qqq_hist = self._add_features(qqq_hist)
            iwm_hist = self._add_features(iwm_hist)

            spy = spy_hist.iloc[-1]
            qqq = qqq_hist.iloc[-1]
            iwm = iwm_hist.iloc[-1]

            spy_bull = spy["Close"] > spy["SMA_20"] > spy["SMA_50"]
            qqq_bull = qqq["Close"] > qqq["SMA_20"] > qqq["SMA_50"]
            iwm_bull = iwm["Close"] > iwm["SMA_20"] > iwm["SMA_50"]

            spy_bear = spy["Close"] < spy["SMA_20"] < spy["SMA_50"]
            qqq_bear = qqq["Close"] < qqq["SMA_20"] < qqq["SMA_50"]
            iwm_bear = iwm["Close"] < iwm["SMA_20"] < iwm["SMA_50"]

            bullish_count = sum([spy_bull, qqq_bull, iwm_bull])
            bearish_count = sum([spy_bear, qqq_bear, iwm_bear])

            breadth_weak = (
                qqq_change is not None and qqq_change < 0 and
                iwm_change is not None and iwm_change < 0
            )
            short_term_weak = spy["RET_5D"] < 0 and qqq["RET_5D"] < 0
            medium_term_weak = spy["RET_20D"] < 0 and qqq["RET_20D"] < 0

            vix_level = float(vix_hist["Close"].iloc[-1]) if vix_hist is not None else None
            elevated_fear = vix_level is not None and vix_level >= 22
            high_fear = vix_level is not None and vix_level >= 28
            yield_stress = tnx_change is not None and tnx_change >= 2.5

            if bullish_count >= 2:
                detected_regime = "DISTRIBUTION" if (breadth_weak or short_term_weak or elevated_fear or yield_stress) else "MARKUP"
            elif bearish_count >= 2:
                detected_regime = "MARKDOWN" if (high_fear or medium_term_weak) else "DISTRIBUTION"
            else:
                detected_regime = "DISTRIBUTION" if (elevated_fear or short_term_weak) else "ACCUMULATION"

            logger.info(
                "Market regime detected: %s | SPY=%s QQQ=%s IWM=%s VIX=%s",
                detected_regime,
                self._format_pct(spy_change),
                self._format_pct(qqq_change),
                self._format_pct(iwm_change),
                f"{vix_level:.2f}" if vix_level is not None else "N/A",
            )
            return RISK_PROFILES[detected_regime].copy()

        except Exception:
            logger.exception("Market regime analysis failed. Defaulting to ACCUMULATION.")
            return RISK_PROFILES["ACCUMULATION"].copy()

    @staticmethod
    def _add_features(hist: pd.DataFrame) -> pd.DataFrame:
        hist = hist.copy()
        hist["SMA_20"] = hist["Close"].rolling(20).mean()
        hist["SMA_50"] = hist["Close"].rolling(50).mean()
        hist["SMA_200_PROXY"] = hist["Close"].rolling(100).mean()
        hist["RET_5D"] = hist["Close"].pct_change(5)
        hist["RET_20D"] = hist["Close"].pct_change(20)
        return hist

    @staticmethod
    def _format_pct(value: float | None) -> str:
        return f"{value:.2f}%" if value is not None else "N/A"
