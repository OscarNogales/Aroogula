from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services
from backend.api.schemas import UpdateSettingsRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/get_settings")
def get_current_settings(request: Request):
    services = get_services(request)
    return services.settings.settings


@router.post("/update_settings")
def update_settings(update_request: UpdateSettingsRequest, request: Request):
    services = get_services(request)
    try:
        updated_dict = services.settings.update_settings(update_request.new_settings_dict)
        logger.info("Successfully updated settings.")
        return {
            "status": "success",
            "message": "Settings updated successfully.",
            "payload": updated_dict,
        }
    except Exception as exc:
        logger.exception("Unable to update settings.")
        return {
            "status": "error",
            "message": f"Unable to update settings: {exc}",
        }
