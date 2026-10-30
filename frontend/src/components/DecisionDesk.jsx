import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getJSON } from '../api.js'
import MetricCard, { hourLabel, mw, signedMw } from './MetricCard.jsx'

const FALLBACK_DAY = '2026-01-16'

export default function DecisionDesk() {
  const [days, setDays] = useState([])
  const [deliveryDay, setDeliveryDay] = useState(FALLBACK_DAY)
  const [data, setData] = useState(null)
  const [state, setState] = useState({ loading: true, error: null })

  // Load the list of usable delivery days once.
  useEffect(() => {
    let cancelled = false
    getJSON('/api/days')
      .then((body) => {
        if (cancelled) return
        setDays(body.days)
        if (!body.days.some((d) => d.delivery_day === FALLBACK_DAY)) {
          setDeliveryDay(body.days[0]?.delivery_day ?? '')
        }
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: error.message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const load = useCallback(async (day) => {
    if (!day) return
    setState({ loading: true, error: null })
    setData(null)
    try {
      setData(await getJSON('/api/decision', { delivery: day }))
      setState({ loading: false, error: null })
    } catch (error) {
      setState({ loading: false, error: error.message })
    }
  }, [])

  useEffect(() => {
    load(deliveryDay)
  }, [deliveryDay, load])

  const worstHours = useMemo(() => {
    if (!data) return []
    return [...data.hours]
      .sort((a, b) => Math.abs(b.error_mw) - Math.abs(a.error_mw))
      .slice(0, 6)
  }, [data])

  const m = data?.metrics
  const biasTone = m && m.bias_mw > 500 ? 'bad' : m && m.bias_mw < -500 ? 'warn' : 'good'

  return (
    <>
      <section className="panel">
        <h2>What we knew at the 09:50 gate</h2>
        <p className="hint">
          The day-ahead auction closes at 09:50 the day before delivery. Select a
          delivery day to see the last forecast published before that deadline —
          exactly what a trader could have acted on.
        </p>

        <div className="row">
          <label className="field">
            Delivery day
            <select
              value={deliveryDay}
              onChange={(event) => setDeliveryDay(event.target.value)}
              disabled={days.length === 0}
            >
              {days.map((day) => (
                <option key={day.delivery_day} value={day.delivery_day}>
                  {day.delivery_day}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="primary"
            onClick={() => load(deliveryDay)}
            disabled={state.loading || !deliveryDay}
          >
            {state.loading ? 'Analysing…' : 'Analyse'}
          </button>
        </div>

        {state.loading && !data && <div className="status loading">Loading…</div>}
        {state.error && <div className="status error">{state.error}</div>}
      </section>

      {data && (
        <>
          <section className="panel">
            <h2>Forecast vintages available that morning</h2>
            <p className="hint">
              Each publication is a separate “vintage”. Only the ones before{' '}
              <strong>{data.decision_deadline.slice(11, 16)} UTC</strong> were
              usable; the highlighted chip is the one this analysis uses.
            </p>
            <div className="vintages">
              {data.available_vintages.map((publishTime) => (
                <span
                  key={publishTime}
                  className={`vintage ${
                    publishTime === data.chosen_publish_time ? 'chosen' : ''
                  }`}
                >
                  {publishTime === data.chosen_publish_time
                    ? `★ ${publishTime.slice(11, 16)} — decision vintage`
                    : publishTime.slice(11, 16)}
                </span>
              ))}
              <span className="vintage too-late">later runs arrive after the gate</span>
            </div>

            <dl className="meta" style={{ marginTop: 18 }}>
              <dt>Decision deadline</dt>
              <dd>{data.decision_deadline}</dd>
              <dt>Forecast published at</dt>
              <dd>{data.chosen_publish_time}</dd>
              <dt>Delivery day</dt>
              <dd>{data.delivery_day}</dd>
              <dt>Hours compared</dt>
              <dd>{data.hours.length}</dd>
            </dl>
          </section>

          <section className="panel">
            <h2>How wrong was it?</h2>
            <p className="hint">All values in MW. Error = forecast − actual.</p>
            <div className="cards">
              <MetricCard
                label="Mean absolute error"
                value={mw(m.mae_mw)}
                unit=" MW"
                note="typical size of a miss"
                tone="warn"
              />
              <MetricCard
                label="Bias"
                value={signedMw(m.bias_mw)}
                unit=" MW"
                note={
                  m.bias_mw > 0
                    ? 'forecast ran high → thermal under-bought'
                    : 'forecast ran low → thermal over-bought'
                }
                tone={biasTone}
              />
              <MetricCard
                label="Error after bias removed"
                value={mw(m.mae_after_bias_correction_mw)}
                unit=" MW"
                note="the unpredictable part"
                tone={
                  m.mae_after_bias_correction_mw < m.mae_mw * 0.75 ? 'good' : 'warn'
                }
              />
              <MetricCard
                label="Reserve buffer (P90)"
                value={mw(m.p90_abs_error_mw)}
                unit=" MW"
                note="covers 90% of hours"
                tone="bad"
              />
              <MetricCard
                label="Shape correlation"
                value={m.correlation === null ? 'n/a' : m.correlation.toFixed(3)}
                note="1.0 = tracks every swing"
                tone={m.correlation > 0.8 ? 'good' : 'warn'}
              />
            </div>

            <div className="callout">
              On <strong>{data.delivery_day}</strong> the forecast was off by{' '}
              <strong>{mw(m.mae_mw)} MW</strong> on average.{' '}
              {Math.abs(m.bias_mw) > m.mae_mw * 0.5
                ? `Most of that (${signedMw(m.bias_mw)} MW) was a constant offset, so the genuinely unpredictable error was ${mw(m.mae_after_bias_correction_mw)} MW.`
                : `The error was mostly random rather than a constant offset (bias ${signedMw(m.bias_mw)} MW).`}
            </div>

            <div className="chart">
              <div className="chart-title">Forecast vs metered outturn</div>
              <div className="chart-sub">
                Hourly MW · {data.chosen_publish_time} vintage
              </div>
              <ResponsiveContainer width="100%" height={330}>
                <LineChart
                  data={data.hours}
                  margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
                >
                  <CartesianGrid stroke="#2a3342" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="hour"
                    tickFormatter={hourLabel}
                    stroke="#8b97a8"
                    tick={{ fontSize: 11 }}
                    interval={2}
                  />
                  <YAxis stroke="#8b97a8" tick={{ fontSize: 11 }} width={58} />
                  <Tooltip
                    contentStyle={{
                      background: '#161b22',
                      border: '1px solid #2a3342',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelFormatter={(label) => `Delivery hour ${hourLabel(label)} UTC`}
                    formatter={(value, name) => [`${mw(value)} MW`, name]}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone"
                    dataKey="forecast_mw"
                    name="Forecast"
                    stroke="#f0b429"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="actual_mw"
                    name="Actual outturn"
                    stroke="#2f9e44"
                    strokeWidth={2}
                    dot={false}
                  />
                  <ReferenceLine
                    y={0}
                    stroke="#2a3342"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="panel">
            <h2>Largest misses of the day</h2>
            <p className="hint">
              These are the hours a procurement position would have been most
              exposed.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Delivery hour (UTC)</th>
                  <th className="num">Forecast (MW)</th>
                  <th className="num">Actual (MW)</th>
                  <th className="num">Error (MW)</th>
                  <th className="num">Lead time (h)</th>
                </tr>
              </thead>
              <tbody>
                {worstHours.map((point) => (
                  <tr key={point.hour}>
                    <td className="mono">{point.hour.replace('T', ' ').replace(':00Z', '')}</td>
                    <td className="num">{mw(point.forecast_mw)}</td>
                    <td className="num">{mw(point.actual_mw)}</td>
                    <td
                      className="num"
                      style={{ color: point.error_mw > 0 ? '#d29922' : '#58a6ff' }}
                    >
                      {signedMw(point.error_mw, 1)}
                    </td>
                    <td className="num">{point.lead_hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </>
  )
}
