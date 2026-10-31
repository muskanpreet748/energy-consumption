# Wind Decision Desk

**A day-ahead wind procurement pilot for a UK energy utility.**
Built by **Muskanpreet Kaur** · Great Britain wind data · January 2026 · Elexon BMRS

React frontend · Python (FastAPI) backend · Docker · Vercel · 41 tests

---

## 1. The problem

A GB supplier buys electricity on the **day-ahead auction (N2EX)** every
morning. The quantity it must buy is:

```
position = demand − wind generation
```

Wind is only knowable through a forecast, and the auction **gate closes at
09:50** (results publish by 10:00). That single fact drives the whole design:

> The only forecasts that matter are the ones published **before** 09:50.

Elexon's `WINDFOR` dataset re-publishes a wind forecast up to **eight times a
day**, each publication carrying both a `publishTime` (when it was issued) and
a `startTime` (which hour it predicts). If you measure accuracy using the
newest forecast rather than the newest forecast *available at the deadline*,
you silently use information published after the event — **look-ahead bias**.
That understates error, which leads the client to hold too little reserve.

This application answers two questions honestly:

1. **What did we actually know at 09:50?** — the latest forecast available at
   the decision deadline for any chosen delivery day.
2. **How wrong was it?** — quantitative accuracy of *that* forecast against
   metered outturn, across the month.

---

## 2. Headline finding

Across **720 hourly comparisons over 30 delivery days** (2–31 January), each
measured against the forecast visible at 09:50 the day before:

| Metric | Value |
|---|---|
| Mean absolute error | **2,051.6 MW** |
| RMSE | 2,541.4 MW |
| Systematic bias | **+1,759.7 MW** (forecast ran high) |
| MAE after removing that bias | **1,420.7 MW** |
| Pearson correlation (shape) | **0.928** |
| P90 absolute error (reserve buffer) | 4,176.8 MW |

**The forecast is skilful in shape but wrong in level.** It tracks every swing
of the day (r = 0.93), yet sits ~15% above actual output on average — and that
offset **does not shrink as delivery approaches** (still +1,530 MW at 0–6h
lead), which rules out ordinary day-ahead uncertainty.

Two different problems need two different fixes:

* The **+1,760 MW offset** is structural. Candidate causes are a scope
  difference between the two datasets, or curtailment suppressing metered
  output below an unconstrained forecast. It cannot be decomposed using
  Elexon wind data alone (see [Caveats](#6-caveats--things-i-flag-rather-than-hide)).
* The **1,421 MW that remains** is the genuinely unpredictable component —
  that is the number a reserve buffer should be sized against, not 2,052 MW.

A practical secondary result: waiting from the 02:30 run to the 09:30 run
buys only **78 MW** of MAE (2,130 → 2,052). The early forecast is nearly as
good, which is itself decision-useful.

---

## 3. How to run it

### Option A — Docker (recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

* App: <http://localhost:3000>
* API: <http://localhost:8000/api/health>

`web` waits for the `api` healthcheck, and nginx proxies `/api` to the backend
so the browser only ever talks to one origin.

### Option B — manually

```bash
# 1. backend
python -m venv .venv
.venv/Scripts/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn main:app --reload --app-dir backend     # http://127.0.0.1:8000

# 2. frontend (second terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api to :8000
```

### Run the tests

```bash
pytest backend -q               # 41 tests, ~3s
```

---

## 4. Repository map

```
energy-consumption/
├─ api/
│  └─ index.py               # Vercel serverless shim; re-exports the ASGI app
├─ docker-compose.yml        # one-command stack: api + nginx web
├─ requirements.txt          # runtime pins for Vercel (see §8.1)
├─ vercel.json               # deployment config (FastAPI + static frontend)
├─ backend/
│  ├─ Dockerfile             # python:3.12-slim, non-root user
│  ├─ requirements.txt       # fastapi, uvicorn, pytest, httpx
│  ├─ main.py                # FastAPI app: /api/health|meta|days|decision|accuracy
│  ├─ conftest.py            # makes backend/ importable for pytest
│  ├─ core/
│  │  ├─ asof.py             # ★ point-in-time selection — the anti-cheat logic
│  │  ├─ align.py            # 30-minute outturn → hourly delivery periods
│  │  └─ metrics.py          # MAE / RMSE / bias / percentiles / correlation
│  ├─ scripts/
│  │  └─ build_snapshot.py   # downloads from Elexon, asserts row counts
│  ├─ tests/                 # 41 tests: asof, align, metrics, snapshot, API
│  └─ data/snapshot.json     # generated once, committed (2.36 MB)
└─ frontend/
   ├─ Dockerfile             # node:20 build → nginx:alpine serve
   ├─ nginx.conf             # serves SPA, proxies /api to the api container
   ├─ vite.config.js         # dev proxy for /api
   └─ src/
      ├─ App.jsx             # tabbed shell
      ├─ api.js              # fetch wrapper surfacing FastAPI errors
      └─ components/
         ├─ DecisionDesk.jsx       # tab 1: what we knew at 09:50
         ├─ AccuracyDashboard.jsx  # tab 2: month-wide accuracy
         ├─ AboutData.jsx          # tab 3: provenance + caveats
         └─ MetricCard.jsx         # shared metric card + formatting helpers
```

### API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | liveness probe, reports dataset sizes |
| `GET /api/meta` | sources, coverage, conventions, caveats |
| `GET /api/days` | delivery days usable by the Decision Desk |
| `GET /api/decision?delivery=2026-01-16` | the vintage visible at the 09:50 gate + hourly error |
| `GET /api/accuracy` | month-wide, per-lead-time and per-issue-time statistics |

---

## 5. Data

Sourced **only** from the Elexon Insights API (BMRS). Nothing else is used.

**Base URL:** `https://data.elexon.co.uk/bmrs/api/v1`

| Dataset | Request | Rows |
|---|---|---|
| Actuals | `GET /datasets/FUELHH/stream?settlementDateFrom=2026-01-01&settlementDateTo=2026-01-31&fuelType=WIND` | **1,488** (48 half-hours × 31 days) |
| Forecasts | `GET /datasets/WINDFOR/stream?publishDateTimeFrom=2026-01-01T00:00:00Z&publishDateTimeTo=2026-02-01T00:00:00Z` | **18,104** (248 vintages, 793 delivery hours) |

Both fetch in **one API call each** (~1s).

```bash
python backend/scripts/build_snapshot.py    # regenerate backend/data/snapshot.json
```

The script **asserts** the expected row counts (exactly 1,488 actuals, ≥15,000
forecasts, >700 delivery hours). If Elexon changes the format, the build fails
loudly instead of shipping wrong numbers.

### Why a JSON snapshot instead of a database

A committed `snapshot.json` means local runs, Docker and the deployed site all
compute **identical numbers** — no drift, no rate limits, no network
dependency in CI, and a reviewer can run the app offline in 30 seconds. A
production service would use Postgres with a nightly refresh job; the
`build_snapshot.py` script is exactly the ingest step that job would call, and
the `SNAPSHOT_PATH` environment variable points the API at wherever the data
lives.

---

## 6. Caveats — things I flag rather than hide

1. **`WINDFOR.startTime` is hourly, not 30-minute.** The brief describes it as
   30-minute. Verified empirically: 18,104 forecast rows across 793 distinct
   hours. The alignment layer therefore averages each clock hour's two
   half-hourly outturn readings into one hourly MW figure — day-ahead products
   trade hourly anyway, so this matches the thing being decided.
2. **`FUELHH` silently ignores `startDate`/`endDate`.** It requires
   `settlementDateFrom`/`settlementDateTo`. A wrong parameter name returns
   *today's* data with a 200 status — the row-count assertion is the guard.
3. **`WINDFOR` has no delivery-time filter,** only a publish-time window, so
   the whole month is pulled once and filtered in the application.
4. **Outturn publishes D+1.** A settlement period's actual figure appears the
   following day, so the last hours of a month depend on the next month's
   data. January-only scope means 1 January has forecasts but no usable
   decision vintage (its deadline is 31 December), giving **30 usable delivery
   days**.
5. **The +1,760 MW bias is unexplained within scope.** It does not decay with
   lead time, so it is not forecast uncertainty. Reconciling it needs data
   outside the agreed Elexon-wind-only scope. I report it plainly and separate
   it from the random component rather than averaging it away.
6. **January 2026 only,** so "latest forecast" here means latest *as it stood
   at each historical decision deadline*.
7. **Docker images are written but unverified by execution** on the machine
   this was built on, which had no Docker daemon. `docker-compose.yml` parses
   and both Dockerfiles follow standard patterns, but they have not been run.

---

## 7. Design decisions

* **Point-in-time selection is the core of the product.** `core/asof.py`
  filters `publishTime <= (delivery day − 1 day)T09:50:00Z`, then takes the
  newest. Tests assert a forecast published *after* the gate is never selected
  — including one published after the electricity was generated.
* **MW-denominated metrics, no MAPE.** Wind output falls to near zero on calm
  days, which makes percentage errors explode and dominate any average. Every
  metric here is in MW, the unit the client actually buys in.
* **Bias and randomness reported separately.** A constant offset and a random
  miss are different problems with different fixes, so `/api/accuracy`
  reports raw error, error after bias correction, and shape correlation.
* **`by_issue_time` answers a practical question:** does waiting until 09:30
  improve accuracy? (Barely, this month.)
* **Tests are the review artefact.** 41 tests, including 12 HTTP contract
  tests that caught a real aggregation bug during development.

---

## 8. Deployment

* **Live site:** <https://energy-consumption-mu.vercel.app>
* **Repository:** <https://github.com/muskanpreet748/energy-consumption>
* **Verification:** open the deployed URL in an incognito window — no login
  required, confirming public access. `/api/health` reports
  `{"status":"ok","actuals":1488,"forecasts":18104}`.

The deployed API returns **identical figures to a local run** (MAE 2,051.6 MW,
bias +1,759.7 MW, r 0.928), because both read the same committed snapshot.

### 8.1 How the deployment is wired

`vercel.json` uses Vercel's native conventions:

* `api/index.py` is auto-detected as a Python serverless function. It is a thin
  shim that puts `backend/` on `sys.path` and re-exports the ASGI `app`, so the
  domain code has no knowledge of Vercel and stays runnable via `uvicorn` and
  Docker unchanged.
* The frontend is built with `npm --prefix frontend ci && npm run build` and
  served from `frontend/dist`.
* `/api/*` is rewritten to the function, which owns its own routing.
* `functions.includeFiles` force-bundles `backend/data/**` — the snapshot is
  read at runtime, so Python's import tracer alone would not include it.
* The root `requirements.txt` exists **only** because Vercel installs
  dependencies from the repo root. Vercel's requirements parser is not pip: it
  rejects `-r` includes and `pkg[extra]` syntax, so the two runtime pins are
  listed explicitly. `backend/requirements.txt` remains the source of truth for
  local runs, Docker and tests.

> **Note:** the Docker images are provided and wired up in `docker-compose.yml`
> for local use and for any container host (Railway, Render, Fly.io, ECS).
> Vercel does not run Dockerfiles — it uses the build commands in
> `vercel.json` instead. Both paths are supported.

### 8.2 Redeploying

```bash
npm install -g vercel
vercel login
vercel deploy --prod
```

---

## 9. AI tools and open source

This project makes extensive use of AI tooling and open-source software, and
that is disclosed here in full rather than glossed over.

**AI tooling was used for** research into the Elexon Insights API — including
documenting query-parameter behaviour the public docs do not state — for
drafting implementation across the Python backend and React frontend, and for
exploratory analysis against the raw data. Open-source libraries carry the
rest: FastAPI, pytest, React, Recharts, Vite and Docker.

**The author's role** was direction and control: setting the requirements,
including treating the 09:50 gate closure as the organising constraint of the
product; approving the key architecture decisions — committing a JSON snapshot
rather than standing up a database, so local, Docker and deployed builds return
identical figures, and deploying on Vercel; and independently verifying every
headline figure against the running API before publication.

AI was used as an accelerator under the author's direction, not as a substitute
for understanding the result. Every reported number was checked against a live
response rather than accepted from the tool that produced it.

---

## 10. Video

The ≤10-minute walkthrough will be linked here after recording:

* **Part 1 — Client pitch (5 min):** the 09:50 problem, what the Decision
  Desk shows, and the headline bias finding.
* **Part 2 — Technical review (5 min):** point-in-time selection, the
  alignment layer, metrics, tests, and the container/deploy setup.

---

## License and copyright

Copyright © 2026 **Muskanpreet Kaur**. All rights reserved.

This project was built by Muskanpreet Kaur as part of an interview process.
No licence is granted to use, copy, modify or distribute this software without
the author's prior written permission.
