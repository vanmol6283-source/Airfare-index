"""
Quick diagnostic script to test SerpAPI and web scrapers.
Run from backend/ with: venv\Scripts\python.exe test_scrapers.py
"""
import sys, os
# Force ASCII-safe output on Windows console
sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

import asyncio
import logging
from datetime import date, timedelta

# Make sure 'app' is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_scrapers")

# Test parameters
ORIGIN = "DEL"
DESTINATION = "BOM"
DEPARTURE_DATE = date.today() + timedelta(days=14)

SEP = "=" * 60


# ============================================================
# TEST 1: SerpAPI
# ============================================================

def test_serpapi():
    print(f"\n{SEP}")
    print("TEST 1: SerpAPI (Google Flights)")
    print(SEP)
    try:
        from app.scraper.serpapi_scraper import SerpApiScraper
        scraper = SerpApiScraper()
        key_ok = bool(scraper._api_key)
        print(f"  API Key loaded: {key_ok}")
        if scraper._api_key:
            print(f"  Key prefix:    {scraper._api_key[:8]}...")

        quotes = scraper._fetch_sync(ORIGIN, DESTINATION, DEPARTURE_DATE)
        if quotes:
            print(f"  [OK] {len(quotes)} quotes returned")
            for q in quotes[:3]:
                print(f"       {q['carrier']} | base=Rs.{q['base_fare']:.0f} | total=Rs.{q['total_fare']:.0f}")
        else:
            print("  [WARN] No quotes returned (empty result)")
        return bool(quotes)
    except Exception as e:
        print(f"  [FAIL] ERROR: {e}")
        import traceback; traceback.print_exc()
        return False


# ============================================================
# TEST 2: Playwright + Chromium
# ============================================================

def check_playwright():
    print(f"\n{SEP}")
    print("TEST 2: Playwright + Chromium availability")
    print(SEP)
    try:
        import playwright
        try:
            import importlib.metadata
            pw_ver = importlib.metadata.version("playwright")
        except Exception:
            pw_ver = "installed"
        print(f"  [OK] Playwright installed (version: {pw_ver})")
    except ImportError:
        print("  [FAIL] Playwright NOT installed. Run: pip install playwright")
        return False

    chromium_base = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
    print(f"  Playwright browser dir: {chromium_base}")
    if os.path.isdir(chromium_base):
        dirs = os.listdir(chromium_base)
        chromium_dirs = [d for d in dirs if d.startswith("chromium-")]
        if chromium_dirs:
            print(f"  [OK] Chromium found: {chromium_dirs[0]}")
            return True
        else:
            print(f"  [FAIL] Chromium NOT downloaded. Dirs found: {dirs}")
            print("         Run: venv\\Scripts\\playwright.exe install chromium")
            return False
    else:
        print(f"  [FAIL] Playwright directory does not exist: {chromium_base}")
        print("         Run: venv\\Scripts\\playwright.exe install chromium")
        return False


# ============================================================
# TEST 3: robots.txt
# ============================================================

def test_robots():
    print(f"\n{SEP}")
    print("TEST 3: robots.txt compliance check")
    print(SEP)
    from app.scraper.robots_checker import is_allowed

    test_urls = [
        "https://www.ixigo.com/search/result/flight?from=DEL&to=BOM&date=20261001",
        "https://flight.easemytrip.com/FlightList/Index?seg1=DELBOM",
        "https://www.akasaair.com/booking/select-flights?from=DEL&to=BOM",
        "https://book.goindigo.in/booking/SearchTrips?origin=DEL&destination=BOM",
    ]

    all_ok = True
    for url in test_urls:
        try:
            allowed = is_allowed(url)
            status = "ALLOWED" if allowed else "BLOCKED by robots.txt"
            print(f"  [{status}] {url[:65]}")
            if not allowed:
                all_ok = False
        except Exception as e:
            print(f"  [WARN] Error checking {url[:50]}: {e}")
    return all_ok


# ============================================================
# TEST 4: Ixigo
# ============================================================

async def test_ixigo():
    print(f"\n{SEP}")
    print("TEST 4: Ixigo scraper (Playwright)")
    print(SEP)
    try:
        from app.scraper.ixigo import IxigoScraper
        scraper = IxigoScraper()
        print(f"  Scraping {ORIGIN}->{DESTINATION} for {DEPARTURE_DATE}...")
        quotes = await scraper.scrape_route(ORIGIN, DESTINATION, DEPARTURE_DATE)
        if quotes:
            print(f"  [OK] {len(quotes)} quotes returned")
            for q in quotes[:3]:
                print(f"       {q['carrier']} | base=Rs.{q['base_fare']:.0f} | total=Rs.{q['total_fare']:.0f}")
        else:
            print("  [WARN] No quotes (CAPTCHA, no flights, or stale selectors)")
        return bool(quotes)
    except Exception as e:
        print(f"  [FAIL] ERROR: {e}")
        import traceback; traceback.print_exc()
        return False


# ============================================================
# TEST 5: EaseMyTrip
# ============================================================

async def test_easemytrip():
    print(f"\n{SEP}")
    print("TEST 5: EaseMyTrip scraper (Playwright)")
    print(SEP)
    try:
        from app.scraper.easemytrip import EaseMyTripScraper
        scraper = EaseMyTripScraper()
        print(f"  Scraping {ORIGIN}->{DESTINATION} for {DEPARTURE_DATE}...")
        quotes = await scraper.scrape_route(ORIGIN, DESTINATION, DEPARTURE_DATE)
        if quotes:
            print(f"  [OK] {len(quotes)} quotes returned")
            for q in quotes[:3]:
                print(f"       {q['carrier']} | base=Rs.{q['base_fare']:.0f} | total=Rs.{q['total_fare']:.0f}")
        else:
            print("  [WARN] No quotes (CAPTCHA, no flights, or stale selectors)")
        return bool(quotes)
    except Exception as e:
        print(f"  [FAIL] ERROR: {e}")
        import traceback; traceback.print_exc()
        return False


# ============================================================
# TEST 6: Akasa
# ============================================================

async def test_akasa():
    print(f"\n{SEP}")
    print("TEST 6: Akasa Air scraper (Playwright)")
    print(SEP)
    try:
        from app.scraper.akasa import AkasaScraper
        scraper = AkasaScraper()
        print(f"  Scraping {ORIGIN}->{DESTINATION} for {DEPARTURE_DATE}...")
        quotes = await scraper.scrape_route(ORIGIN, DESTINATION, DEPARTURE_DATE)
        if quotes:
            print(f"  [OK] {len(quotes)} quotes returned")
            for q in quotes[:3]:
                print(f"       {q['carrier']} | base=Rs.{q['base_fare']:.0f} | total=Rs.{q['total_fare']:.0f}")
        else:
            print("  [WARN] No quotes (CAPTCHA, no flights, or stale selectors)")
        return bool(quotes)
    except Exception as e:
        print(f"  [FAIL] ERROR: {e}")
        import traceback; traceback.print_exc()
        return False


# ============================================================
# MAIN
# ============================================================

async def main():
    print(f"\n{'*'*60}")
    print("  Airfare Scraper Diagnostic Test")
    print(f"  Route: {ORIGIN}->{DESTINATION}   Departure: {DEPARTURE_DATE}")
    print(f"{'*'*60}")

    results = {}

    results["serpapi"] = test_serpapi()
    playwright_ready = check_playwright()
    results["playwright_chromium"] = playwright_ready
    results["robots_txt"] = test_robots()

    if playwright_ready:
        results["easemytrip"] = await test_easemytrip()
        results["akasa"] = await test_akasa()
    else:
        print("\n[SKIP] Playwright scraper tests — Chromium not installed")
        results["easemytrip"] = False
        results["akasa"] = False

    print(f"\n{SEP}")
    print("SUMMARY")
    print(SEP)
    for name, ok in results.items():
        status = "[OK]  " if ok else "[FAIL]"
        print(f"  {status}  {name}")

    total_ok = sum(results.values())
    print(f"\n  {total_ok}/{len(results)} tests passed\n")


if __name__ == "__main__":
    if sys.platform == 'win32':
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main())
        finally:
            loop.close()
    else:
        asyncio.run(main())
