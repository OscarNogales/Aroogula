import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class EquitySummaryService:
    """
    Computes portfolio-level equity summaries.

    This service combines wallet cash, open portfolio positions,
    current market prices, and historical equity snapshots.
    """

    def __init__(self, wallet, portfolio, market_data, equity_logger):
        self.wallet = wallet
        self.portfolio = portfolio
        self.market_data = market_data
        self.equity_logger = equity_logger

    def get_summary(self, save_snapshot: bool = True) -> dict:
        wallet_response = self.wallet.get_balance()
        cash = float(wallet_response["data"]["equity"])
        mode = wallet_response["data"].get("mode")

        portfolio_response = self.portfolio.get_positions()
        positions = portfolio_response["data"]["positions"]

        portfolio_assets = self._calculate_portfolio_assets(positions)
        total_equity = cash + portfolio_assets

        initial_equity = self._get_initial_equity_today(total_equity)
        today_gain = total_equity - initial_equity
        today_gain_pct = (
            (today_gain / initial_equity) * 100
            if initial_equity
            else 0.0
        )

        open_positions_count = len(positions)
        total_exposure_pct = (
            (portfolio_assets / total_equity) * 100
            if total_equity
            else 0.0
        )

        snapshot = {
            "timestamp": datetime.now(tz=pytz.timezone("America/New_York")).isoformat(timespec="seconds"),
            "cash": cash,
            "portfolio_assets": portfolio_assets,
            "equity": total_equity,
            "open_positions_count": open_positions_count,
            "daily_pnl": today_gain,
            "daily_pnl_pct": today_gain_pct,
            "total_exposure_pct": total_exposure_pct,
            "max_position_weight_pct": self._calculate_max_position_weight(
                positions,
                total_equity,
            ),
            "execution_mode": mode,
        }

        if save_snapshot:
            self.equity_logger.save_entry(snapshot)

        logger.info(
            "Equity summary calculated. equity=%.2f cash=%.2f assets=%.2f",
            total_equity,
            cash,
            portfolio_assets,
        )

        return {
            "status": "success",
            "message": "Successfully retrieved equity summary.",
            "data": {
                "cash": cash,
                "portfolio_assets": portfolio_assets,
                "total_equity": total_equity,
                "equity_gain_pct": today_gain_pct,
                "today_gain": today_gain,
                "today_gain_pct": today_gain_pct,
                "open_positions_count": open_positions_count,
                "total_exposure_pct": total_exposure_pct,
            },
        }

    def _resolve_position_price(self, position: dict) -> tuple[float, str]:
        ticker = position["ticker"]

        current_price = position.get("current_price")

        if current_price is not None:
            return float(current_price), "position_current_price"

        market_price = self.market_data.get_current_price(ticker)

        if market_price is not None:
            return float(market_price), "market_data"

        buy_price = position.get("buy_price")

        if buy_price is not None:
            logger.warning(
                "Using buy_price as fallback for %s because current price is unavailable.",
                ticker,
            )
            return float(buy_price), "buy_price_fallback"

        logger.warning(
            "No usable price found for %s. Using 0.0 for equity calculation.",
            ticker,
        )
        return 0.0, "missing"

    def _calculate_portfolio_assets(self, positions: list[dict]) -> float:
        portfolio_assets = 0.0

        for position in positions:
            shares = float(position.get("shares", 0))

            price, price_source = self._resolve_position_price(position)

            portfolio_assets += price * shares

            if price_source != "market_data" and price_source != "position_current_price":
                logger.warning(
                    "Position %s used non-live price source: %s",
                    position.get("ticker"),
                    price_source,
                )

        return portfolio_assets

    def _get_initial_equity_today(self, fallback_equity: float) -> float:
        equity_df = self.equity_logger.load_all()

        if equity_df.empty:
            return fallback_equity

        today = datetime.today().strftime("%Y-%m-%d")
        today_data = (
            equity_df[equity_df["timestamp"].astype(str) >= today]
            .copy()
            .reset_index(drop=True)
        )

        if today_data.empty:
            return fallback_equity

        return float(today_data.loc[0, "equity"])

    def _calculate_max_position_weight(
        self,
        positions: list[dict],
        total_equity: float,
    ) -> float:
        if not positions or not total_equity:
            return 0.0

        weights = []

        for position in positions:
            shares = float(position.get("shares", 0))
            current_price = position.get("current_price")

            if current_price is None:
                current_price = self.market_data.get_current_price(position["ticker"])

            if current_price is None:
                current_price = position.get("buy_price", 0)

            market_value = float(current_price) * shares
            weights.append((market_value / total_equity) * 100)

        return max(weights) if weights else 0.0