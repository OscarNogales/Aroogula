from __future__ import annotations

import logging

import pandas as pd
from fastapi import APIRouter

from backend.config import paths

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/list")
def get_companies():
    try:
        companies = pd.read_csv(paths.COMPANIES_CSV_PATH)
        logger.info("Successfully fetched companies list.")
        return {
            "status": "success",
            "message": "Successfully fetched all analyzed companies.",
            "payload": companies.to_dict("records"),
        }
    except Exception as exc:
        logger.exception("Unable to fetch companies list.")
        return {
            "status": "error",
            "message": f"Unable to fetch companies list: {exc}",
        }
