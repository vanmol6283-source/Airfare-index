"""
scraper/amadeus_scraper.py — Real-time fare data via Amadeus Flight Offers Search API.

Why this approach:
  ▸ Official, legal API — no bot blocking, no CAPTCHA, no IP bans
  ▸ Free tier: 2,000 API calls/month (enough for daily basket updates)
  ▸ Returns IATA-standard fare breakdown: base + taxes separately
  ▸ Covers all Indian carriers (6E, AI, SG, QP, G8, etc.)
  ▸ Rate limit: 10 req/s — our scheduler adds delays anyway

Setup:
  1. Register at https://developers.amadeus.com
  2. Create app → get AMADEUS_API_KEY and AMADEUS_API_SECRET
  3. Add both to backend/.env (see bottom of this file)
  4. pip install amadeus
  5. Set SCRAPING_ENABLED=true in .env

Free tier limits (as of 2026):
  - 2,000 calls/month on test environment
  - Production tier requires business registration (free for research)
  - Test env uses cached/near-real data — perfectly fine for an index
"""

import asyncio
import logging
from datetime import date
from typing import List, Dict, Any, Optional

from app.scraper.base import BaseScraper
from app.config import settings

logger = logging.getLogger(__name__)


class AmadeusScraper(BaseScraper):
    """
    Real-time fare scraper using Amadeus Flight Offers Search API.

    Covers all IATA carriers operating Indian domestic routes.
    Returns economy class fare breakdown per flight offer.
    """

    source_name = "amadeus.com"

    def __init__(self):
        super().__init__()
        self._client = None  # lazy-init so import errors are clear

    def _get_client(self):
        """Lazy-initialise the Amadeus SDK client."""
        if self._client is not None:
            return self._client

        try:
            from amadeus import Client, ResponseError  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Amadeus SDK not installed. Run: pip install amadeus"
            )

        api_key = getattr(settings, "AMADEUS_API_KEY", None)
        api_secret = getattr(settings, "AMADEUS_API_SECRET", None)

        if not api_key or not api_secret:
            raise RuntimeError(
                "AMADEUS_API_KEY and AMADEUS_API_SECRET must be set in .env. "
                "Register free at https://developers.amadeus.com"
            )

        from amadeus import Client
        self._client = Client(
            client_id=api_key,
            client_secret=api_secret,
            # Use "production" once you get production access
            # hostname="production",
            hostname="test",          # free test environment
            log_level="silent",
        )
        return self._client

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Fetch live economy fares for a single route/date via Amadeus API.

        The Amadeus SDK is synchronous — we run it in a thread pool
        so it doesn't block the async event loop.
        """
        loop = asyncio.get_event_loop()
        quotes = await loop.run_in_executor(
            None,  # default thread pool
            self._fetch_sync,
            origin,
            destination,
            departure_date,
        )
        return quotes

    def _fetch_sync(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """Synchronous Amadeus API call (runs in thread pool)."""
        try:
            from amadeus import ResponseError
            client = self._get_client()

            response = client.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=departure_date.isoformat(),
                adults=1,
                travelClass="ECONOMY",
                currencyCode="INR",
                max=10,          # up to 10 offers per route
                nonStop="false", # include connecting flights
            )

            quotes = []
            for offer in response.data:
                parsed = _parse_offer(offer, origin, destination)
                if parsed:
                    quotes.append(parsed)

            logger.debug(
                "[Amadeus] %s→%s dep=%s → %d quotes",
                origin, destination, departure_date, len(quotes),
            )
            return quotes

        except Exception as exc:
            # ResponseError covers 429, auth failures, etc.
            logger.error(
                "[Amadeus] %s→%s dep=%s → error: %s",
                origin, destination, departure_date, exc,
            )
            return []


def _parse_offer(offer: dict, origin: str, destination: str) -> Optional[Dict[str, Any]]:
    """
    Extract fare components from an Amadeus Flight Offer object.

    Amadeus returns:
        price.grandTotal       — total including taxes (INR)
        price.base             — base fare (INR)
        price.fees             — list of fee breakdowns
        validatingAirlineCodes — list of marketing carriers
        itineraries[0].segments[0].carrierCode — operating carrier
    """
    try:
        price = offer.get("price", {})
        base_fare = float(price.get("base", 0))
        total_fare = float(price.get("grandTotal", 0))

        if base_fare <= 0 or total_fare <= 0:
            return None

        taxes = total_fare - base_fare

        # Carrier code from first segment
        carrier = None
        itineraries = offer.get("itineraries", [])
        if itineraries:
            segments = itineraries[0].get("segments", [])
            if segments:
                carrier = segments[0].get("carrierCode")

        # Flight number from first segment
        flight_number = None
        if itineraries and itineraries[0].get("segments"):
            seg = itineraries[0]["segments"][0]
            flight_number = f"{seg.get('carrierCode', '')}{seg.get('number', '')}"

        return {
            "carrier": carrier,
            "flight_number": flight_number,
            "fare_class": "Y",          # Economy
            "base_fare": round(base_fare, 2),
            "taxes": round(taxes, 2),
            "udf": 0,                   # included in taxes by Amadeus
            "convenience_fee": 0,
            "total_fare": round(total_fare, 2),
        }

    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("[Amadeus] Failed to parse offer: %s", exc)
        return None
