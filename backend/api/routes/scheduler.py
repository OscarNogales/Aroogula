from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from backend.api.dependencies import get_services
from backend.api.responses import error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


def get_scheduler_jobs(owner: str, scheduler) -> list[dict[str, Any]]:
    if scheduler is None:
        return []

    jobs = []

    for job in scheduler.get_jobs():
        jobs.append({
            "owner": owner,
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return jobs


@router.get("/status")
def scheduler_status(request: Request):
    services = get_services(request)

    try:
        bot_status = str(services.state.data.get("bot_status", "PAUSED"))

        jobs = []

        schedulers = [
            ("trade_analyzer", getattr(services.trade_analyzer, "scheduler", None)),
            ("broker", getattr(services.broker, "scheduler", None)),
            ("news_feeder", getattr(services.news_feeder, "scheduler", None)),
            ("dossiers", getattr(services.dossiers, "scheduler", None))
        ]


        for owner, scheduler in schedulers:
            jobs.extend(
                get_scheduler_jobs(owner, scheduler)
            )

        return {
            "status": "success",
            "message": "Successfully retrieved scheduler status.",
            "data": {
                "bot_status": bot_status,
                "jobs": jobs,
            },
        }

    except Exception as exc:
        logger.exception("Unable to retrieve scheduler status.")
        return error_response(
            message=f"Unable to retrieve scheduler status: {exc}"
        )