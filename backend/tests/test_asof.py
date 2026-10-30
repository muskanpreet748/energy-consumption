"""Tests for point-in-time forecast selection.

The central risk in this product is look-ahead bias: measuring accuracy
with a forecast that was not actually available at decision time. These
tests pin that behaviour down.
"""

import pytest

from core.asof import (
    GATE_TIME,
    available_vintages,
    deadline_for,
    pick_vintage,
)

# One delivery hour, forecast at four different moments.
FORECASTS = [
    {"publishTime": "2026-01-15T02:30:00Z",
     "startTime": "2026-01-16T12:00:00Z", "generation": 9020},
    {"publishTime": "2026-01-15T09:30:00Z",
     "startTime": "2026-01-16T12:00:00Z", "generation": 7802},
    # Published after gate closure: ineligible.
    {"publishTime": "2026-01-15T12:25:00Z",
     "startTime": "2026-01-16T12:00:00Z", "generation": 7673},
    # Published after the electricity was generated: hindsight, not a forecast.
    {"publishTime": "2026-01-16T22:30:00Z",
     "startTime": "2026-01-16T12:00:00Z", "generation": 8433},
]


def test_gate_is_0950():
    assert GATE_TIME == "09:50"


def test_deadline_is_previous_day_at_0950():
    assert deadline_for("2026-01-16") == "2026-01-15T09:50:00Z"


def test_deadline_rejects_malformed_date():
    with pytest.raises(ValueError):
        deadline_for("16 January 2026")


def test_picks_last_forecast_published_before_the_gate():
    chosen, rows = pick_vintage(FORECASTS, "2026-01-16")
    assert chosen == "2026-01-15T09:30:00Z"
    assert rows[0]["generation"] == 7802


def test_never_selects_a_forecast_from_the_future():
    chosen, _ = pick_vintage(FORECASTS, "2026-01-16")
    assert chosen < deadline_for("2026-01-16")


def test_post_gate_vintages_are_not_offered():
    assert available_vintages(FORECASTS, "2026-01-16") == [
        "2026-01-15T02:30:00Z",
        "2026-01-15T09:30:00Z",
    ]


def test_raises_when_no_forecast_existed():
    with pytest.raises(ValueError, match="No forecast was published"):
        pick_vintage(FORECASTS, "2026-01-01")


def test_returns_rows_sorted_by_delivery_time():
    _, rows = pick_vintage(FORECASTS, "2026-01-16")
    assert [row["startTime"] for row in rows] == ["2026-01-16T12:00:00Z"]
