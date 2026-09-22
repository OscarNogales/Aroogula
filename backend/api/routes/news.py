from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services
from backend.api.schemas import ToggleCommand

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/toggle", tags=["news-feeder"])


def _toggle_response(source: str, state: bool) -> dict:
    return {
        "status": "success",
        f"{source}_is_on": state,
    }


@router.post("/edgar")
def toggle_edgar(command: ToggleCommand, request: Request):
    services = get_services(request)
    try:
        services.news_feeder.toggle_EDGARBot(turn_on=command.turn_on)
        logger.info("EDGAR toggle updated. state=%s", command.turn_on)
        return _toggle_response("edgar", command.turn_on)
    except Exception:
        logger.exception("Failed to update EDGAR toggle. requested_state=%s", command.turn_on)
        return {
            "status": "error",
            "message": "Unable to update EDGAR toggle.",
            "requested_state": command.turn_on,
        }


@router.post("/bloomberg")
def toggle_bloomberg(command: ToggleCommand, request: Request):
    services = get_services(request)
    try:
        services.news_feeder.toggle_BloombergBot(turn_on=command.turn_on)
        logger.info("Bloomberg toggle updated. state=%s", command.turn_on)
        return _toggle_response("bloomberg", command.turn_on)
    except Exception:
        logger.exception("Failed to update Bloomberg toggle. requested_state=%s", command.turn_on)
        return {
            "status": "error",
            "message": "Unable to update Bloomberg toggle.",
            "requested_state": command.turn_on,
        }


@router.post("/yahoo")
def toggle_yahoo(command: ToggleCommand, request: Request):
    services = get_services(request)
    try:
        services.news_feeder.toggle_YahooBot(turn_on=command.turn_on)
        logger.info("Yahoo toggle updated. state=%s", command.turn_on)
        return _toggle_response("yahoo", command.turn_on)
    except Exception:
        logger.exception("Failed to update Yahoo toggle. requested_state=%s", command.turn_on)
        return {
            "status": "error",
            "message": "Unable to update Yahoo toggle.",
            "requested_state": command.turn_on,
        }


@router.post("/forbes")
def toggle_forbes(command: ToggleCommand, request: Request):
    services = get_services(request)
    try:
        services.news_feeder.toggle_ForbesBot(turn_on=command.turn_on)
        logger.info("Forbes toggle updated. state=%s", command.turn_on)
        return _toggle_response("forbes", command.turn_on)
    except Exception:
        logger.exception("Failed to update Forbes toggle. requested_state=%s", command.turn_on)
        return {
            "status": "error",
            "message": "Unable to update Forbes toggle.",
            "requested_state": command.turn_on,
        }
