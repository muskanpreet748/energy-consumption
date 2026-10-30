"""Point-in-time ("as-of") selection of the forecast a trader could see.

Why this module exists
----------------------
WINDFOR re-publishes a wind forecast up to eight times a day. Only the
publications that happened *before* the day-ahead auction gate closure
were ever available to the person making the purchase decision.

Comparing the *newest* forecast against actuals would silently use
information published after the event - a look-ahead bias that
understates forecast error and would lead the client to hold far too
little reserve capacity.

Every function here therefore treats ``publishTime`` as the clock that
decides eligibility, never ``startTime``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

#: N2EX day-ahead auction gate closure. Decisions for delivery day D are
#: locked in at 09:50 on day D - 1 (results publish by 10:00).
GATE_TIME = "09:50"

DATE_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_timestamp(value: str) -> datetime:
    """Parse an Elexon UTC timestamp such as ``2026-01-15T09:30:00Z``."""
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise ValueError(f"Unrecognised Elexon timestamp: {value!r}") from exc


def deadline_for(delivery_day: str) -> str:
    """Return the decision deadline for a delivery day.

    Delivery on 2026-01-16 is bought at the auction that closes on
    2026-01-15, so the deadline is ``2026-01-15T09:50:00Z``.
    """
    try:
        day = datetime.strptime(delivery_day, DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"delivery_day must look like '2026-01-16', got {delivery_day!r}"
        ) from exc
    decision_day = day - timedelta(days=1)
    return f"{decision_day:{DATE_FORMAT}}T{GATE_TIME}:00Z"


def eligible(forecasts: list[dict], delivery_day: str) -> list[dict]:
    """Forecast rows published strictly before the decision deadline."""
    deadline = deadline_for(delivery_day)
    return [row for row in forecasts if row["publishTime"] <= deadline]


def available_vintages(forecasts: list[dict], delivery_day: str) -> list[str]:
    """Publish timestamps the trader could choose from, oldest first.

    Only vintages published on the decision day itself are returned -
    these are the candidates that were genuinely in play that morning.
    """
    deadline = deadline_for(delivery_day)
    decision_day = deadline[:10]
    return sorted(
        {
            row["publishTime"]
            for row in forecasts
            if decision_day <= row["publishTime"] <= deadline
        }
    )


def pick_vintage(forecasts: list[dict], delivery_day: str) -> tuple[str, list[dict]]:
    """Select the newest forecast published before the deadline.

    Returns ``(chosen_publish_time, rows)`` where ``rows`` are the
    forecast points issued in that single publication run.

    Raises
    ------
    ValueError
        If no forecast existed before the deadline, or if the selected
        vintage covers none of the delivery day.
    """
    allowed = eligible(forecasts, delivery_day)
    if not allowed:
        raise ValueError(
            f"No forecast was published before the deadline "
            f"{deadline_for(delivery_day)}"
        )

    chosen = max(row["publishTime"] for row in allowed)
    rows = [row for row in allowed if row["publishTime"] == chosen]

    covers_delivery = any(
        row["startTime"].startswith(delivery_day) for row in rows
    )
    if not covers_delivery:
        raise ValueError(
            f"Vintage {chosen} does not cover delivery day {delivery_day}"
        )

    return chosen, sorted(rows, key=lambda row: row["startTime"])
