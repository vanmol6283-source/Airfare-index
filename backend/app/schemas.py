"""
schemas.py — Pydantic v2 schemas for request/response validation.

All monetary values are in INR.
All dates are ISO-8601 strings (YYYY-MM-DD).
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ── Basket ────────────────────────────────────────────────────────────────────

class BasketItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route: str
    origin: str
    destination: str
    ap_window: int          # days before departure
    weight: float
    base_fare: Optional[float]
    is_active: bool


# ── Raw Quote ─────────────────────────────────────────────────────────────────

class RawQuoteIn(BaseModel):
    """Schema for inserting quotes (used by scraper internally)."""
    origin: str
    destination: str
    carrier: Optional[str] = None
    flight_number: Optional[str] = None
    fare_class: Optional[str] = None
    departure_date: date
    collection_date: date
    ap_days: int
    base_fare: float
    taxes: float = 0.0
    udf: float = 0.0
    convenience_fee: float = 0.0
    total_fare: float
    source: str


class RawQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: str
    destination: str
    carrier: Optional[str]
    departure_date: date
    collection_date: date
    ap_days: int
    base_fare: float
    taxes: float
    total_fare: float
    source: str
    is_valid: bool


# ── Index ─────────────────────────────────────────────────────────────────────

class IndexHistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    apix: float
    frequency: str = "daily"


class IndexSummary(BaseModel):
    apix_today: float = Field(alias="apixToday")
    mom_change: float = Field(alias="momChange")
    yoy_change: float = Field(alias="yoyChange")
    last_updated: datetime = Field(alias="lastUpdated")
    routes_tracked: int = Field(alias="routesTracked")
    data_points_today: int = Field(alias="dataPointsToday")

    model_config = ConfigDict(populate_by_name=True)


# ── Route-level detail (basket item enriched with computed fields) ─────────────

class HistoryPoint(BaseModel):
    date: str
    fare: float


class BasketItemDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    route: str
    origin: str
    destination: str
    ap_window: str = Field(alias="apWindow")
    base_fare: float = Field(alias="baseFare")
    current_fare: float = Field(alias="currentFare")
    price_relative: float = Field(alias="priceRelative")
    weight: float
    change_7d: float = Field(alias="change7d")
    change_30d: float = Field(alias="change30d")
    data_points: int = Field(alias="dataPoints")
    history: List[HistoryPoint]


# ── Data Quality ──────────────────────────────────────────────────────────────

class DataQualityStatOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: str
    last_scraped: datetime = Field(alias="lastScraped")
    quotes_collected: int = Field(alias="quotesCollected")
    quotes_rejected: int = Field(alias="quotesRejected")
    back_test_deviation_pct: float = Field(alias="backTestDeviationPct")


# ── Scrape run ────────────────────────────────────────────────────────────────

class ScrapeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    started_at: datetime = Field(alias="startedAt")
    finished_at: Optional[datetime] = Field(alias="finishedAt")
    status: str
    quotes_collected: int = Field(alias="quotesCollected")
    quotes_rejected: int = Field(alias="quotesRejected")
    error_message: Optional[str] = Field(alias="errorMessage")


# ── Generic responses ─────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
