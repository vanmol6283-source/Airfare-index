"""
scraper/serpapi_scraper.py — Google Flights data via SerpAPI.

SerpAPI wraps Google Flights and returns structured JSON — no browser,
no CAPTCHA, no IP bans. Data comes from Google's flight index which
aggregates fares from all major Indian carriers.

Free tier: 250 searches/month
  → 8 routes × 5 AP windows = 40 calls per run
  → Fits: 6 full runs/month (weekly+ cadence)
  → Recommended: reduce AP windows to 3 (T+7, T+14, T+30) = 24 calls/run
    giving 10 runs/month comfortably

API endpoint:
  GET https://serpapi.com/search
  Params:
    engine          = google_flights
    departure_id    = {IATA origin}       e.g. DEL
    arrival_id      = {IATA dest}         e.g. BOM
    outbound_date   = {YYYY-MM-DD}
    currency        = INR
    hl              = en
    type            = 2                   (1=round trip, 2=one-way)
    travel_class    = 1                   (1=Economy, 2=Premium Eco, 3=Business)
    adults          = 1
    api_key         = {SERPAPI_KEY}

Response structure (relevant fields):
  {
    "best_flights": [
      {
        "flights": [
          {
            "airline": "IndiGo",
            "airline_logo": "https://...",
            "flight_number": "6E-123",
            "departure_airport": { "id": "DEL", ... },
            "arrival_airport":   { "id": "BOM", ... }
          }
        ],
        "price": 4250,          ← total fare in INR (what we store as total_fare)
        "type": "One way"
      }
    ],
    "other_flights": [ ... ],   ← same structure, more options
    "price_insights": {
      "lowest_price": 3800,
      "typical_price_range": [3500, 5200],
      "price_level": "low"      ← "low" | "typical" | "high" | "high"
    }
  }

Error handling:
  401 → Invalid API key. Log error, return [], do not crash pipeline.
  402 → Quota exceeded (250/month hit). Log warning, return [].
  429 → Rate limit (10 req/s). Wait 60s, retry once.
  Empty response → No flights on that route/date. Return [] gracefully.
  Any exception → Log + return []. Pipeline continues with partial data.

Note on base fare:
  Google Flights shows the total fare (base + taxes + fees).
  There is no separate base/taxes breakdown in the SerpAPI response.
  We estimate: base_fare = total / 1.18 (18% GST approximation).
  This is the same estimation used by the mock scraper and OTA scrapers.
  For a CPI research index, this consistency is more important than
  absolute accuracy of the base/tax split.
"""

import asyncio
import logging
import time
from datetime import date
from typing import Any, Dict, List, Optional

import requests

from app.scraper.base import BaseScraper
from app.config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SERPAPI_BASE_URL = "https://serpapi.com/search"

REQUEST_TIMEOUT_S = 20     # SerpAPI is fast; 20s is generous
RATE_LIMIT_WAIT_S = 60     # Wait 60s on 429 before retry
MAX_QUOTES_PER_ROUTE = 8   # Cap quotes extracted per route

# Airline display name → IATA carrier code
# Google Flights uses full airline names; we map to standard codes
AIRLINE_NAME_TO_CODE: Dict[str, str] = {
    "indigo": "6E",
    "air india": "AI",
    "air india express": "IX",
    "akasa": "QP",
    "akasa air": "QP",
    "spicejet": "SG",
    "go first": "G8",
    "go airlines": "G8",
    "vistara": "UK",
    "alliance air": "CD",
    "star air": "S5",
    "blue dart aviation": "BZ",
}


class SerpApiScraper(BaseScraper):
    """
    Google Flights scraper using the SerpAPI intermediary service.

    Uses simple HTTP requests (no browser, no Playwright).
    Runs in an executor thread pool so it doesn't block the async pipeline.

    Quota management:
      - Logs a warning when 402 is returned (quota exhausted)
      - After a 402, all subsequent routes in the same run return []
        (no point burning retries when quota is gone for the month)
    """

    source_name = "serpapi.com (google_flights)"

    def __init__(self):
        super().__init__()
        self._api_key = settings.SERPAPI_KEY
        self._quota_exhausted = False   # Set True on 402 — skip rest of run

    # ── Public interface (called by BaseScraper.collect_all_routes) ───────────

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Fetch Google Flights data for one route/date via SerpAPI.

        Runs the synchronous HTTP call in a thread pool executor
        so it doesn't block the async event loop.
        """
        if self._quota_exhausted:
            logger.debug(
                "[SerpAPI] Quota exhausted — skipping %s→%s", origin, destination
            )
            return []

        if not self._api_key:
            logger.error(
                "[SerpAPI] SERPAPI_KEY not set in .env — cannot fetch real data"
            )
            return []

        loop = asyncio.get_event_loop()
        quotes = await loop.run_in_executor(
            None,   # default thread pool
            self._fetch_sync,
            origin,
            destination,
            departure_date,
        )
        return quotes

    # ── Synchronous HTTP call (runs in thread pool) ───────────────────────────

    def _fetch_sync(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Make the SerpAPI HTTP request and parse the response.

        Returns a list of fare quote dicts on success.
        Returns [] on any error, quota exhaustion, or empty results.
        Never raises — all exceptions are caught and logged.
        """
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date.isoformat(),
            "currency": "INR",
            "hl": "en",
            "type": "2",            # one-way
            "travel_class": "1",    # economy
            "adults": "1",
            "api_key": self._api_key,
        }

        try:
            response = requests.get(
                SERPAPI_BASE_URL,
                params=params,
                timeout=REQUEST_TIMEOUT_S,
            )
        except requests.Timeout:
            logger.error(
                "[SerpAPI] Timeout after %ds for %s→%s dep=%s",
                REQUEST_TIMEOUT_S, origin, destination, departure_date,
            )
            return []
        except requests.ConnectionError as exc:
            logger.error(
                "[SerpAPI] Connection error for %s→%s: %s",
                origin, destination, exc,
            )
            return []

        # ── HTTP status handling ──────────────────────────────────────────────

        if response.status_code == 401:
            logger.error(
                "[SerpAPI] 401 Unauthorized — check SERPAPI_KEY in .env. "
                "Key value used: %s...", self._api_key[:8] if self._api_key else "empty"
            )
            return []

        if response.status_code == 402:
            logger.warning(
                "[SerpAPI] 402 Payment Required — monthly quota of 250 searches "
                "is exhausted. Remaining routes will use web scrapers as fallback. "
                "Quota resets on the 1st of next month."
            )
            self._quota_exhausted = True
            return []

        if response.status_code == 429:
            logger.warning(
                "[SerpAPI] 429 Rate limit hit for %s→%s — "
                "waiting %ds before retry", origin, destination, RATE_LIMIT_WAIT_S
            )
            time.sleep(RATE_LIMIT_WAIT_S)
            # Single retry after rate-limit wait
            try:
                response = requests.get(
                    SERPAPI_BASE_URL, params=params, timeout=REQUEST_TIMEOUT_S
                )
            except Exception:
                return []

        if response.status_code != 200:
            logger.error(
                "[SerpAPI] HTTP %d for %s→%s dep=%s",
                response.status_code, origin, destination, departure_date,
            )
            return []

        # ── Parse JSON response ───────────────────────────────────────────────

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("[SerpAPI] Invalid JSON response: %s", exc)
            return []

        # Check for SerpAPI-level error messages
        if "error" in data:
            logger.error("[SerpAPI] API error: %s", data["error"])
            return []

        quotes = self._parse_response(data, origin, destination)

        logger.info(
            "[SerpAPI] %s→%s dep=%s → %d quotes (search used 1 of 250/month)",
            origin, destination, departure_date, len(quotes),
        )
        return quotes

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse_response(
        self,
        data: dict,
        origin: str,
        destination: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract fare quotes from SerpAPI Google Flights response.

        Combines best_flights and other_flights arrays.
        Each element becomes one quote dict.
        Caps at MAX_QUOTES_PER_ROUTE to avoid bloating the DB.
        """
        all_offers = []
        all_offers.extend(data.get("best_flights", []))
        all_offers.extend(data.get("other_flights", []))

        if not all_offers:
            logger.info(
                "[SerpAPI] No flights found for %s→%s — "
                "route may have no service on this date", origin, destination,
            )
            return []

        quotes: List[Dict[str, Any]] = []
        for offer in all_offers[:MAX_QUOTES_PER_ROUTE]:
            quote = self._parse_offer(offer)
            if quote:
                quotes.append(quote)

        return quotes

    def _parse_offer(self, offer: dict) -> Optional[Dict[str, Any]]:
        """
        Parse a single flight offer from SerpAPI response.

        Extracts:
          - total_fare from offer["price"]
          - carrier code from offer["flights"][0]["airline"]
          - flight number from offer["flights"][0]["flight_number"]
          - estimates base_fare as total / 1.18 (18% GST approximation)

        Returns None if the offer is malformed or fare is invalid.
        """
        try:
            total_fare = float(offer.get("price", 0))
        except (TypeError, ValueError):
            return None

        if total_fare <= 0:
            return None

        # Carrier detection from first flight segment
        carrier_code = "XX"
        flight_number = None
        flights = offer.get("flights", [])
        if flights:
            first_flight = flights[0]
            airline_name = first_flight.get("airline", "")
            carrier_code = _resolve_carrier(airline_name) or "XX"
            flight_number = first_flight.get("flight_number")

        # Estimate base fare (Google Flights shows total including all taxes)
        base_fare = round(total_fare / 1.18, -1)
        taxes = round(total_fare - base_fare, 2)

        # Sanity bounds
        if not (500 <= base_fare <= 60_000):
            return None

        return {
            "carrier": carrier_code,
            "flight_number": flight_number,
            "fare_class": "Y",          # Economy (we always request economy)
            "base_fare": base_fare,
            "taxes": taxes,
            "udf": 0,                   # Included in Google Flights total
            "convenience_fee": 0,
            "total_fare": total_fare,
        }


# ── Utility ───────────────────────────────────────────────────────────────────

def _resolve_carrier(airline_name: str) -> Optional[str]:
    """Map full airline name to IATA code. Case-insensitive substring match."""
    if not airline_name:
        return None
    name = airline_name.strip().lower()
    for key, code in AIRLINE_NAME_TO_CODE.items():
        if key in name:
            return code
    return None
