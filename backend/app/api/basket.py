"""
api/basket.py — GET /basket and GET /route/:id endpoints.
"""

from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import numpy as np

from app.database import get_db
from app.models import BasketItem, RawQuote

router = APIRouter()


def _get_current_fare_and_date(db: Session, origin: str, destination: str, ap_window: int):
    """Get the most recent representative fare and its date for a basket item."""
    latest_quote = (
        db.query(RawQuote.collection_date)
        .filter(
            RawQuote.origin == origin,
            RawQuote.destination == destination,
            RawQuote.ap_days == ap_window,
            RawQuote.is_valid == True,
        )
        .order_by(RawQuote.collection_date.desc())
        .first()
    )
    if not latest_quote:
        return None, None
    latest_date = latest_quote[0]
    quotes = (
        db.query(RawQuote.base_fare)
        .filter(
            RawQuote.origin == origin,
            RawQuote.destination == destination,
            RawQuote.ap_days == ap_window,
            RawQuote.collection_date == latest_date,
            RawQuote.is_valid == True,
        )
        .all()
    )
    return float(np.median([q.base_fare for q in quotes])), latest_date


def _get_fare_on_date(db: Session, origin: str, destination: str, ap_window: int, target_date: date) -> Optional[float]:
    """Get representative fare on a specific date."""
    quotes = (
        db.query(RawQuote.base_fare)
        .filter(
            RawQuote.origin == origin,
            RawQuote.destination == destination,
            RawQuote.ap_days == ap_window,
            RawQuote.collection_date == target_date,
            RawQuote.is_valid == True,  # noqa
        )
        .all()
    )
    if not quotes:
        return None
    return float(np.median([q.base_fare for q in quotes]))


def _get_history(db: Session, origin: str, destination: str, ap_window: int, latest_date: date, days: int = 30) -> List[dict]:
    """Get daily fare history for last N days ending at latest_date."""
    history = []
    if not latest_date:
        return history
    for i in range(days, -1, -1):
        d = latest_date - timedelta(days=i)
        fare = _get_fare_on_date(db, origin, destination, ap_window, d)
        if fare:
            history.append({"date": str(d), "fare": round(fare, 2)})
    return history


def _build_item_detail(db: Session, item: BasketItem) -> dict:
    """Build the enriched basket item dict for API response."""
    current_fare, latest_date = _get_current_fare_and_date(db, item.origin, item.destination, item.ap_window)
    base_fare = item.base_fare or current_fare or 0

    price_relative = (current_fare / base_fare) if (base_fare and current_fare) else 1.0

    # 7-day change
    change_7d = None
    if latest_date and current_fare:
        fare_7d = _get_fare_on_date(db, item.origin, item.destination, item.ap_window, latest_date - timedelta(days=7))
        if fare_7d and fare_7d > 0:
            change_7d = round(((current_fare - fare_7d) / fare_7d) * 100, 2)

    # 30-day change
    change_30d = None
    if latest_date and current_fare:
        fare_30d = _get_fare_on_date(db, item.origin, item.destination, item.ap_window, latest_date - timedelta(days=30))
        if fare_30d and fare_30d > 0:
            change_30d = round(((current_fare - fare_30d) / fare_30d) * 100, 2)

    # Data points (last 30 days)
    data_points = 0
    if latest_date:
        data_points = (
            db.query(RawQuote)
            .filter(
                RawQuote.origin == item.origin,
                RawQuote.destination == item.destination,
                RawQuote.ap_days == item.ap_window,
                RawQuote.collection_date >= latest_date - timedelta(days=30),
                RawQuote.is_valid == True,
            )
            .count()
        )

    history = _get_history(db, item.origin, item.destination, item.ap_window, latest_date)

    return {
        "route": item.route,
        "origin": item.origin,
        "destination": item.destination,
        "apWindow": f"T+{item.ap_window}",
        "baseFare": round(base_fare, 2),
        "currentFare": round(current_fare or base_fare, 2),
        "priceRelative": round(price_relative, 2),  # Truncated to 2 decimal places as requested
        "weight": round(item.weight, 2),            # Truncated to 2 decimal places as requested
        "change7d": change_7d,                      # Now None if unavailable
        "change30d": change_30d,
        "dataPoints": data_points,
        "history": history,
    }


@router.get(
    "/basket",
    summary="Get all basket items",
    description="Returns all active basket items with current fares, price relatives, and 30-day history.",
)
def get_basket(db: Session = Depends(get_db)):
    items = (
        db.query(BasketItem)
        .filter(BasketItem.is_active == True)  # noqa
        .order_by(BasketItem.route, BasketItem.ap_window)
        .all()
    )

    if not items:
        raise HTTPException(
            status_code=404,
            detail="No basket items found. Run: python seed_data.py",
        )

    return [_build_item_detail(db, item) for item in items]


@router.get(
    "/route/{route_id}",
    summary="Get single route detail",
    description="Returns all AP-window observations for a specific route with fare history.",
)
def get_route(route_id: str, db: Session = Depends(get_db)):
    # Normalise: accept DEL-BOM or DEL_BOM
    route_id = route_id.upper().replace("_", "-")

    items = (
        db.query(BasketItem)
        .filter(BasketItem.route == route_id, BasketItem.is_active == True)  # noqa
        .order_by(BasketItem.ap_window)
        .all()
    )

    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"Route '{route_id}' not found in basket. Valid routes: DEL-BOM, DEL-BLR, ...",
        )

    return [_build_item_detail(db, item) for item in items]
