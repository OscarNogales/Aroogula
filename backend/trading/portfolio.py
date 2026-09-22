"""Portfolio state and bot-managed trade persistence.

This module owns the local representation of trades managed by the bot.
Pandas and CSV persistence are implementation details of this class and should
not be accessed directly by consumers such as Broker or RiskGuard.
"""

import logging
import os

import pandas as pd


logger = logging.getLogger(__name__)


class Portfolio:
    """Manage the bot's locally tracked open trades.

    The portfolio stores bot-specific trade metadata such as the originating
    news item, AI confidence, stop-loss, take-profit, and maximum observed
    price. In Alpaca modes, ``get_positions`` may enrich these local records
    with live account data.

    Notes
    -----
    ``self.df`` remains an internal persistence detail. Other components should
    interact with the portfolio through the public methods defined here.
    """

    def __init__(
        self,
        mode: str = "local_sim",
        alpaca_client=None,
        portfolio_path: str = "portfolio_state.csv",
    ):
        """Initialize the portfolio and load previously persisted trades.

        Parameters
        ----------
        mode:
            Active trading mode. Currently supports ``local_sim``,
            ``alpaca_paper``, and ``alpaca_live``.
        alpaca_client:
            Alpaca trading client used only when live Alpaca position data is
            requested.
        portfolio_path:
            CSV file used to persist bot-managed open trades.
        """
        self.mode = mode
        self.client = alpaca_client
        self.portfolio_path = portfolio_path

        self.columns = [
            "trade_id",
            "news_id",
            "ticker",
            "buy_price",
            "max_price",
            "take_profit",
            "stop_loss",
            "shares",
            "buy_reason",
            "decision_id",
            "ai_confidence",
            "timestamp",
        ]

        self.df = self._load_portfolio()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_portfolio(self) -> pd.DataFrame:
        """Load the locally persisted portfolio into memory.

        Returns an empty DataFrame with the expected schema when the portfolio
        file does not exist. Existing records are normalized to the current
        column layout and missing ``max_price`` values fall back to
        ``buy_price``.
        """
        if not os.path.exists(self.portfolio_path):
            return pd.DataFrame(columns=self.columns)

        try:
            portfolio_df = pd.read_csv(self.portfolio_path)
            portfolio_df = portfolio_df.reindex(columns=self.columns)
            portfolio_df["max_price"] = portfolio_df["max_price"].fillna(
                portfolio_df["buy_price"]
            )
            return portfolio_df
        except Exception:
            # NOTE: We already identified this fallback as something to harden
            # later. For now it preserves the current local_sim behavior.
            logger.exception("Failed to load portfolio from %s.", self.portfolio_path)
            return pd.DataFrame(columns=self.columns)

    def save(self) -> bool:
        """Persist the current in-memory portfolio to the configured CSV file.

        Returns
        -------
        bool
            ``True`` when the file is written successfully; otherwise ``False``.
        """
        try:
            self.df.to_csv(self.portfolio_path, index=False)
            return True
        except Exception:
            logger.exception("Failed to save portfolio.")
            return False

    # ------------------------------------------------------------------
    # Bot-managed trade queries
    # ------------------------------------------------------------------

    def get_open_trades(self) -> list[dict]:
        """Return all open trades currently managed by the bot.

        The returned records are plain Python dictionaries so callers do not
        depend on the internal pandas representation.
        """
        return self.df.to_dict(orient="records")

    def has_open_trades(self) -> bool:
        """Return whether the bot currently has at least one open trade."""
        return not self.df.empty

    def get_trade(self, trade_id: str) -> dict | None:
        """Return one bot-managed trade by its unique trade ID.

        Parameters
        ----------
        trade_id:
            Unique identifier assigned to the trade.

        Returns
        -------
        dict | None
            The matching trade as a plain dictionary, or ``None`` when the
            trade is not present in the portfolio.
        """
        trade_mask = self.df["trade_id"] == trade_id
        matching_trades = self.df[trade_mask]

        if matching_trades.empty:
            logger.error("Trade %s not found in the portfolio.", trade_id)
            return None

        return matching_trades.iloc[0].to_dict()

    def get_trade_ids(self) -> list[str]:
        """Return the IDs of all bot-managed open trades."""
        return self.df["trade_id"].to_list()

    def get_shares_owned(self, ticker: str) -> float:
        """Return the total shares tracked by the bot for one ticker."""
        ticker_trades = self.df[self.df["ticker"] == ticker]

        if ticker_trades.empty:
            return 0.0

        return float(ticker_trades["shares"].sum())

    def get_buy_reasons(self, ticker: str) -> list:
        """Return the stored buy reasons for all open trades of one ticker."""
        ticker_mask = self.df["ticker"] == ticker
        ticker_trades = self.df[ticker_mask]

        if ticker_trades.empty:
            return []

        return ticker_trades["buy_reason"].tolist()

    # ------------------------------------------------------------------
    # Position view
    # ------------------------------------------------------------------

    def get_positions(self) -> dict:
        """Return a position view suitable for the current trading mode.

        In ``local_sim`` this returns the bot's locally tracked trades. In an
        Alpaca mode it enriches those local records with live price and PnL
        information retrieved from Alpaca.

        This method currently combines local trade metadata with external
        account data. We are intentionally leaving that behavior intact during
        the first refactor; the Alpaca/local position-provider split will come
        later.
        """
        if self.df.empty:
            return {
                "status": "success",
                "message": "Empty portfolio.",
                "data": {"positions": []},
            }

        local_positions = self.get_open_trades()

        if self.mode == "local_sim":
            return {
                "status": "success",
                "message": "Local positions obtained.",
                "data": {"positions": local_positions},
            }

        if self.mode in {"alpaca_paper", "alpaca_live"} and self.client is not None:
            try:
                alpaca_positions = self.client.get_all_positions()
                alpaca_positions_by_symbol = {
                    position.symbol: position for position in alpaca_positions
                }

                merged_positions = []

                for local_position in local_positions:
                    ticker = local_position["ticker"]
                    live_position = alpaca_positions_by_symbol.get(ticker)

                    if live_position is not None:
                        local_position["current_price"] = float(
                            live_position.current_price
                        )
                        local_position["unrealized_pl"] = float(
                            live_position.unrealized_pl
                        )
                        local_position["unrealized_plpc"] = (
                            float(live_position.unrealized_plpc) * 100
                        )

                    merged_positions.append(local_position)

                return {
                    "status": "success",
                    "message": "Positions retrieved from Alpaca successfully.",
                    "data": {"positions": merged_positions},
                }

            except Exception as exc:
                logger.exception("Failed to retrieve positions from Alpaca.")
                return {
                    "status": "error",
                    "message": f"Error retrieving positions from Alpaca: {exc}",
                    "data": {"positions": local_positions},
                }

        return {
            "status": "error",
            "message": f"No position provider is available for mode '{self.mode}'.",
            "data": {"positions": local_positions},
        }

    # ------------------------------------------------------------------
    # Trade mutations
    # ------------------------------------------------------------------

    def add_trade(self, trade_data: dict) -> dict:
        """Register a newly opened trade and persist the updated portfolio.

        If persistence fails, the in-memory portfolio is restored to its
        previous state.
        """
        previous_portfolio = self.df.copy()

        try:
            new_trade = pd.DataFrame([trade_data]).reindex(columns=self.columns)
            self.df = pd.concat([self.df, new_trade], ignore_index=True)

            if not self.save():
                raise RuntimeError(
                    f"Portfolio save failed in {self.add_trade.__qualname__}."
                )

            return {
                "status": "success",
                "message": f"Registered buy for {trade_data.get('ticker')}.",
                "data": {"trade_id": trade_data.get("trade_id")},
            }

        except Exception as exc:
            self.df = previous_portfolio
            logger.exception("Failed to add trade %s.", trade_data.get("trade_id"))

            return {
                "status": "error",
                "message": (
                    "Error trying to add trade "
                    f"{trade_data.get('trade_id', 'None')}: {exc}"
                ),
            }

    def remove_trade(self, trade_id: str) -> dict:
        """Remove an open trade and persist the updated portfolio.

        If persistence fails, the in-memory portfolio is restored to its
        previous state.
        """
        previous_portfolio = self.df.copy()

        try:
            trade_mask = self.df["trade_id"] == trade_id
            matching_indices = self.df[trade_mask].index

            if matching_indices.empty:
                logger.error("Trade %s was not found in the portfolio.", trade_id)
                return {
                    "status": "error",
                    "message": f"Trade {trade_id} was not found in the portfolio.",
                }

            self.df.drop(matching_indices, inplace=True)
            self.df.reset_index(drop=True, inplace=True)

            if not self.save():
                raise RuntimeError(
                    f"Portfolio save failed in {self.remove_trade.__qualname__}."
                )

            return {
                "status": "success",
                "message": f"Position {trade_id} closed.",
            }

        except Exception as exc:
            self.df = previous_portfolio
            logger.exception("Failed to remove trade %s.", trade_id)

            return {
                "status": "error",
                "message": f"Error trying to remove trade {trade_id}: {exc}",
            }

    def update_max_price(self, trade_id: str, current_price: float) -> dict:
        """Update the highest observed price used by the trailing stop logic.

        If persistence fails, the in-memory portfolio is restored to its
        previous state.
        """
        previous_portfolio = self.df.copy()

        try:
            trade_mask = self.df["trade_id"] == trade_id

            if self.df[trade_mask].empty:
                return {
                    "status": "error",
                    "message": f"Trade {trade_id} not found.",
                }

            self.df.loc[trade_mask, "max_price"] = current_price

            if not self.save():
                raise RuntimeError(
                    f"Portfolio save failed in {self.update_max_price.__qualname__}."
                )

            return {
                "status": "success",
                "message": f"Trailing stop price updated for {trade_id}.",
                "data": {"new_max_price": current_price},
            }

        except Exception as e:
            self.df = previous_portfolio
            logger.exception("Unable to update max price for %s.", trade_id)

            return {
                "status": "error",
                "message": f"Unable to update max price for {trade_id}: {e}",
            }

    def update_shares(self, trade_id: str, new_shares: float) -> dict:
        previous_portfolio = self.df.copy()

        try:
            if new_shares <= 0:
                return {
                    "status": "error",
                    "message": "New share quantity must be greater than zero.",
                }

            share_mask = self.df["trade_id"] == trade_id

            if self.df[share_mask].empty:
                return {
                    "status": "error",
                    "message": f"Trade {trade_id} not found.",
                }

            self.df.loc[share_mask, "shares"] = new_shares

            if not self.save():
                raise RuntimeError(
                    f"Portfolio save failed in {self.update_shares.__qualname__}."
                )

            return {
                "status": "success",
                "message": f"Share quantity updated for {trade_id}.",
                "data": {"new_shares_hold": new_shares},
            }

        except Exception as e:
            self.df = previous_portfolio

            logger.exception(
                "Unable to update shares for %s.",
                trade_id,
            )

            return {
                "status": "error",
                "message": f"Unable to update shares for {trade_id}: {e}",
            }