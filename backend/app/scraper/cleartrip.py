"""
scraper/cleartrip.py — ClearTrip OTA scraper (requests-based, no JS render needed).

Role in pipeline:
  ▸ ClearTrip allows bot access (robots.txt: Allowed)
  ▸ Unlike most OTAs, ClearTrip's search results are partially SSR
    and accessible via their JSON API endpoint
  ▸ Covers all carriers including Air India, IndiGo, SpiceJet, Akasa,
    Vistara merged into Air India, AIX
  ▸ Uses requests + JSON API (no Playwright needed → faster, lower load)

API endpoint:
  POST https://www.cleartrip.com/cfapi/flights/search
  Headers: Content-Type: application/json, accept: application/json
  Body: { source, destination, departDate, adults, cabin }

Fallback:
  If API fails (auth/bot-block), falls back to Playwright page scrape.

Last verified: September 2026
"""

import logging
import json
import random
import time
from datetime import date
from typing import Any, Dict, List, Optional

import requests

from app.scraper.base import BaseScraper, USER_AGENT
from app.scraper.robots_checker import is_allowed

logger = logging.getLogger(__name__)

# ── Endpoints ─────────────────────────────────────────────────────────────────

CLEARTRIP_API_URL = "https://www.cleartrip.com/cfapi/flights/search"
CLEARTRIP_SEARCH_URL = (
    "https://www.cleartrip.com/flights/results"
    "?from={origin}&to={destination}&depart_date={date_str}"
    "&adults=1&childs=0&infants=0&class=Economy&intl=n"
)

# Carrier code mapping (ClearTrip uses IATA codes)
CARRIER_MAP = {
    "6E": "6E",  # IndiGo
    "AI": "AI",  # Air India
    "SG": "SG",  # SpiceJet
    "QP": "QP",  # Akasa
    "IX": "IX",  # Air India Express
    "G8": "G8",  # Go First (historical)
}


class ClearTripScraper(BaseScraper):
    """
    ClearTrip OTA scraper — uses requests JSON API.

    Tries the JSON API first (fast, lightweight). Falls back to
    Playwright page scrape on API auth failure.
    """

    source_name = "cleartrip.com"

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.6533.120 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://www.cleartrip.com",
            "Referer": "https://www.cleartrip.com/",
            "x-ct-dp": "in",
            "x-ct-app": "web",
        })

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Fetch ClearTrip fares for a single route/date.
        Runs sync HTTP in thread pool via asyncio executor.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        quotes = await loop.run_in_executor(
            None,
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
        """Synchronous HTTP fetch — runs in thread pool."""
        search_url = CLEARTRIP_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=departure_date.strftime("%d/%m/%Y"),
        )

        if not is_allowed(search_url):
            logger.warning("[ClearTrip] robots.txt DISALLOWED %s→%s — skipping", origin, destination)
            return []

        # Try JSON API first
        try:
            quotes = self._fetch_api(origin, destination, departure_date)
            if quotes:
                logger.info("[ClearTrip] %s→%s dep=%s → %d quotes (API)", origin, destination, departure_date, len(quotes))
                return quotes
        except Exception as exc:
            logger.debug("[ClearTrip] API attempt failed: %s — falling back to page scrape", exc)

        # Fallback: page scrape via requests + BeautifulSoup
        try:
            quotes = self._fetch_page(origin, destination, departure_date)
            logger.info("[ClearTrip] %s→%s dep=%s → %d quotes (page)", origin, destination, departure_date, len(quotes))
            return quotes
        except Exception as exc:
            logger.warning("[ClearTrip] Page scrape also failed for %s→%s: %s", origin, destination, exc)
            return []

    def _fetch_api(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """Attempt ClearTrip's JSON search API."""
        payload = {
            "source": origin,
            "destination": destination,
            "departDate": departure_date.strftime("%Y-%m-%d"),
            "adults": 1,
            "children": 0,
            "infants": 0,
            "cabin": "Economy",
            "tripType": "ONE_WAY",
            "searchType": "domestic",
        }

        # Add random small delay to be polite
        time.sleep(random.uniform(1.0, 3.0))

        resp = self._session.post(
            CLEARTRIP_API_URL,
            json=payload,
            timeout=self.timeout,
        )

        if resp.status_code == 401 or resp.status_code == 403:
            raise ValueError(f"API auth failed: HTTP {resp.status_code}")

        resp.raise_for_status()
        data = resp.json()

        return _parse_api_response(data, origin, destination, departure_date)

    def _fetch_page(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """Fallback: scrape the HTML results page with BeautifulSoup."""
        from bs4 import BeautifulSoup

        url = CLEARTRIP_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=departure_date.strftime("%d/%m/%Y"),
        )

        time.sleep(random.uniform(2.0, 5.0))
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # ClearTrip embeds flight data in a <script id="__NEXT_DATA__"> JSON blob
        next_data_script = soup.find("script", {"id": "__NEXT_DATA__"})
        if next_data_script and next_data_script.string:
            try:
                next_data = json.loads(next_data_script.string)
                flights = _extract_from_next_data(next_data)
                if flights:
                    return _format_quotes(flights, origin, destination, departure_date)
            except Exception as exc:
                logger.debug("[ClearTrip] __NEXT_DATA__ parse failed: %s", exc)

        # Last resort: look for price spans
        return _parse_html_prices(soup, origin, destination, departure_date)


def _parse_api_response(data: dict, origin, destination, departure_date) -> List[Dict[str, Any]]:
    """Parse ClearTrip JSON API response into quote dicts."""
    quotes = []
    try:
        # ClearTrip API returns results under various keys depending on version
        results = (
            data.get("results", [])
            or data.get("flights", [])
            or data.get("data", {}).get("flights", [])
            or data.get("flightList", [])
        )

        for flight in results[:15]:
            try:
                # Price might be in nested price/fare object
                price_info = (
                    flight.get("price")
                    or flight.get("fare")
                    or flight.get("pricing")
                    or {}
                )
                total = float(
                    price_info.get("totalFare")
                    or price_info.get("total")
                    or price_info.get("grandTotal")
                    or flight.get("totalFare")
                    or 0
                )
                base = float(
                    price_info.get("baseFare")
                    or price_info.get("base")
                    or flight.get("baseFare")
                    or total * 0.72
                )
                taxes = float(
                    price_info.get("taxes")
                    or price_info.get("tax")
                    or flight.get("taxes")
                    or total - base
                )

                if total < 500:
                    continue

                carrier = (
                    flight.get("airline")
                    or flight.get("carrier")
                    or flight.get("airlineCode")
                    or flight.get("operatingAirline")
                )
                if isinstance(carrier, dict):
                    carrier = carrier.get("code") or carrier.get("iataCode")

                flight_no = (
                    flight.get("flightNumber")
                    or flight.get("flight_number")
                    or flight.get("number")
                )

                quotes.append({
                    "carrier": str(carrier).upper()[:2] if carrier else None,
                    "flight_number": str(flight_no) if flight_no else None,
                    "fare_class": "E",
                    "base_fare": round(base, 2),
                    "taxes": round(taxes, 2),
                    "udf": 0,
                    "convenience_fee": float(price_info.get("convenienceFee", 0)),
                    "total_fare": round(total, 2),
                })
            except Exception:
                continue

    except Exception as exc:
        logger.debug("[ClearTrip] API parse error: %s", exc)

    return quotes


def _extract_from_next_data(data: dict) -> list:
    """Recursively find flight lists in Next.js __NEXT_DATA__ blob."""
    # Walk down common Next.js page data paths
    try:
        page_props = data.get("props", {}).get("pageProps", {})
        for key in ("flights", "flightList", "results", "searchResults"):
            if key in page_props:
                return page_props[key]
        # Fallback: look in nested initialState or dehydratedState
        initial = page_props.get("initialState") or page_props.get("dehydratedState") or {}
        for key in ("flights", "flightResults", "flightList"):
            if key in initial:
                return initial[key]
    except Exception:
        pass
    return []


def _format_quotes(flights: list, origin, destination, departure_date) -> List[Dict[str, Any]]:
    """Format raw flight objects into standard quote dicts."""
    quotes = []
    for f in flights[:15]:
        try:
            total = float(f.get("totalFare") or f.get("price") or f.get("fare") or 0)
            if total < 500:
                continue
            base = float(f.get("baseFare") or total * 0.72)
            taxes = round(total - base, 2)
            quotes.append({
                "carrier": str(f.get("airline") or f.get("carrier") or "")[:2].upper() or None,
                "flight_number": f.get("flightNumber") or f.get("flight_number"),
                "fare_class": "E",
                "base_fare": round(base, 2),
                "taxes": taxes,
                "udf": 0,
                "convenience_fee": 0,
                "total_fare": round(total, 2),
            })
        except Exception:
            continue
    return quotes


def _parse_html_prices(soup, origin, destination, departure_date) -> List[Dict[str, Any]]:
    """Last-resort HTML parser — finds price patterns in page text."""
    import re
    quotes = []
    price_pattern = re.compile(r"(?:Rs\.?|₹|INR)\s*([\d,]+)", re.IGNORECASE)
    found = price_pattern.findall(soup.get_text())
    seen = set()
    for p_str in found[:20]:
        try:
            total = float(p_str.replace(",", ""))
            if total < 500 or total in seen:
                continue
            seen.add(total)
            base = round(total * 0.72, 2)
            taxes = round(total - base, 2)
            quotes.append({
                "carrier": None,
                "flight_number": None,
                "fare_class": "E",
                "base_fare": base,
                "taxes": taxes,
                "udf": 0,
                "convenience_fee": 0,
                "total_fare": total,
            })
        except Exception:
            continue
    return quotes[:10]
