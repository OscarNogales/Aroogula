from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Query

from backend.app.event_bus import event_bus
from backend.api.dependencies import get_services
from backend.api.responses import error_response

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/trade-journal")
def get_trade_journal(request: Request,
                      limit: int = Query(default=50, ge=1, le=500)):
    services = get_services(request)

    try:
        ledger = services.ledger

        recent_trades = ledger.get_recent(limit)
        recent_trades_dict = ledger.to_json_records(recent_trades)

        result = {
            "status": "success",
            "message": f"Succesfully retrieved {limit} events from Ledger",
            "data": {
                    "trades": recent_trades_dict
                }
            }

        logger.info(result["message"])
        return result
    except Exception as e:
        result = error_response(f"Unable to retrieve trade events from Ledger, error {e}")
        logger.error(result["message"])
        return result