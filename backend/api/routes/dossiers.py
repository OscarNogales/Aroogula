from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dossiers", tags=["dossiers"])


@router.get("/{ticker}")
def get_dossier(ticker: str, request: Request):
    services = get_services(request)
    try:
        dossier = services.dossiers.get(ticker)

        if not dossier:
            logger.warning("No dossier found. ticker=%s", ticker)
            return {
                "status": "error",
                "message": f"No dossier found for {ticker}.",
                "payload": None,
            }

        logger.info("Successfully fetched dossier. ticker=%s", ticker)
        return {
            "status": "success",
            "message": f"Successfully fetched dossier for {ticker}.",
            "payload": str(dossier),
        }

    except Exception as e:
        logger.exception("Error fetching dossier. ticker=%s", ticker)
        return {
            "status": "error",
            "message": f"Could not get dossier associated with {ticker}: {e}",
            "payload": None,
        }


@router.get("/profile/{ticker}")
def get_company_profile(ticker: str, request: Request):
    services = get_services(request)

    try:
        profile = services.dossiers.get_profile(ticker)

        logger.info("Successfully fetched profile. ticker=%s", ticker)

        return {
            "status": "success",
            "message": f"Successfully fetched company profile for {ticker}.",
            "payload": profile,
        }

    except Exception as e:
        logger.exception("Error fetching profile. ticker=%s", ticker)

        return {
            "status": "error",
            "message": f"Could not get company profile associated with {ticker}: {e}",
            "payload": {
                "ticker": ticker,
                "name": ticker,
                "sector": "Unknown",
                "industry": "Unknown",
                "market_cap_label": "N/A",
                "revenue_trend": "N/A",
                "risk_level": "N/A",
                "outlook": "N/A",
                "summary": "",
                "logo_ticker": ticker,
            },
        }