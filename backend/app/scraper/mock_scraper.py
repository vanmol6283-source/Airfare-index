"""
scraper/mock_scraper.py — Deterministic mock scraper for development/testing.

Produces realistic INR fare data without making real network requests.
Used when SCRAPING_ENABLED=False (the default in development).

The mock generates fares using:
  - Route-specific base prices
  - AP-window price curves (last-minute premium, early-discount)
  - Day-of-week variation
  - ±5% random noise
  - Weekly / seasonal trend
"""

import math
import random
from datetime import date
from typing import List, Dict, Any

from app.scraper.base import BaseScraper

# Route base fares (economy, INR) — calibrated to realistic Indian market prices
ROUTE_BASE_FARES: Dict[str, float] = {
    "DEL-BOM": 5200,
    "DEL-BLR": 4800,
    "BOM-BLR": 3800,
    "DEL-CCU": 4500,
    "BLR-HYD": 2800,
    "MAA-DEL": 4900,
    "DEL-HYD": 3900,
    "BOM-CCU": 4200,
}

# AP-window multipliers: [T+1, T+7, T+15, T+30, T+45]
# Last-minute tickets are most expensive; deep advance is cheapest
AP_MULTIPLIERS: Dict[int, float] = {
    1:  1.70,
    7:  1.40,
    15: 1.20,
    30: 1.05,
    45: 0.88,
}

# Day-of-week demand premium (0=Mon)
DOW_PREMIUM: Dict[int, float] = {
    0: 1.05,   # Monday: moderate
    1: 0.97,   # Tuesday: cheapest
    2: 0.98,   # Wednesday
    3: 1.03,   # Thursday
    4: 1.15,   # Friday: peak
    5: 1.18,   # Saturday: peak
    6: 1.08,   # Sunday: high
}

CARRIERS: Dict[str, List[str]] = {
    "DEL-BOM": ["6E", "AI", "QP", "G8"],
    "DEL-BLR": ["6E", "AI", "QP"],
    "BOM-BLR": ["6E", "AI", "QP"],
    "DEL-CCU": ["6E", "AI"],
    "BLR-HYD": ["6E", "AI"],
    "MAA-DEL": ["6E", "AI", "QP"],
    "DEL-HYD": ["6E", "AI", "G8"],
    "BOM-CCU": ["6E", "AI"],
}


class MockScraper(BaseScraper):
    """
    Deterministic fake scraper for development.

    Produces 2–4 fare quotes per route/date combination,
    simulating multiple carriers and slight price variations.
    """

    source_name = "mock.dev"

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> List[Dict[str, Any]]:
        route = f"{origin}-{destination}"
        base = ROUTE_BASE_FARES.get(route, 4000)

        ap_days_approx = (departure_date - date.today()).days
        # Clamp to known windows for multiplier lookup
        ap_key = min(
            settings_ap_windows(),
            key=lambda w: abs(w - max(1, ap_days_approx)),
        )
        ap_mult = AP_MULTIPLIERS.get(ap_key, 1.0)
        dow_mult = DOW_PREMIUM.get(departure_date.weekday(), 1.0)

        # Seasonal trend: slight upward drift over time
        days_from_ref = (departure_date - date(2026, 5, 29)).days
        trend_mult = 1 + (days_from_ref / 365) * 0.08

        # Seed randomness deterministically from the date + route
        # so repeated calls return same values (reproducible)
        rng = random.Random(
            hash(f"{route}-{departure_date.isoformat()}")
        )

        carriers = CARRIERS.get(route, ["6E", "AI"])
        n_quotes = rng.randint(2, min(len(carriers), 4))
        selected = rng.sample(carriers, n_quotes)

        quotes = []
        for carrier in selected:
            noise = rng.uniform(0.95, 1.06)
            # Carrier premium: AI and QP slightly higher
            carrier_mult = 1.08 if carrier == "AI" else 1.03 if carrier == "QP" else 1.0
            fare = base * ap_mult * dow_mult * trend_mult * noise * carrier_mult
            fare = round(fare, -1)  # round to nearest 10

            taxes = round(fare * 0.18, -1)   # ~18% GST equivalent
            udf = 295 if "DEL" in route or "BOM" in route else 150

            quotes.append({
                "carrier": carrier,
                "flight_number": f"{carrier}{rng.randint(100, 999)}",
                "fare_class": rng.choice(["S", "Q", "T", "V"]),
                "base_fare": fare,
                "taxes": taxes,
                "udf": udf,
                "convenience_fee": 0,
                "total_fare": fare + taxes + udf,
            })

        return quotes


def settings_ap_windows():
    from app.config import settings
    return settings.AP_WINDOWS
