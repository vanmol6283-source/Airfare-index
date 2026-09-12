"""
pipeline/apix_pipeline.py — APIx Real-time Airfare Price Index Pipeline
========================================================================

Implements the 8-stage methodology:
  1. Robust point estimate per cell (MAD outlier removal + median)
  2. Cross-source reconciliation (inverse-variance weighting)
  3. Fare decomposition (base vs tax, regulatory-calibrated, not flat %)
  4. AP-window elasticity curve (log-linear fit)
  5. Missing cell imputation (using elasticity model)
  6. Route-level aggregation across carriers (DGCA market-share weights)
  7. Index construction (Törnqvist chain index)
  8. Validation vs DGCA monthly averages (MAPE)

Input:  A pandas DataFrame of raw scraped/API fare quotes.
Output: PipelineOutput dataclass with all intermediate tables + final index.

This module is STATELESS — no DB access. The scheduler (scheduler.py)
feeds it a DataFrame from the DB and stores its output back to the DB.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Regulatory / reference data ───────────────────────────────────────────────
# Source: AERA airport tariff orders + DGCA carrier statistics FY2024

GST_RATE_ECONOMY = 0.05  # 5% GST on economy base fare (India)

# Per-airport fixed charges: UDF + PSF + RCS levies (INR)
# Source: AERA airport tariff orders. Update periodically.
AIRPORT_FIXED_CHARGES = {
    "DEL": 500, "BOM": 450, "BLR": 400, "CCU": 350,
    "HYD": 400, "MAA": 380, "GOI": 300, "AMD": 280,
    "PNQ": 260, "JAI": 260, "LKO": 240, "ATQ": 220,
}
DEFAULT_AIRPORT_CHARGE = 250  # fallback for airports not listed

# DGCA FY2024 domestic carrier market share (route-agnostic fallback)
# Source: DGCA Monthly Domestic Traffic Report
CARRIER_MARKET_SHARE = {
    "6E": 0.60,  # IndiGo
    "AI": 0.13,  # Air India
    "SG": 0.05,  # SpiceJet
    "QP": 0.10,  # Akasa Air
    "IX": 0.07,  # Air India Express
    "UK": 0.05,  # Vistara (merged into AI, weight kept for legacy data)
    "G8": 0.00,  # Go First (ceased operations)
}

# AP window buckets — must match config.py AP_WINDOWS
AP_BUCKETS = [1, 7, 15, 30, 45]

MIN_OBS_PER_CELL = 3          # minimum observations for a non-sparse estimate
OUTLIER_MAD_THRESHOLD = 3.5   # modified z-score threshold (Iglewicz & Hoaglin)


# ── Stage 0 — Input helpers ───────────────────────────────────────────────────

def bucket_ap_window(departure_date: pd.Timestamp, collection_date: pd.Timestamp) -> int:
    """Snap raw (departure - collection) day-gap to the nearest defined AP bucket."""
    days = max(0, (departure_date - collection_date).days)
    return min(AP_BUCKETS, key=lambda w: abs(w - days))


def validate_input_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalise the raw input DataFrame.
    Ensures required columns are present and typed correctly.
    Drops rows with null route, carrier, or fare.
    """
    required = [
        "route", "origin", "destination", "carrier_code",
        "ap_window_bucket", "collection_date", "total_fare_inr", "source",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Input DataFrame missing required columns: {missing}")

    df = df.copy()
    df["collection_date"] = pd.to_datetime(df["collection_date"])
    df["total_fare_inr"] = pd.to_numeric(df["total_fare_inr"], errors="coerce")
    df = df.dropna(subset=["route", "carrier_code", "total_fare_inr"])
    df = df[df["total_fare_inr"] > 0]
    return df


# ── Stage 1 — Robust point estimate (MAD outlier removal + median) ────────────

def mad_outlier_mask(
    values: np.ndarray,
    threshold: float = OUTLIER_MAD_THRESHOLD,
) -> np.ndarray:
    """
    Median Absolute Deviation (MAD) outlier detection.

    Uses the modified z-score method (Iglewicz & Hoaglin 1993):
        modified_z = 0.6745 * |x - median| / MAD
    Flags observations with |modified_z| > threshold as outliers.

    Returns boolean mask: True = keep, False = outlier.

    Why MAD over IQR or z-score:
      - Airfare distributions are right-skewed (occasional extreme high fares)
      - MAD is resistant to these extremes (unlike variance/std-based methods)
      - More sensitive to subtle outliers than IQR (factor of 3.0 is too lenient)
    """
    if len(values) < 2:
        return np.ones(len(values), dtype=bool)
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    if mad == 0:
        # All values identical — no outliers possible
        return np.ones(len(values), dtype=bool)
    modified_z = 0.6745 * (values - med) / mad
    return np.abs(modified_z) <= threshold


def stage1_robust_cell_estimate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Stage 1: Collapse raw quotes into robust cell estimates.

    Groups by (route, carrier_code, ap_window_bucket, collection_date, source).
    Within each cell:
      1. Apply MAD outlier filter
      2. Compute median of remaining observations
      3. Flag sparse cells (n < MIN_OBS_PER_CELL)

    Returns one row per cell with columns:
      fare_median_inr, n_obs, n_outliers_removed, is_sparse
    """
    group_cols = ["route", "carrier_code", "ap_window_bucket", "collection_date", "source"]

    def _agg(g: pd.DataFrame) -> pd.Series:
        vals = g["total_fare_inr"].to_numpy(dtype=float)
        mask = mad_outlier_mask(vals)
        clean = vals[mask]
        n = len(clean)
        return pd.Series({
            "fare_median_inr": float(np.median(clean)) if n > 0 else np.nan,
            "n_obs": int(n),
            "n_outliers_removed": int(len(vals) - n),
            "is_sparse": n < MIN_OBS_PER_CELL,
        })

    result = (
        df.groupby(group_cols, observed=True)
        .apply(_agg, include_groups=False)
        .reset_index()
    )
    logger.debug("Stage 1: %d cells, %d sparse",
                 len(result), result["is_sparse"].sum())
    return result


# ── Stage 2 — Cross-source reconciliation (inverse-variance weighting) ────────

def stage2_reconcile_sources(
    cell_df: pd.DataFrame,
    source_variance: dict,
) -> pd.DataFrame:
    """
    Stage 2: Fuse multiple sources' estimates for the same cell.

    Cell = (route, carrier_code, ap_window_bucket, collection_date).
    When multiple sources (e.g. SerpAPI + Ixigo) observe the same cell,
    combine using inverse-variance weighting:

        w_s = 1 / sigma_s^2
        fare_fused = sum(w_s * fare_s) / sum(w_s)

    source_variance: {source_name: variance_inr_squared}
        Start with equal variances → simple mean.
        Update empirically from stage8 deviations over time.

    If only one source observes a cell, its estimate passes through unchanged.
    """
    group_cols = ["route", "carrier_code", "ap_window_bucket", "collection_date"]

    def _fuse(g: pd.DataFrame) -> pd.Series:
        g = g.dropna(subset=["fare_median_inr"])
        if g.empty:
            return pd.Series({
                "fare_reconciled_inr": np.nan,
                "n_sources": 0,
                "total_n_obs": 0,
                "any_sparse": True,
            })
        weights = g["source"].map(lambda s: 1.0 / max(source_variance.get(s, 1.0), 0.01))
        fused = float(np.average(g["fare_median_inr"], weights=weights))
        return pd.Series({
            "fare_reconciled_inr": fused,
            "n_sources": int(g["source"].nunique()),
            "total_n_obs": int(g["n_obs"].sum()),
            "any_sparse": bool(g["is_sparse"].any()),
        })

    result = (
        cell_df.groupby(group_cols, observed=True)
        .apply(_fuse, include_groups=False)
        .reset_index()
    )
    logger.debug("Stage 2: %d reconciled cells, %d have multiple sources",
                 len(result), (result["n_sources"] > 1).sum())
    return result


# ── Stage 3 — Fare decomposition (regulatory-calibrated) ─────────────────────

def stage3_decompose_fare(row: pd.Series) -> pd.Series:
    """
    Stage 3: Decompose total fare into base fare + taxes/UDF.

    Formula (India aviation tax structure):
        Total = Base * (1 + GST_RATE) + F_origin + F_destination
        => Base = (Total - F_origin - F_destination) / (1 + GST_RATE)

    Uses AERA-published per-airport fixed charges (UDF + PSF + RCS levy)
    instead of a flat percentage approximation.

    Applied row-wise to the reconciled fare DataFrame.
    """
    origin = row.get("origin", "")
    destination = row.get("destination", "")
    total = row.get("fare_reconciled_inr", np.nan)

    if pd.isna(total) or total <= 0:
        return pd.Series({"base_fare_inr": np.nan, "tax_udf_inr": np.nan})

    f_o = AIRPORT_FIXED_CHARGES.get(origin, DEFAULT_AIRPORT_CHARGE)
    f_d = AIRPORT_FIXED_CHARGES.get(destination, DEFAULT_AIRPORT_CHARGE)

    base = (total - f_o - f_d) / (1.0 + GST_RATE_ECONOMY)
    base = max(base, 100.0)   # guard against negative base fares
    tax_udf = total - base

    return pd.Series({
        "base_fare_inr": round(base, 2),
        "tax_udf_inr": round(tax_udf, 2),
    })


def apply_decomposition(reconciled: pd.DataFrame, route_meta: pd.DataFrame) -> pd.DataFrame:
    """Apply stage3_decompose_fare across the reconciled DataFrame."""
    df = reconciled.merge(route_meta, on="route", how="left")
    decomp = df.apply(stage3_decompose_fare, axis=1)
    return pd.concat([df, decomp], axis=1)


# ── Stage 4 — AP-window elasticity curve: ln(p) = alpha + beta * ln(w) ────────

def stage4_fit_elasticity(panel_df: pd.DataFrame) -> pd.DataFrame:
    """
    Stage 4: Fit log-linear advance-purchase elasticity curve per (route, date).

        ln(fare) = alpha + beta * ln(ap_window)

    beta < 0: fares rise as departure approaches (expected, confirmed in literature).
    |beta| measures fare elasticity w.r.t. booking lead time.

    Requires at least 2 non-null AP windows to fit. Returns NaN otherwise.

    The elasticity curve serves two purposes:
      1. Imputation (Stage 5): fill missing AP-window cells
      2. Dashboard: "Lead-time elasticity" curve visualisation (per PS requirement)
    """
    group_cols = ["route", "collection_date"]

    def _fit(g: pd.DataFrame) -> pd.Series:
        g = g.dropna(subset=["fare_reconciled_inr"])
        g = g[g["fare_reconciled_inr"] > 0]
        if len(g) < 2:
            return pd.Series({"alpha": np.nan, "beta": np.nan, "r_squared": np.nan})
        x = np.log(g["ap_window_bucket"].to_numpy(dtype=float))
        y = np.log(g["fare_reconciled_inr"].to_numpy(dtype=float))
        try:
            coeffs = np.polyfit(x, y, 1)
            beta, alpha = float(coeffs[0]), float(coeffs[1])
            # Compute R² for quality indicator
            y_hat = alpha + beta * x
            ss_res = np.sum((y - y_hat) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        except np.linalg.LinAlgError:
            return pd.Series({"alpha": np.nan, "beta": np.nan, "r_squared": np.nan})

        return pd.Series({"alpha": alpha, "beta": beta, "r_squared": r2})

    result = (
        panel_df.groupby(group_cols, observed=True)
        .apply(_fit, include_groups=False)
        .reset_index()
    )
    valid = result["alpha"].notna().sum()
    logger.debug("Stage 4: %d elasticity curves fitted, %d valid", len(result), valid)
    return result


# ── Stage 5 — Impute missing cells using elasticity model ─────────────────────

def stage5_impute_missing(
    panel_df: pd.DataFrame,
    elasticity_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Stage 5: Fill missing (route, carrier, ap_window, date) cells.

    Imputation formula:
        p_hat = exp(alpha + beta * ln(ap_window))

    Only applied when:
      - fare_reconciled_inr is NaN (missing, not observed)
      - alpha and beta are available (elasticity curve fitted)

    Imputed rows are flagged with is_imputed=True so downstream stages
    can weight them differently or exclude them from quality metrics.
    """
    merged = panel_df.merge(
        elasticity_df[["route", "collection_date", "alpha", "beta"]],
        on=["route", "collection_date"],
        how="left",
    )

    needs_impute = (
        merged["fare_reconciled_inr"].isna()
        & merged["alpha"].notna()
        & merged["beta"].notna()
        & (merged["ap_window_bucket"] > 0)
    )

    if needs_impute.any():
        imputed_vals = np.exp(
            merged.loc[needs_impute, "alpha"]
            + merged.loc[needs_impute, "beta"]
            * np.log(merged.loc[needs_impute, "ap_window_bucket"].astype(float))
        )
        merged.loc[needs_impute, "fare_reconciled_inr"] = imputed_vals.round(2)
        logger.debug("Stage 5: imputed %d missing cells", needs_impute.sum())

    merged["is_imputed"] = needs_impute
    return merged.drop(columns=["alpha", "beta"], errors="ignore")


# ── Stage 6 — Route-level aggregation (carrier market-share weighting) ────────

def stage6_aggregate_route(panel_df: pd.DataFrame) -> pd.DataFrame:
    """
    Stage 6: Collapse the carrier dimension into a single route-level fare.

    For each (route, ap_window_bucket, collection_date):
      - Weight each carrier's fare by its DGCA market share
      - Renormalize weights to carriers actually observed that day
      - Compute weighted average → route_fare_inr

    This gives a market-representative fare for the route,
    not just the cheapest or an unweighted mean.
    """
    group_cols = ["route", "ap_window_bucket", "collection_date"]

    def _agg(g: pd.DataFrame) -> float:
        g = g.dropna(subset=["fare_reconciled_inr"])
        if g.empty:
            return np.nan
        weights = g["carrier_code"].map(
            lambda c: CARRIER_MARKET_SHARE.get(c, 0.01)
        ).to_numpy(dtype=float)
        weight_sum = weights.sum()
        if weight_sum <= 0:
            return float(g["fare_reconciled_inr"].mean())
        weights = weights / weight_sum
        return float(np.average(g["fare_reconciled_inr"].to_numpy(), weights=weights))

    result = (
        panel_df.groupby(group_cols, observed=True)
        .apply(lambda g: _agg(g), include_groups=False)
        .reset_index(name="route_fare_inr")
    )
    result = result.dropna(subset=["route_fare_inr"])
    logger.debug("Stage 6: %d route-level fare observations", len(result))
    return result


# ── Stage 7 — Törnqvist chain index ──────────────────────────────────────────

def stage7_tornqvist_index(
    route_panel: pd.DataFrame,
    route_ap_weights: dict,
    base_value: float = 100.0,
) -> pd.DataFrame:
    """
    Stage 7: Construct the chain-linked Törnqvist price index.

    The Törnqvist index is superlative (satisfies time-reversal and factor-
    reversal tests) and is recommended by the IMF PPI Manual for high-
    frequency price indices. It is preferred over Laspeyres for airfare
    because basket composition shifts with booking patterns.

    Chain-linking formula:
        ln(APIx_t / APIx_{t-1}) = Σ_{r,w} s̄_{r,w} * ln(p_{r,w,t} / p_{r,w,t-1})

    Where s̄_{r,w} = average expenditure share of cell (r,w) in periods t and t-1.
    We approximate s̄ with fixed route_ap_weights (updated periodically from DGCA).

    Missing cells in a given period: renormalize weights to observed cells only
    (avoids index bias from systematic missing data patterns).

    route_ap_weights: dict {(route, ap_window_bucket): expenditure_share}
        Must sum to 1.0 across the full basket.
        See build_equal_ap_weights() or build_dgca_weighted_ap_weights().
    """
    pivot = route_panel.pivot_table(
        index="collection_date",
        columns=["route", "ap_window_bucket"],
        values="route_fare_inr",
    ).sort_index()

    dates = pivot.index.tolist()
    if not dates:
        return pd.DataFrame(columns=["collection_date", "apix", "basket_coverage_pct"])

    index_vals = [base_value]
    coverage_vals = [100.0]
    total_cells = len(pivot.columns)

    for i in range(1, len(dates)):
        prev_row = pivot.iloc[i - 1]
        curr_row = pivot.iloc[i]

        log_ratio_sum = 0.0
        weight_sum_used = 0.0
        cells_used = 0

        for (route, w) in pivot.columns:
            p_prev = prev_row.get((route, w), np.nan)
            p_curr = curr_row.get((route, w), np.nan)
            weight = route_ap_weights.get((route, w), 0.0)

            if pd.isna(p_prev) or pd.isna(p_curr) or p_prev <= 0 or p_curr <= 0:
                continue
            if weight == 0:
                continue

            log_ratio_sum += weight * np.log(p_curr / p_prev)
            weight_sum_used += weight
            cells_used += 1

        if weight_sum_used > 0:
            # Renormalize: missing cells → redistribute their weight
            growth = np.exp(log_ratio_sum / weight_sum_used * sum(route_ap_weights.values()))
        else:
            growth = 1.0   # no data → index flat for this period

        index_vals.append(round(index_vals[-1] * growth, 4))
        coverage_vals.append(round(cells_used / total_cells * 100.0, 2) if total_cells > 0 else 0.0)

    result = pd.DataFrame({
        "collection_date": dates,
        "apix": index_vals,
        "basket_coverage_pct": coverage_vals,
    })
    logger.info("Stage 7: computed %d daily APIx values (latest=%.4f)",
                len(result), result["apix"].iloc[-1] if len(result) > 0 else 0)
    return result


def build_equal_ap_weights(routes: list, dgca_route_share: dict) -> dict:
    """
    Build route_ap_weights assuming equal split across AP buckets within each route.

    Replace with build_dgca_weighted_ap_weights() once you have booking-curve data.
    """
    weights = {}
    n_routes = len(routes)
    for r in routes:
        route_share = dgca_route_share.get(r, 1.0 / max(n_routes, 1))
        per_bucket = route_share / len(AP_BUCKETS)
        for w in AP_BUCKETS:
            weights[(r, w)] = per_bucket
    # Normalise to sum = 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}
    return weights


def build_dgca_weighted_ap_weights(
    routes: list,
    dgca_route_share: dict,
    ap_booking_curve: dict,
) -> dict:
    """
    Build route_ap_weights using DGCA route share + empirical booking curve.

    ap_booking_curve: {ap_window: share_of_bookings_at_this_window}
        e.g. {1: 0.05, 7: 0.15, 15: 0.25, 30: 0.35, 45: 0.20}
        Estimate from DGCA advance-purchase booking data if available.
    """
    # Normalise booking curve
    total_bc = sum(ap_booking_curve.values())
    norm_bc = {w: v / total_bc for w, v in ap_booking_curve.items()}

    weights = {}
    for r in routes:
        route_share = dgca_route_share.get(r, 1.0 / max(len(routes), 1))
        for w in AP_BUCKETS:
            weights[(r, w)] = route_share * norm_bc.get(w, 1.0 / len(AP_BUCKETS))

    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}
    return weights


# ── Stage 8 — Validation vs DGCA monthly averages (MAPE) ─────────────────────

def stage8_validate_against_dgca(
    route_panel: pd.DataFrame,
    dgca_monthly_avg: pd.DataFrame,
) -> pd.DataFrame:
    """
    Stage 8: Compute Mean Absolute Percentage Error vs DGCA benchmarks.

    Aggregates our daily route_fare_inr to monthly mean per route and compares
    against DGCA's published monthly average fare.

    dgca_monthly_avg: DataFrame with columns [route, month (YYYY-MM), dgca_avg_fare_inr]

    Returns per-route MAPE (%) — the PS requires demonstrating this for 30 days.
    A MAPE < 5% is considered excellent for a price index.
    """
    rp = route_panel.copy()
    rp["month"] = pd.to_datetime(rp["collection_date"]).dt.to_period("M").astype(str)

    our_monthly = (
        rp.groupby(["route", "month"])["route_fare_inr"]
        .mean()
        .reset_index()
        .rename(columns={"route_fare_inr": "our_avg_fare_inr"})
    )

    merged = our_monthly.merge(dgca_monthly_avg, on=["route", "month"], how="inner")
    if merged.empty:
        logger.warning("Stage 8: no overlapping months between our data and DGCA benchmarks")
        return pd.DataFrame(columns=["route", "mape_pct", "n_months"])

    merged["abs_pct_error"] = (
        (merged["our_avg_fare_inr"] - merged["dgca_avg_fare_inr"]).abs()
        / merged["dgca_avg_fare_inr"].clip(lower=1.0)
        * 100.0
    )

    mape = (
        merged.groupby("route")
        .agg(
            mape_pct=("abs_pct_error", "mean"),
            n_months=("month", "count"),
        )
        .reset_index()
    )
    mape["mape_pct"] = mape["mape_pct"].round(3)

    overall_mape = merged["abs_pct_error"].mean()
    logger.info("Stage 8: overall MAPE=%.2f%% across %d route-months",
                overall_mape, len(merged))
    return mape


# ── PipelineOutput dataclass ──────────────────────────────────────────────────

@dataclass
class PipelineOutput:
    """All intermediate and final outputs from the 8-stage pipeline."""
    cell_estimates: pd.DataFrame       # Stage 1: robust cell medians
    reconciled: pd.DataFrame           # Stage 2: cross-source fused fares
    decomposed: pd.DataFrame           # Stage 3: base fare + tax breakdown
    elasticity: pd.DataFrame           # Stage 4: alpha, beta, R² per route/date
    imputed_panel: pd.DataFrame        # Stage 5: panel with imputed cells
    route_panel: pd.DataFrame          # Stage 6: route-level market-share weighted fare
    apix_series: pd.DataFrame          # Stage 7: daily Törnqvist APIx
    validation: Optional[pd.DataFrame] = None   # Stage 8: MAPE vs DGCA


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_apix_pipeline(
    raw_df: pd.DataFrame,
    source_variance: dict,
    dgca_route_share: dict,
    dgca_monthly_avg: Optional[pd.DataFrame] = None,
    ap_booking_curve: Optional[dict] = None,
) -> PipelineOutput:
    """
    Run the full 8-stage APIx pipeline.

    Args:
        raw_df: Raw fare observations with required columns:
            route, origin, destination, carrier_code, ap_window_bucket,
            collection_date (datetime), total_fare_inr, source

        source_variance: {source_name: variance_inr²}
            Historical variance of each source's fare estimates.
            Use equal variance (all 1.0) if no history available.

        dgca_route_share: {route: traffic_share}
            DGCA route-level passenger share, normalised to sum=1.
            e.g. {"DEL-BOM": 0.22, "DEL-BLR": 0.18, ...}

        dgca_monthly_avg: Optional DataFrame for Stage 8 validation.
            Columns: [route, month (YYYY-MM str), dgca_avg_fare_inr]

        ap_booking_curve: Optional dict for DGCA-weighted AP weights.
            If None, uses equal split across AP buckets.

    Returns:
        PipelineOutput with all 8 stage results.
    """
    logger.info("=== APIx Pipeline started (%d raw quotes) ===", len(raw_df))

    # Validate input
    raw_df = validate_input_df(raw_df)
    if raw_df.empty:
        raise ValueError("Input DataFrame is empty after validation. No quotes to process.")

    routes = raw_df["route"].unique().tolist()
    route_meta = raw_df[["route", "origin", "destination"]].drop_duplicates("route")

    # Build AP weights
    if ap_booking_curve:
        ap_weights = build_dgca_weighted_ap_weights(routes, dgca_route_share, ap_booking_curve)
    else:
        ap_weights = build_equal_ap_weights(routes, dgca_route_share)

    # Run stages
    cell_estimates = stage1_robust_cell_estimate(raw_df)
    reconciled = stage2_reconcile_sources(cell_estimates, source_variance)
    decomposed = apply_decomposition(reconciled, route_meta)
    elasticity = stage4_fit_elasticity(reconciled)
    imputed = stage5_impute_missing(reconciled, elasticity)
    route_panel = stage6_aggregate_route(imputed)
    apix_series = stage7_tornqvist_index(route_panel, ap_weights)

    validation = None
    if dgca_monthly_avg is not None and not dgca_monthly_avg.empty:
        validation = stage8_validate_against_dgca(route_panel, dgca_monthly_avg)

    logger.info("=== APIx Pipeline complete ===")

    return PipelineOutput(
        cell_estimates=cell_estimates,
        reconciled=reconciled,
        decomposed=decomposed,
        elasticity=elasticity,
        imputed_panel=imputed,
        route_panel=route_panel,
        apix_series=apix_series,
        validation=validation,
    )
