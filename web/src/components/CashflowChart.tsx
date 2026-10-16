import type { MonthFigures } from '../types.ts'

const monthShort = new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric' })
const juta = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })

const SERIES = [
  { key: 'provenInflows', label: 'Proven by QRIS', className: 'qris' },
  { key: 'claimedSales', label: 'Claimed in notebook', className: 'notebook' },
  { key: 'receiptPurchases', label: 'Purchases on receipts', className: 'receipts' },
] as const

// A round step for the axis (1, 2, 2.5 or 5 times a power of ten), giving four or five gridlines.
function niceScale(max: number): { top: number; step: number } {
  if (max <= 0) return { top: 1_000_000, step: 250_000 }
  const raw = max / 4
  const power = 10 ** Math.floor(Math.log10(raw))
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * power >= raw) ?? 10) * power
  return { top: Math.ceil((max * 1.04) / step) * step, step }
}

function inJuta(value: number): string {
  return juta.format(value / 1_000_000)
}

// Grouped bars per month: what QRIS proves, what the notebook claims and what the receipts show
// was bought. The table that follows it carries the exact figures and is its text alternative.
export default function CashflowChart({ months }: { months: MonthFigures[] }) {
  if (months.length === 0) return null
  const max = Math.max(...months.flatMap((m) => SERIES.map((s) => m[s.key])))
  const { top, step } = niceScale(max)
  const ticks: number[] = []
  for (let v = 0; v <= top + 1; v += step) ticks.push(v)

  return (
    <div className="cf-chart">
      <ul className="cf-legend" aria-hidden="true">
        {SERIES.map((s) => (
          <li key={s.key}>
            <span className={`cf-swatch ${s.className}`} />
            {s.label}
          </li>
        ))}
      </ul>
      <div className="cf-plot" aria-hidden="true">
        <span className="cf-unit">juta Rp</span>
        <div className="cf-grid">
          {ticks.map((v) => (
            <span key={v} className="cf-tick" style={{ bottom: `${(v / top) * 100}%` }}>
              <span className="cf-tick-label mono">{inJuta(v)}</span>
            </span>
          ))}
        </div>
        <div className="cf-groups">
          {months.map((m) => (
            <div className="cf-group" key={m.month}>
              <div className="cf-bars">
                {SERIES.map((s) => {
                  const value = m[s.key]
                  return (
                    <span key={s.key} className={`cf-bar ${s.className}`}>
                      <span className="cf-fill" style={{ height: `${(value / top) * 100}%` }}>
                        <span className="cf-value mono">{value === 0 ? '0' : inJuta(value)}</span>
                      </span>
                    </span>
                  )
                })}
              </div>
              <span className="cf-month">{monthShort.format(new Date(`${m.month}-01T00:00:00`))}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
