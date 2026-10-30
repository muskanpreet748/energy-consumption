"""Regression tests against the committed January 2026 snapshot.

These fail if the ingest script, the selection logic, or the upstream
data ever disagree about what the decision forecast should be.
"""

import json
from functools import lru_cache
from pathlib import Path

import pytest

from core.asof import deadline_for, pick_vintage

SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "snapshot.json"


@lru_cache(maxsize=1)
def forecasts() -> tuple:
    if not SNAPSHOT.exists():
        pytest.skip("snapshot not generated - run scripts/build_snapshot.py")
    return tuple(json.loads(SNAPSHOT.read_text(encoding="utf-8"))["forecasts"])


@pytest.mark.parametrize("delivery_day", ["2026-01-16", "2026-01-23", "2026-01-30"])
def test_decision_vintage_is_the_0930_run(delivery_day):
    """The last publication before the 09:50 gate is the decision forecast."""
    chosen, rows = pick_vintage(list(forecasts()), delivery_day)
    decision_day = deadline_for(delivery_day)[:10]
    assert chosen.startswith(decision_day)
    assert chosen.endswith("T09:30:00Z")
    assert chosen < deadline_for(delivery_day)
    assert rows


def test_snapshot_is_not_silently_empty():
    assert len(forecasts()) >= 15_000
