"""
scraper/indigo.py — IndiGo (6E) direct website scraper.

Updated to use StealthScraper base class (was BaseScraper).
Stealth patches, CAPTCHA detection, and retry logic now inherited.

⚠  ETHICAL NOTICE (unchanged):
    Research-purpose only. Respects robots.txt, uses random delays,
    backs off on CAPTCHA, does NOT bypass anti-bot measures.
    Contact IndiGo data partnerships for an official data feed.

IndiGo tech stack (as of Sep 2026):
  - React SPA at book.goindigo.in
  - Akamai Bot Manager protection
  - CAPTCHA triggered after 2–4 rapid requests from same IP
  - Stealth mode + 3–8s delays provide ~30 min before detection

URL pattern:
  https://book.goindigo.in/booking/SearchTrips
    ?origin={IATA}
    &destination={IATA}
    &departDate={YYYYMMDD}
    &tripType=O
    &adult=1&child=0&infant=0
    &currency=INR&cabinClass=ECONOMY

Selector maintenance:
  IndiGo updates their booking UI frequently. If scraper returns 0 quotes,
  inspect live site: open DevTools → search a flight → find price element
  → right-click → Copy → Copy selector. Update PRICE_SELECTORS below.
  Last verified: September 2026.
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

INDIGO_URL_TEMPLATE = (
    "https://book.goindigo.in/booking/SearchTrips"
    "?origin={origin}&destination={destination}"
    "&departDate={dep_date}&tripType=O"
    "&adult=1&child=0&infant=0"
    "&currency=INR&cabinClass=ECONOMY"
)

# ── CSS selectors (try all, use first that works) ─────────────────────────────

FLIGHT_CARD_SELECTORS = [
    ".flight-fare",
    "[data-testid='fare']",
    "[class*='FareOption']",
    "[class*='fareOption']",
    "[class*='FlightCard']",
    "[class*='flightCard']",
    "[class*='FareCard']",
    "[class*='flight-result']",
    ".fare-strip",
    "[class*='PriceCell']",
]

PRICE_SELECTORS = [
    ".fare-amount",
    ".flight-fare .amount",
    "[data-testid='fare'] .price",
    "[class*='FareAmount']",
    "[class*='fareAmount']",
    "[class*='TotalPrice']",
    "[class*='totalPrice']",
    "[class*='Price']:not([class*='strike']):not([class*='old'])",
    "[class*='price']:not([class*='strike']):not([class*='old'])",
]

MAX_QUOTES = 6      # cap IndiGo quotes per route (they show Saver/Flexi/Corporate)


class IndigoScraper(StealthScraper):
    """
    Playwright stealth scraper for IndiGo (book.goindigo.in).

    Returns economy class fare quotes for the requested route/date.
    Returns [] on CAPTCHA (after retry), 429, robots.txt block,
    or any unrecognised page structure.

    Carrier code: 6E (IndiGo's IATA code)
    """

    source_name = "goindigo.in"

    async def _scrape_page(
        self,
        page,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Navigate to IndiGo booking search and extract fare quotes.
        """
        url = INDIGO_URL_TEMPLATE.format(
            origin=origin,
            destination=destination,
            dep_date=departure_date.strftime("%Y%m%d"),
        )

        # ── robots.txt ────────────────────────────────────────────────────────
        if not is_allowed(url):
            logger.info("[IndiGo] robots.txt disallows %s→%s — skipping", origin, destination)
            return []

        # ── Navigate ──────────────────────────────────────────────────────────
        logger.debug("[IndiGo] Navigating to %s", url)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=35_000)
        except Exception as exc:
            logger.error("[IndiGo] Navigation failed for %s→%s: %s", origin, destination, exc)
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
            page, FLIGHT_CARD_SELECTORS, timeout_ms=20_000
        )

        if card_selector is None:
            logger.warning(
                "[IndiGo] No fare elements found for %s→%s dep=%s "
                "(CAPTCHA, no flights, or stale selectors)",
                origin, destination, departure_date,
            )
            # Post-load CAPTCHA check (Akamai sometimes injects after JS runs)
            content = await page.content()
            signal = detect_captcha(content)
            if signal:
                raise CaptchaDetectedError(signal=signal, url=url)
            return []

        # ── Extract fare elements ─────────────────────────────────────────────
        cards = await page.query_selector_all(card_selector)
        logger.debug("[IndiGo] Found %d fare elements for %s→%s", len(cards), origin, destination)

        quotes: List[Dict[str, Any]] = []
        for card in cards[:MAX_QUOTES]:
            quote = await _parse_indigo_card(card)
            if quote:
                quotes.append(quote)

        logger.info(
            "[IndiGo] %s→%s dep=%s → %d quotes",
            origin, destination, departure_date, len(quotes),
        )
        return quotes


# ── Card parser ───────────────────────────────────────────────────────────────

async def _parse_indigo_card(card) -> Optional[Dict[str, Any]]:
    """Extract fare from a single IndiGo fare element."""
    total_fare: Optional[float] = None

    for selector in PRICE_SELECTORS:
        try:
            el = await card.query_selector(selector)
            if not el:
                # Try the card element itself
                el = card
            text = await el.text_content()
            total_fare = _parse_inr(text)
            if total_fare and total_fare > 0:
                break
        except Exception:
            continue

    if not total_fare or total_fare <= 0:
        return None

    # IndiGo fares include ~22% taxes/fees/UDF
    # More accurate than 18% GST alone (IndiGo has higher airport charges)
    base_fare = round(total_fare / 1.22, -1)
    taxes = round(total_fare - base_fare, 2)

    if not (500 <= base_fare <= 60_000):
        return None

    return {
        "carrier": "6E",
        "flight_number": None,    # IndiGo doesn't surface flight numbers in fare cards
        "fare_class": "Y",
        "base_fare": base_fare,
        "taxes": taxes,
        "udf": 295,               # IndiGo UDF at major airports (DEL/BOM) is ₹295
        "convenience_fee": 0,
        "total_fare": total_fare,
    }
