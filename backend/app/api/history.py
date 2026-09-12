"""
api/history.py — GET /index-history endpoint.
"""

from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IndexValue
from app.pipeline.index import aggregate_by_frequency

router = APIRouter()


@router.get(
    "/index-history",
    summary="Get index history",
    description=(
        "Returns the daily APIx index history. "
        "Optionally aggregated to weekly or monthly frequency by arithmetic averaging."
    ),
)
def get_index_history(
    freq: Literal["daily", "weekly", "monthly"] = Query(
        default="daily",
        description="Aggregation frequency: daily, weekly, or monthly",
    ),
    db: Session = Depends(get_db),
):
    records = (
        db.query(IndexValue)
        .order_by(IndexValue.date.asc())
        .all()
    )

    return aggregate_by_frequency(records, freq)
