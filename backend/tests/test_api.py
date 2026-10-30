"""API contract tests.

These exercise the running application in-process via TestClient, so the
response schema, status codes and the look-ahead bias rule are all
checked without needing a live server.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    """Boot the app (including the snapshot load) once per module."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_dataset_sizes(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["actuals"] == 1488
    assert body["forecasts"] == 18104


def test_meta_documents_sources_and_caveats(client):
    body = client.get("/api/meta").json()
    assert body["source"].startswith("Elexon")
    assert body["gate_time_utc"] == "09:50"
    assert body["vintage_count"] == 248
    assert body["delivery_period"]["from"] == "2026-01-01"
    assert any("hourly" in caveat for caveat in body["known_caveats"])


def test_days_lists_every_usable_delivery_day(client):
    body = client.get("/api/days").json()
    assert len(body["days"]) == 30            # 2 Jan - 31 Jan
    assert body["days"][0]["delivery_day"] == "2026-01-02"
    assert all(
        day["chosen_publish_time"].endswith("T09:30:00Z") for day in body["days"]
    )


def test_decision_uses_the_last_forecast_before_the_gate(client):
    body = client.get("/api/decision", params={"delivery": "2026-01-16"}).json()

    assert body["chosen_publish_time"] == "2026-01-15T09:30:00Z"
    assert body["decision_deadline"] == "2026-01-15T09:50:00Z"
    assert body["chosen_publish_time"] < body["decision_deadline"]
    assert body["available_vintages"] == [
        "2026-01-15T02:30:00Z",
        "2026-01-15T04:30:00Z",
        "2026-01-15T07:30:00Z",
        "2026-01-15T09:30:00Z",
    ]
    assert len(body["hours"]) == 24


def test_decision_exposes_both_bias_and_random_error(client):
    metrics = client.get("/api/decision", params={"delivery": "2026-01-16"}).json()[
        "metrics"
    ]
    for field in (
        "mae_mw",
        "rmse_mw",
        "bias_mw",
        "mae_after_bias_correction_mw",
        "correlation",
        "p90_abs_error_mw",
    ):
        assert field in metrics, f"{field} missing from decision metrics"
    # Removing a constant offset can only reduce absolute error.
    assert metrics["mae_after_bias_correction_mw"] <= metrics["mae_mw"]


def test_decision_rejects_a_malformed_date(client):
    assert client.get("/api/decision", params={"delivery": "not-a-date"}).status_code == 422


def test_decision_returns_404_when_no_forecast_existed(client):
    response = client.get("/api/decision", params={"delivery": "2026-01-01"})
    assert response.status_code == 404
    assert "No forecast was published" in response.json()["detail"]


def test_decision_returns_404_outside_the_dataset(client):
    response = client.get("/api/decision", params={"delivery": "2026-07-04"})
    assert response.status_code == 404


def test_accuracy_covers_thirty_delivery_days(client):
    body = client.get("/api/accuracy").json()
    assert len(body["daily"]) == 30
    assert body["overall"]["n"] == 720        # 30 days x 24 hours


def test_accuracy_separates_systematic_bias_from_random_error(client):
    overall = client.get("/api/accuracy").json()["overall"]
    # January 2026: the forecast runs high and tracks shape well.
    assert overall["bias_mw"] > 0
    assert overall["mae_after_bias_correction_mw"] < overall["mae_mw"]
    assert overall["correlation"] > 0.8


def test_accuracy_compares_every_pre_gate_publication(client):
    body = client.get("/api/accuracy").json()
    assert [bucket["bucket"] for bucket in body["by_issue_time"]] == [
        "02:30",
        "04:30",
        "07:30",
        "09:30",
    ]
    assert all(bucket["n"] == 720 for bucket in body["by_issue_time"])


def test_accuracy_only_reports_day_ahead_lead_times(client):
    buckets = {b["bucket"] for b in client.get("/api/accuracy").json()["by_lead_time"]}
    assert buckets <= {"12-24h", "24-48h", "48h+"}
