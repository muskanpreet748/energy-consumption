"""FastAPI service exposing the day-ahead wind analysis.

The service is read-only: it loads the committed Elexon snapshot once at
startup and answers questions about it. Two questions matter:

``/api/decision``  what the trader could see at 09:50, and how wrong it was
``/api/accuracy``  how the forecast performed across the whole month

Run locally with::

    uvicorn main:app --reload --app-dir backend
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.align import actuals_by_hour, build_series
from core.asof import GATE_TIME, available_vintages, deadline_for, pick_vintage
from core.metrics import bias, lead_bucket, mae, percentile, rmse, summarise

DEFAULT_SNAPSHOT = Path(__file__).resolve().parent / "data" / "snapshot.json"


# --------------------------------------------------------------------------- #
# Response models
# --------------------------------------------------------------------------- #
class ErrorStats(BaseModel):
    """Forecast error summary, all values in MW."""

    n: int
    mae_mw: float = Field(description="Mean absolute error")
    rmse_mw: float = Field(description="Root mean squared error")
    bias_mw: float = Field(description="Mean signed error; positive = forecast too high")
    mae_after_bias_correction_mw: float = Field(
        description="MAE once the constant offset is removed - the random component"
    )
    correlation: float | None = Field(
        default=None,
        description="Pearson r between forecast and actual; None if a series is constant",
    )
    p50_abs_error_mw: float
    p90_abs_error_mw: float
    max_abs_error_mw: float


class HourPoint(BaseModel):
    hour: str
    forecast_mw: float
    actual_mw: float
    error_mw: float
    lead_hours: float


class DecisionResponse(BaseModel):
    delivery_day: str
    decision_deadline: str
    gate_time: str
    chosen_publish_time: str = Field(description="The vintage the trader actually saw")
    available_vintages: list[str]
    hours: list[HourPoint]
    metrics: ErrorStats


class DailyAccuracy(BaseModel):
    delivery_day: str
    chosen_publish_time: str
    stats: ErrorStats


class BucketStats(BaseModel):
    bucket: str
    n: int
    mae_mw: float
    rmse_mw: float
    bias_mw: float


class AccuracyResponse(BaseModel):
    overall: ErrorStats
    daily: list[DailyAccuracy]
    by_lead_time: list[BucketStats]
    by_issue_time: list[BucketStats]


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
def load_snapshot() -> tuple[dict, dict, dict]:
    """Read the snapshot and pre-compute the indexes the API needs."""
    path = Path(os.getenv("SNAPSHOT_PATH", DEFAULT_SNAPSHOT))
    if not path.exists():
        raise RuntimeError(
            f"Snapshot not found at {path}. "
            "Run: python backend/scripts/build_snapshot.py"
        )

    snapshot = json.loads(path.read_text(encoding="utf-8"))
    hourly_actuals = actuals_by_hour(snapshot["actuals"])

    by_publish: dict[str, list[dict]] = defaultdict(list)
    for row in snapshot["forecasts"]:
        by_publish[row["publishTime"]].append(row)

    return snapshot, hourly_actuals, dict(by_publish)


@asynccontextmanager
async def lifespan(app: FastAPI):
    snapshot, hourly_actuals, by_publish = load_snapshot()
    app.state.snapshot = snapshot
    app.state.hourly_actuals = hourly_actuals
    app.state.by_publish = by_publish
    yield


app = FastAPI(
    title="UK Day-Ahead Wind Decision Support",
    version="1.0.0",
    description=(
        "Point-in-time forecast selection and accuracy analysis for a UK "
        "energy utility procuring on the day-ahead market. Data: Elexon "
        "BMRS FUELHH (actuals) and WINDFOR (forecasts), January 2026."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOW_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _delivery_days() -> list[str]:
    """Delivery days that have both an outturn and a usable forecast."""
    days: list[str] = []
    for row in app.state.snapshot["actuals"]:
        day = row["settlementDate"]
        if day not in days:
            days.append(day)
    return sorted(days)


def _series_for(delivery_day: str, publish_time: str) -> list[dict]:
    """Forecast points for one vintage, restricted to one delivery day."""
    rows = [
        row
        for row in app.state.by_publish.get(publish_time, [])
        if row["startTime"].startswith(delivery_day)
    ]
    return build_series(rows, app.state.hourly_actuals)


def _bucket_stats(grouped: dict[str, list[float]]) -> list[BucketStats]:
    return [
        BucketStats(
            bucket=name,
            n=len(errors),
            mae_mw=round(mae(errors), 1),
            rmse_mw=round(rmse(errors), 1),
            bias_mw=round(bias(errors), 1),
        )
        for name, errors in sorted(grouped.items())
        if errors
    ]


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    """Liveness probe used by Docker and the deployment platform."""
    return {
        "status": "ok",
        "actuals": len(app.state.snapshot["actuals"]),
        "forecasts": len(app.state.snapshot["forecasts"]),
    }


@app.get("/api/meta")
def meta() -> dict:
    """Dataset coverage and the conventions this API applies."""
    forecasts = app.state.snapshot["forecasts"]
    publish_times = sorted({row["publishTime"] for row in forecasts})
    start_times = sorted({row["startTime"] for row in forecasts})

    return {
        "source": "Elexon Insights API (BMRS)",
        "endpoints": {
            "actuals": "GET /datasets/FUELHH/stream?settlementDateFrom&settlementDateTo&fuelType=WIND",
            "forecasts": "GET /datasets/WINDFOR/stream?publishDateTimeFrom&publishDateTimeTo",
            "base_url": "https://data.elexon.co.uk/bmrs/api/v1",
        },
        "delivery_period": {
            "from": min(app.state.hourly_actuals)[:10],
            "to": max(app.state.hourly_actuals)[:10],
        },
        "forecast_coverage": {"from": start_times[0], "to": start_times[-1]},
        "publish_window": {"from": publish_times[0], "to": publish_times[-1]},
        "vintage_count": len(publish_times),
        "gate_time_utc": GATE_TIME,
        "conventions": {
            "actual_resolution": "30 minutes (averaged to hourly for joins)",
            "forecast_resolution": "hourly",
            "units": "MW",
            "timezone": "UTC (January = UK local time, no BST shift)",
            "error_sign": "forecast minus actual; positive = forecast too high",
        },
        "known_caveats": [
            "WINDFOR startTime is hourly even though the brief describes 30 minutes.",
            "WINDFOR offers no delivery-time filter, only a publish-time window.",
            "The API silently ignores startDate/endDate on FUELHH.",
            "Actual outturn for a settlement period publishes the following day.",
        ],
    }


@app.get("/api/days")
def days() -> dict:
    """Delivery days available for the Decision Desk."""
    available = []
    for day in _delivery_days():
        try:
            chosen, _ = pick_vintage(app.state.snapshot["forecasts"], day)
        except ValueError:
            continue
        available.append({"delivery_day": day, "chosen_publish_time": chosen})
    return {"days": available}


@app.get("/api/decision", response_model=DecisionResponse)
def decision(
    delivery: str = Query(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Delivery day to inspect, e.g. 2026-01-16",
    ),
) -> DecisionResponse:
    """Everything knowable at the 09:50 gate, plus how wrong it proved."""
    try:
        chosen, _ = pick_vintage(app.state.snapshot["forecasts"], delivery)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    series = _series_for(delivery, chosen)
    if not series:
        raise HTTPException(
            status_code=404,
            detail=f"Vintage {chosen} has no matching outturn for {delivery}",
        )

    return DecisionResponse(
        delivery_day=delivery,
        decision_deadline=deadline_for(delivery),
        gate_time=GATE_TIME,
        chosen_publish_time=chosen,
        available_vintages=available_vintages(app.state.snapshot["forecasts"], delivery),
        hours=series,
        metrics=summarise([(point["forecast_mw"], point["actual_mw"]) for point in series]),
    )


@app.get("/api/accuracy", response_model=AccuracyResponse)
def accuracy() -> AccuracyResponse:
    """Month-wide accuracy from the decision vintage only.

    ``by_issue_time`` re-runs the same calculation for every pre-gate
    publication of that morning, which answers the trader's practical
    question: does waiting until 09:30 actually buy better accuracy?
    """
    daily: list[DailyAccuracy] = []
    all_pairs: list[tuple[float, float]] = []
    by_lead: dict[str, list[float]] = defaultdict(list)
    by_issue: dict[str, list[float]] = defaultdict(list)

    for day in _delivery_days():
        try:
            chosen, _ = pick_vintage(app.state.snapshot["forecasts"], day)
        except ValueError:
            continue                      # no forecast existed yet (1 Jan)

        series = _series_for(day, chosen)
        if not series:
            continue

        pairs = [(point["forecast_mw"], point["actual_mw"]) for point in series]
        daily.append(
            DailyAccuracy(
                delivery_day=day,
                chosen_publish_time=chosen,
                stats=summarise(pairs),
            )
        )
        all_pairs.extend(pairs)

        for point in series:
            by_lead[lead_bucket(point["lead_hours"])].append(point["error_mw"])

        for publish_time in available_vintages(app.state.snapshot["forecasts"], day):
            issue_series = _series_for(day, publish_time)
            if not issue_series:
                continue
            clock = publish_time[11:16]
            by_issue[clock].extend(point["error_mw"] for point in issue_series)

    if not daily:
        raise HTTPException(status_code=404, detail="No delivery day has usable data")

    ordered_issue = sorted(by_issue)
    issue_stats = [
        BucketStats(
            bucket=clock,
            n=len(by_issue[clock]),
            mae_mw=round(mae(by_issue[clock]), 1),
            rmse_mw=round(rmse(by_issue[clock]), 1),
            bias_mw=round(bias(by_issue[clock]), 1),
        )
        for clock in ordered_issue
    ]

    return AccuracyResponse(
        overall=summarise(all_pairs),
        daily=daily,
        by_lead_time=_bucket_stats(by_lead),
        by_issue_time=issue_stats,
    )
