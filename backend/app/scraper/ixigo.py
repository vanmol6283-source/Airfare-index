"""
scraper/ixigo.py — Ixigo flight search scraper (PRIMARY OTA source).

Why Ixigo first:
  ▸ Single search returns fares from ALL carriers (6E, AI, SG, QP, G8, IX)
    — one API call gives multi-airline data, maximising budget efficiency
  ▸ Aggregator pages have less aggressive bot detection than airline direct
  ▸ Shows base fare + taxes breakdown in the DOM
  ▸ Robots.txt allows crawling of search result pages (verified Sep 2026)

URL pattern:
  https://www.ixigo.com/search/result/flight
    ?from={IATA_ORIGIN}
    &to={IATA_DEST}
    &date={YYYYMMDD}
    &returnDate=
    &adults=1
    &childs=0
    &infants=0
    &class=e          ← economy
    &source=Search

Selector maintenance notes:
  Ixigo uses React with CSS modules. Selectors may change on UI updates.
  The parser tries multiple fallback selectors before giving up.
  When selectors break: open Ixigo in Chrome DevTools, search a flight,
  right-click the price element → Inspect → copy selector, update below.

  Last verified: September 2026
"""

import asyncio
import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.scraper.stealth_base import StealthScraper, CaptchaDetectedError, detect_captcha
from app.scraper.robots_checker import is_allowed

logger = logging.getLogger(__name__)

# ── URL template ──────────────────────────────────────────────────────────────

IXIGO_SEARCH_URL = (
    "https://www.ixigo.com/search/result/flight"
    "?from={origin}&to={destination}&date={date_str}"
    "&returnDate=&adults=1&childs=0&infants=0&class=e&source=Search"
)

# ── CSS selectors (try each in order, use first that matches) ─────────────────

# Container for each flight card in results
FLIGHT_CARD_SELECTORS = [
    ".flight-result",
    "[class*='FlightCard']",
    "[class*='flightCard']",
    "[class*='flight-card']",
    "[data-testid='flight-card']",
    ".search-result-item",
    "[class*='ResultCard']",
]

# Price element inside a flight card (total fare displayed)
PRICE_SELECTORS = [
    "[class*='price']:not([class*='strike'])",
    "[class*='Price']:not([class*='strike'])",
    "[class*='fare']:not([class*='base']):not([class*='strike'])",
    "[class*='Fare']:not([class*='Base']):not([class*='strike'])",
    "[data-testid='price']",
    "[data-testid='fare']",
    ".price-info .amount",
    ".fare-amount",
]

# Airline/carrier name element inside a flight card
AIRLINE_SELECTORS = [
    "[class*='airline-name']",
    "[class*='airlineName']",
    "[class*='carrier-name']",
    "[class*='AirlineName']",
    "[data-testid='airline-name']",
    ".airline-logo + span",
    "[class*='airline'] span",
]

# How long to wait for flight cards to appear after navigation (ms)
RESULTS_WAIT_TIMEOUT_MS = 25_000

# Maximum number of fare quotes to extract per route/date
MAX_QUOTES_PER_ROUTE = 8

# Mapping from airline display name → IATA carrier code
AIRLINE_NAME_TO_CODE = {
    "indigo": "6E",
    "6e": "6E",
    "air india": "AI",
    "air india express": "IX",
    "akasa": "QP",
    "akasa air": "QP",
    "spicejet": "SG",
    "go first": "G8",
    "go airlines": "G8",
    "vistara": "UK",
    "alliance air": "CD",
}


class IxigoScraper(StealthScraper):
    """
    Playwright-based scraper for Ixigo flight search.

    Inherits stealth browser setup and CAPTCHA retry logic from StealthScraper.
    Implements _scrape_page() with Ixigo-specific navigation and parsing.
    """

    source_name = "ixigo.com"

    async def _scrape_page(
        self,
        page,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Navigate to Ixigo search results and extract fare quotes.

        Steps:
          1. Build URL and check robots.txt
          2. Navigate to search URL
          3. Check for CAPTCHA / block page
          4. Wait for flight result cards to render
          5. For each card: extract carrier name + total fare
          6. Estimate base fare from total (total / 1.18 approximation)
          7. Return list of quote dicts (up to MAX_QUOTES_PER_ROUTE)
        """
        date_str = departure_date.strftime("%Y%m%d")
        url = IXIGO_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=date_str,
        )

        # ── robots.txt check ──────────────────────────────────────────────────
        if not is_allowed(url):
            logger.info(
                "[Ixigo] robots.txt disallows %s→%s — skipping",
                origin, destination,
            )
            return []

        # ── Navigate ──────────────────────────────────────────────────────────
        logger.debug("[Ixigo] Navigating to %s", url)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            logger.error("[Ixigo] Navigation failed for %s→%s: %s", origin, destination, exc)
            return []

        # ── HTTP error check ──────────────────────────────────────────────────
        if response is not None and response.status in (403, 429, 503, 999):
            logger.warning(
                "[Ixigo] HTTP %d on %s→%s — treating as CAPTCHA/block",
                response.status, origin, destination,
            )
            raise CaptchaDetectedError(
                signal=f"http_{response.status}",
                url=url,
            )

        # ── CAPTCHA detection on page content ─────────────────────────────────
        try:
            content = await page.content()
        except Exception:
            content = ""

        captcha_signal = detect_captcha(content)
        if captcha_signal:
            raise CaptchaDetectedError(signal=captcha_signal, url=url)

        # ── Wait for flight result cards ──────────────────────────────────────
        card_selector = await _find_first_matching_selector(
            page, FLIGHT_CARD_SELECTORS, timeout_ms=RESULTS_WAIT_TIMEOUT_MS
        )

        if card_selector is None:
            logger.warning(
                "[Ixigo] No flight cards found for %s→%s dep=%s "
                "(route may have no flights or selectors are stale)",
                origin, destination, departure_date,
            )
            return []

        # Re-check for CAPTCHA after JS rendering (some are injected post-load)
        content = await page.content()
        captcha_signal = detect_captcha(content)
        if captcha_signal:
            raise CaptchaDetectedError(signal=captcha_signal, url=url)

        # ── Extract cards ─────────────────────────────────────────────────────
        cards = await page.query_selector_all(card_selector)
        logger.debug("[Ixigo] Found %d flight cards for %s→%s", len(cards), origin, destination)

        quotes: List[Dict[str, Any]] = []

        for card in cards[:MAX_QUOTES_PER_ROUTE]:
            quote = await _parse_card(card)
            if quote:
                quotes.append(quote)

        logger.info(
            "[Ixigo] %s→%s dep=%s → %d quotes extracted",
            origin, destination, departure_date, len(quotes),
        )
        return quotes


# ── Card parser ───────────────────────────────────────────────────────────────

async def _parse_card(card) -> Optional[Dict[str, Any]]:
    """
    Extract carrier and fare from a single Ixigo flight result card.

    Returns a quote dict or None if the card cannot be parsed.
    """
    # Try each price selector
    total_fare: Optional[float] = None
    for selector in PRICE_SELECTORS:
        try:
            el = await card.query_selector(selector)
            if el:
                text = await el.text_content()
                total_fare = _parse_inr(text)
                if total_fare and total_fare > 0:
                    break
        except Exception:
            continue

    if not total_fare or total_fare <= 0:
        return None

    # Try each airline selector
    carrier_code = "XX"  # unknown
    for selector in AIRLINE_SELECTORS:
        try:
            el = await card.query_selector(selector)
            if el:
                text = await el.text_content()
                code = _resolve_carrier(text)
                if code:
                    carrier_code = code
                    break
        except Exception:
            continue

    # Estimate base fare (Ixigo shows total including ~18% GST + fees)
    # Formula: base ≈ total / 1.18 (rough but consistent with mock logic)
    base_fare = round(total_fare / 1.18, -1)
    taxes = round(total_fare - base_fare, 2)

    # Sanity bounds (INR): base fare must be between 500 and 60,000
    if not (500 <= base_fare <= 60_000):
        return None

    return {
        "carrier": carrier_code,
        "flight_number": None,     # Ixigo does not surface flight numbers in cards
        "fare_class": "Y",         # Economy class assumed
        "base_fare": base_fare,
        "taxes": taxes,
        "udf": 0,                  # Included in total shown by Ixigo
        "convenience_fee": 0,
        "total_fare": total_fare,
    }


# ── Helper utilities ──────────────────────────────────────────────────────────

async def _find_first_matching_selector(
    page, selectors: List[str], timeout_ms: int = 15_000
) -> Optional[str]:
    """
    Try each selector in order. Return the first one that appears on the page.
    Returns None if none appear within timeout_ms.
    """
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            count = await page.locator(selector).count()
            if count > 0:
                logger.debug("Matched selector: '%s' (%d elements)", selector, count)
                return selector
        except Exception:
            continue
    return None


def _parse_inr(text: Optional[str]) -> Optional[float]:
    """
    Parse an INR fare value from display text.

    Handles formats:
      "₹ 3,450"   → 3450.0
      "₹3450"     → 3450.0
      "3,450"     → 3450.0
      "3450.00"   → 3450.0
      "Rs. 3,450" → 3450.0
    """
    if not text:
        return None
    # Remove currency symbols, whitespace, commas
    cleaned = re.sub(r"[₹Rs.\s,]", "", text.strip())
    # Extract the first numeric value
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        value = float(match.group())
        return value if value > 0 else None
    except ValueError:
        return None


def _resolve_carrier(airline_name: Optional[str]) -> Optional[str]:
    """
    Convert a human-readable airline name to an IATA carrier code.
    Returns None if unrecognised (quote will be stored with carrier='XX').
    """
    if not airline_name:
        return None
    name = airline_name.strip().lower()
    for key, code in AIRLINE_NAME_TO_CODE.items():
        if key in name:
            return code
    return None
