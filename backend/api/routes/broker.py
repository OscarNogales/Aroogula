from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services
from backend.api.responses import error_response
from backend.api.schemas import BuyRequest, SellRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/broker", tags=["broker"])


@router.post("/liquidation")
def sell_everything(request: Request):
    services = get_services(request)
    try:
        result = services.broker.liquidate_all()
        logger.info("Liquidation request completed.")
        return result
    except Exception as exc:
        logger.exception("Unable to liquidate all positions.")
        return error_response(message=f"Unable to liquidate all positions: {exc}")


@router.post("/buy")
def buy_action(buy_request: BuyRequest, request: Request):
    services = get_services(request)
    try:
        result = services.broker.buy(
            ticker=buy_request.ticker,
            invest_amount=buy_request.amount,
            buy_reason="User-driven action.",
            news_id=f"MANUAL_{uuid4().hex[:6]}",
        )

        logger.info(
            "Manual buy request completed. ticker=%s amount=%.2f status=%s",
            buy_request.ticker,
            buy_request.amount,
            result.get("status"),
        )
        return result

    except Exception as exc:
        logger.exception(
            "Unable to complete manual buy. ticker=%s amount=%.2f",
            buy_request.ticker,
            buy_request.amount,
        )
        return error_response(
            message=f"Unable to buy ${buy_request.amount:.2f} of {buy_request.ticker}: {exc}",
        )


@router.post("/sell")
def sell_action(sell_request: SellRequest, request: Request):
    services = get_services(request)
    try:
        result = services.broker.sell(
            t_id=sell_request.trade_id,
            sell_reason="User-driven action.",
        )

        profit = result.get("data", {}).get("pnl_dollars")
        logger.info(
            "Manual sell request completed. trade_id=%s pnl=%s status=%s",
            sell_request.trade_id,
            profit,
            result.get("status"),
        )
        return result

    except Exception as exc:
        logger.exception("Unable to complete manual sell. trade_id=%s", sell_request.trade_id)
        return error_response(message=f"Unable to sell trade {sell_request.trade_id}: {exc}")


@router.post("/stock")
def check_stock(request: Request):
    services = get_services(request)
    try:
        result = services.broker.check_stock()
        data = result.get("data", {})

        logger.info(
            "Stock check completed. actions_taken=%s today_profit=%s status=%s",
            data.get("actions_taken"),
            data.get("today_profit", data.get("pnl_today")),
            result.get("status"),
        )
        return result

    except Exception as exc:
        logger.exception("Unable to perform stock check.")
        return error_response(message=f"Unable to perform stock check: {exc}")
