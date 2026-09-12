"""
pipeline/index.py — APIx index construction module.

Formula:
    APIx(t) = Σᵢ [W(i) × PR(i,t)] / ΣW(i)
    PR(i,t) = P(i,t) / P(i,0) × 100

Where:
    i        = basket item (route × AP window)
    W(i)     = traffic weight (normalised, sum = 100)
    P(i,t)   = observed fare at time t (median of valid quotes for that day)
    P(i,0)   = base period fare

Change measures:
    MoM% = (APIx_month2 - APIx_month1) / APIx_month1 × 100
    YoY% = (APIx_t - APIx_t-12mo) / APIx_t-12mo × 100
"""

import logging
from datetime import date, timedelta
from typing import List, Optional, Tuple, Dict

import numpy as np
from sqlalchemy.orm import Session

from app.models import BasketItem, RawQuote, IndexValue

logger = logging.getLogger(__name__)


def compute_representative_fare(
    db: Session,
    origin: str,
    destination: str,
    ap_window: int,
    collection_date: date,
) -> Optional[float]:
    """
    Compute the representative fare for a basket item on a given date.

    Representative fare = median of all valid base-fare quotes collected
    on `collection_date` for the given route and AP window.

    Returns None if no valid quotes exist for that day.
    """
    quotes = (
        db.query(RawQuote.base_fare)
        .filter(
            RawQuote.origin == origin,
            RawQuote.destination == destination,
            RawQuote.ap_days == ap_window,
            RawQuote.collection_date == collection_date,
            RawQuote.is_valid == True,  # noqa: E712
        )
        .all()
    )

    if not quotes:
        return None

    fares = [q.base_fare for q in quotes]
    return float(np.median(fares))


def compute_price_relative(
    current_fare: float,
    base_fare: float,
) -> float:
    """PR(i,t) = P(i,t) / P(i,0) × 100"""
    if base_fare is None or base_fare == 0:
        return 100.0
    return (current_fare / base_fare) * 100.0


def compute_apix_for_date(
    db: Session,
    target_date: date,
) -> Optional[Tuple[float, float]]:
    """
    Compute the APIx value for a specific date.

    Returns:
        (apix_value, basket_coverage_pct) or None if insufficient data.

    Raises:
        ValueError if fewer than 50% of basket items have data.
    """
    basket = (
        db.query(BasketItem)
        .filter(BasketItem.is_active == True)  # noqa: E712
        .all()
    )

    if not basket:
        logger.warning("Basket is empty — cannot compute APIx")
        return None

    weighted_sum = 0.0
    weight_total = 0.0
    items_with_data = 0

    for item in basket:
        if item.base_fare is None:
            logger.warning(
                "Basket item %s AP+%s has no base fare set",
                item.route, item.ap_window,
            )
            continue

        current_fare = compute_representative_fare(
            db,
            item.origin,
            item.destination,
            item.ap_window,
            target_date,
        )

        if current_fare is None:
            logger.debug(
                "No quote for %s AP+%s on %s — skipping",
                item.route, item.ap_window, target_date,
            )
            continue

        pr = compute_price_relative(current_fare, item.base_fare)
        weighted_sum += item.weight * pr
        weight_total += item.weight
        items_with_data += 1

    if weight_total == 0:
        logger.warning("No basket items had data on %s", target_date)
        return None

    coverage = (items_with_data / len(basket)) * 100.0

    if coverage < 50.0:
        logger.warning(
            "Basket coverage on %s is only %.1f%% — index not published",
            target_date, coverage,
        )
        return None

    apix = weighted_sum / weight_total
    return round(apix, 4), round(coverage, 2)


def store_index_value(db: Session, target_date: date, apix: float, coverage: float):
    """
    Upsert the computed APIx value for a date.
    """
    existing = db.query(IndexValue).filter(IndexValue.date == target_date).first()
    if existing:
        existing.apix = apix
        existing.basket_coverage = coverage
    else:
        db.add(IndexValue(date=target_date, apix=apix, basket_coverage=coverage))
    db.commit()
    logger.info("Stored APIx=%.4f for %s (coverage=%.1f%%)", apix, target_date, coverage)


def compute_mom_change(db: Session, current_date: date) -> float:
    """
    Month-on-Month change = (current_month_avg - prev_month_avg) / prev_month_avg × 100
    """
    # Current month: all index values in the current calendar month up to today
    curr_start = current_date.replace(day=1)
    curr_values = (
        db.query(IndexValue.apix)
        .filter(IndexValue.date >= curr_start, IndexValue.date <= current_date)
        .all()
    )

    # Previous calendar month
    prev_end = curr_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    prev_values = (
        db.query(IndexValue.apix)
        .filter(IndexValue.date >= prev_start, IndexValue.date <= prev_end)
        .all()
    )

    if not curr_values or not prev_values:
        return 0.0

    curr_avg = np.mean([v.apix for v in curr_values])
    prev_avg = np.mean([v.apix for v in prev_values])

    if prev_avg == 0:
        return 0.0

    return round(((curr_avg - prev_avg) / prev_avg) * 100.0, 4)


def compute_yoy_change(db: Session, current_date: date) -> float:
    """
    Year-on-Year change = (APIx_today - APIx_same_day_last_year) / APIx_last_year × 100
    Uses a 7-day window around the same date last year to handle missing values.
    """
    last_year_date = current_date.replace(year=current_date.year - 1)
    window_start = last_year_date - timedelta(days=3)
    window_end = last_year_date + timedelta(days=3)

    last_year_values = (
        db.query(IndexValue.apix)
        .filter(IndexValue.date >= window_start, IndexValue.date <= window_end)
        .all()
    )

    today_row = db.query(IndexValue).filter(IndexValue.date == current_date).first()

    if not last_year_values or not today_row:
        return 0.0

    last_year_avg = np.mean([v.apix for v in last_year_values])
    if last_year_avg == 0:
        return 0.0

    return round(((today_row.apix - last_year_avg) / last_year_avg) * 100.0, 4)


def aggregate_by_frequency(
    records: List[IndexValue],
    frequency: str,
) -> List[dict]:
    """
    Aggregate daily IndexValue records into weekly or monthly periods.

    Weekly:  Monday-aligned week; value = mean of daily values in that week.
    Monthly: Calendar month; value = mean of daily values in that month.
    """
    if frequency == "daily":
        return [
            {"date": str(r.date), "apix": round(r.apix, 4), "frequency": "daily"}
            for r in records
        ]

    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)

    for r in records:
        d = r.date
        if frequency == "weekly":
            # ISO Monday
            dow = d.weekday()   # 0=Mon
            monday = d - timedelta(days=dow)
            key = str(monday)
        elif frequency == "monthly":
            key = f"{d.year}-{d.month:02d}"
        else:
            key = str(d)

        groups[key].append(r.apix)

    return sorted(
        [
            {
                "date": k,
                "apix": round(float(np.mean(v)), 4),
                "frequency": frequency,
            }
            for k, v in groups.items()
        ],
        key=lambda x: x["date"],
    )
