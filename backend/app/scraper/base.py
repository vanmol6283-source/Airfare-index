"""
scraper/base.py — Abstract base scraper and shared utilities.

Design principles:
  ▸ Ethical: respects robots.txt, uses configurable delays, sets
    a descriptive User-Agent identifying the research purpose.
  ▸ Resilient: exponential-backoff retries via tenacity.
  ▸ Observable: every run is logged in scrape_runs table.
  ▸ Extensible: each airline/OTA subclasses BaseScraper and
    implements `scrape_route(origin, dest, departure_date)`.
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import List, Optional, Dict, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.config import settings

logger = logging.getLogger(__name__)

# Research-identifying User-Agent (required for ethical scraping)
USER_AGENT = (
    "AirfarePriceIndexBot/1.0 "
    "(Research; CPI augmentation study; "
    "contact: research@airfareindex.in)"
)


class BaseScraper(ABC):
    """
    Abstract base class for all airline / OTA scrapers.

    Subclasses must implement:
        source_name: str   — identifier, e.g. "indigo.com"
        scrape_route()     — returns list of raw quote dicts
    """

    source_name: str = "unknown"

    def __init__(self):
        self.delay_min = settings.SCRAPING_DELAY_MIN_S
        self.delay_max = settings.SCRAPING_DELAY_MAX_S
        self.timeout = settings.SCRAPING_TIMEOUT_S

    # ── Public interface ──────────────────────────────────────────────────────

    async def collect_all_routes(
        self,
        collection_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Collect quotes for all basket routes × AP windows for a given date.
        Returns a flat list of raw quote dicts.
        """
        quotes: List[Dict[str, Any]] = []
        ap_windows = settings.AP_WINDOWS

        for route in settings.BASKET_ROUTES:
            origin, destination = route.split("-")
            for ap_days in ap_windows:
                departure_date = collection_date + timedelta(days=ap_days)
                try:
                    route_quotes = await self._scrape_with_delay(
                        origin, destination, departure_date, collection_date, ap_days
                    )
                    quotes.extend(route_quotes)
                    logger.debug(
                        "[%s] %s AP+%d → %d quotes",
                        self.source_name, route, ap_days, len(route_quotes),
                    )
                except Exception as exc:
                    logger.error(
                        "[%s] Failed %s AP+%d: %s",
                        self.source_name, route, ap_days, exc,
                    )

        logger.info("[%s] Total quotes collected: %d", self.source_name, len(quotes))
        return quotes

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _scrape_with_delay(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        collection_date: date,
        ap_days: int,
    ) -> List[Dict[str, Any]]:
        """Wrap scrape_route with random delay and attach metadata."""
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)

        raw = await self.scrape_route(origin, destination, departure_date)

        # Attach common metadata
        for q in raw:
            q.setdefault("collection_date", collection_date)
            q.setdefault("departure_date", departure_date)
            q.setdefault("ap_days", ap_days)
            q.setdefault("source", self.source_name)
            q.setdefault("origin", origin)
            q.setdefault("destination", destination)

        return raw

    # ── Abstract ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Fetch available fares for a single route and departure date.

        Returns a list of dicts with at minimum:
            base_fare: float
            total_fare: float
            carrier: str (optional)
            flight_number: str (optional)
            fare_class: str (optional)
            taxes: float (optional)
        """
        ...
