from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services
from backend.api.schemas import EquityGraphRequest, TickerGraphRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graphs", tags=["graphs"])


def _empty_graph_error(message: str) -> dict:
    return {
        "status": "error",
        "message": message,
        "time": None,
        "close": None,
        "open": None,
        "high": None,
        "low": None,
    }


@router.post("/equity_graph")
def equity_log_graph(request_data: EquityGraphRequest, request: Request):
    services = get_services(request)
    try:
        graph_data = services.equity_logger.equity_graph(time=request_data.time)
        logger.info("Successfully fetched equity history. time=%s", request_data.time)
        return graph_data

    except Exception as exc:
        logger.exception("Unable to fetch equity history. time=%s", request_data.time)
        return _empty_graph_error(f"Unable to fetch equity history: {exc}")


@router.post("/ticker_graph")
def ticker_graph(graph_request: TickerGraphRequest, request: Request):
    services = get_services(request)
    try:
        chart_data = services.chart_engine.tickerGraph(
            ticker=graph_request.ticker,
            period=graph_request.period,
            mean=graph_request.mean,
        )

        logger.info(
            "Successfully retrieved ticker graph. ticker=%s period=%s mean=%s",
            graph_request.ticker,
            graph_request.period,
            graph_request.mean,
        )
        return chart_data

    except Exception as exc:
        logger.exception(
            "Unable to retrieve ticker graph. ticker=%s period=%s mean=%s",
            graph_request.ticker,
            graph_request.period,
            graph_request.mean,
        )
        return _empty_graph_error(f"Unable to retrieve ticker graph: {exc}")
