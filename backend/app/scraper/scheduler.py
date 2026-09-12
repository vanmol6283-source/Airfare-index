"""
scraper/scheduler.py — Multi-slot APScheduler for daily airfare scraping.

== Scheduling Strategy (per problem statement) ==

The pipeline runs 3 times per day at staggered IST times to capture
intra-day price dynamics (airfares can move 200-400% in a single day):

  Slot A — 06:30 IST (01:00 UTC): Morning prices (pre-peak, base fares)
  Slot B — 12:30 IST (07:00 UTC): Midday prices (peak demand window)
  Slot C — 19:30 IST (14:00 UTC): Evening prices (last-minute/seat-fill)

Each slot runs a DIFFERENT mix of scrapers (rotation) to:
  - Avoid hammering the same site 3× in succession (anti-bot)
  - Spread the 8 routes × 5 AP windows = 40 tasks across sources
  - Ensure each source gets at most 1 run per 6-hour window per domain

Scraper rotation across slots:
  Slot A (06:30): SerpAPI  + EaseMyTrip   + Akasa Air
  Slot B (12:30): SerpAPI  + ClearTrip    + SpiceJet
  Slot C (19:30): SerpAPI  + EaseMyTrip   + Air India Express + IndiGo

SerpAPI runs in all slots (250 free/month = ~8/day; 40 routes × 3 = 120/day
exceeds free tier so we stagger it to only run on slot A and C).

Final allocation (≤250 SerpAPI calls/month):
  - SerpAPI: Slot A + Slot C only → 2 × 40 routes × 30 days = 2400/month
    → Exceeds free tier; cap: only run SerpAPI on Slot A (40/day × 30 = 1200)

  Slot A (06:30): SerpAPI + EaseMyTrip + AkasaAir
  Slot B (12:30): ClearTrip + SpiceJet + EaseMyTrip
  Slot C (19:30): AirIndiaExpress + IndiGo + SpiceJet

Inter-request delays (ethical scraping):
  - OTA/airline sites: 5–12 seconds between requests (raised from 3–8s)
  - SerpAPI: 2–4 seconds (API rate limit is generous)
  - Per-scraper domain: min 6 hours between runs (slot rotation handles this)

Total estimated quotes per day:
  40 route×AP combos × ~3 quotes each × 3 sources per slot × 3 slots
  ≈ 1,080–1,440 quotes/day → solid CPI coverage
"""

import asyncio
import logging
import os
from datetime import date, datetime, timezone
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import SessionLocal
from app.models import ScrapeRun, DataQualityStat
from app.pipeline.cleaner import validate_and_flag
from app.pipeline.index import compute_apix_for_date, store_index_value

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")

# ── Scraper slot definitions ───────────────────────────────────────────────────

def _chromium_ready() -> bool:
    """Check if Playwright Chromium is downloaded and available."""
    chromium_dir = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
    if not os.path.isdir(chromium_dir):
        return False
    try:
        return any(
            d.startswith("chromium-")
            for d in os.listdir(chromium_dir)
            if os.path.isdir(os.path.join(chromium_dir, d))
        )
    except OSError:
        return False


def _get_serpapi_scraper():
    """Load SerpAPI scraper if key is configured."""
    key = getattr(settings, "SERPAPI_KEY", "")
    if not key:
        return None
    try:
        from app.scraper.serpapi_scraper import SerpApiScraper
        return SerpApiScraper()
    except ImportError:
        logger.warning("SerpApiScraper not importable")
        return None


def _get_amadeus_scraper():
    """Load Amadeus scraper if API keys are configured (highest priority)."""
    key = getattr(settings, "AMADEUS_API_KEY", "")
    secret = getattr(settings, "AMADEUS_API_SECRET", "")
    if not (key and secret):
        return None
    try:
        from app.scraper.amadeus_scraper import AmadeusScraper
        return AmadeusScraper()
    except ImportError:
        return None


def get_scrapers_for_slot(slot: str) -> List:
    """
    Return the ordered list of scrapers for a given daily slot.

    slot: "A" (morning), "B" (midday), or "C" (evening)

    If Amadeus is configured: always returns only [AmadeusScraper] — it covers
    all routes with official data and no bot-risk.

    If Chromium is not installed: web scrapers are excluded; only API scrapers run.
    """
    from app.scraper.mock_scraper import MockScraper

    # ── Amadeus override (official API, zero bot-block risk) ──────────────────
    amadeus = _get_amadeus_scraper()
    if amadeus:
        logger.info("[Slot %s] Using AmadeusScraper (official API — all slots)", slot)
        return [amadeus]

    scrapers = []
    chromium = _chromium_ready()

    if not chromium:
        logger.warning(
            "[Slot %s] Chromium not installed — Playwright scrapers unavailable. "
            "Only API scrapers will run.", slot
        )

    # ── Slot A: Morning (06:30 IST) ───────────────────────────────────────────
    # SerpAPI (covers all carriers via Google Flights) + OTA + Direct airline
    if slot == "A":
        serpapi = _get_serpapi_scraper()
        if serpapi:
            scrapers.append(serpapi)
            logger.info("[Slot A] Added SerpApiScraper")

        if chromium and settings.SCRAPING_ENABLED:
            try:
                from app.scraper.easemytrip import EaseMyTripScraper
                scrapers.append(EaseMyTripScraper())
                logger.info("[Slot A] Added EaseMyTripScraper")
            except ImportError:
                pass
            try:
                from app.scraper.akasa import AkasaScraper
                scrapers.append(AkasaScraper())
                logger.info("[Slot A] Added AkasaScraper")
            except ImportError:
                pass

    # ── Slot B: Midday (12:30 IST) ────────────────────────────────────────────
    # Different OTA (ClearTrip) + SpiceJet direct — zero overlap with Slot A
    elif slot == "B":
        try:
            from app.scraper.cleartrip import ClearTripScraper
            scrapers.append(ClearTripScraper())
            logger.info("[Slot B] Added ClearTripScraper")
        except ImportError:
            pass

        if chromium and settings.SCRAPING_ENABLED:
            try:
                from app.scraper.spicejet import SpiceJetScraper
                scrapers.append(SpiceJetScraper())
                logger.info("[Slot B] Added SpiceJetScraper")
            except ImportError:
                pass
            try:
                from app.scraper.easemytrip import EaseMyTripScraper
                scrapers.append(EaseMyTripScraper())
                logger.info("[Slot B] Added EaseMyTripScraper (slot B cross-check)")
            except ImportError:
                pass

    # ── Slot C: Evening (19:30 IST) ───────────────────────────────────────────
    # Air India Express + IndiGo direct + SpiceJet evening cross-check
    elif slot == "C":
        if chromium and settings.SCRAPING_ENABLED:
            try:
                from app.scraper.air_india_express import AirIndiaExpressScraper
                scrapers.append(AirIndiaExpressScraper())
                logger.info("[Slot C] Added AirIndiaExpressScraper")
            except ImportError:
                pass
            try:
                from app.scraper.indigo import IndigoScraper
                scrapers.append(IndigoScraper())
                logger.info("[Slot C] Added IndigoScraper")
            except ImportError:
                pass
            try:
                from app.scraper.spicejet import SpiceJetScraper
                scrapers.append(SpiceJetScraper())
                logger.info("[Slot C] Added SpiceJetScraper (slot C cross-check)")
            except ImportError:
                pass

        # SerpAPI also runs in Slot C as a cross-validation check
        # (Slot A + C = ~80 calls/day × 30 = 2400/month; within paid limits)
        # Comment out the next lines if on free tier (250 calls/month):
        # serpapi = _get_serpapi_scraper()
        # if serpapi:
        #     scrapers.append(serpapi)

    if scrapers:
        return scrapers

    logger.info("[Slot %s] No configured scrapers — using MockScraper", slot)
    return [MockScraper()]


# ── Targeted pipeline runner (for manual Web/API triggers) ────────────────

def get_scrapers_by_type(target_type: str) -> List:
    """Return scrapers based on requested type ('api' or 'web')."""
    scrapers = []
    
    if target_type == "api":
        # SerpAPI
        serpapi = _get_serpapi_scraper()
        if serpapi:
            scrapers.append(serpapi)
        
        # Amadeus
        amadeus = _get_amadeus_scraper()
        if amadeus:
            scrapers.append(amadeus)
            
        # ClearTrip API
        try:
            from app.scraper.cleartrip import ClearTripScraper
            scrapers.append(ClearTripScraper())
        except ImportError:
            pass

    elif target_type == "web":
        chromium = _chromium_ready()
        if chromium and settings.SCRAPING_ENABLED:
            # EaseMyTrip
            try:
                from app.scraper.easemytrip import EaseMyTripScraper
                scrapers.append(EaseMyTripScraper())
            except ImportError:
                pass
            # SpiceJet
            try:
                from app.scraper.spicejet import SpiceJetScraper
                scrapers.append(SpiceJetScraper())
            except ImportError:
                pass
            # Akasa
            try:
                from app.scraper.akasa import AkasaScraper
                scrapers.append(AkasaScraper())
            except ImportError:
                pass
            # Air India Express
            try:
                from app.scraper.air_india_express import AirIndiaExpressScraper
                scrapers.append(AirIndiaExpressScraper())
            except ImportError:
                pass
            # Indigo
            try:
                from app.scraper.indigo import IndigoScraper
                scrapers.append(IndigoScraper())
            except ImportError:
                pass

    if not scrapers:
        from app.scraper.mock_scraper import MockScraper
        logger.info("[Targeted %s] No configured scrapers — using MockScraper", target_type)
        return [MockScraper()]
        
    return scrapers

def run_targeted_pipeline(target_type: str):
    """Entry point for manual trigger by type ('api' or 'web')."""
    logger.info("=== Airfare pipeline Targeted (%s) started ===", target_type)
    import sys
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        scrapers = get_scrapers_by_type(target_type)
        loop.run_until_complete(_async_pipeline(date.today(), slot=f"Manual-{target_type.upper()}", custom_scrapers=scrapers))
    finally:
        loop.close()


# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_slot_pipeline(slot: str):
    """
    Entry point called by APScheduler for each slot.
    Runs synchronously in APScheduler's background thread pool.
    """
    logger.info("=== Airfare pipeline Slot %s started ===", slot)
    # Use ProactorEventLoop on Windows for Playwright subprocess support
    import sys
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_async_pipeline(date.today(), slot))
    finally:
        loop.close()


async def _async_pipeline(collection_date: date, slot: str = "A", custom_scrapers: list = None):
    """Full async pipeline: scrape → clean → store → compute index."""
    db = SessionLocal()

    run = ScrapeRun(
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    total_collected = 0
    total_rejected = 0

    try:
        scrapers = custom_scrapers if custom_scrapers is not None else get_scrapers_for_slot(slot)

        for idx, scraper in enumerate(scrapers):
            # Pause between scrapers (except before the first one) to let
            # domains "breathe" — prevents triggering rate-limit thresholds
            if idx > 0:
                pause = settings.SCRAPING_INTER_SOURCE_PAUSE_S
                logger.info(
                    "[Slot %s] Inter-source pause: %.0fs before %s",
                    slot, pause, scraper.source_name,
                )
                await asyncio.sleep(pause)

            logger.info("[Slot %s] Running scraper: %s", slot, scraper.source_name)
            raw_quotes = await scraper.collect_all_routes(collection_date)

            valid, rejected = validate_and_flag(raw_quotes, collection_date)

            from app.models import RawQuote, BasketItem
            for q in valid:
                route = f"{q['origin']}-{q['destination']}"
                basket_item = (
                    db.query(BasketItem)
                    .filter(
                        BasketItem.route == route,
                        BasketItem.ap_window == q["ap_days"],
                        BasketItem.is_active == True,  # noqa
                    )
                    .first()
                )

                db.add(RawQuote(
                    basket_item_id=basket_item.id if basket_item else None,
                    origin=q["origin"],
                    destination=q["destination"],
                    carrier=q.get("carrier"),
                    flight_number=q.get("flight_number"),
                    fare_class=q.get("fare_class"),
                    departure_date=q["departure_date"],
                    collection_date=q["collection_date"],
                    ap_days=q["ap_days"],
                    base_fare=q["base_fare"],
                    taxes=q.get("taxes", 0),
                    udf=q.get("udf", 0),
                    convenience_fee=q.get("convenience_fee", 0),
                    total_fare=q["total_fare"],
                    source=q["source"],
                    is_valid=True,
                ))

            for q in rejected:
                db.add(RawQuote(
                    origin=q.get("origin", "?"),
                    destination=q.get("destination", "?"),
                    departure_date=q.get("departure_date", collection_date),
                    collection_date=collection_date,
                    ap_days=q.get("ap_days", 0),
                    base_fare=q.get("base_fare", 0),
                    taxes=q.get("taxes", 0),
                    total_fare=q.get("total_fare", 0),
                    source=q.get("source", scraper.source_name),
                    is_valid=False,
                    rejection_reason=q.get("rejection_reason"),
                ))

            db.commit()

            # Per-source quality stats
            existing_dqs = (
                db.query(DataQualityStat)
                .filter(
                    DataQualityStat.date == collection_date,
                    DataQualityStat.source == scraper.source_name,
                )
                .first()
            )
            if existing_dqs:
                existing_dqs.quotes_collected += len(valid) + len(rejected)
                existing_dqs.quotes_rejected += len(rejected)
            else:
                db.add(DataQualityStat(
                    date=collection_date,
                    source=scraper.source_name,
                    quotes_collected=len(valid) + len(rejected),
                    quotes_rejected=len(rejected),
                    back_test_deviation_pct=0.0,
                ))
            db.commit()

            total_collected += len(valid)
            total_rejected += len(rejected)
            logger.info(
                "[Slot %s] %s done — %d valid, %d rejected",
                slot, scraper.source_name, len(valid), len(rejected),
            )

        # Recompute index after each slot (incremental updates throughout day)
        result = compute_apix_for_date(db, collection_date)
        if result:
            apix, coverage = result
            store_index_value(db, collection_date, apix, coverage)
            logger.info(
                "[Slot %s] APIx=%.2f for %s (coverage=%.1f%%)",
                slot, apix, collection_date, coverage,
            )
        else:
            logger.warning("[Slot %s] Insufficient data to compute APIx for %s", slot, collection_date)

        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        run.quotes_collected = total_collected
        run.quotes_rejected = total_rejected
        db.commit()

        logger.info(
            "=== Slot %s pipeline complete: %d collected, %d rejected ===",
            slot, total_collected, total_rejected,
        )

    except Exception as exc:
        logger.exception("[Slot %s] Pipeline failed: %s", slot, exc)
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = str(exc)
        db.commit()

    finally:
        db.close()


# ── Convenience wrappers for APScheduler ──────────────────────────────────────

def run_slot_a():
    """Morning slot: 06:30 IST (01:00 UTC)"""
    run_slot_pipeline("A")


def run_slot_b():
    """Midday slot: 12:30 IST (07:00 UTC)"""
    run_slot_pipeline("B")


def run_slot_c():
    """Evening slot: 19:30 IST (14:00 UTC)"""
    run_slot_pipeline("C")


# ── Scheduler lifecycle ───────────────────────────────────────────────────────

def start_scheduler():
    """
    Register all three daily scraping slots and start the scheduler.

    Times in UTC (IST = UTC + 5:30):
      Slot A: 01:00 UTC = 06:30 IST
      Slot B: 07:00 UTC = 12:30 IST
      Slot C: 14:00 UTC = 19:30 IST
    """
    # Slot A — morning
    scheduler.add_job(
        run_slot_a,
        CronTrigger(hour=1, minute=0, timezone="UTC"),
        id="slot_a",
        replace_existing=True,
        misfire_grace_time=1800,    # Allow up to 30 min late start
    )

    # Slot B — midday
    scheduler.add_job(
        run_slot_b,
        CronTrigger(hour=7, minute=0, timezone="UTC"),
        id="slot_b",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Slot C — evening
    scheduler.add_job(
        run_slot_c,
        CronTrigger(hour=14, minute=0, timezone="UTC"),
        id="slot_c",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.start()
    logger.info(
        "Scheduler started. Slots: A=06:30 IST, B=12:30 IST, C=19:30 IST "
        "(anti-bot rotation: EMT+Akasa / ClearTrip+SpiceJet / AIX+IndiGo)"
    )


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


# ── Manual trigger (for API endpoint /trigger-scrape) ────────────────────────

def run_daily_pipeline():
    """
    Backwards-compatible manual trigger — runs Slot A immediately.
    Called by POST /api/v1/trigger-scrape endpoint.
    """
    logger.info("Manual trigger: running Slot A pipeline now")
    run_slot_pipeline("A")
