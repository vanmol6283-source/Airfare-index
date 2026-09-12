"""
scraper/air_india_express.py — Air India Express direct website scraper.

Role in pipeline:
  ▸ Direct airline scraper for Air India Express (IATA: IX)
  ▸ robots.txt: ALLOWED for flight search pages (verified Sep 2026)
  ▸ Budget subsidiary of Air India; heavy DEL-BOM/South India traffic
  ▸ Important for capturing intra-region low-cost fares

URL pattern:
  https://www.airindiaexpress.com/search-results
    ?from={IATA_ORIGIN}
    &to={IATA_DEST}
    &date={YYYY-MM-DD}
    &type=OW        <- One Way
    &adult=1&child=0&infant=0

Last verified: September 2026
"""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.scraper.stealth_base import StealthScraper, CaptchaDetectedError, detect_captcha
from app.scraper.robots_checker import is_allowed
from app.scraper.ixigo import _parse_inr, _find_first_matching_selector

logger = logging.getLogger(__name__)

# ── URL template ──────────────────────────────────────────────────────────────

AIX_SEARCH_URL = (
    "https://www.airindiaexpress.com/search-results"
    "?from={origin}&to={destination}&date={date_str}"
    "&type=OW&adult=1&child=0&infant=0"
)

# ── CSS selectors ─────────────────────────────────────────────────────────────
# Air India Express uses Angular with predictable class names

FLIGHT_CARD_SELECTORS = [
    "[class*='flight-card']",
    "[class*='FlightCard']",
    "[class*='flightCard']",
    "app-flight-card",
    "[class*='journey-card']",
    "[class*='result-item']",
    "[class*='ResultItem']",
    ".flight-list-item",
    "[class*='flight-list']",
    "[data-testid*='flight']",
]

PRICE_SELECTORS = [
    "[class*='price']:not([class*='strike'])",
    "[class*='Price']:not([class*='strike'])",
    "[class*='fare']:not([class*='base'])",
    "[class*='amount']",
    "[data-testid='total-price']",
    "[data-testid='fare']",
    ".price",
    ".total-fare",
    "[class*='totalFare']",
    "[class*='total-fare']",
]

AIRLINE_CODE = "IX"


class AirIndiaExpressScraper(StealthScraper):
    """
    Scrapes Air India Express direct booking site for economy fares.
    """

    source_name = "airindiaexpress.com"

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """Check robots.txt then delegate to Playwright thread."""
        url = AIX_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=departure_date.strftime("%Y-%m-%d"),
        )
        if not is_allowed(url):
            logger.warning("[AIX] robots.txt DISALLOWED %s→%s — skipping", origin, destination)
            return []
        return await super().scrape_route(origin, destination, departure_date)

    async def _scrape_page(self, page, origin, destination, departure_date):
        """Navigate Air India Express and extract fare data."""
        url = AIX_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=departure_date.strftime("%Y-%m-%d"),
        )

        logger.debug("[AIX] Navigating to %s", url)
        await page.goto(url, wait_until="networkidle", timeout=45000)

        content = await page.content()
        signal = detect_captcha(content.lower())
        if signal:
            raise CaptchaDetectedError(signal=signal, url=url)

        # Wait for flight results
        card_selector = None
        for sel in FLIGHT_CARD_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=12000)
                card_selector = sel
                break
            except Exception:
                continue

        if not card_selector:
            logger.warning("[AIX] No flight cards found for %s→%s", origin, destination)
            return []

        cards = await page.query_selector_all(card_selector)
        logger.debug("[AIX] Found %d flight cards", len(cards))

        quotes = []
        for card in cards[:10]:
            try:
                quote = await _extract_quote(card, origin, destination, departure_date)
                if quote:
                    quotes.append(quote)
            except Exception as exc:
                logger.debug("[AIX] Card parse error: %s", exc)

        logger.info("[AIX] %s→%s dep=%s → %d quotes", origin, destination, departure_date, len(quotes))
        return quotes


async def _extract_quote(card, origin, destination, departure_date) -> Optional[Dict[str, Any]]:
    """Extract fare info from a single flight card element."""
    price_el = None
    for sel in PRICE_SELECTORS:
        price_el = await card.query_selector(sel)
        if price_el:
            break

    if not price_el:
        return None

    price_text = await price_el.inner_text()
    total_fare = _parse_inr(price_text)
    if not total_fare or total_fare < 500:
        return None

    # Air India Express shows total fare; estimate breakdown
    taxes_est = round(total_fare * 0.18 + 450, 2)
    base_fare = round(total_fare - taxes_est, 2)
    if base_fare < 200:
        base_fare = round(total_fare * 0.73, 2)
        taxes_est = round(total_fare - base_fare, 2)

    return {
        "carrier": AIRLINE_CODE,
        "flight_number": None,
        "fare_class": "E",
        "base_fare": base_fare,
        "taxes": taxes_est,
        "udf": 0,
        "convenience_fee": 0,
        "total_fare": total_fare,
    }
