/** Single headline number with a label and an optional explanation. */
export default function MetricCard({ label, value, unit, note, tone }) {
  return (
    <div className={`card ${tone || ''}`}>
      <div className="label">{label}</div>
      <div className="value">
        {value}
        {unit ? <span className="unit">{unit}</span> : null}
      </div>
      {note ? <div className="note">{note}</div> : null}
    </div>
  )
}

/** Format a megawatt figure for display. */
export const mw = (value, digits = 0) =>
  Number(value).toLocaleString('en-GB', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })

/** Sign-aware megawatt figure, e.g. "+1,760". */
export const signedMw = (value, digits = 0) => {
  const n = Number(value)
  return `${n > 0 ? '+' : ''}${mw(n, digits)}`
}

/** '2026-01-16T12:00:00Z' -> '12:00' */
export const hourLabel = (iso) => iso.slice(11, 16)
