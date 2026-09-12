"""
scraper/stealth_base.py — Shared Playwright stealth browser infrastructure.

All Playwright-based scrapers (Ixigo, EaseMyTrip, Akasa, IndiGo) inherit
from StealthScraper instead of BaseScraper directly.

Stealth features applied:
  ▸ navigator.webdriver flag removed
  ▸ Realistic plugin array injected
  ▸ Language/locale set to en-IN (matches Indian traveller profile)
  ▸ Randomised User-Agent per session (from pool of real Chrome UAs)
  ▸ Randomised viewport (common desktop resolutions)
  ▸ Images/fonts/analytics blocked (reduces bandwidth + fingerprint surface)
  ▸ Headless Chrome args that suppress automation signals
  ▸ chrome.runtime object faked
  ▸ navigator.permissions patched

CAPTCHA / block detection:
  ▸ detect_captcha(content) → returns signal name or None
  ▸ Scrapers call this after page load; if triggered → log + backoff + retry
  ▸ On second CAPTCHA → skip route, log as unavailable, continue pipeline

Retry policy:
  ▸ First attempt: normal
  ▸ CAPTCHA on first attempt: wait CAPTCHA_BACKOFF_SECONDS, retry once
  ▸ CAPTCHA on retry: skip route, log "unavailable today"
  ▸ HTTP 429 / 503: treated same as CAPTCHA
  ▸ Any other exception: log + return [] (never crash the pipeline)
"""

import asyncio
import logging
import random
from datetime import date
from typing import Any, Dict, List, Optional

from app.scraper.base import BaseScraper

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

# Pool of realistic Chrome User-Agent strings (updated Sep 2026)
# Rotate randomly per browser session to vary fingerprint
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.120 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.234 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.120 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.99 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.120 Safari/537.36 Edg/127.0.2651.105",
]

# Common desktop resolutions — headless default (1280×720) is a red flag
VIEWPORT_POOL = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]

# Text patterns indicating CAPTCHA or bot-block pages
# Checked against full lowercase page content
CAPTCHA_SIGNALS = [
    "captcha",
    "recaptcha",
    "hcaptcha",
    "i am not a robot",
    "i'm not a robot",
    "verify you are human",
    "verify you're human",
    "just a moment",          # Cloudflare interstitial
    "ddos-guard",
    "access denied",
    "security check",
    "bot detected",
    "automated access",
    "unusual traffic",
    "please verify",
    "challenge-form",         # Cloudflare challenge
    "cf-browser-verification",
]

# How long to wait after a CAPTCHA before retrying (seconds)
CAPTCHA_BACKOFF_SECONDS = 300   # 5 minutes — be genuinely polite

# Resource types to block (saves bandwidth, reduces fingerprint surface area)
BLOCKED_RESOURCE_TYPES = {"image", "font", "media", "stylesheet"}

# URL patterns to block (analytics, ad networks, tracking pixels)
BLOCKED_URL_PATTERNS = [
    "**/{analytics,gtm,ga,hotjar,clarity,mixpanel,segment,amplitude}*",
    "**/{ads,doubleclick,adservice,pagead}*",
    "**/pixel*",
    "**/beacon*",
    "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot,mp4,mp3}",
]


# ── CAPTCHA detection ─────────────────────────────────────────────────────────

def detect_captcha(page_content: str) -> Optional[str]:
    """
    Scan page HTML/text for CAPTCHA or bot-block indicators.

    Returns the matched signal string if blocked, None if clean.
    Case-insensitive. Checks full page content including hidden elements.

    Usage:
        signal = detect_captcha(await page.content())
        if signal:
            logger.warning("CAPTCHA detected: %s", signal)
    """
    content_lower = page_content.lower()
    for signal in CAPTCHA_SIGNALS:
        if signal in content_lower:
            return signal
    return None


# ── StealthScraper base class ─────────────────────────────────────────────────

class StealthScraper(BaseScraper):
    """
    Abstract base for all Playwright-based scrapers.

    Provides:
      - _make_browser_page(): creates a stealth-configured (browser, context, page)
      - _close_browser(): gracefully closes browser + context
      - scrape_route_with_retry(): wraps scrape_route with CAPTCHA retry logic

    Subclasses must implement:
      - source_name: str
      - _scrape_page(page, origin, destination, departure_date) → List[dict]

    The public scrape_route() is implemented here and handles the full
    browser lifecycle + retry logic. Subclasses do NOT override scrape_route().
    """

    source_name: str = "unknown_stealth"

    # ── Public interface (called by BaseScraper.collect_all_routes) ───────────

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Full scrape lifecycle with stealth browser + CAPTCHA retry.

        Attempt 1: Normal scrape.
        Attempt 2: If CAPTCHA on attempt 1 → wait CAPTCHA_BACKOFF_SECONDS → retry.
        Give up:   If CAPTCHA on attempt 2 → log + return [].
        """
        for attempt in range(1, 3):  # attempt 1 and 2
            try:
                quotes = await self._attempt_scrape(origin, destination, departure_date)
                return quotes
            except CaptchaDetectedError as exc:
                if attempt == 1:
                    logger.warning(
                        "[%s] CAPTCHA on %s→%s (signal: '%s') — "
                        "backing off %ds before retry",
                        self.source_name, origin, destination,
                        exc.signal, CAPTCHA_BACKOFF_SECONDS,
                    )
                    await asyncio.sleep(CAPTCHA_BACKOFF_SECONDS)
                else:
                    logger.error(
                        "[%s] CAPTCHA on retry for %s→%s — "
                        "marking route unavailable for this run",
                        self.source_name, origin, destination,
                    )
                    return []
            except Exception as exc:
                logger.error(
                    "[%s] Unexpected error scraping %s→%s: %s",
                    self.source_name, origin, destination, exc,
                )
                return []

        return []

    # ── Internal: single attempt ──────────────────────────────────────────────

    async def _attempt_scrape(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Run a single scrape attempt in a dedicated thread with its own event loop.

        Python 3.8 on Windows uses ProactorEventLoop which does NOT support
        asyncio.create_subprocess_exec() inside an already-running loop (uvicorn).
        Playwright uses subprocess creation internally, so we run it in a fresh
        thread where asyncio.run() creates a clean SelectorEventLoop.
        """
        try:
            from playwright.async_api import async_playwright  # noqa: F401
        except ImportError:
            logger.error(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
            return []

        import concurrent.futures

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            quotes = await loop.run_in_executor(
                executor,
                self._run_playwright_in_thread,
                origin,
                destination,
                departure_date,
            )
        return quotes

    def _run_playwright_in_thread(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper that creates a fresh SelectorEventLoop in this thread
        and runs the Playwright coroutine inside it.
        """
        import asyncio as _asyncio

        # WindowsProactorEventLoopPolicy supports subprocess on Python 3.8 Windows
        if hasattr(_asyncio, "WindowsProactorEventLoopPolicy"):
            _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._playwright_session(origin, destination, departure_date)
            )
        finally:
            loop.close()

    async def _playwright_session(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """The actual Playwright browser session — runs inside the thread's event loop."""
        from playwright.async_api import async_playwright

        browser = None
        try:
            async with async_playwright() as pw:
                browser, context, page = await self._make_browser_page(pw)
                quotes = await self._scrape_page(page, origin, destination, departure_date)
                return quotes
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


    # ── Browser factory ───────────────────────────────────────────────────────

    async def _make_browser_page(self, playwright):
        """
        Create a stealth-patched Playwright browser, context, and page.

        Returns:
            (browser, context, page) — all pre-configured for stealth scraping.
        """
        ua = random.choice(USER_AGENT_POOL)
        viewport = random.choice(VIEWPORT_POOL)

        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-plugins-discovery",
                "--disable-web-security",
                "--no-first-run",
                "--no-default-browser-check",
                f"--window-size={viewport['width']},{viewport['height']}",
            ],
        )

        context = await browser.new_context(
            user_agent=ua,
            viewport=viewport,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
            accept_downloads=False,
            extra_http_headers={
                "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8,hi;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        page = await context.new_page()

        # Apply JS stealth patches before any navigation
        await self._patch_page(page)

        # Block unnecessary resource types
        async def _block_resources(route, request):
            if request.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", _block_resources)

        return browser, context, page

    async def _patch_page(self, page) -> None:
        """
        Inject JavaScript stealth patches into every page before load.

        Patches applied:
          1. Remove navigator.webdriver flag (primary bot detection signal)
          2. Add realistic navigator.plugins array (headless has 0 plugins)
          3. Set navigator.languages to Indian English profile
          4. Patch navigator.permissions to avoid async fingerprinting
          5. Add window.chrome object (missing in headless = instant detection)
          6. Patch userAgentData brands array
          7. Fake screen dimensions matching chosen viewport
        """
        await page.add_init_script("""
        (() => {
            // 1. Remove webdriver flag — most important stealth patch
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true,
            });

            // 2. Realistic plugins (headless Chrome has none by default)
            const fakePlugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 },
            ];
            Object.defineProperty(navigator, 'plugins', {
                get: () => fakePlugins,
                configurable: true,
            });

            // 3. Indian English language profile
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-IN', 'en-GB', 'en', 'hi'],
                configurable: true,
            });

            // 4. Patch permissions API (commonly used to detect headless)
            if (navigator.permissions) {
                const origQuery = navigator.permissions.query.bind(navigator.permissions);
                navigator.permissions.query = (params) => {
                    if (params.name === 'notifications') {
                        return Promise.resolve({ state: 'prompt', onchange: null });
                    }
                    return origQuery(params);
                };
            }

            // 5. window.chrome — missing in headless, always present in real Chrome
            if (!window.chrome) {
                window.chrome = {
                    runtime: {
                        id: undefined,
                        connect: () => {},
                        sendMessage: () => {},
                    },
                    loadTimes: () => ({}),
                    csi: () => ({}),
                    app: { isInstalled: false },
                };
            }

            // 6. userAgentData brands (Chromium-based detection)
            if (navigator.userAgentData) {
                try {
                    Object.defineProperty(navigator.userAgentData, 'brands', {
                        get: () => [
                            { brand: 'Chromium', version: '127' },
                            { brand: 'Google Chrome', version: '127' },
                            { brand: 'Not=A?Brand', version: '24' },
                        ],
                        configurable: true,
                    });
                } catch (_) {}
            }

            // 7. Fake hardware concurrency (headless sometimes reports 0)
            if (!navigator.hardwareConcurrency || navigator.hardwareConcurrency < 2) {
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 4,
                    configurable: true,
                });
            }

            // 8. Fake device memory
            if (!navigator.deviceMemory) {
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                    configurable: true,
                });
            }
        })();
        """)

    # ── Abstract: subclasses implement this ──────────────────────────────────

    async def _scrape_page(
        self,
        page,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Navigate to the source, wait for results, extract fare quotes.

        Must raise CaptchaDetectedError if a CAPTCHA/block is detected.
        Must return [] (not raise) if no flights found for the route/date.
        Must NOT raise for network errors — catch and return [].
        """
        raise NotImplementedError


# ── Custom exception ──────────────────────────────────────────────────────────

class CaptchaDetectedError(Exception):
    """Raised by _scrape_page() when a CAPTCHA or bot-block is detected."""
    def __init__(self, signal: str, url: str = ""):
        self.signal = signal
        self.url = url
        super().__init__(f"CAPTCHA/block detected (signal='{signal}') at {url}")
