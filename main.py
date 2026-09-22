"""Main FastAPI entrypoint for the Aroogula trading backend.

This file intentionally stays small. It configures logging, creates the service
container, and mounts API routers. Backend code lives under backend/, grouped by responsibility. Route handlers
live in backend/api/routes/.
"""

from __future__ import annotations

import logging

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.api.routes.broker import router as broker_router
from backend.api.routes.companies import router as company_router
from backend.api.routes.dossiers import router as dossier_router
from backend.api.routes.graphs import router as graph_router
from backend.api.routes.news import router as news_feeder_router
from backend.api.routes.portfolio import router as portfolio_router
from backend.api.routes.settings import router as settings_router
from backend.api.routes.analysis import router as trade_analyzer_router
from backend.api.routes.events import router as events_router
from backend.api.routes.scheduler import router as scheduler_router
from backend.api.routes.bot import router as start_bot_router
from backend.api.routes.journal import router as trade_journal_router

from backend.config import paths
from backend.app.services import create_services

from backend.config.logging import setup_logging

paths.ensure_directories()
setup_logging(paths.APP_LOG_PATH)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aroogula Trading Backend")

# Dist
BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "dist"

app.mount(
    "/js",
    StaticFiles(directory=DIST_DIR / "js"),
    name="js",
)

app.mount(
    "/styles",
    StaticFiles(directory=DIST_DIR / "styles"),
    name="styles",
)

# app.mount(
#    "/assets",
#    StaticFiles(directory=DIST_DIR / "assets"),
#    name="assets",
# )

@app.get("/")
def serve_frontend():
    return FileResponse(DIST_DIR / "index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:1430",
        "http://localhost:1430",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.state.services = create_services()

app.include_router(settings_router)
app.include_router(company_router)
app.include_router(news_feeder_router)
app.include_router(dossier_router)
app.include_router(portfolio_router)
app.include_router(broker_router)
app.include_router(trade_analyzer_router)
app.include_router(graph_router)
app.include_router(events_router)
app.include_router(scheduler_router)
app.include_router(start_bot_router)
app.include_router(trade_journal_router)

logger.info("Aroogula backend initialized successfully.")
