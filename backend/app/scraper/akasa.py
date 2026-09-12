"""
scraper/akasa.py — Akasa Air direct website scraper.

Role in pipeline:
  ▸ Direct airline scraper for Akasa Air (IATA: QP)
  ▸ Runs to supplement OTA data with carrier-direct fares
    (OTAs sometimes mark up fares vs direct booking)
  ▸ Akasa is chosen for direct scraping because:
      - Newest airline site (launched 2022), less hardened anti-bot
      - Clean React architecture, selectors are predictable
      - No Akamai / Cloudflare Pro protection (as of Sep 2026)

URL pattern:
  https://www.akasaair.com/booking/select-flights
    ?from={IATA_ORIGIN}
    &to={IATA_DEST}
    &departDate={YYYY-MM-DD}
    &tripType=O          ← One way
    &adults=1
    &children=0
    &infants=0

Selector maintenance notes:
  Akasa uses Next.js with CSS modules. Class names include a hash suffix
  (e.g. FlightCard_root__aB3xK). We match on the base class name using
  CSS attribute substring matching: [class*='FlightCard'].
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

AKASA_SEARCH_URL = (
    "https://www.akasaair.com/booking/select-flights"
    "?from={origin}&to={destination}&departDate={date_str}"
    "&tripType=O&adults=1&children=0&infants=0"
)

# ── CSS selectors ─────────────────────────────────────────────────────────────

FLIGHT_CARD_SELECTORS = [
    "[class*='FlightCard']",
    "[class*='flight-card']",
    "[class*='flightCard']",
    "[class*='FareCard']",
    "[class*='fareCard']",
    "[data-testid='flight-option']",
    "[data-testid='fare-card']",
    ".flight-option",
    "[class*='ResultItem']",
]

# Akasa shows fare options (Saver, Value, Flex) — we pick the cheapest (Saver)
FARE_OPTION_SELECTORS = [
    "[class*='FareOption']:first-child",
    "[class*='fareOption']:first-child",
    "[class*='Saver']",
    "[class*='saver']",
    "[class*='BasicFare']",
    "[class*='basicFare']",
]

PRICE_SELECTORS = [
    "[class*='price']:not([class*='strike'])",
    "[class*='Price']:not([class*='strike'])",
    "[class*='amount']",
    "[class*='Amount']",
    "[class*='fare']:not([class*='base'])",
    "[data-testid='price']",
    "[data-testid='amount']",
    ".price",
    ".amount",
]

# Akasa always = QP, so carrier detection is trivial
AKASA_CARRIER_CODE = "QP"
MAX_QUOTES = 3    # Akasa has fewer fare options (Saver/Value/Flex)


class AkasaScraper(StealthScraper):
    """
    Playwright-based scraper for Akasa Air direct booking website.

    Returns economy fare quotes for Akasa Air only.
    Complements OTA data with direct carrier pricing.
    """

    source_name = "akasaair.com"

    async def _scrape_page(
        self,
        page,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Navigate to Akasa booking page, extract available fare tiers.

        Akasa shows multiple fare tiers (Saver, Value, Flex) for each flight.
        We extract all available tiers as separate quotes (different prices,
        different refundability — all valid economy fares).
        """
        date_str = departure_date.strftime("%Y-%m-%d")
        url = AKASA_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=date_str,
        )

        # ── robots.txt ────────────────────────────────────────────────────────
        if not is_allowed(url):
            logger.info("[Akasa] robots.txt disallows %s→%s — skipping", origin, destination)
            return []

        # ── Navigate ──────────────────────────────────────────────────────────
        logger.debug("[Akasa] Navigating to %s", url)
        try:
            response = await page.goto(url, wait_until="networkidle", timeout=40_000)
        except Exception as exc:
            logger.error("[Akasa] Navigation failed for %s→%s: %s", origin, destination, exc)
            return []

        if response is not None and response.status in (403, 429, 503):
            raise CaptchaDetectedError(signal=f"http_{response.status}", url=url)

        # ── CAPTCHA check ─────────────────────────────────────────────────────
        try:
            content = await page.content()
        except Exception:
            content = ""

        signal = detect_captcha(content)
        if signal:
            raise CaptchaDetectedError(signal=signal, url=url)

        # ── Wait for flight cards ─────────────────────────────────────────────
        # Akasa uses "networkidle" wait above; flight cards should be ready.
        # Add a short explicit wait for the card selector as extra assurance.
        card_selector = await _find_first_matching_selector(
            page, FLIGHT_CARD_SELECTORS, timeout_ms=20_000
        )

        if card_selector is None:
            # Check for "no flights available" message before giving up
            no_flights = await _check_no_flights(page)
            if no_flights:
                logger.info("[Akasa] No flights available for %s→%s on %s", origin, destination, departure_date)
            else:
                logger.warning("[Akasa] Selectors may be stale for %s→%s — no cards found", origin, destination)
            return []

        # ── Extract fare quotes ───────────────────────────────────────────────
        cards = await page.query_selector_all(card_selector)
        logger.debug("[Akasa] Found %d flight cards for %s→%s", len(cards), origin, destination)

        quotes: List[Dict[str, Any]] = []
        for card in cards[:MAX_QUOTES]:
            fares = await _extract_akasa_fares(card)
            quotes.extend(fares)

        logger.info(
            "[Akasa] %s→%s dep=%s → %d quotes",
            origin, destination, departure_date, len(quotes),
        )
        return quotes


# ── Card parser ───────────────────────────────────────────────────────────────

async def _extract_akasa_fares(card) -> List[Dict[str, Any]]:
    """
    Extract all fare tiers from a single Akasa flight card.

    Akasa shows multiple price tiers per flight. We extract each as a
    separate quote so the cleaner/index can take the median across them.
    """
    quotes = []

    # Try fare-option containers first (for multi-tier layout)
    for selector in FARE_OPTION_SELECTORS:
        try:
            options = await card.query_selector_all(selector)
            if options:
                for option in options:
                    quote = await _parse_fare_element(option)
                    if quote:
                        quotes.append(quote)
                if quotes:
                    return quotes
        except Exception:
            continue

    # Fallback: treat the whole card as a single price
    quote = await _parse_fare_element(card)
    if quote:
        quotes.append(quote)

    return quotes


async def _parse_fare_element(element) -> Optional[Dict[str, Any]]:
    """Parse a single fare element (either a card or a fare-tier option)."""
    total_fare: Optional[float] = None

    for selector in PRICE_SELECTORS:
        try:
            el = await element.query_selector(selector)
            if el:
                text = await el.text_content()
                total_fare = _parse_inr(text)
                if total_fare and total_fare > 0:
                    break
        except Exception:
            continue

    if not total_fare or total_fare <= 0:
        return None

    base_fare = round(total_fare / 1.18, -1)
    taxes = round(total_fare - base_fare, 2)

    if not (500 <= base_fare <= 60_000):
        return None

    return {
        "carrier": AKASA_CARRIER_CODE,
        "flight_number": None,
        "fare_class": "Y",
        "base_fare": base_fare,
        "taxes": taxes,
        "udf": 0,
        "convenience_fee": 0,
        "total_fare": total_fare,
    }


async def _check_no_flights(page) -> bool:
    """Return True if the page shows a 'no flights available' message."""
    no_flight_signals = [
        "no flights",
        "no flight",
        "unavailable",
        "not available",
        "no results",
        "try different dates",
    ]
    try:
        content = (await page.content()).lower()
        return any(signal in content for signal in no_flight_signals)
    except Exception:
        return False
