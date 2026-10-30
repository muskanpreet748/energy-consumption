"""Forecast error metrics, expressed in megawatts.

All metrics take ``forecast - actual`` as their input error, so a
positive number always means the forecast was too high (wind delivered
less than predicted) and the client would have under-bought thermal
generation.

MAPE is deliberately absent: wind output drops to near zero on calm
days, which makes percentage errors explode and dominate any average.
MW-denominated errors stay meaningful across the whole month.

January 2026 shows a large, persistent positive bias that does not shrink
as delivery approaches. Because a systematic offset and a random miss are
different problems with different fixes, :func:`summarise` reports both
the raw error and the error left after the mean bias is removed, plus the
correlation that shows how well the forecast tracks the *shape* of the
day regardless of level.
"""

from __future__ import annotations

import math
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


def correlation(pairs: Iterable[tuple[float, float]]) -> float | None:
    """Pearson correlation between forecast and actual levels.

    Shows how well the forecast tracks the shape of the day irrespective
    of any constant offset. Returns ``None`` when either series is
    constant, in which case correlation is undefined.
    """
    pairs = list(pairs)
    if len(pairs) < 2:
        return None

    forecasts = [pair[0] for pair in pairs]
    actuals = [pair[1] for pair in pairs]
    mean_f, mean_a = statistics.fmean(forecasts), statistics.fmean(actuals)

    numerator = sum((f - mean_f) * (a - mean_a) for f, a in pairs)
    spread_f = math.sqrt(sum((f - mean_f) ** 2 for f in forecasts))
    spread_a = math.sqrt(sum((a - mean_a) ** 2 for a in actuals))
    denominator = spread_f * spread_a

    if denominator == 0:
        return None
    return numerator / denominator


def summarise(pairs: Iterable[tuple[float, float]]) -> dict:
    """Summary statistics for a set of (forecast, actual) pairs."""
    pairs = list(pairs)
    if not pairs:
        raise ValueError("summarise() needs at least one pair")

    errors = [forecast - actual for forecast, actual in pairs]
    absolute = [abs(error) for error in errors]
    mean_bias = bias(errors)

    return {
        "n": len(errors),
        "mae_mw": round(mae(errors), 1),
        "rmse_mw": round(rmse(errors), 1),
        "bias_mw": round(mean_bias, 1),
        # Error that remains once the constant offset is removed: the
        # genuinely unpredictable, hour-to-hour component.
        "mae_after_bias_correction_mw": round(
            mae([error - mean_bias for error in errors]), 1
        ),
        "correlation": (
            round(correlation(pairs), 3) if correlation(pairs) is not None else None
        ),
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
