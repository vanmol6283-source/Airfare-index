"""
api/summary.py — GET /summary endpoint.

Returns the top-level index summary including:
  - Latest APIx value
  - MoM and YoY change
  - Last updated timestamp
  - Routes tracked
  - Data points collected today
"""

from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IndexValue, RawQuote, BasketItem
from app.pipeline.index import compute_mom_change, compute_yoy_change
from app.schemas import IndexSummary

router = APIRouter()


@router.get(
    "/summary",
    response_model=IndexSummary,
    summary="Get current index summary",
    description=(
        "Returns the latest APIx value, period-on-period changes, "
        "routes tracked, and today's data point count."
    ),
)
def get_summary(db: Session = Depends(get_db)):
    # Latest index value
    latest = (
        db.query(IndexValue)
        .order_by(IndexValue.date.desc())
        .first()
    )

    if not latest:
        raise HTTPException(
            status_code=404,
            detail="No index values found. Run the seeder first: python seed_data.py",
        )

    today = date.today()

    # Data points collected today
    data_points_today = (
        db.query(RawQuote)
        .filter(
            RawQuote.collection_date == today,
            RawQuote.is_valid == True,  # noqa
        )
        .count()
    )

    # If no data yet today, use latest available day's count
    if data_points_today == 0:
        data_points_today = (
            db.query(RawQuote)
            .filter(
                RawQuote.collection_date == latest.date,
                RawQuote.is_valid == True,  # noqa
            )
            .count()
        )

    routes_tracked = (
        db.query(BasketItem.route)
        .filter(BasketItem.is_active == True)  # noqa
        .distinct()
        .count()
    )

    # Period-on-period changes
    reference_date = latest.date
    mom = compute_mom_change(db, reference_date)
    yoy = compute_yoy_change(db, reference_date)

    last_updated = datetime.combine(latest.date, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    return IndexSummary(
        apixToday=round(latest.apix, 2),
        momChange=round(mom, 2),
        yoyChange=round(yoy, 2),
        lastUpdated=last_updated,
        routesTracked=routes_tracked,
        dataPointsToday=data_points_today,
    )
