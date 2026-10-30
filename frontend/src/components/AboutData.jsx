import { useEffect, useState } from 'react'
import { getJSON } from '../api.js'

export default function AboutData() {
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getJSON('/api/meta')
      .then((body) => !cancelled && setMeta(body))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  if (error) return <div className="status error">{error}</div>
  if (!meta)
    return <div className="status loading">Loading dataset description…</div>

  return (
    <>
      <section className="panel">
        <h2>Where the numbers come from</h2>
        <p className="hint">
          National-level Great Britain wind data, from Elexon alone. Nothing else
          is used.
        </p>
        <dl className="meta">
          <dt>Source</dt>
          <dd>{meta.source}</dd>
          <dt>Base URL</dt>
          <dd>{meta.endpoints.base_url}</dd>
          <dt>Actuals endpoint</dt>
          <dd>{meta.endpoints.actuals}</dd>
          <dt>Forecast endpoint</dt>
          <dd>{meta.endpoints.forecasts}</dd>
          <dt>Delivery period covered</dt>
          <dd>
            {meta.delivery_period.from} → {meta.delivery_period.to}
          </dd>
          <dt>Forecast horizon held</dt>
          <dd>
            {meta.forecast_coverage.from} → {meta.forecast_coverage.to}
          </dd>
          <dt>Publish window held</dt>
          <dd>
            {meta.publish_window.from} → {meta.publish_window.to}
          </dd>
          <dt>Distinct forecast vintages</dt>
            <dd>{meta.vintage_count}</dd>
          <dt>Day-ahead gate closure</dt>
          <dd>{meta.gate_time_utc} UTC</dd>
        </dl>
      </section>

      <section className="panel">
        <h2>Conventions used by this application</h2>
        <dl className="meta">
          <dt>Actual resolution</dt>
          <dd>{meta.conventions.actual_resolution}</dd>
          <dt>Forecast resolution</dt>
          <dd>{meta.conventions.forecast_resolution}</dd>
          <dt>Units</dt>
          <dd>{meta.conventions.units}</dd>
          <dt>Timezone</dt>
          <dd>{meta.conventions.timezone}</dd>
          <dt>Error sign</dt>
          <dd>{meta.conventions.error_sign}</dd>
        </dl>

        <div className="callout">
          <strong>Why hourly?</strong> The outturn arrives every 30 minutes while
          the forecast arrives every hour, and day-ahead products trade hourly.
          Each clock hour's two half-hourly MW readings are averaged into one
          hourly figure before anything is compared.
        </div>
      </section>

      <section className="panel">
        <h2>Known caveats</h2>
        <p className="hint">
          Raised deliberately — these affect how the numbers should be read.
        </p>
        <ul className="caveats">
          {meta.known_caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
          <li>
            WINDFOR publishes up to eight vintages a day and offers no
            delivery-time filter, only a publish-time window, so the full month
            is pulled once and filtered in the application.
          </li>
          <li>
            The systematic positive bias cannot be decomposed using Elexon wind
            data alone. Candidate explanations are a scope difference between the
            two datasets, or curtailment suppressing metered outturn below an
            unconstrained forecast. Reconciling this needs data outside the
            agreed scope.
          </li>
          <li>
            Snapshot is fixed to January 2026, so “latest forecast” here means
            latest as it stood at each historical decision deadline.
          </li>
        </ul>
      </section>

      <section className="panel">
        <h2>Refreshing the data</h2>
        <p className="hint">
          The snapshot is generated once and committed, so the application runs
          offline and identically in Docker and on the deployed host.
        </p>
        <dl className="meta">
          <dt>Regenerate</dt>
          <dd>python backend/scripts/build_snapshot.py</dd>
          <dt>Row-count guard</dt>
          <dd>asserts 1,488 actuals and ≥15,000 forecasts</dd>
        </dl>
      </section>
    </>
  )
}
