"""
main.py — FastAPI application entry point.

Provides:
  GET  /api/v1/summary
  GET  /api/v1/basket
  GET  /api/v1/index-history
  GET  /api/v1/route/{id}
  GET  /api/v1/data-quality
  GET  /api/v1/scrape-runs
  POST /api/v1/trigger-scrape
  GET  /health
  GET  /docs          (Swagger UI)
  GET  /redoc         (ReDoc)
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base
from app.api import summary, basket, history, data_quality
from app.scraper.scheduler import start_scheduler, stop_scheduler

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Creating database tables…")
    Base.metadata.create_all(bind=engine)
    logger.info("Starting background scheduler…")
    start_scheduler()
    logger.info("Application startup complete.")
    yield
    # Shutdown
    stop_scheduler()
    logger.info("Application shutdown.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "REST API for the Airfare Price Index (APIx) — "
        "a real-time domestic aviation price monitor for India. "
        "Designed for consumption by statistical organisations, "
        "policy bodies, and researchers."
    ),
    contact={
        "name": "APIx Research Team",
        "email": "research@airfareindex.in",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = settings.API_PREFIX

app.include_router(summary.router, prefix=PREFIX, tags=["Index Summary"])
app.include_router(basket.router, prefix=PREFIX, tags=["Basket & Routes"])
app.include_router(history.router, prefix=PREFIX, tags=["Index History"])
app.include_router(data_quality.router, prefix=PREFIX, tags=["Data Quality"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    return JSONResponse({
        "status": "ok",
        "version": settings.APP_VERSION,
        "database": settings.DATABASE_URL.split("///")[0],
    })


# ── Root redirect ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return JSONResponse({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    })
