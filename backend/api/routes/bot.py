from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from backend.api.schemas import ToggleCommand
from backend.api.dependencies import get_services

logger = logging.getLogger(__name__)
router = APIRouter(tags=["portfolio"])

@router.post("/api/bot/toggle")
def toggle_bot(command: ToggleCommand, request: Request):
    services = get_services(request)

    result = services.trade_analyzer.toggle_Aroogula(
        turn_on=command.turn_on
    )

    logger.info(result["message"])
    return result