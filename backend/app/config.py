"""
config.py — Application configuration

All settings are read from environment variables / .env file.
Defaults are tuned for local development.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────────────────────
    APP_NAME: str = "Airfare Price Index API"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = False

    # ── Database ────────────────────────────────────────────────────────────
    # SQLite by default — swap for postgresql+asyncpg://... in production
    DATABASE_URL: str = "sqlite:///./airfare_index.db"

    # ── API ─────────────────────────────────────────────────────────────────
    API_PREFIX: str = "/api/v1"
    API_KEY: str = "dev-api-key-change-in-production"

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Frontend dev server + production Vercel origins
    CORS_ORIGINS: List[str] = [
        # Local dev
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:3000",
        # Vercel production + preview deployments
        "https://airfare-index.vercel.app",
    ]
    # Allow all *.vercel.app subdomains (set via CORS_ORIGIN_REGEX env var)
    CORS_ORIGIN_REGEX: str = r"https://.*\.vercel\.app"

    # ── Scraping ─────────────────────────────────────────────────────────────
    SCRAPING_ENABLED: bool = False        # Set True when live scraping is desired

    # Per-request delays (randomised between min and max for ethical scraping)
    # Raised from 3-8s → 5-12s because we run 3 slots/day per site
    SCRAPING_DELAY_MIN_S: float = 5.0
    SCRAPING_DELAY_MAX_S: float = 12.0

    # Pause between scrapers within one slot (lets the site breathe)
    SCRAPING_INTER_SOURCE_PAUSE_S: float = 60.0

    SCRAPING_MAX_RETRIES: int = 3
    SCRAPING_TIMEOUT_S: int = 45         # Raised: airline SPAs load slowly


    # ── Amadeus API (official, no bot blocking) ───────────────────────────────
    # Register free at https://developers.amadeus.com
    AMADEUS_API_KEY: str = ""
    AMADEUS_API_SECRET: str = ""

    # ── SerpAPI (Google Flights data) ─────────────────────────────────────────
    # Register at https://serpapi.com — 250 free searches/month
    # When set, SerpApiScraper is used (after Amadeus check, before web scrapers)
    SERPAPI_KEY: str = ""

    # ── Index construction ────────────────────────────────────────────────────
    BASE_PERIOD_DATE: str = "2026-05-29"  # APIx = 100 on this date

    # ── Scheduler ────────────────────────────────────────────────────────────
    # Cron expression for daily scrape (09:30 IST = 04:00 UTC)
    SCRAPE_CRON: str = "0 4 * * *"

    # ── Routes in the basket ─────────────────────────────────────────────────
    BASKET_ROUTES: List[str] = [
        "DEL-BOM",
        "DEL-BLR",
        "BOM-BLR",
        "DEL-CCU",
        "BLR-HYD",
        "MAA-DEL",
        "DEL-HYD",
        "BOM-CCU",
    ]

    # ── AP windows (days before departure) ──────────────────────────────────
    # Problem statement specifies: T+1, T+7, T+15, T+30, T+45
    # (Previous incorrect values were T+14 and T+60 — now corrected)
    AP_WINDOWS: List[int] = [1, 7, 15, 30, 45]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"     # ignore system env vars like DEBUG, PATH etc.


settings = Settings()
