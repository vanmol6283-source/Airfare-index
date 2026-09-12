"""
scraper/easemytrip.py — EaseMyTrip flight search scraper (BACKUP OTA source).

Role in pipeline:
  ▸ Runs after Ixigo to fill gaps left by CAPTCHA-blocked routes
  ▸ Also covers all carriers (6E, AI, SG, QP, G8, IX) in one search
  ▸ Different infrastructure from Ixigo → independent failure modes
    (CAPTCHA on Ixigo does NOT imply CAPTCHA on EaseMyTrip)

URL pattern:
  https://flight.easemytrip.com/FlightList/Index
    ?seg1={ORIGIN}{DEST}
    &trvldt1={DD/MM/YYYY}
    &TravelType=1            ← one-way
    &PassengerCount=1-0-0-0  ← 1 adult, 0 child, 0 infant, 0 senior
    &Cbntype=E               ← Economy

Selector maintenance notes:
  EaseMyTrip uses server-side rendering with jQuery UI updates.
  Selectors are more stable than React-based sites but can shift on redesigns.
  Last verified: September 2026
"""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.scraper.stealth_base import StealthScraper, CaptchaDetectedError, detect_captcha
from app.scraper.robots_checker import is_allowed
from app.scraper.ixigo import (     # reuse shared helpers
    _parse_inr,
    _resolve_carrier,
    _find_first_matching_selector,
    MAX_QUOTES_PER_ROUTE,
)

logger = logging.getLogger(__name__)

# ── URL template ──────────────────────────────────────────────────────────────

EASEMYTRIP_SEARCH_URL = (
    "https://flight.easemytrip.com/FlightList/Index"
    "?seg1={origin}{destination}"
    "&trvldt1={date_str}"
    "&TravelType=1&PassengerCount=1-0-0-0&Cbntype=E"
)

# ── CSS selectors ─────────────────────────────────────────────────────────────

FLIGHT_CARD_SELECTORS = [
    ".flight-dtls",
    ".fli-list",
    "[class*='flightDetail']",
    "[class*='flight-detail']",
    "[class*='FlightDetail']",
    ".rs-flt-dtls",
    "[class*='result-item']",
]

PRICE_SELECTORS = [
    ".fli-fare .price",
    ".fare-price",
    "[class*='farePrice']",
    "[class*='FarePrice']",
    "[class*='totalFare']",
    "[class*='total-fare']",
    ".price-box .amount",
    "[data-price]",
    "[class*='price']:not([class*='strike'])",
]

AIRLINE_SELECTORS = [
    ".airline-name",
    "[class*='airlineName']",
    "[class*='AirlineName']",
    "[class*='carrier']",
    ".fli-name",
    "img[alt]",       # EaseMyTrip uses alt text on airline logo images
]


class EaseMyTripScraper(StealthScraper):
    """
    Playwright-based scraper for EaseMyTrip flight search.

    Backup OTA: runs only for routes where Ixigo returned 0 quotes
    (due to CAPTCHA, no-results, or selector failure).
    """

    source_name = "easemytrip.com"

    async def _scrape_page(
        self,
        page,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Navigate to EaseMyTrip search, wait for results, extract fares.
        """
        date_str = departure_date.strftime("%d/%m/%Y")
        url = EASEMYTRIP_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date_str=date_str,
        )

        # ── robots.txt ────────────────────────────────────────────────────────
        if not is_allowed(url):
            logger.info("[EaseMyTrip] robots.txt disallows %s→%s — skipping", origin, destination)
            return []

        # ── Navigate ──────────────────────────────────────────────────────────
        logger.debug("[EaseMyTrip] Navigating to %s", url)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            logger.error("[EaseMyTrip] Navigation failed for %s→%s: %s", origin, destination, exc)
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

        # ── Wait for results ──────────────────────────────────────────────────
        card_selector = await _find_first_matching_selector(
            page, FLIGHT_CARD_SELECTORS, timeout_ms=25_000
        )

        if card_selector is None:
            logger.warning(
                "[EaseMyTrip] No flight cards found for %s→%s dep=%s",
                origin, destination, departure_date,
            )
            return []

        # Final CAPTCHA check post-JS render
        content = await page.content()
        if detect_captcha(content):
            raise CaptchaDetectedError(signal="post_render_block", url=url)

        # ── Extract cards ─────────────────────────────────────────────────────
        cards = await page.query_selector_all(card_selector)
        logger.debug(
            "[EaseMyTrip] Found %d flight cards for %s→%s",
            len(cards), origin, destination,
        )

        quotes: List[Dict[str, Any]] = []
        for card in cards[:MAX_QUOTES_PER_ROUTE]:
            quote = await _parse_emt_card(card)
            if quote:
                quotes.append(quote)

        logger.info(
            "[EaseMyTrip] %s→%s dep=%s → %d quotes",
            origin, destination, departure_date, len(quotes),
        )
        return quotes


# ── Card parser ───────────────────────────────────────────────────────────────

async def _parse_emt_card(card) -> Optional[Dict[str, Any]]:
    """Extract carrier code and fare from an EaseMyTrip flight card."""
    total_fare: Optional[float] = None
    for selector in PRICE_SELECTORS:
        try:
            el = await card.query_selector(selector)
            if el:
                # Try data-price attribute first (machine-readable)
                data_price = await el.get_attribute("data-price")
                if data_price:
                    total_fare = _parse_inr(data_price)
                if not total_fare:
                    text = await el.text_content()
                    total_fare = _parse_inr(text)
                if total_fare and total_fare > 0:
                    break
        except Exception:
            continue

    if not total_fare or total_fare <= 0:
        return None

    # Carrier detection — try text selectors, then img alt attribute
    carrier_code = "XX"
    for selector in AIRLINE_SELECTORS:
        try:
            el = await card.query_selector(selector)
            if el:
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                if tag == "img":
                    text = await el.get_attribute("alt") or ""
                else:
                    text = await el.text_content() or ""
                code = _resolve_carrier(text)
                if code:
                    carrier_code = code
                    break
        except Exception:
            continue

    base_fare = round(total_fare / 1.18, -1)
    taxes = round(total_fare - base_fare, 2)

    if not (500 <= base_fare <= 60_000):
        return None

    return {
        "carrier": carrier_code,
        "flight_number": None,
        "fare_class": "Y",
        "base_fare": base_fare,
        "taxes": taxes,
        "udf": 0,
        "convenience_fee": 0,
        "total_fare": total_fare,
    }
