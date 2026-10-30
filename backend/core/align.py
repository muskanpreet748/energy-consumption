"""Reconcile the two datasets' different time resolutions.

FUELHH reports an average MW figure for every 30 minutes; WINDFOR
reports an average MW figure for every clock hour; and GB day-ahead
auctions are traded in hourly products.

So the joins in this module collapse each clock hour's two half-hourly
outturn values into a single hourly MW figure. That gives one forecast
and one actual per delivery hour - the only shape in which a forecast
error is meaningful.
"""

from __future__ import annotations

from collections import defaultdict

from core.asof import parse_timestamp


def actuals_by_hour(actuals: list[dict]) -> dict[str, float]:
    """Aggregate 30-minute outturn rows into hourly MW averages.

    Keys are the hour-start timestamps used by WINDFOR, e.g.
    ``2026-01-16T12:00:00Z``. Both half-hours of an hour share that key
    because only the ``HH`` part is kept.
    """
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in actuals:
        hour_key = row["startTime"][:13] + ":00:00Z"
        buckets[hour_key].append(float(row["generation"]))

    if not buckets:
        raise ValueError("No actuals supplied")

    # An isolated half-hour is still a valid hourly average; a gap would
    # simply have no entry here and be skipped by the join.
    return {hour: sum(values) / len(values) for hour, values in buckets.items()}


def build_series(rows: list[dict], hourly_actuals: dict[str, float]) -> list[dict]:
    """Join one forecast vintage to the outturn it was predicting.

    Rows without a matching actual (the outturn for a settlement period
    publishes on the following day) are dropped rather than guessed.
    """
    series: list[dict] = []

    for row in rows:
        actual = hourly_actuals.get(row["startTime"])
        if actual is None:
            continue

        published = parse_timestamp(row["publishTime"])
        delivered = parse_timestamp(row["startTime"])
        lead_hours = (delivered - published).total_seconds() / 3600
        if lead_hours < 0:
            continue  # published after delivery: not a forecast

        forecast = float(row["generation"])
        series.append(
            {
                "hour": row["startTime"],
                "forecast_mw": forecast,
                "actual_mw": round(actual, 1),
                "error_mw": round(forecast - actual, 1),
                "lead_hours": round(lead_hours, 1),
            }
        )

    return sorted(series, key=lambda point: point["hour"])
