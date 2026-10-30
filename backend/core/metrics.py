"""Forecast error metrics, expressed in megawatts.

All metrics take ``forecast - actual`` as their input error, so a
positive number always means the forecast was too high (wind delivered
less than predicted) and the client would have under-bought thermal
generation.

MAPE is deliberately absent: wind output drops to near zero on calm
days, which makes percentage errors explode and dominate any average.
MW-denominated errors stay meaningful across the whole month.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence

#: Lead-time buckets, in hours ahead of the publication being evaluated.
LEAD_BUCKETS: tuple[tuple[float, str], ...] = (
    (6, "0-6h"),
    (12, "6-12h"),
    (24, "12-24h"),
    (48, "24-48h"),
    (float("inf"), "48h+"),
)


def mae(errors: Iterable[float]) -> float:
    """Mean absolute error - the typical size of a miss, in MW."""
    values = list(errors)
    if not values:
        raise ValueError("mae() needs at least one error")
    return statistics.fmean(abs(value) for value in values)


def rmse(errors: Iterable[float]) -> float:
    """Root mean squared error - penalises the occasional large miss."""
    values = list(errors)
    if not values:
        raise ValueError("rmse() needs at least one error")
    return statistics.fmean(value * value for value in values) ** 0.5


def bias(errors: Iterable[float]) -> float:
    """Mean signed error - positive means the forecast was too high."""
    values = list(errors)
    if not values:
        raise ValueError("bias() needs at least one error")
    return statistics.fmean(values)


def percentile(values: Sequence[float], p: float) -> float:
    """Linear-interpolated percentile, matching numpy's default."""
    if not values:
        raise ValueError("percentile() needs at least one value")
    if not 0 <= p <= 100:
        raise ValueError("percentile must be between 0 and 100")

    ordered = sorted(values)
    position = (len(ordered) - 1) * (p / 100)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarise(pairs: Iterable[tuple[float, float]]) -> dict:
    """Summary statistics for a set of (forecast, actual) pairs."""
    pairs = list(pairs)
    if not pairs:
        raise ValueError("summarise() needs at least one pair")

    errors = [forecast - actual for forecast, actual in pairs]
    absolute = [abs(error) for error in errors]

    return {
        "n": len(errors),
        "mae_mw": round(mae(errors), 1),
        "rmse_mw": round(rmse(errors), 1),
        "bias_mw": round(bias(errors), 1),
        "p50_abs_error_mw": round(percentile(absolute, 50), 1),
        "p90_abs_error_mw": round(percentile(absolute, 90), 1),
        "max_abs_error_mw": round(max(absolute), 1),
    }


def lead_bucket(lead_hours: float) -> str:
    """Classify a lead time into a named bucket such as ``12-24h``."""
    for limit, name in LEAD_BUCKETS:
        if lead_hours < limit:
            return name
    return LEAD_BUCKETS[-1][1]
