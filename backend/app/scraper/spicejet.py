"""
scraper/spicejet.py — SpiceJet direct website scraper.

Role in pipeline:
  ▸ Direct airline scraper for SpiceJet (IATA: SG)
  ▸ robots.txt: ALLOWED for flight search pages
  ▸ Supplements OTA data with carrier-direct fares
  ▸ Captures SpiceJet-exclusive ancillary bundles (SpiceSaver, SpiceMax)

URL pattern:
  https://www.spicejet.com/
    ?from={IATA_ORIGIN}
    &to={IATA_DEST}
    &date={YYYY-MM-DD}
    &type=O          <- One way
    &adults=1&childs=0&infants=0&infantsW=0

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

SPICEJET_SEARCH_URL = (
    "https://www.spicejet.com/"
    "?from={origin}&to={destination}&date={date_str}"
    "&type=O&adults=1&childs=0&infants=0&infantsW=0"
)

# ── CSS selectors ─────────────────────────────────────────────────────────────

FLIGHT_CARD_SELECTORS = [
    "[class*='flightCard']",
    "[class*='FlightCard']",
    "[class*='flight-card']",
    "[class*='ResultCard']",
    "[class*='resultCard']",
    "[class*='flight-result']",
    "[data-testid*='flight']",
    ".flight-info",
    "[class*='FlightInfo']",
    "[class*='flightInfo']",
]

PRICE_SELECTORS = [
    "[class*='price']:not([class*='cross']):not([class*='strike'])",
    "[class*='Price']:not([class*='cross']):not([class*='strike'])",
    "[class*='amount']",
    "[class*='Amount']",
    "[class*='fare']",
    "[data-testid='price']",
    "[data-testid='amount']",
    ".price",
    ".amount",
]

AIRLINE_CODE = "SG"


class SpiceJetScraper(StealthScraper):
    """
    Scrapes SpiceJet's direct booking site for economy fares.
    Returns the cheapest available fare per departure.
    """

    source_name = "spicejet.com"

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """Check robots.txt then delegate to Playwright thread."""
        url = SPICEJET_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=departure_date.strftime("%Y-%m-%d"),
        )
        if not is_allowed(url):
            logger.warning("[SpiceJet] robots.txt DISALLOWED %s→%s — skipping", origin, destination)
            return []
        return await super().scrape_route(origin, destination, departure_date)

    async def _scrape_page(self, page, origin, destination, departure_date):
        """Navigate SpiceJet and extract fare data."""
        url = SPICEJET_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=departure_date.strftime("%Y-%m-%d"),
        )

        logger.debug("[SpiceJet] Navigating to %s", url)
        await page.goto(url, wait_until="networkidle", timeout=45000)

        # Check for CAPTCHA / block
        content = await page.content()
        signal = detect_captcha(content.lower())
        if signal:
            raise CaptchaDetectedError(signal=signal, url=url)

        # Wait for flight cards to appear
        card_selector = None
        for sel in FLIGHT_CARD_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=12000)
                card_selector = sel
                break
            except Exception:
                continue

        if not card_selector:
            logger.warning("[SpiceJet] Selectors stale for %s→%s — no cards found", origin, destination)
            return []

        cards = await page.query_selector_all(card_selector)
        logger.debug("[SpiceJet] Found %d flight cards", len(cards))

        quotes = []
        for card in cards[:10]:  # cap at 10 results per route
            try:
                quote = await _extract_quote(card, origin, destination, departure_date)
                if quote:
                    quotes.append(quote)
            except Exception as exc:
                logger.debug("[SpiceJet] Card parse error: %s", exc)

        logger.info("[SpiceJet] %s→%s dep=%s → %d quotes", origin, destination, departure_date, len(quotes))
        return quotes


async def _extract_quote(card, origin, destination, departure_date) -> Optional[Dict[str, Any]]:
    """Extract fare info from a single flight card element."""
    # Get price text
    price_sel = _find_first_matching_selector(PRICE_SELECTORS)
    price_el = await card.query_selector(price_sel or PRICE_SELECTORS[0])
    if not price_el:
        # Try all selectors
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

    # Estimate base fare (SpiceJet doesn't break it down on results page)
    # Approx: taxes ~18% GST + ₹500 UDF
    taxes_est = round(total_fare * 0.18 + 500, 2)
    base_fare = round(total_fare - taxes_est, 2)
    if base_fare < 200:
        base_fare = round(total_fare * 0.72, 2)
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
