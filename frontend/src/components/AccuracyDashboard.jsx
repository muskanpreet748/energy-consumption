import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getJSON } from '../api.js'
import MetricCard, { mw, signedMw } from './MetricCard.jsx'

const chartTooltip = {
  contentStyle: {
    background: '#161b22',
    border: '1px solid #2a3342',
    borderRadius: 8,
    fontSize: 12,
  },
  formatter: (value, name) => [`${mw(value)} MW`, name],
}

function MiniBarChart({ data, dataKey, name, height = 220, reference }) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#2a3342" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="bucket" stroke="#8b97a8" tick={{ fontSize: 11 }} />
          <YAxis stroke="#8b97a8" tick={{ fontSize: 11 }} width={54} />
          <Tooltip {...chartTooltip} cursor={{ fill: 'rgba(76,141,255,0.07)' }} />
          <Bar dataKey={dataKey} name={name} fill="#4c8dff" radius={[4, 4, 0, 0]} />
          {reference !== undefined && (
            <ReferenceLine
              y={reference}
              stroke="#f0b429"
              strokeDasharray="4 4"
              label={{ value: 'month avg', fill: '#f0b429', fontSize: 10, position: 'insideTopRight' }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function AccuracyDashboard() {
  const [data, setData] = useState(null)
  const [state, setState] = useState({ loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    getJSON('/api/accuracy')
      .then((body) => {
        if (cancelled) return
        setData(body)
        setState({ loading: false, error: null })
      })
      .catch((error) => {
        if (cancelled) return
        setState({ loading: false, error: error.message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (state.loading && !data) {
    return (
      <section className="panel">
        <div className="status loading">Loading January 2026 accuracy…</div>
      </section>
    )
  }
  if (state.error) {
    return (
      <section className="panel">
        <div className="status error">{state.error}</div>
      </section>
    )
  }
  if (!data) return null

  const o = data.overall
  const issueTimes = data.by_issue_time
  const bestIssue = issueTimes.reduce((a, b) => (a.mae_mw <= b.mae_mw ? a : b))
  const gain = issueTimes[0].mae_mw - bestIssue.mae_mw
  const offsetShare = Math.round((Math.abs(o.bias_mw) / o.mae_mw) * 100)

  const dailyChart = data.daily.map((row) => ({
    bucket: row.delivery_day.slice(8),
    mae: row.stats.mae_mw,
    bias: row.stats.bias_mw,
  }))
  const worstDays = [...data.daily]
    .sort((a, b) => b.stats.mae_mw - a.stats.mae_mw)
    .slice(0, 5)

  return (
    <>
      <section className="panel">
        <h2>January 2026 — day-ahead forecast accuracy</h2>
        <p className="hint">
          {data.overall.n} hourly comparisons across {data.daily.length} delivery
          days, each measured against the forecast visible at 09:50 the day
          before. All values in MW.
        </p>

        <div className="cards">
          <MetricCard
            label="Mean absolute error"
            value={mw(o.mae_mw)}
            unit=" MW"
            note="headline day-ahead error"
            tone="warn"
          />
          <MetricCard
            label="RMSE"
            value={mw(o.rmse_mw)}
            unit=" MW"
            note="penalises big misses"
            tone="warn"
          />
          <MetricCard
            label="Systematic bias"
            value={signedMw(o.bias_mw)}
            unit=" MW"
            note={`${offsetShare}% of raw error`}
            tone={o.bias_mw > 0 ? 'bad' : 'good'}
          />
          <MetricCard
            label="Error after bias removed"
            value={mw(o.mae_after_bias_correction_mw)}
            unit=" MW"
            note="unpredictable component"
            tone="good"
          />
          <MetricCard
            label="Reserve buffer (P90)"
            value={mw(o.p90_abs_error_mw)}
            unit=" MW"
            note="covers 90% of hours"
            tone="bad"
          />
          <MetricCard
            label="Shape correlation"
            value={o.correlation === null ? 'n/a' : o.correlation.toFixed(3)}
            note="forecast vs outturn"
            tone={o.correlation > 0.8 ? 'good' : 'warn'}
          />
        </div>

        <div className="callout warn">
          <strong>The headline finding.</strong> The forecast tracks the shape of
          the day very well (r = {o.correlation?.toFixed(2)}), but runs{' '}
          <strong>{signedMw(o.bias_mw)} MW high on average</strong> — roughly{' '}
          {Math.round((o.bias_mw / 11581) * 100)}% of mean output, and it does{' '}
          <em>not</em> shrink as delivery approaches. Because wind forecast error
          feeds the thermal purchase one-for-one, a persistent optimistic bias
          means the position is structurally short. Once that constant offset is
          removed, the genuinely unpredictable error is{' '}
          <strong>{mw(o.mae_after_bias_correction_mw)} MW</strong> — the figure a
          reserve buffer should be sized against.
        </div>
      </section>

      <section className="panel">
        <div className="grid-2">
          <div>
            <div className="chart-title">Error by delivery day</div>
            <div className="chart-sub">Daily mean absolute error (MW)</div>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={dailyChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#2a3342" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="bucket" stroke="#8b97a8" tick={{ fontSize: 10 }} interval={1} />
                <YAxis stroke="#8b97a8" tick={{ fontSize: 11 }} width={54} />
                <Tooltip {...chartTooltip} cursor={{ fill: 'rgba(76,141,255,0.07)' }} />
                <Bar dataKey="mae" name="MAE" fill="#4c8dff" radius={[3, 3, 0, 0]} />
                <ReferenceLine
                  y={o.mae_mw}
                  stroke="#f0b429"
                  strokeDasharray="4 4"
                  label={{ value: 'month avg', fill: '#f0b429', fontSize: 10, position: 'insideTopRight' }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div>
            <div className="chart-title">Error by lead time</div>
            <div className="chart-sub">How far ahead of delivery the forecast was made</div>
            <MiniBarChart data={data.by_lead_time} dataKey="mae_mw" name="MAE" reference={o.mae_mw} />
          </div>

          <div>
            <div className="chart-title">Does waiting help? Error by publication time</div>
            <div className="chart-sub">
              Every pre-gate run that morning, measured against the same delivery day
            </div>
            <MiniBarChart data={data.by_issue_time} dataKey="mae_mw" name="MAE" reference={o.mae_mw} />
            <div className="callout">
              Moving from the 02:30 run to the {bestIssue.bucket} run changes MAE
              from {mw(issueTimes[0].mae_mw)} MW to {mw(bestIssue.mae_mw)} MW — a{' '}
              <strong>{mw(gain)} MW</strong> improvement for waiting{' '}
              {bestIssue.bucket.slice(0, 2) - issueTimes[0].bucket.slice(0, 2)} hours
              longer. Marginal, which is itself decision-useful: the early run is
              nearly as good.
            </div>
          </div>

          <div>
            <div className="chart-title">Worst delivery days</div>
            <div className="chart-sub">Days where the position was most exposed</div>
            <table>
              <thead>
                <tr>
                  <th>Delivery day</th>
                  <th className="num">MAE (MW)</th>
                  <th className="num">Bias (MW)</th>
                  <th className="num">P90 (MW)</th>
                  <th className="num">r</th>
                </tr>
              </thead>
              <tbody>
                {worstDays.map((row) => (
                  <tr key={row.delivery_day}>
                    <td className="mono">{row.delivery_day}</td>
                    <td className="num">{mw(row.stats.mae_mw)}</td>
                    <td className="num">{signedMw(row.stats.bias_mw)}</td>
                    <td className="num">{mw(row.stats.p90_abs_error_mw)}</td>
                    <td className="num">{row.stats.correlation?.toFixed(2) ?? 'n/a'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Day-by-day detail</h2>
        <p className="hint">
          Every decision vintage, in date order.
        </p>
        <table>
          <thead>
            <tr>
              <th>Delivery day</th>
              <th>Decision vintage</th>
              <th className="num">MAE (MW)</th>
              <th className="num">RMSE (MW)</th>
              <th className="num">Bias (MW)</th>
              <th className="num">Bias-corrected MAE</th>
              <th className="num">P90 (MW)</th>
              <th className="num">r</th>
            </tr>
          </thead>
          <tbody>
            {data.daily.map((row) => (
              <tr key={row.delivery_day}>
                <td className="mono">{row.delivery_day}</td>
                <td className="mono">{row.chosen_publish_time.slice(5, 16).replace('T', ' ')}</td>
                <td className="num">{mw(row.stats.mae_mw)}</td>
                <td className="num">{mw(row.stats.rmse_mw)}</td>
                <td className="num" style={{ color: row.stats.bias_mw > 0 ? '#d29922' : '#58a6ff' }}>
                  {signedMw(row.stats.bias_mw)}
                </td>
                <td className="num">{mw(row.stats.mae_after_bias_correction_mw)}</td>
                <td className="num">{mw(row.stats.p90_abs_error_mw)}</td>
                <td className="num">{row.stats.correlation?.toFixed(2) ?? 'n/a'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
