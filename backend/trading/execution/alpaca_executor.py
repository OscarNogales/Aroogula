from .order_template import ExecutionResult

from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from threading import Thread, Event, Lock
from uuid import uuid4
from dataclasses import dataclass, field

import logging


logger = logging.getLogger(__name__)


@dataclass
class PendingOrder:
    event: Event = field(default_factory=Event)

    status: str = "NEW"

    filled_quantity: float | None = None
    filled_price: float | None = None

    broker_order_id: str | None = None

    message: str = "Order submitted to Alpaca."


class AlpacaExecutor:

    TERMINAL_EVENTS = {
        "fill",
        "canceled",
        "rejected",
        "expired",
    }

    def __init__(
        self,
        trading_client,
        trading_stream,
        mode: str,
        order_timeout: float = 10.0,
    ):
        self.client = trading_client
        self.stream = trading_stream
        self.mode = mode

        self.order_timeout = order_timeout

        self.pending_orders: dict[str, PendingOrder] = {}
        self.pending_lock = Lock()

        self.stream_thread: Thread | None = None

        self.stream.subscribe_trade_updates(
            self._on_trade_update
        )

    # -----------------------------------------------
    #               ASSET VALIDATION
    # -----------------------------------------------

    def _validate_asset(
        self,
        ticker: str,
        require_fractionable: bool = False,
    ):
        asset = self.client.get_asset(ticker)

        if not asset.tradable:
            raise RuntimeError(
                f"{ticker} is not tradable through Alpaca."
            )

        if require_fractionable and not asset.fractionable:
            raise RuntimeError(
                f"{ticker} does not support fractional trading through Alpaca."
            )

        return asset

    # -----------------------------------------------
    #                  STREAM
    # -----------------------------------------------

    def start_stream(self):
        if (
            self.stream_thread is not None
            and self.stream_thread.is_alive()
        ):
            logger.debug("Alpaca trading stream is already running.")
            return

        self.stream_thread = Thread(
            target=self._run_stream,
            name="alpaca-trading-stream",
            daemon=True,
        )

        self.stream_thread.start()

        logger.info(
            "Alpaca trading stream started. mode=%s",
            self.mode,
        )

    def _run_stream(self):
        try:
            self.stream.run()

        except Exception:
            logger.exception(
                "Alpaca trading stream stopped unexpectedly."
            )

    # -----------------------------------------------
    #             PENDING ORDER REGISTRY
    # -----------------------------------------------

    def _register_order(
        self,
        client_order_id: str,
        pending: PendingOrder,
    ):
        with self.pending_lock:
            self.pending_orders[client_order_id] = pending

    def _get_pending_order(
        self,
        client_order_id: str,
    ) -> PendingOrder | None:
        with self.pending_lock:
            return self.pending_orders.get(client_order_id)

    def _remove_order(
        self,
        client_order_id: str,
    ):
        with self.pending_lock:
            self.pending_orders.pop(client_order_id, None)

    # -----------------------------------------------
    #              TRADE UPDATE LISTENER
    # -----------------------------------------------

    async def _on_trade_update(self, data):
        order = data.order

        client_order_id = order.client_order_id
        event_name = str(data.event).lower()

        pending = self._get_pending_order(
            client_order_id
        )

        if pending is None:
            logger.debug(
                "Ignoring Alpaca event for unknown order. "
                "client_order_id=%s event=%s",
                client_order_id,
                event_name,
            )
            return

        pending.broker_order_id = str(order.id)

        if order.filled_qty is not None:
            pending.filled_quantity = float(
                order.filled_qty
            )

        if order.filled_avg_price is not None:
            pending.filled_price = float(
                order.filled_avg_price
            )

        # -------------------------------------------
        #                EVENT TYPES
        # -------------------------------------------

        if event_name == "partial_fill":
            pending.status = "PARTIALLY_FILLED"
            pending.message = (
                "Order partially filled; waiting "
                "for remaining quantity."
            )

        elif event_name == "fill":
            pending.status = "FILLED"
            pending.message = (
                "Order filled successfully."
            )

        elif event_name in {
            "canceled",
            "rejected",
            "expired",
        }:
            pending.status = event_name.upper()

            pending.message = (
                f"Alpaca order ended with "
                f"status {pending.status}."
            )

        # -------------------------------------------
        #                   LOGGER
        # -------------------------------------------

        logger.info(
            "Alpaca trade update | "
            "event=%s ticker=%s "
            "client_order_id=%s "
            "broker_order_id=%s "
            "filled_qty=%s "
            "filled_avg_price=%s",
            event_name,
            order.symbol,
            client_order_id,
            order.id,
            order.filled_qty,
            order.filled_avg_price,
        )


        if event_name in self.TERMINAL_EVENTS:
            pending.event.set()

    # -----------------------------------------------
    #           RESULT CONSTRUCTION
    # -----------------------------------------------

    def _build_result(
        self,
        *,
        ticker: str,
        client_order_id: str,
        pending: PendingOrder,
        requested_notional: float | None = None,
        requested_quantity: float | None = None,
    ) -> ExecutionResult:

        final_status = pending.status

        if (
            final_status in {
                "CANCELED",
                "EXPIRED",
            }
            and pending.filled_quantity is not None
            and pending.filled_quantity > 0
        ):
            final_status = "PARTIALLY_FILLED"

        return ExecutionResult(
            status=final_status,
            ticker=ticker,
            mode=self.mode,

            requested_notional=requested_notional,
            requested_quantity=requested_quantity,

            filled_quantity=pending.filled_quantity,
            filled_price=pending.filled_price,

            broker_order_id=pending.broker_order_id,
            client_order_id=client_order_id,

            message=pending.message,
        )

    # -----------------------------------------------
    #                   BUY
    # -----------------------------------------------

    def buy(
        self,
        ticker: str,
        amount: float,
    ) -> ExecutionResult:

        ticker = ticker.upper().strip()

        try:
            if not ticker:
                raise RuntimeError(
                    "Ticker cannot be empty."
                )

            if amount <= 0:
                raise RuntimeError(
                    "Buy amount must be greater than zero."
                )

            self._validate_asset(
                ticker,
                require_fractionable=True,
            )

            client_order_id = (
                f"AROOGULA-{ticker}-BUY-{uuid4()}"
            )

            pending = PendingOrder()

            self._register_order(
                client_order_id,
                pending,
            )

            order_request = MarketOrderRequest(
                symbol=ticker,
                notional=float(amount),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                client_order_id=client_order_id,
            )

            submitted_order = self.client.submit_order(
                order_data=order_request
            )

            pending.broker_order_id = str(
                submitted_order.id
            )

            logger.info(
                "Alpaca BUY submitted | "
                "ticker=%s amount=$%.2f "
                "client_order_id=%s "
                "broker_order_id=%s",
                ticker,
                amount,
                client_order_id,
                submitted_order.id,
            )

            finished = pending.event.wait(
                timeout=self.order_timeout
            )

            if not finished:
                logger.warning(
                    "Timed out waiting for Alpaca BUY | "
                    "ticker=%s client_order_id=%s "
                    "broker_order_id=%s",
                    ticker,
                    client_order_id,
                    pending.broker_order_id,
                )

                return ExecutionResult(
                    status="PENDING",
                    ticker=ticker,
                    mode=self.mode,
                    requested_notional=amount,
                    requested_quantity=None,
                    filled_quantity=pending.filled_quantity,
                    filled_price=pending.filled_price,
                    broker_order_id=pending.broker_order_id,
                    client_order_id=client_order_id,
                    message=(
                        "Timed out waiting for a terminal "
                        "Alpaca order event."
                    ),
                )

            result = self._build_result(
                ticker=ticker,
                client_order_id=client_order_id,
                pending=pending,
                requested_notional=amount,
            )

            self._remove_order(
                client_order_id
            )

            logger.info(
                "Alpaca BUY completed | %s",
                result,
            )

            return result

        except Exception as e:
            logger.exception(
                "Unable to process Alpaca BUY for %s",
                ticker,
            )

            return ExecutionResult(
                status="FAILED",
                ticker=ticker,
                mode=self.mode,
                requested_notional=amount,
                requested_quantity=None,
                filled_quantity=None,
                filled_price=None,
                broker_order_id=None,
                client_order_id=None,
                message=str(e),
            )

    # -----------------------------------------------
    #                   SELL
    # -----------------------------------------------

    def sell(
        self,
        ticker: str,
        shares: float,
    ) -> ExecutionResult:

        ticker = ticker.upper().strip()

        try:
            if not ticker:
                raise RuntimeError(
                    "Ticker cannot be empty."
                )

            if shares <= 0:
                raise RuntimeError(
                    "Sell quantity must be greater than zero."
                )

            fractional = not float(shares).is_integer()

            self._validate_asset(
                ticker,
                require_fractionable=fractional,
            )

            client_order_id = (
                f"AROOGULA-{ticker}-SELL-{uuid4()}"
            )

            pending = PendingOrder()

            self._register_order(
                client_order_id,
                pending,
            )

            order_request = MarketOrderRequest(
                symbol=ticker,
                qty=float(shares),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                client_order_id=client_order_id,
            )

            submitted_order = self.client.submit_order(
                order_data=order_request
            )

            pending.broker_order_id = str(
                submitted_order.id
            )

            logger.info(
                "Alpaca SELL submitted | "
                "ticker=%s shares=%.9f "
                "client_order_id=%s "
                "broker_order_id=%s",
                ticker,
                shares,
                client_order_id,
                submitted_order.id,
            )

            finished = pending.event.wait(
                timeout=self.order_timeout
            )

            if not finished:
                logger.warning(
                    "Timed out waiting for Alpaca SELL | "
                    "ticker=%s client_order_id=%s "
                    "broker_order_id=%s",
                    ticker,
                    client_order_id,
                    pending.broker_order_id,
                )

                return ExecutionResult(
                    status="PENDING",
                    ticker=ticker,
                    mode=self.mode,
                    requested_notional=None,
                    requested_quantity=shares,
                    filled_quantity=pending.filled_quantity,
                    filled_price=pending.filled_price,
                    broker_order_id=pending.broker_order_id,
                    client_order_id=client_order_id,
                    message=(
                        "Timed out waiting for a terminal "
                        "Alpaca order event."
                    ),
                )

            result = self._build_result(
                ticker=ticker,
                client_order_id=client_order_id,
                pending=pending,
                requested_quantity=shares,
            )

            self._remove_order(
                client_order_id
            )

            logger.info(
                "Alpaca SELL completed | %s",
                result,
            )

            return result

        except Exception as e:
            logger.exception(
                "Unable to process Alpaca SELL for %s",
                ticker,
            )

            return ExecutionResult(
                status="FAILED",
                ticker=ticker,
                mode=self.mode,
                requested_notional=None,
                requested_quantity=shares,
                filled_quantity=None,
                filled_price=None,
                broker_order_id=None,
                client_order_id=None,
                message=str(e),
            )