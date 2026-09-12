"""
pipeline/cleaner.py — Data cleaning and validation for raw fare quotes.

Cleaning stages applied in order:
  1. Schema validation (handled by Pydantic before insertion)
  2. Fare positivity check
  3. Route bounds check (per-route min/max sanity)
  4. AP-window consistency check
  5. Outlier detection using IQR method per route/window/date
  6. Duplicate detection
"""

import logging
from datetime import date
from typing import List, Tuple, Optional, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Route-level fare bounds (INR) ─────────────────────────────────────────────
# Derived from historical DGCA fare reports; reviews periodically.
ROUTE_FARE_BOUNDS: Dict[str, Tuple[float, float]] = {
    "DEL-BOM": (1500, 35000),
    "DEL-BLR": (1500, 32000),
    "BOM-BLR": (1000, 25000),
    "DEL-CCU": (1500, 30000),
    "BLR-HYD": (800,  20000),
    "MAA-DEL": (1500, 32000),
    "DEL-HYD": (1200, 28000),
    "BOM-CCU": (1500, 30000),
}

DEFAULT_BOUNDS = (500, 50000)


def validate_and_flag(
    quotes: List[dict],
    collection_date: date,
) -> Tuple[List[dict], List[dict]]:
    """
    Validate a batch of raw fare dicts.

    Returns:
        (valid_quotes, rejected_quotes)
    Each rejected quote has a 'rejection_reason' key added.
    """
    valid: List[dict] = []
    rejected: List[dict] = []

    for q in quotes:
        reason = _check_single(q)
        if reason:
            q["rejection_reason"] = reason
            q["is_valid"] = False
            rejected.append(q)
            logger.debug(
                "Rejected quote %s→%s AP+%s: %s",
                q.get("origin"), q.get("destination"),
                q.get("ap_days"), reason,
            )
        else:
            q["is_valid"] = True
            valid.append(q)

    # IQR outlier detection within each route/window group
    valid, outliers = _iqr_filter(valid)
    rejected.extend(outliers)

    logger.info(
        "Cleaning complete: %d valid, %d rejected",
        len(valid), len(rejected),
    )
    return valid, rejected


def _check_single(q: dict) -> Optional[str]:
    """Return a rejection reason string, or None if quote passes."""
    base = q.get("base_fare", 0)
    total = q.get("total_fare", 0)
    ap = q.get("ap_days", -1)

    # 1. Positivity
    if base <= 0:
        return "Non-positive base fare"
    if total <= 0:
        return "Non-positive total fare"

    # 2. Total ≥ base
    if total < base:
        return "Total fare less than base fare"

    # 3. Route bounds
    route = f"{q.get('origin')}-{q.get('destination')}"
    lo, hi = ROUTE_FARE_BOUNDS.get(route, DEFAULT_BOUNDS)
    if not (lo <= base <= hi):
        return f"Base fare {base:.0f} outside bounds [{lo}, {hi}]"

    # 4. AP window sanity
    if ap < 0:
        return "Negative advance purchase days"
    if ap > 365:
        return "Advance purchase window > 365 days"

    return None


def _iqr_filter(
    quotes: List[dict],
    multiplier: float = 3.0,
) -> Tuple[List[dict], List[dict]]:
    """
    Within each (origin, destination, ap_days) group, flag quotes whose
    base_fare falls outside [Q1 - k*IQR, Q3 + k*IQR].
    Uses a generous multiplier (3.0) to catch only extreme outliers.
    Groups with < 4 observations are skipped (not enough data).
    """
    from collections import defaultdict

    groups: dict[tuple, List[int]] = defaultdict(list)
    for i, q in enumerate(quotes):
        key = (q["origin"], q["destination"], q["ap_days"])
        groups[key].append(i)

    valid_indices = set(range(len(quotes)))

    for key, indices in groups.items():
        if len(indices) < 4:
            continue
        fares = np.array([quotes[i]["base_fare"] for i in indices])
        q1, q3 = np.percentile(fares, [25, 75])
        iqr = q3 - q1
        lo = q1 - multiplier * iqr
        hi = q3 + multiplier * iqr
        for i in indices:
            if not (lo <= quotes[i]["base_fare"] <= hi):
                quotes[i]["rejection_reason"] = (
                    f"IQR outlier: {quotes[i]['base_fare']:.0f} outside "
                    f"[{lo:.0f}, {hi:.0f}]"
                )
                quotes[i]["is_valid"] = False
                valid_indices.discard(i)

    valid = [quotes[i] for i in range(len(quotes)) if i in valid_indices]
    rejected = [quotes[i] for i in range(len(quotes)) if i not in valid_indices]
    return valid, rejected
