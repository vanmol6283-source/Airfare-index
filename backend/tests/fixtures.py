"""
tests/fixtures.py — Minimal test data for integration tests.
"""

from datetime import date, timedelta
from app.models import BasketItem, RawQuote, IndexValue


def seed_test_data(db):
    """Insert minimal data for test assertions."""
    # One basket item per route (just T+7)
    routes = [
        ("DEL-BOM", "DEL", "BOM", 1,  3.21, 5200),
        ("DEL-BOM", "DEL", "BOM", 7,  3.21, 5200),
        ("DEL-BOM", "DEL", "BOM", 15, 3.21, 5200),
        ("DEL-BOM", "DEL", "BOM", 30, 3.21, 5200),
        ("DEL-BOM", "DEL", "BOM", 45, 3.21, 5200),
        ("DEL-BLR", "DEL", "BLR", 7,  2.88, 4800),
        ("BOM-BLR", "BOM", "BLR", 7,  2.10, 3800),
        ("DEL-CCU", "DEL", "CCU", 7,  1.85, 4500),
        ("BLR-HYD", "BLR", "HYD", 7,  1.42, 2800),
        ("MAA-DEL", "MAA", "DEL", 7,  1.68, 4900),
        ("DEL-HYD", "DEL", "HYD", 7,  1.55, 3900),
        ("BOM-CCU", "BOM", "CCU", 7,  1.38, 4200),
    ]

    basket_items = {}
    for route, origin, dest, ap, weight, base_fare in routes:
        item = BasketItem(
            route=route, origin=origin, destination=dest,
            ap_window=ap, weight=weight, base_fare=base_fare, is_active=True,
        )
        db.add(item)
        db.flush()
        basket_items[(route, ap)] = item.id

    db.commit()

    # 35 days of quotes and index values
    today = date.today()
    for days_back in range(35, -1, -1):
        col_date = today - timedelta(days=days_back)
        for route, origin, dest, ap, weight, base_fare in routes:
            import random
            rng = random.Random(days_back * 100 + ap)
            for _ in range(2):
                fare = base_fare * (1 + days_back * 0.001) * rng.uniform(0.98, 1.02)
                fare = round(fare, -1)
                db.add(RawQuote(
                    basket_item_id=basket_items.get((route, ap)),
                    origin=origin,
                    destination=dest,
                    ap_days=ap,
                    departure_date=col_date + timedelta(days=ap),
                    collection_date=col_date,
                    base_fare=fare,
                    taxes=round(fare * 0.18, -1),
                    udf=295,
                    convenience_fee=0,
                    total_fare=round(fare * 1.18 + 295, -1),
                    source="test.seeded",
                    is_valid=True,
                ))

        # Simple index: mean price relative across all items for this date
        db.add(IndexValue(
            date=col_date,
            apix=100 + (35 - days_back) * 0.12,
            basket_coverage=100.0,
        ))

    db.commit()
