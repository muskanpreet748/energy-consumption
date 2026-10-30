"""Tests for the forecast error metrics."""

import math

import pytest

from core.metrics import (
    bias,
    correlation,
    lead_bucket,
    mae,
    percentile,
    rmse,
    summarise,
)


def test_mae_takes_absolute_values():
    assert mae([3, -4]) == 3.5


def test_rmse_penalises_large_misses():
    assert math.isclose(rmse([3, -4]), math.sqrt(12.5))


def test_bias_reports_direction():
    assert bias([10, -10]) == 0
    assert bias([10, 12]) == 11          # forecast too high
    assert bias([-10, -12]) == -11       # forecast too low


def test_percentile_interpolates():
    assert percentile(list(range(1, 11)), 90) == 9.1
    assert percentile([5], 90) == 5


def test_percentile_rejects_bad_arguments():
    with pytest.raises(ValueError):
        percentile([], 90)
    with pytest.raises(ValueError):
        percentile([1, 2], 150)


def test_summarise_returns_every_reported_field():
    stats = summarise([(110, 100), (90, 100)])   # errors +10 and -10
    assert stats["n"] == 2
    assert stats["mae_mw"] == 10.0
    assert stats["rmse_mw"] == 10.0
    assert stats["bias_mw"] == 0.0
    assert stats["max_abs_error_mw"] == 10.0


def test_summarise_separates_constant_bias_from_random_error():
    # Forecast is uniformly 100 MW high: raw error is 100, but once the
    # offset is removed there is no unpredicted variation left at all.
    stats = summarise([(100, 0), (200, 100), (300, 200)])
    assert stats["bias_mw"] == 100.0
    assert stats["mae_mw"] == 100.0
    assert stats["mae_after_bias_correction_mw"] == 0.0


def test_correlation_is_high_for_a_pure_constant_shift():
    # Perfectly correlated shapes, wrong level.
    pairs = [(110, 100), (210, 200), (310, 300)]
    assert correlation(pairs) == pytest.approx(1.0)


def test_correlation_is_none_when_a_series_is_constant():
    assert correlation([(110, 100), (90, 100)]) is None
    assert correlation([(100, 100)]) is None


def test_summarise_needs_at_least_one_pair():
    with pytest.raises(ValueError):
        summarise([])


def test_lead_buckets_are_inclusive_at_the_lower_bound():
    assert lead_bucket(0) == "0-6h"
    assert lead_bucket(5.99) == "0-6h"
    assert lead_bucket(6) == "6-12h"
    assert lead_bucket(12) == "12-24h"
    assert lead_bucket(24) == "24-48h"
    assert lead_bucket(48) == "48h+"
    assert lead_bucket(300) == "48h+"
