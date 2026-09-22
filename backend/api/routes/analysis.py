from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trade_analyzer", tags=["trade-analyzer"])


@router.post("/news_check")
def news_check(request: Request):
    services = get_services(request)
    try:
        result = services.trade_analyzer.check_news()
        logger.info(
            "News check completed. status=%s actions_taken=%s",
            result.get("status"),
            result.get("actions_taken"),
        )
        return result

    except Exception as exc:
        logger.exception("Unable to check fresh news.")
        return {
            "status": "error",
            "message": f"Unable to check fresh news: {exc}",
            "actions_taken": None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

