from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services
from backend.api.responses import error_response

from backend.analytics.portfolio_snapshot import make_enriched_positions

logger = logging.getLogger(__name__)
router = APIRouter(tags=["portfolio"])


@router.get("/api/wallet/balance")
def get_wallet_balance(request: Request):
    services = get_services(request)
    try:
        balance = services.wallet.get_balance()
        logger.info("Successfully retrieved wallet balance.")
        return balance
    except Exception as exc:
        logger.exception("Failed to retrieve wallet balance.")
        return error_response(message=f"Failed to retrieve wallet balance: {exc}")


@router.get("/api/portfolio/positions")
def get_portfolio_positions(request: Request):
    services = get_services(request)
    try:
        positions = services.portfolio.get_positions()
        logger.info("Successfully retrieved portfolio positions.")
        return positions
    except Exception as exc:
        logger.exception("Unable to retrieve portfolio positions.")
        return error_response(message=f"Unable to retrieve portfolio positions: {exc}")

@router.get("/api/portfolio/enriched_positions")
def get_portfolio_enriched_positions(request: Request):
    services = get_services(request)

    try:
        result = services.portfolio.get_positions()
        raw_positions = result["data"]["positions"]
        market_data = services.trade_analyzer.market_data
        for position in raw_positions:
            make_enriched_positions(position, market_data)
        return result

    except Exception as exc:
        logger.exception("Unable to make the enriched portfolio positions.")
        return error_response(
            message=f"Unable to retrieve enriched portfolio positions: {exc}"
        )
        


@router.get("/api/portfolio/equity_summary")
def get_equity_summary(request: Request):
    services = get_services(request)
    try:
        summary = services.equity_summary.get_summary()
        logger.info("Successfully retrieved equity summary.")
        return summary
    except Exception as exc:
        logger.exception("Unable to retrieve equity summary.")
        return error_response(message=f"Unable to retrieve equity summary: {exc}")
