"""
models.py — SQLAlchemy ORM models.

Tables (original):
    basket_items        — route × AP-window basket composition + weights
    raw_quotes          — every fare observation scraped (immutable log)
    index_values        — computed daily composite APIx values
    scrape_runs         — audit log of scraping jobs
    data_quality_stats  — per-source quality statistics

Tables (new — support 8-stage pipeline):
    cell_estimates      — Stage 1: robust median per (route, carrier, ap_window, date, source)
    elasticity_params   — Stage 4: log-linear fit (alpha, beta) per (route, date)
    route_index_values  — Stage 6: per-route daily market-share weighted fare + sub-index
    dgca_benchmarks     — Stage 8: DGCA published monthly average fares (back-test input)
    seasonal_calendar   — Event/holiday calendar for dashboard spike annotation
    source_variance_stats — Stage 2 input: rolling variance per data source
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, Float, String, Date, DateTime,
    Boolean, Text, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# ORIGINAL TABLES (unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

class BasketItem(Base):
    """
    One row per route × AP-window combination.
    Defines basket composition and weights for index calculation.
    """
    __tablename__ = "basket_items"

    id = Column(Integer, primary_key=True, index=True)
    route = Column(String(16), nullable=False)         # e.g. "DEL-BOM"
    origin = Column(String(3), nullable=False)          # IATA code
    destination = Column(String(3), nullable=False)     # IATA code
    ap_window = Column(Integer, nullable=False)         # days before departure (1,7,15,30,45)
    weight = Column(Float, nullable=False)              # normalised weight (sum≈100)
    base_fare = Column(Float, nullable=True)            # fare at base period (INR)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    quotes = relationship("RawQuote", back_populates="basket_item")

    __table_args__ = (
        UniqueConstraint("route", "ap_window", name="uq_basket_route_window"),
    )


class RawQuote(Base):
    """
    Immutable log of every fare observation collected by the scraper.
    One row per quote; base fare and taxes stored separately.
    """
    __tablename__ = "raw_quotes"

    id = Column(Integer, primary_key=True, index=True)
    basket_item_id = Column(Integer, ForeignKey("basket_items.id"), nullable=True)

    # Route / flight metadata
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    carrier = Column(String(8), nullable=True)          # IATA carrier code
    flight_number = Column(String(10), nullable=True)
    fare_class = Column(String(4), nullable=True)       # Y, S, Q, …

    # Timing
    departure_date = Column(Date, nullable=False)
    collection_date = Column(Date, nullable=False)
    ap_days = Column(Integer, nullable=False)
    collection_timestamp = Column(DateTime, default=datetime.utcnow)

    # Fare breakdown (INR)
    base_fare = Column(Float, nullable=False)
    taxes = Column(Float, nullable=True, default=0)
    udf = Column(Float, nullable=True, default=0)
    convenience_fee = Column(Float, nullable=True, default=0)
    total_fare = Column(Float, nullable=False)

    # Source metadata
    source = Column(String(64), nullable=False)
    is_valid = Column(Boolean, default=True)
    rejection_reason = Column(String(128), nullable=True)

    basket_item = relationship("BasketItem", back_populates="quotes")

    __table_args__ = (
        # Original indexes
        Index("ix_raw_quotes_route_date", "origin", "destination", "collection_date"),
        Index("ix_raw_quotes_collection_date", "collection_date"),
        # NEW: compound index for compute_representative_fare() query performance
        # This query runs 40× per pipeline invocation — must be fast
        Index(
            "ix_raw_quotes_pipeline_lookup",
            "origin", "destination", "ap_days", "collection_date", "is_valid",
        ),
        # NEW: carrier-level analysis index
        Index("ix_raw_quotes_carrier_route", "carrier", "origin", "destination", "collection_date"),
    )


class IndexValue(Base):
    """
    Computed composite APIx index values — one row per date.
    Aggregated weekly/monthly values are derived at query time.
    """
    __tablename__ = "index_values"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    apix = Column(Float, nullable=False)
    basket_coverage = Column(Float, nullable=True)   # % of basket items with data
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScrapeRun(Base):
    """Audit log for each scheduled scraping job execution."""
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, default="running")
    quotes_attempted = Column(Integer, default=0)
    quotes_collected = Column(Integer, default=0)
    quotes_rejected = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


class DataQualityStat(Base):
    """Per-source daily quality statistics."""
    __tablename__ = "data_quality_stats"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(64), nullable=False)
    quotes_collected = Column(Integer, default=0)
    quotes_rejected = Column(Integer, default=0)
    back_test_deviation_pct = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("date", "source", name="uq_dqs_date_source"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TABLES — 8-stage pipeline support
# ═══════════════════════════════════════════════════════════════════════════════

class CellEstimate(Base):
    """
    Stage 1 output: robust median fare per (route, carrier, ap_window, date, source).

    One row per cell after MAD outlier removal. Preserved for:
      - Pipeline diagnostics
      - Source variance computation (feeds Stage 2 next run)
      - Dashboard "raw vs cleaned" comparison
    """
    __tablename__ = "cell_estimates"

    id = Column(Integer, primary_key=True, index=True)
    route = Column(String(16), nullable=False)
    carrier_code = Column(String(8), nullable=False)
    ap_window_bucket = Column(Integer, nullable=False)
    collection_date = Column(Date, nullable=False, index=True)
    source = Column(String(64), nullable=False)

    fare_median_inr = Column(Float, nullable=True)
    n_obs = Column(Integer, nullable=False, default=0)
    n_outliers_removed = Column(Integer, nullable=False, default=0)
    is_sparse = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cell_est_route_date", "route", "collection_date"),
        UniqueConstraint(
            "route", "carrier_code", "ap_window_bucket", "collection_date", "source",
            name="uq_cell_estimate",
        ),
    )


class ElasticityParam(Base):
    """
    Stage 4 output: log-linear AP-window elasticity curve parameters.

    Stored per (route, collection_date).
    Serves dashboard "lead-time elasticity" visualisation (PS requirement).
    beta < 0 means fares increase as departure approaches.
    """
    __tablename__ = "elasticity_params"

    id = Column(Integer, primary_key=True, index=True)
    route = Column(String(16), nullable=False)
    collection_date = Column(Date, nullable=False, index=True)

    alpha = Column(Float, nullable=True)       # intercept: ln(p) = alpha + beta*ln(w)
    beta = Column(Float, nullable=True)        # slope (elasticity) — expected < 0
    r_squared = Column(Float, nullable=True)   # fit quality (0–1)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("route", "collection_date", name="uq_elasticity_route_date"),
        Index("ix_elasticity_date", "collection_date"),
    )


class RouteIndexValue(Base):
    """
    Stage 6 output: per-route, per-AP-window daily market-share weighted fares.

    Enables DGCA to analyse individual routes independently of the composite index.
    Also used for route-level heatmap in the dashboard (PS requirement).
    """
    __tablename__ = "route_index_values"

    id = Column(Integer, primary_key=True, index=True)
    route = Column(String(16), nullable=False)
    ap_window_bucket = Column(Integer, nullable=False)
    collection_date = Column(Date, nullable=False, index=True)

    route_fare_inr = Column(Float, nullable=True)   # market-share weighted fare
    is_imputed = Column(Boolean, default=False)      # True if filled by elasticity model

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "route", "ap_window_bucket", "collection_date",
            name="uq_route_index_value",
        ),
        Index("ix_route_iv_route_date", "route", "collection_date"),
    )


class DGCABenchmark(Base):
    """
    Stage 8 input: DGCA officially published monthly average fares by route.

    Populated manually from DGCA Monthly Traffic Reports (Excel/PDF).
    Used for 30-day back-test validation as required by the problem statement.
    """
    __tablename__ = "dgca_benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    route = Column(String(16), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)          # 1–12
    dgca_avg_fare_inr = Column(Float, nullable=False)
    source_document = Column(String(128), nullable=True)  # e.g. "DGCA_Traffic_Report_Aug2026"
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("route", "year", "month", name="uq_dgca_benchmark"),
        Index("ix_dgca_benchmark_route", "route"),
    )


class SeasonalCalendar(Base):
    """
    Event/holiday calendar for dashboard spike annotation.

    Allows DGCA analysts to correlate fare spikes with known demand events
    (festivals, IPL, school holidays, long weekends).

    Pre-populated with Indian aviation demand events. Maintained annually.
    """
    __tablename__ = "seasonal_calendar"

    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(128), nullable=False)  # e.g. "Diwali 2026"
    event_type = Column(String(32), nullable=False)   # FESTIVAL / HOLIDAY / SPORT / OTHER
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_seasonal_dates", "start_date", "end_date"),
    )


class SourceVarianceStat(Base):
    """
    Stage 2 input: rolling historical variance per data source.

    Updated after each pipeline run by comparing each source's cell estimates
    against the reconciled (fused) value. Lower variance → higher weight.

    Enables adaptive inverse-variance weighting that improves over time
    as more pipeline runs accumulate.
    """
    __tablename__ = "source_variance_stats"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False, unique=True)
    variance_inr_squared = Column(Float, nullable=False, default=1.0)
    n_samples = Column(Integer, nullable=False, default=0)
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
