"""
seed_data.py — Seeds 90 days of historical airfare data for demonstration.

Runs BEFORE starting the server for the first time.

Usage:
    cd backend
    python seed_data.py

What it does:
  1. Creates all database tables
  2. Inserts basket items (8 routes × 5 AP windows = 40 items)
  3. Generates 90 days of simulated fare quotes using MockScraper logic
  4. Computes and stores APIx index values for each day
  5. Creates data quality stat records

This gives a 90-day back-tested history for demonstration.
"""

import asyncio
import sys
import os
import logging
from datetime import date, timedelta, datetime, timezone

# Make sure imports resolve from backend/ directory
sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, Base, SessionLocal
from app.models import BasketItem, RawQuote, IndexValue, DataQualityStat
from app.pipeline.cleaner import validate_and_flag
from app.pipeline.index import compute_apix_for_date, store_index_value

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── Basket configuration ───────────────────────────────────────────────────────
# Weights based on approximate DGCA FY2024 passenger traffic shares
# (normalised so sum = 100)
BASKET = [
    # route, origin, dest, ap_window_days, weight, base_fare (INR)
    # AP windows: T+1, T+7, T+15, T+30, T+45 (per problem statement)
    # Weights: approximate DGCA FY2024 passenger traffic shares (normalised sum≈100)
    ("DEL-BOM", "DEL", "BOM", 1,  3.21, 8900),
    ("DEL-BOM", "DEL", "BOM", 7,  3.21, 6800),
    ("DEL-BOM", "DEL", "BOM", 15, 3.21, 5800),
    ("DEL-BOM", "DEL", "BOM", 30, 3.21, 5200),
    ("DEL-BOM", "DEL", "BOM", 45, 3.21, 4700),

    ("DEL-BLR", "DEL", "BLR", 1,  2.88, 8200),
    ("DEL-BLR", "DEL", "BLR", 7,  2.88, 6300),
    ("DEL-BLR", "DEL", "BLR", 15, 2.88, 5400),
    ("DEL-BLR", "DEL", "BLR", 30, 2.88, 4800),
    ("DEL-BLR", "DEL", "BLR", 45, 2.88, 4300),

    ("BOM-BLR", "BOM", "BLR", 1,  2.10, 6500),
    ("BOM-BLR", "BOM", "BLR", 7,  2.10, 5000),
    ("BOM-BLR", "BOM", "BLR", 15, 2.10, 4200),
    ("BOM-BLR", "BOM", "BLR", 30, 2.10, 3800),
    ("BOM-BLR", "BOM", "BLR", 45, 2.10, 3400),

    ("DEL-CCU", "DEL", "CCU", 1,  1.85, 7800),
    ("DEL-CCU", "DEL", "CCU", 7,  1.85, 6000),
    ("DEL-CCU", "DEL", "CCU", 15, 1.85, 5100),
    ("DEL-CCU", "DEL", "CCU", 30, 1.85, 4500),
    ("DEL-CCU", "DEL", "CCU", 45, 1.85, 4000),

    ("BLR-HYD", "BLR", "HYD", 1,  1.42, 5400),
    ("BLR-HYD", "BLR", "HYD", 7,  1.42, 4100),
    ("BLR-HYD", "BLR", "HYD", 15, 1.42, 3500),
    ("BLR-HYD", "BLR", "HYD", 30, 1.42, 2800),
    ("BLR-HYD", "BLR", "HYD", 45, 1.42, 2500),

    ("MAA-DEL", "MAA", "DEL", 1,  1.68, 8100),
    ("MAA-DEL", "MAA", "DEL", 7,  1.68, 6200),
    ("MAA-DEL", "MAA", "DEL", 15, 1.68, 5300),
    ("MAA-DEL", "MAA", "DEL", 30, 1.68, 4900),
    ("MAA-DEL", "MAA", "DEL", 45, 1.68, 4400),

    ("DEL-HYD", "DEL", "HYD", 1,  1.55, 7200),
    ("DEL-HYD", "DEL", "HYD", 7,  1.55, 5500),
    ("DEL-HYD", "DEL", "HYD", 15, 1.55, 4700),
    ("DEL-HYD", "DEL", "HYD", 30, 1.55, 3900),
    ("DEL-HYD", "DEL", "HYD", 45, 1.55, 3500),

    ("BOM-CCU", "BOM", "CCU", 1,  1.38, 7500),
    ("BOM-CCU", "BOM", "CCU", 7,  1.38, 5700),
    ("BOM-CCU", "BOM", "CCU", 15, 1.38, 4900),
    ("BOM-CCU", "BOM", "CCU", 30, 1.38, 4200),
    ("BOM-CCU", "BOM", "CCU", 45, 1.38, 3700),
]

# Verify weights sum to ~100
total_weight = sum(b[4] for b in BASKET)
logger.info(f"Total basket weight: {total_weight:.2f} (should be ~100)")


def generate_fare(base_fare: float, day_index: int, ap_window: int) -> float:
    """
    Generate a realistic fare for a given day offset from the base period.

    Incorporates:
      - Gradual upward trend (~8% per year)
      - Weekly seasonality (Mon/Fri peaks)
      - AP-window variation
      - Small random noise (deterministic via day_index)
    """
    import math, random
    rng = random.Random(day_index * 31 + ap_window * 97)

    # Long-term trend: ~8% annual rise
    trend = 1 + (day_index / 365) * 0.08

    # Weekly cycle: sin wave with period 7 days
    weekly = 1 + 0.04 * math.sin(2 * math.pi * day_index / 7)

    # AP window multiplier
    ap_mult = {1: 1.70, 7: 1.40, 15: 1.20, 30: 1.05, 45: 0.90}.get(ap_window, 1.0)

    # Random noise ±4%
    noise = rng.uniform(0.96, 1.04)

    fare = base_fare * trend * weekly * ap_mult * noise
    return round(fare / ap_mult, -1)  # return base (not AP-adjusted) for storage


def seed():
    logger.info("=" * 60)
    logger.info("Airfare Price Index — Data Seeder")
    logger.info("=" * 60)

    # Create tables
    logger.info("\n[1/5] Creating database tables…")
    Base.metadata.create_all(bind=engine)
    logger.info("  Tables created.")

    db = SessionLocal()

    try:
        # ── Basket items ──────────────────────────────────────────────────────
        logger.info("\n[2/5] Inserting basket items…")
        existing = db.query(BasketItem).count()
        if existing > 0:
            logger.info(f"  Basket already has {existing} items — skipping.")
        else:
            for route, origin, dest, ap_window, weight, base_fare in BASKET:
                db.add(BasketItem(
                    route=route,
                    origin=origin,
                    destination=dest,
                    ap_window=ap_window,
                    weight=weight,
                    base_fare=base_fare,
                    is_active=True,
                ))
            db.commit()
            logger.info(f"  Inserted {len(BASKET)} basket items.")

        # ── Historical quotes ─────────────────────────────────────────────────
        logger.info("\n[3/5] Generating 90 days of historical fare quotes…")
        base_date = date(2026, 5, 29)  # Base period
        today = date(2026, 8, 27)
        all_dates = []
        d = base_date
        while d <= today:
            all_dates.append(d)
            d += timedelta(days=1)

        # Check if quotes already exist
        existing_quotes = db.query(RawQuote).count()
        if existing_quotes > 0:
            logger.info(f"  {existing_quotes} quotes already exist — skipping.")
        else:
            total_quotes = 0
            for day_i, collection_date in enumerate(all_dates):
                for route, origin, dest, ap_window, weight, base_fare in BASKET:
                    # Generate 2-3 quotes per basket item per day (simulating multi-source)
                    import random
                    rng = random.Random(day_i * 1000 + hash(route) % 997 + ap_window)
                    n_quotes = rng.randint(2, 3)

                    for q_i in range(n_quotes):
                        fare = generate_fare(base_fare, day_i, ap_window)
                        noise = rng.uniform(0.98, 1.03)
                        fare = round(fare * noise, -1)
                        taxes = round(fare * 0.185, -1)
                        udf = 295 if origin in ("DEL", "BOM") or dest in ("DEL", "BOM") else 150

                        carrier = rng.choice(["6E", "AI", "QP"])
                        dep_date = collection_date + timedelta(days=ap_window)

                        basket_item = (
                            db.query(BasketItem)
                            .filter(
                                BasketItem.route == route,
                                BasketItem.ap_window == ap_window,
                            )
                            .first()
                        )

                        db.add(RawQuote(
                            basket_item_id=basket_item.id if basket_item else None,
                            origin=origin,
                            destination=dest,
                            carrier=carrier,
                            fare_class=rng.choice(["S", "Q", "T"]),
                            departure_date=dep_date,
                            collection_date=collection_date,
                            ap_days=ap_window,
                            base_fare=fare,
                            taxes=taxes,
                            udf=udf,
                            convenience_fee=0,
                            total_fare=fare + taxes + udf,
                            source=f"{carrier.lower()}.seeded",
                            is_valid=True,
                        ))
                        total_quotes += 1

                if day_i % 10 == 0:
                    db.commit()
                    logger.info(f"  Day {day_i+1}/{len(all_dates)} seeded…")

            db.commit()
            logger.info(f"  Total quotes inserted: {total_quotes}")

        # ── Index values ──────────────────────────────────────────────────────
        logger.info("\n[4/5] Computing index values for all seeded days…")
        all_dates2 = []
        d = base_date
        while d <= today:
            all_dates2.append(d)
            d += timedelta(days=1)

        existing_index = db.query(IndexValue).count()
        if existing_index > 0:
            logger.info(f"  {existing_index} index values already exist — skipping.")
        else:
            computed = 0
            for collection_date in all_dates2:
                result = compute_apix_for_date(db, collection_date)
                if result:
                    apix, coverage = result
                    store_index_value(db, collection_date, apix, coverage)
                    computed += 1
            logger.info(f"  Computed {computed} daily index values.")

        # ── Data quality stubs ─────────────────────────────────────────────────
        logger.info("\n[5/5] Adding data quality records…")
        existing_dqs = db.query(DataQualityStat).count()
        if existing_dqs > 0:
            logger.info(f"  {existing_dqs} quality records already exist — skipping.")
        else:
            d = base_date
            while d <= today:
                for source in ["6E.seeded", "AI.seeded", "QP.seeded"]:
                    n = len(BASKET) * 2  # ~2 quotes per item per day
                    db.add(DataQualityStat(
                        date=d,
                        source=source,
                        quotes_collected=n,
                        quotes_rejected=0,
                        back_test_deviation_pct=round(abs(0.5 + (hash(str(d) + source) % 200) / 100), 2),
                    ))
                d += timedelta(days=1)
            db.commit()
            logger.info("  Quality records inserted.")

        logger.info("\n" + "=" * 60)
        logger.info("Seeding complete!")
        logger.info("")

        # Print final summary
        n_basket = db.query(BasketItem).count()
        n_quotes = db.query(RawQuote).count()
        n_index = db.query(IndexValue).count()
        latest = db.query(IndexValue).order_by(IndexValue.date.desc()).first()

        logger.info(f"  Basket items  : {n_basket}")
        logger.info(f"  Total quotes  : {n_quotes:,}")
        logger.info(f"  Index values  : {n_index}")
        if latest:
            logger.info(f"  Latest APIx   : {latest.apix:.2f} ({latest.date})")
        logger.info("")
        logger.info("Now start the server:")
        logger.info("  uvicorn app.main:app --reload --port 8000")
        logger.info("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    seed()
