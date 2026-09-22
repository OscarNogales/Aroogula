"""Market data helpers used by the trading decision pipeline.

This service is intentionally focused on data collection and lightweight
feature engineering. It does not decide whether to trade; it only returns the
market/ticker facts needed by RiskGuard, MarketRegimeAnalyzer, and AILogger.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketDataService:
    """Fetches market data and computes decision-time technical features."""

    def __init__(self, alpaca_client: Any | None = None, mode: str = "local_sim"):
        self.alpaca_client = alpaca_client
        self.mode = mode

    def get_current_price(self, ticker: str) -> float:
        """Return the latest available market price for a ticker."""
        ticker = ticker.upper()
        if self.alpaca_client is not None:
            try:
                from alpaca.data.requests import StockLatestTradeRequest

                request_params = StockLatestTradeRequest(symbol_or_symbols=ticker)
                trade = self.alpaca_client.get_stock_latest_trade(request_params)
                return float(trade[ticker].price)
            except Exception:
                logger.warning("Alpaca price fetch failed for %s. Falling back to yfinance.", ticker, exc_info=True)

        try:
            ticker_data = yf.Ticker(ticker)
            return float(ticker_data.fast_info["last_price"])
        except Exception as error:
            logger.exception("Critical price fetch failure for %s.", ticker)
            raise ValueError(f"Could not fetch current price for {ticker}: {error}") from error

    def get_change_and_history(self, ticker_symbol: str, period: str = "90d") -> tuple[pd.DataFrame | None, float | None]:
        """Return price history and latest one-day percent change."""
        try:
            hist = yf.Ticker(ticker_symbol).history(period=period)
        except Exception:
            logger.exception("Failed to download history for %s.", ticker_symbol)
            return None, None

        if hist is None or hist.empty or len(hist) < 2:
            logger.warning("Not enough history for %s with period=%s.", ticker_symbol, period)
            return None, None

        hist = hist.copy()
        prev_close = float(hist["Close"].iloc[-2])
        current_close = float(hist["Close"].iloc[-1])
        pct_change = ((current_close - prev_close) / prev_close) * 100 if prev_close else None
        return hist, pct_change

    def get_index_snapshot(self) -> dict[str, float | None]:
        """Return a compact snapshot of broad market indicators."""

        def get_change(ticker_symbol: str) -> tuple[float | None, float | None]:
            # Prefer Alpaca for normal equity/ETF tickers if available.
            try:
                if self.alpaca_client is not None and not ticker_symbol.startswith("^"):
                    from alpaca.data.requests import StockBarsRequest
                    from alpaca.data.timeframe import TimeFrame

                    request_params = StockBarsRequest(
                        symbol_or_symbols=ticker_symbol,
                        timeframe=TimeFrame.Day,
                        start=datetime.now() - timedelta(days=7),
                    )
                    bars = self.alpaca_client.get_stock_bars(request_params).df
                    if bars is not None and not bars.empty and len(bars) >= 2:
                        prev_close = float(bars.iloc[-2]["close"])
                        curr_price = float(bars.iloc[-1]["close"])
                        pct_change = ((curr_price - prev_close) / prev_close) * 100 if prev_close else None
                        return curr_price, pct_change
            except Exception:
                logger.debug("Alpaca index fetch failed for %s; falling back to yfinance.", ticker_symbol, exc_info=True)

            try:
                # Small pause reduces yfinance throttling in repeated scans.
                time.sleep(0.25)
                hist = yf.Ticker(ticker_symbol).history(period="5d")
                if hist is not None and not hist.empty and len(hist) >= 2:
                    prev_close = float(hist["Close"].iloc[-2])
                    current_price = float(hist["Close"].iloc[-1])
                    pct_change = ((current_price - prev_close) / prev_close) * 100 if prev_close else None
                    return current_price, pct_change
            except Exception:
                logger.debug("YFinance index fetch failed for %s.", ticker_symbol, exc_info=True)

            return None, None

        _, spy_change = get_change("SPY")
        vix_curr, vix_change = get_change("^VIX")
        tnx_curr, tnx_change = get_change("^TNX")
        _, qqq_change = get_change("QQQ")
        _, iwm_change = get_change("IWM")

        def safe_round(value: float | None) -> float | None:
            return round(value, 2) if value is not None else None

        return {
            "vix_level": safe_round(vix_curr),
            "interest_rate": safe_round(tnx_curr),
            "vix_trend_pct": safe_round(vix_change),
            "rates_trend_pct": safe_round(tnx_change),
            "sp500_trend_pct": safe_round(spy_change),
            "tech_trend_pct": safe_round(qqq_change),
            "smallcap_trend_pct": safe_round(iwm_change),
        }

    def get_ticker_decision_features(self, ticker: str) -> dict[str, float | None]:
        """Return ticker-level features captured at decision time."""
        hist, day_change_pct = self.get_change_and_history(ticker, period="90d")

        empty_features = {
            "price_at_decision": None,
            "day_change_pct": None,
            "volume": None,
            "relative_volume": None,
            "rsi_14": None,
            "atr_14": None,
        }

        if hist is None or hist.empty:
            return empty_features

        hist = hist.copy()
        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]

        price = float(close.iloc[-1]) if len(close) else None
        volume = float(hist["Volume"].iloc[-1]) if "Volume" in hist.columns and not hist["Volume"].empty else None
        avg_volume = float(hist["Volume"].tail(20).mean()) if "Volume" in hist.columns and len(hist) >= 20 else None
        relative_volume = float(volume / avg_volume) if volume and avg_volume else None

        return {
            "price_at_decision": price,
            "day_change_pct": float(day_change_pct) if day_change_pct is not None else None,
            "volume": volume,
            "relative_volume": relative_volume,
            "rsi_14": self.calculate_rsi(close, period=14),
            "atr_14": self.calculate_atr(high, low, close, period=14),
        }

    @staticmethod
    def calculate_rsi(close: pd.Series, period: int = 14) -> float | None:
        """Calculate the latest RSI value."""
        if close is None or len(close) < period + 1:
            return None

        delta = close.diff()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)

        avg_gain = gains.rolling(period).mean()
        avg_loss = losses.rolling(period).mean()
        last_loss = avg_loss.iloc[-1]

        if pd.isna(last_loss):
            return None
        if float(last_loss) == 0:
            return 100.0

        rs = avg_gain.iloc[-1] / last_loss
        rsi = 100 - (100 / (1 + rs))
        return round(float(rsi), 2) if not pd.isna(rsi) else None

    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
        """Calculate the latest Average True Range value."""
        if high is None or low is None or close is None or len(close) < period + 1:
            return None

        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr = true_range.rolling(period).mean().iloc[-1]
        return round(float(atr), 4) if not pd.isna(atr) else None
