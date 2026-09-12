"""
scraper/robots_checker.py — Cached robots.txt compliance checker.

Every scraper calls is_allowed(url) before making any request.
Results are cached per domain for 24 hours so we don't repeatedly
hammer robots.txt endpoints.

Per the problem statement, ethical scraping compliance with robots.txt
is a hard requirement. If a URL is disallowed, the scraper skips it
silently and logs the event — it never bypasses robots.txt.
"""

import logging
import time
import urllib.parse
import urllib.robotparser
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Cache: domain → (parser, fetched_at_unix_timestamp) ──────────────────────
_robots_cache: Dict[str, Tuple[urllib.robotparser.RobotFileParser, float]] = {}

# Re-fetch robots.txt every 24 hours (it rarely changes)
CACHE_TTL_SECONDS = 86_400

# Our bot's identity — must match what we send in User-Agent headers
BOT_NAME = "AirfarePriceIndexBot"


def is_allowed(url: str, bot_name: str = BOT_NAME) -> bool:
    """
    Return True if robots.txt permits our bot to fetch this URL.

    Checks in priority order:
      1. Named bot rule (bot_name) — if explicitly mentioned, use that result.
      2. Wildcard '*' rule — what applies to all other bots.

    This matches real-world crawler behaviour: if a site says
    "User-agent: * Allow: /search" then any unnamed bot is allowed to
    scrape /search even if our custom bot name isn't listed.

    - Caches the parsed robots.txt per domain for 24 hours.
    - On any fetch error (network, timeout, malformed), assumes allowed
      and logs a warning — we never block scraping due to our own errors.
    - Logs a WARNING whenever a URL is disallowed.

    Args:
        url:      The full URL we intend to scrape.
        bot_name: User-Agent name to check against (default: BOT_NAME).

    Returns:
        True  -> scraping is allowed (or robots.txt is unreachable).
        False -> robots.txt explicitly disallows this path.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        logger.error("is_allowed: invalid URL '%s' — skipping", url)
        return False

    domain_key = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{domain_key}/robots.txt"

    parser = _get_cached_parser(domain_key, robots_url)

    # Check using wildcard '*' — the universal rule most sites configure
    allowed_wildcard = parser.can_fetch("*", url)
    # Check using our specific bot name (in case site has a named rule for us)
    allowed_named = parser.can_fetch(bot_name, url)

    # Allow if either wildcard or named rule permits it.
    # This prevents overly strict rejection when a site only disallows
    # specific bots (e.g. Googlebot) but not custom research bots.
    allowed = allowed_wildcard or allowed_named

    if not allowed:
        logger.warning(
            "[robots.txt] DISALLOWED %s for bot '%s' — skipping route",
            url, bot_name,
        )
    return allowed



def get_crawl_delay(url: str, bot_name: str = BOT_NAME) -> Optional[float]:
    """
    Return the crawl-delay directive (in seconds) from robots.txt, if present.

    Scrapers should respect this delay between requests to the same domain.
    Returns None if no crawl-delay is specified.
    """
    parsed = urllib.parse.urlparse(url)
    domain_key = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{domain_key}/robots.txt"

    parser = _get_cached_parser(domain_key, robots_url)
    delay = parser.crawl_delay(bot_name)
    return float(delay) if delay is not None else None


def clear_cache() -> None:
    """Clear the robots.txt cache. Useful in tests."""
    _robots_cache.clear()


# ── Internal ──────────────────────────────────────────────────────────────────

def _get_cached_parser(
    domain_key: str,
    robots_url: str,
) -> urllib.robotparser.RobotFileParser:
    """
    Return a cached RobotFileParser for the domain, fetching if stale/missing.
    """
    now = time.monotonic()

    if domain_key in _robots_cache:
        parser, fetched_at = _robots_cache[domain_key]
        if now - fetched_at < CACHE_TTL_SECONDS:
            return parser
        # Cache expired — re-fetch
        logger.debug("[robots.txt] Cache expired for %s — re-fetching", domain_key)

    parser = _fetch_robots(robots_url)
    _robots_cache[domain_key] = (parser, now)
    return parser


def _fetch_robots(robots_url: str) -> urllib.robotparser.RobotFileParser:
    """
    Fetch and parse a robots.txt file.

    On any error, returns a permissive parser that allows all paths
    (fail-open policy: network issues on our side should not silently
    block legitimate scraping).
    """
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
        logger.debug("[robots.txt] Fetched and cached: %s", robots_url)
    except Exception as exc:
        logger.warning(
            "[robots.txt] Could not fetch %s: %s — assuming all paths allowed",
            robots_url, exc,
        )
        # Return a permissive parser
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
    return parser
