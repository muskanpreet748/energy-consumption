"""Tests for the 30-minute to hourly reconciliation."""

import pytest

from core.align import actuals_by_hour, build_series


def test_half_hours_are_averaged_into_one_hour():
    actuals = [
        {"startTime": "2026-01-16T12:00:00Z", "generation": 100},
        {"startTime": "2026-01-16T12:30:00Z", "generation": 200},
        {"startTime": "2026-01-16T13:00:00Z", "generation": 300},
        {"startTime": "2026-01-16T13:30:00Z", "generation": 400},
    ]
    assert actuals_by_hour(actuals) == {
        "2026-01-16T12:00:00Z": 150.0,
        "2026-01-16T13:00:00Z": 350.0,
    }


def test_lone_half_hour_is_still_usable():
    actuals = [{"startTime": "2026-01-16T12:30:00Z", "generation": 500}]
    assert actuals_by_hour(actuals) == {"2026-01-16T12:00:00Z": 500.0}


def test_empty_actuals_are_rejected():
    with pytest.raises(ValueError):
        actuals_by_hour([])


def test_series_joins_forecast_to_actual_with_error_and_lead_time():
    rows = [{
        "publishTime": "2026-01-15T09:30:00Z",
        "startTime": "2026-01-16T12:00:00Z",
        "generation": 180,
    }]
    series = build_series(rows, {"2026-01-16T12:00:00Z": 150.0})

    assert series == [{
        "hour": "2026-01-16T12:00:00Z",
        "forecast_mw": 180.0,
        "actual_mw": 150.0,
        "error_mw": 30.0,
        "lead_hours": 26.5,
    }]


def test_hours_without_outturn_are_skipped_not_invented():
    rows = [{
        "publishTime": "2026-01-15T09:30:00Z",
        "startTime": "2026-01-16T12:00:00Z",
        "generation": 180,
    }]
    assert build_series(rows, {}) == []


def test_forecasts_published_after_delivery_are_excluded():
    rows = [{
        "publishTime": "2026-01-16T22:30:00Z",
        "startTime": "2026-01-16T12:00:00Z",
        "generation": 8433,
    }]
    assert build_series(rows, {"2026-01-16T12:00:00Z": 8767.0}) == []
