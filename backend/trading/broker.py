"""
Broker is intentionally focused on execution and portfolio/wallet mutation. It
should not decide whether an opportunity is good; TradeAnalyzer/RiskGuard do
that before calling Broker.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import uuid4

import pandas as pd
import pytz
from math import isclose

from backend.app.event_bus import event_bus
from .execution.order_template import ExecutionResult

logger = logging.getLogger(__name__)


class Broker:
    def __init__(
        self,
        wallet,
        ledger,
        portfolio,
        memory,
        market_data, 
        executor,
        settings_path: str,
        alpaca_client=None,
        mode: str = "local_sim",
        equity_logger=None,
    ):
        self.wallet = wallet
        self.ledger = ledger
        self.portfolio = portfolio
        self.memory = memory
        self.client = alpaca_client
        self.market_data = market_data
        self.executor = executor
        self.mode = mode
        self.equity_logger = equity_logger

        with open(settings_path, "r") as f:
            self.settings = json.load(f)

        self.seen_ids = set(self.ledger.seen_ids()) if self.ledger is not None else set()


        self.broker_status = "PAUSED"
        self._configure_scheduler()
        self._sync_risk_checker()


    def _get_current_assets_valuation(self) -> float:
        """Return the current market value of all open portfolio positions."""
        current_assets = self.portfolio.get_open_trades()

        if not current_assets:
            return 0.0

        total_value = 0.0

        for trade in current_assets:
            ticker = trade["ticker"]
            shares = float(trade["shares"])

            current_price = self.market_data.get_current_price(ticker)
            total_value += shares * current_price

        return total_value

    def _now_timestamp(self) -> str:
        return datetime.now(
            tz=pytz.timezone("America/New_York")
        ).isoformat(timespec="seconds")

    def _today_ny_date(self) -> str:
        return datetime.now(
            tz=pytz.timezone("America/New_York")
        ).date().isoformat()

    def buy(
    self,
    ticker: str | None = None,
    invest_amount: float | None = None,
    buy_reason: str = "",
    news_id: str | None = None,
    stop_loss_pct: float = 0.05,
    take_profit_pct: float = 0.10,
    decision_id: str | None = None,
    ai_confidence: float | None = None,
    **legacy_kwargs,
) -> dict:
        """Execute a buy order and register it in Portfolio and Ledger.

        Accepts legacy aliases used by older code:
        - tkr -> ticker
        - db_id -> news_id
        - sl -> stop_loss_pct
        - tp -> take_profit_pct
        """

        # ---------------------------------------------------------
        # Normalize legacy arguments
        # ---------------------------------------------------------
        ticker = ticker or legacy_kwargs.get("tkr")
        news_id = news_id or legacy_kwargs.get("db_id")

        stop_loss_pct = legacy_kwargs.get("sl", stop_loss_pct)
        take_profit_pct = legacy_kwargs.get("tp", take_profit_pct)

        decision_id = decision_id or legacy_kwargs.get("decision_id")

        if ai_confidence is None:
            ai_confidence = legacy_kwargs.get("ai_confidence")

        # ---------------------------------------------------------
        # Validate request
        # ---------------------------------------------------------
        if ticker is None or invest_amount is None or news_id is None:
            return {
                "status": "error",
                "message": (
                    "Missing ticker, invest_amount, or news_id for buy order."
                ),
            }

        ticker = ticker.upper()
        news_id = str(news_id)

        if news_id in self.seen_ids:
            return {
                "status": "ignored",
                "message": f"News {news_id} was already traded.",
            }

        try:
            # ---------------------------------------------------------
            # Account state before execution
            # ---------------------------------------------------------
            cash_before = float(
                self.wallet.get_balance()["data"]["cash"]
            )

            assets_before = self._get_current_assets_valuation()

            trade_id = f"TRD-{uuid4().hex[:8].upper()}"
            timestamp = self._now_timestamp()

            # ---------------------------------------------------------
            # Execute order
            # ---------------------------------------------------------
            execution_result = self.executor.buy(
                ticker,
                invest_amount,
            )

            if execution_result.status != "FILLED":
                raise RuntimeError(
                    f"Unable to process buy request for {trade_id}, "
                    f"ticker: {ticker}. "
                    f"{execution_result.message}"
                )

            # A FILLED execution should always contain fill information.
            if (
                execution_result.filled_price is None
                or execution_result.filled_quantity is None
            ):
                raise RuntimeError(
                    f"Executor returned FILLED for {ticker}, but fill information is missing."
                )

            filled_price = execution_result.filled_price
            filled_quantity = execution_result.filled_quantity

            total_cost = filled_price * filled_quantity

            # ---------------------------------------------------------
            # Register bot-managed position
            # ---------------------------------------------------------
            trade_data = {
                "trade_id": trade_id,
                "decision_id": decision_id,
                "news_id": news_id,
                "ticker": ticker,
                "buy_price": filled_price,
                "max_price": filled_price,
                "take_profit": (
                    filled_price * (1 + float(take_profit_pct))
                ),
                "stop_loss": (
                    filled_price * (1 - float(stop_loss_pct))
                ),
                "shares": filled_quantity,
                "buy_reason": buy_reason,
                "ai_confidence": ai_confidence,
                "timestamp": timestamp,
            }

            add_result = self.portfolio.add_trade(trade_data)

            if (
                not isinstance(add_result, dict)
                or add_result.get("status") != "success"
            ):
                error_message = (
                    add_result.get(
                        "message",
                        "Unknown portfolio error.",
                    )
                    if isinstance(add_result, dict)
                    else "Portfolio add_trade returned an invalid response."
                )

                raise RuntimeError(
                    f"Unable to add {trade_id} to portfolio. "
                    f"Portfolio error: {error_message}"
                )

            self.seen_ids.add(news_id)

            # ---------------------------------------------------------
            # Account state after execution
            # ---------------------------------------------------------
            cash_after = float(
                self.wallet.get_balance()["data"]["cash"]
            )

            assets_after = assets_before + total_cost

            equity_before = cash_before + assets_before
            equity_after = cash_after + assets_after

            # ---------------------------------------------------------
            # Ledger
            # ---------------------------------------------------------
            ledger_result = self._record_trade_event(
                {
                    "trade_id": trade_id,
                    "news_id": news_id,
                    "ticker": ticker,
                    "action": "BUY",
                    "status": "success",
                    "timestamp": timestamp,
                    "entry_price": filled_price,
                    "shares": filled_quantity,
                    "position_value": total_cost,
                    "cash_before": cash_before,
                    "cash_after": cash_after,
                    "buy_reason": buy_reason,
                    "execution_mode": execution_result.mode,
                    "decision_id": decision_id,
                    "ai_confidence": ai_confidence,
                    "equity_before": equity_before,
                    "equity_after": equity_after,
                    "strategy_version": self.settings.get(
                        "strategy_version",
                        "v1",
                    ),
                }
            )

            if (
                not isinstance(ledger_result, dict)
                or ledger_result.get("status") != "success"
            ):
                error_message = (
                    ledger_result.get(
                        "message",
                        "Unknown ledger error.",
                    )
                    if isinstance(ledger_result, dict)
                    else "Ledger returned an invalid response."
                )

                # Temporary local-sim compensation.
                #
                # This cannot be used as the Alpaca strategy because a real
                # FILLED order cannot simply be "undone" by changing Wallet.
                if execution_result.mode == "local_sim":
                    self.portfolio.remove_trade(trade_id)
                    self.wallet.update_balance(total_cost)
                    self.seen_ids.discard(news_id)

                raise RuntimeError(error_message)

            # ---------------------------------------------------------
            # Finalize
            # ---------------------------------------------------------
            self._sync_risk_checker()

            logger.info(
                "Bought %s shares of %s at %.2f. [%s]",
                filled_quantity,
                ticker,
                filled_price,
                execution_result.message,
            )

            return {
                "status": "success",
                "message": (
                    f"Bought {filled_quantity} shares of {ticker}. "
                    f"[{execution_result.message}]"
                ),
                "data": trade_data,
            }

        except Exception as error:
            logger.exception(
                "Buy order failed for %s.",
                ticker,
            )

            return {
                "status": "error",
                "message": str(error),
            }

    def sell(
        self,
        t_id: str,
        sell_reason: str,
        current_price: float | None = None,  # Legacy compatibility for now
    ) -> dict:
        """Sell a portfolio position and register the execution in the ledger."""

        # ---------------------------------------------------------
        # Load trade
        # ---------------------------------------------------------
        trade = self.portfolio.get_trade(t_id)

        if not trade:
            return {
                "status": "error",
                "message": f"Trade {t_id} was not found in portfolio.",
            }

        ticker = str(trade["ticker"]).upper()
        qty = float(trade["shares"])
        buy_price = float(trade["buy_price"])
        news_id = trade["news_id"]

        try:
            # ---------------------------------------------------------
            # Account state before execution
            # ---------------------------------------------------------
            assets_before = self._get_current_assets_valuation()
            cash_before = float(
                self.wallet.get_balance()["data"]["cash"]
            )

            # ---------------------------------------------------------
            # Execute sell order
            # ---------------------------------------------------------
            execution_result = self.executor.sell(
                ticker,
                qty,
            )

            if execution_result.status not in {
                "FILLED",
                "PARTIALLY_FILLED",
            }:
                raise RuntimeError(
                    f"Unable to process sell request for {t_id}, "
                    f"ticker: {ticker}. "
                    f"Execution status: {execution_result.status}. "
                    f"{execution_result.message}"
                )

            if (
                execution_result.filled_price is None
                or execution_result.filled_quantity is None
            ):
                raise RuntimeError(
                    f"Executor returned {execution_result.status} for {t_id}, "
                    "but fill information is missing."
                )

            sell_price = float(execution_result.filled_price)
            shares_sold = float(execution_result.filled_quantity)

            if shares_sold <= 0:
                raise RuntimeError(
                    f"Executor returned an invalid filled quantity "
                    f"for {t_id}: {shares_sold}."
                )

            # ---------------------------------------------------------
            # Validate execution result
            # ---------------------------------------------------------
            if execution_result.status == "FILLED":
                if not isclose(
                    qty,
                    shares_sold,
                    rel_tol=1e-9,
                    abs_tol=1e-8,
                ):
                    raise RuntimeError(
                        f"Executor returned FILLED for {t_id}, "
                        f"but requested {qty:.8f} shares and "
                        f"filled {shares_sold:.8f}."
                    )

            elif execution_result.status == "PARTIALLY_FILLED":
                if shares_sold >= qty:
                    raise RuntimeError(
                        f"Executor returned PARTIALLY_FILLED for {t_id}, "
                        f"but filled {shares_sold:.8f} of "
                        f"{qty:.8f} requested shares."
                    )

                logger.warning(
                    "Order %s was partially filled. "
                    "Requested: %.8f | Filled: %.8f | Remaining: %.8f",
                    t_id,
                    qty,
                    shares_sold,
                    qty - shares_sold,
                )

            # ---------------------------------------------------------
            # Calculate realized result
            # ---------------------------------------------------------
            revenue = sell_price * shares_sold
            cost_basis = buy_price * shares_sold

            profit_dollars = revenue - cost_basis
            pnl_pct = (
                (profit_dollars / cost_basis) * 100
                if cost_basis
                else None
            )

            # ---------------------------------------------------------
            # Update Portfolio
            # ---------------------------------------------------------
            if execution_result.status == "FILLED":
                portfolio_result = self.portfolio.remove_trade(t_id)

            else:
                remaining_shares = qty - shares_sold

                portfolio_result = self.portfolio.update_shares(
                    t_id,
                    remaining_shares,
                )

            if (
                not isinstance(portfolio_result, dict)
                or portfolio_result.get("status") != "success"
            ):
                error_message = (
                    portfolio_result.get(
                        "message",
                        "Unknown portfolio error.",
                    )
                    if isinstance(portfolio_result, dict)
                    else "Portfolio returned an invalid response."
                )

                # Local execution already credited the sale revenue,
                # so compensate if Portfolio could not be updated.
                if execution_result.mode == "local_sim":
                    self.wallet.update_balance(-revenue)

                raise RuntimeError(
                    f"Unable to update portfolio for {t_id}. "
                    f"Portfolio error: {error_message}"
                )

            # ---------------------------------------------------------
            # Account state after execution
            # ---------------------------------------------------------
            cash_after = float(
                self.wallet.get_balance()["data"]["cash"]
            )

            assets_after = assets_before - revenue

            equity_before = cash_before + assets_before
            equity_after = cash_after + assets_after

            timestamp = self._now_timestamp()

            # ---------------------------------------------------------
            # Holding time
            # ---------------------------------------------------------
            buy_timestamp = pd.to_datetime(
                trade["timestamp"],
                errors="coerce",
                utc=True,
            )

            sell_timestamp = pd.Timestamp.now(tz="UTC")

            holding_minutes = None

            if pd.notna(buy_timestamp):
                holding_minutes = float(
                    (
                        sell_timestamp - buy_timestamp
                    ).total_seconds()
                    / 60
                )

            # ---------------------------------------------------------
            # Ledger
            # ---------------------------------------------------------
            ledger_event = {
                "trade_id": t_id,
                "news_id": news_id,
                "ticker": ticker,
                "action": "SELL",
                "status": "success",
                "timestamp": timestamp,
                "entry_price": buy_price,
                "exit_price": sell_price,
                "shares": shares_sold,
                "position_value": revenue,
                "cash_before": cash_before,
                "cash_after": cash_after,
                "buy_reason": trade["buy_reason"],
                "sell_reason": sell_reason,
                "pnl_dollars": profit_dollars,
                "pnl_pct": pnl_pct,
                "exit_trigger": sell_reason,
                "was_profitable": profit_dollars > 0,
                "execution_mode": execution_result.mode,
                "decision_id": trade.get("decision_id"),
                "ai_confidence": trade.get("ai_confidence"),
                "equity_before": equity_before,
                "equity_after": equity_after,
                "holding_minutes": holding_minutes,
                "strategy_version": self.settings.get(
                    "strategy_version",
                    "v1",
                ),
            }

            ledger_result = self._record_trade_event(
                ledger_event
            )

            if (
                not isinstance(ledger_result, dict)
                or ledger_result.get("status") != "success"
            ):
                error_message = (
                    ledger_result.get(
                        "message",
                        "Unknown ledger error.",
                    )
                    if isinstance(ledger_result, dict)
                    else "Ledger returned an invalid response."
                )

                # -----------------------------------------------------
                # Local-sim compensation
                # -----------------------------------------------------
                if execution_result.mode == "local_sim":

                    if execution_result.status == "FILLED":
                        self.portfolio.add_trade(trade)

                    elif execution_result.status == "PARTIALLY_FILLED":
                        self.portfolio.update_shares(
                            t_id,
                            qty,
                        )

                    self.wallet.update_balance(-revenue)

                raise RuntimeError(error_message)

            # ---------------------------------------------------------
            # Update market memory
            # ---------------------------------------------------------
            try:
                self.memory.update_memory_sell(
                    ticker=ticker,
                    database_id=news_id,
                    decision=sell_reason,
                    macro_state={
                        "pnl_result": profit_dollars
                    },
                )

            except Exception:
                logger.exception(
                    "Failed to update market memory after selling %s.",
                    ticker,
                )

            # ---------------------------------------------------------
            # Finalize
            # ---------------------------------------------------------
            self._sync_risk_checker()

            logger.info(
                "Sold %.8f shares of %s at %.2f. "
                "PnL=$%.2f. Execution=%s",
                shares_sold,
                ticker,
                sell_price,
                profit_dollars,
                execution_result.status,
            )

            if execution_result.status == "PARTIALLY_FILLED":
                message = (
                    f"Partially sold {shares_sold} shares of {ticker}. "
                    f"{qty - shares_sold} shares remain. "
                    f"PnL: ${profit_dollars:.2f}"
                )
            else:
                message = (
                    f"Sold {shares_sold} shares of {ticker}. "
                    f"PnL: ${profit_dollars:.2f}"
                )

            return {
                "status": "success",
                "message": message,
                "data": ledger_event,
            }

        except Exception as error:
            logger.exception(
                "Sell order failed for trade_id=%s.",
                t_id,
            )

            return {
                "status": "error",
                "message": f"Error selling {t_id}: {error}",
            }
    def check_stock(self) -> dict:
        """Check open positions against take-profit, trailing stop, and stop-loss rules."""

        self._emit("risk_check_started", {
                "message": "Checking open positions.",
            })

        if not self.portfolio.has_open_trades():
                    result = {
                        "status": "success",
                        "message": "Portfolio is empty.",
                        "data": {"actions_taken": []},
                    }
        
                    self._emit("risk_check_completed", {
                        "message": "Portfolio is empty.",
                        "actions_taken": [],
                        "profit_today": 0,
                    })
        
                    return result

        portfolio_copy = self.portfolio.get_open_trades()
        portfolio_assets = 0.0

        try:
            portfolio_assets = self._get_current_assets_valuation()
        except Exception as error:
            logger.exception("Failed to compute portfolio assets during stock check.")

            result = {
                "status": "error",
                "message": "Risk check failed because portfolio prices could not be fetched.",
                "data": {
                    "actions_taken": [],
                    "open_positions_count": int(len(portfolio_copy)),
                    "error": str(error),
                },
            }

            self._emit("risk_check_failed", {
                "message": result["message"],
                "open_positions_count": int(len(portfolio_copy)),
                "error": str(error),
            })

            return result

        cash = float(self.wallet.get_balance()["data"]["cash"])
        equity = cash + portfolio_assets
        timestamp = self._now_timestamp()
        self._record_equity_snapshot(
            {
                "timestamp": timestamp,
                "portfolio_assets": portfolio_assets,
                "cash": cash,
                "equity": equity,
                "open_positions_count": int(len(portfolio_copy)),
                "execution_mode": self.mode,
            }
        )

        
        today = self._today_ny_date()
        try:
            ledger_df = self.ledger.get_all()
            today_trades = ledger_df[
                ledger_df["timestamp"].astype(str).str[:10] == today
            ]
            self.total_pnl = float(today_trades.get("pnl_dollars", pd.Series(dtype=float)).fillna(0).sum())
        except Exception:
            logger.exception("Failed to calculate today's realized PnL.")
            self.total_pnl = 0.0

        actions_taken = []
        successfully_checked = 0
        failed_checks = []

        for row in portfolio_copy:
            trade_id = row["trade_id"]
            ticker = row["ticker"]
            buy_price = float(row["buy_price"])
            max_price = float(row["max_price"])
            take_profit = float(row["take_profit"])
            stop_loss = float(row["stop_loss"])

            try:
                current_price = self.market_data.get_current_price(ticker)
                peak_drop = (current_price - max_price) / max_price if max_price else 0

                if current_price > max_price:
                    self.portfolio.update_max_price(trade_id, current_price)

                if take_profit > 0 and current_price >= take_profit:
                    actions_taken.append(
                        self.sell(trade_id, "Take Profit Reached", current_price)
                    )
                    successfully_checked += 1
                    continue

                if (
                    current_price < max_price
                    and -peak_drop >= 0.01
                    and max_price > 1.02 * buy_price
                ):
                    actions_taken.append(
                        self.sell(
                            trade_id,
                            "Price dropped 1% from peak",
                            current_price,
                        )
                    )
                    successfully_checked += 1
                    continue

                if stop_loss > 0 and current_price <= stop_loss:
                    actions_taken.append(
                        self.sell(trade_id, "Stop Loss Triggered", current_price)
                    )
                    successfully_checked += 1
                    continue

                successfully_checked += 1

            except Exception as error:
                failed_checks.append({
                    "trade_id": trade_id,
                    "ticker": ticker,
                    "error": str(error),
                })

                logger.exception("Risk check failed for %s.", ticker)

        successful_actions = [
            action
            for action in actions_taken
            if isinstance(action, dict) and action.get("status") == "success"
        ]

        failed_actions = [
            action
            for action in actions_taken
            if not isinstance(action, dict) or action.get("status") != "success"
        ]

        if not failed_checks and not failed_actions:
            status = "success"
            message = (
                f"Risk review completed successfully. "
                f"{successfully_checked} positions checked and "
                f"{len(successful_actions)} positions closed."
            )

        elif successfully_checked > 0:
            status = "partial"
            message = (
                f"Risk review completed with warnings. "
                f"{successfully_checked} positions checked successfully, "
                f"{len(failed_checks)} checks failed, and "
                f"{len(failed_actions)} sell actions failed."
            )

        else:
            status = "error"
            message = (
                f"Risk review failed. "
                f"Unable to successfully check any of the "
                f"{len(portfolio_copy)} open positions."
            )


        result = {
            "status": status,
            "message": message,
            "data": {
                "actions_taken": actions_taken,
                "positions_closed": len(successful_actions),
                "successful_checks": successfully_checked,
                "failed_checks": failed_checks,
                "failed_actions": failed_actions,
                "profit_today": self.total_pnl,
            },
        }

        self._emit("risk_check_completed", {
            "status": status,
            "message": message,
            "actions_taken": actions_taken,
            "positions_closed": len(successful_actions),
            "profit_today": self.total_pnl,
            "successful_checks": successfully_checked,
            "failed_checks": failed_checks,
            "failed_actions": failed_actions,
        })

        if successful_actions:
            self._emit("portfolio_changed", {
            "reason": "risk_check_closed_positions",
            "actions_taken": successful_actions,
            "positions_closed": len(successful_actions),
        })

        return result

    def liquidate_all(self, reason: str = "Emergency Liquidation") -> dict:
        """Sell all open positions at the current market price."""
        trade_ids = self.portfolio.get_trade_ids()
        if not trade_ids:
            return {"status": "success", "message": "Portfolio was already empty.", "data": {"total_pnl": 0.0, "actions": []}}

        actions_taken = []
        total_pnl = 0.0
        for trade_id in trade_ids:
            result = self.sell(trade_id, reason)
            if result.get("status") == "success":
                total_pnl += float(result["data"].get("pnl_dollars", 0.0))
            actions_taken.append(result)

        return {
            "status": "success",
            "message": f"Liquidated {len(actions_taken)} positions.",
            "data": {"total_pnl": total_pnl, "actions": actions_taken},
        }

    def _record_trade_event(self, event: dict) -> dict:
        if self.ledger is None:
            return {
                "status": "error",
                "message": "Ledger is not configured.",
            }

        try:
            self.ledger.add_event(event)
            return {
                "status": "success",
                "message": "Trade event recorded.",
            }
        except Exception as e:
            logger.exception("Failed to record trade event: %s", event)
            return {
                "status": "error",
                "message": f"Failed to record trade event: {e}",
            }

    def _record_equity_snapshot(self, snapshot: dict) -> None:
        try:
            if self.equity_logger is not None:
                self.equity_logger.save_entry(snapshot)
            elif hasattr(self.ledger, "add_equity_log"):
                self.ledger.add_equity_log(snapshot)
        except Exception:
            logger.exception("Failed to record equity snapshot.")

    def _configure_scheduler(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        self.scheduler = BackgroundScheduler(timezone="America/New_York")
        self.scheduler.add_job(
            self.check_stock,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour="9-16",
                minute="*/5",
                timezone="America/New_York",
            ),
            id="check_stock_loop",
            name="Risk / Position Check",
            replace_existing=True,
        )
        self.scheduler.start()
        self.scheduler.pause_job("check_stock_loop")

    def _sync_risk_checker(self):
        if self.portfolio.has_open_trades():
            if self.broker_status != "ACTIVE":
                self.broker_status = "ACTIVE"
                self.scheduler.resume_job("check_stock_loop")
                logger.info("Risk checker is now active.")
        else:
            if self.broker_status != "PAUSED":
                self.broker_status = "PAUSED"
                self.scheduler.pause_job("check_stock_loop")
                logger.info("Risk checker is now paused.")

    def _emit(self, event_type: str, payload: dict | None = None) -> None:
            """Publish a UI event without letting event failures break trading."""
            try:
                event_bus.publish(event_type, payload or {})
            except Exception:
                logger.exception("Failed to publish event: %s", event_type)
        
