"""Download January 2026 wind data from the Elexon Insights API.

Produces ``backend/data/snapshot.json`` containing:

* ``actuals``   - FUELHH, fuelType=WIND, 30-minute metered outturn (MW)
* ``forecasts`` - WINDFOR, hourly forecast (MW) together with the time the
                  forecast was published

The snapshot is committed to the repository so the application can run
without any network dependency or API rate-limit risk.

Usage
-----
    python backend/scripts/build_snapshot.py
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "snapshot.json"

# January 2026 - the period the purchase decisions cover.
DATE_FROM = "2026-01-01"
DATE_TO = "2026-01-31"
PUBLISH_FROM = f"{DATE_FROM}T00:00:00Z"
PUBLISH_TO = "2026-02-01T00:00:00Z"

# Expected shapes. If either fails the upstream format has changed and we
# must stop rather than silently ship wrong numbers.
EXPECTED_ACTUALS = 48 * 31          # 48 half-hours x 31 days
MIN_FORECASTS = 15_000


def get(path: str, **params: str) -> list:
    """GET a JSON array from Elexon, retrying with exponential backoff."""
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    last_error: Exception | None = None

    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"Unexpected payload type from {url}")
            return payload
        except Exception as exc:            # noqa: BLE001 - retry any transport error
            last_error = exc
            delay = 2**attempt
            print(f"  retry {attempt + 1}/4 in {delay}s: {exc}")
            time.sleep(delay)

    raise RuntimeError(f"Giving up on {url}: {last_error}")


def main() -> None:
    print("Fetching FUELHH (actual wind outturn) ...")
    # NOTE: settlementDateFrom / settlementDateTo are the real parameter
    # names. The API silently ignores startDate / endDate, so a mistake
    # here would quietly return today's data instead of January 2026.
    actuals = get(
        "/datasets/FUELHH/stream",
        settlementDateFrom=DATE_FROM,
        settlementDateTo=DATE_TO,
        fuelType="WIND",
    )

    print("Fetching WINDFOR (wind generation forecast) ...")
    # WINDFOR offers no delivery-time filter at all - only a publish-time
    # window - so we pull the whole month and filter in the application.
    forecasts = get(
        "/datasets/WINDFOR/stream",
        publishDateTimeFrom=PUBLISH_FROM,
        publishDateTimeTo=PUBLISH_TO,
    )

    assert len(actuals) == EXPECTED_ACTUALS, (
        f"expected {EXPECTED_ACTUALS} actuals, received {len(actuals)}"
    )
    assert len(forecasts) >= MIN_FORECASTS, (
        f"expected at least {MIN_FORECASTS} forecasts, received {len(forecasts)}"
    )

    unique_hours = len({row["startTime"] for row in forecasts})
    vintages = len({row["publishTime"] for row in forecasts})
    assert unique_hours > 700, f"forecast horizon looks wrong: {unique_hours} hours"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"actuals": actuals, "forecasts": forecasts}),
        encoding="utf-8",
    )

    print(f"  actuals            : {len(actuals)}")
    print(f"  forecasts          : {len(forecasts)}")
    print(f"  distinct vintages  : {vintages}")
    print(f"  distinct hours     : {unique_hours}")
    print(f"  written to         : {OUT_PATH}")


if __name__ == "__main__":
    main()
