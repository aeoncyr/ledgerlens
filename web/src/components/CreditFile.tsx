import { useState, type ReactNode } from 'react'
import {
  ASSESSMENT_LABEL,
  ASSESSMENT_TONE,
  type Citation,
  type CreditFileData,
  type EvidenceItem,
  type Finding,
} from '../types.ts'
import EvidenceViewer from './EvidenceViewer.tsx'

const rupiah = new Intl.NumberFormat('id-ID')
const monthName = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })

const FIVE_C = [
  ['character', 'Character'],
  ['capacity', 'Capacity'],
  ['capital', 'Capital'],
  ['collateral', 'Collateral'],
  ['conditions', 'Conditions'],
] as const

const SEVERITY_LABEL = { high: 'Material', medium: 'Needs an answer', low: 'Minor' }

function rp(value: number | null): string {
  return value === null ? '—' : `Rp\u00a0${rupiah.format(value)}`
}

// Where a figure without a piece of evidence behind it comes from.
function origin(key: string): string {
  if (key.startsWith('requested') || key === 'tenor_months') return 'the application'
  if (key.startsWith('kur_')) return 'KUR programme rules'
  if (['capacity_basis', 'max_installment', 'evidence_strength'].includes(key)) {
    return 'the lender’s policy, applied by code'
  }
  return 'the monthly cash flow above'
}

function month(key: string): string {
  return monthName.format(new Date(`${key}-01T00:00:00`))
}

// The policy's haircut on net cash flow, by outcome: only verified and partly verified files get an
// instalment.
const HAIRCUT: Partial<Record<CreditFileData['assessment'], string>> = {
  verified: '20% haircut for a verified file',
  partially_verified: '40% haircut for a partly verified file',
}

// A round top for the revenue scale: 1, 2, 2.5 or 5 times a power of ten, just above the high end.
function scaleTop(value: number): number {
  if (value <= 0) return 1
  const target = value * 1.08
  const power = 10 ** Math.floor(Math.log10(target))
  const step = [1, 2, 2.5, 5, 10].find((m) => m * power >= target) ?? 10
  return step * power
}

// Monthly revenue as a range: the floor that hard evidence proves, and the upper estimate once the
// notebook is counted. The months table below is the same data as a table.
function RevenueRange({ low, high }: { low: number; high: number }) {
  const upper = Math.max(low, high)
  const top = scaleTop(upper)
  const lowPct = (low / top) * 100
  const highPct = (upper / top) * 100
  return (
    <div className="range">
      <h2 className="range-title">Monthly revenue</h2>
      <div
        className="range-track"
        role="img"
        aria-label={`Monthly revenue from ${rp(low)} proven by QRIS to ${rp(upper)} with the notebook`}
      >
        {low > 0 && <span className="range-floor" style={{ width: `${lowPct}%` }} />}
        <span
          className="range-upper"
          style={{
            left: low > 0 ? `calc(${lowPct}% + 2px)` : 0,
            width: `max(0px, calc(${highPct - lowPct}% - ${low > 0 ? 2 : 0}px))`,
          }}
        />
      </div>
      <div className="range-axis mono" aria-hidden="true">
        <span>0</span>
        <span>{rp(top)}</span>
      </div>
      <dl className="range-legend">
        <div>
          <dt>
            <span className="swatch floor" aria-hidden="true" />
            Floor
          </dt>
          <dd className="mono">{low > 0 ? rp(low) : 'None'}</dd>
          <dd className="fine">
            {low > 0 ? 'Proven by QRIS, hard evidence' : 'No QRIS history, so nothing is proven'}
          </dd>
        </div>
        <div>
          <dt>
            <span className="swatch upper" aria-hidden="true" />
            Upper estimate
          </dt>
          <dd className="mono">{rp(upper)}</dd>
          <dd className="fine">With the notebook</dd>
        </div>
      </dl>
    </div>
  )
}

// A credit file as LedgerLens produces it: outcome, figures, findings, the 5C memo and the evidence,
// with every citation opening the evidence it points to.
export default function CreditFile({
  file,
  findingExtra,
}: {
  file: CreditFileData
  // The officer's file adds an answer box under each open question.
  findingExtra?: (finding: Finding, index: number) => ReactNode
}) {
  const [open, setOpen] = useState<{ item: EvidenceItem; locator: string | null } | null>(null)
  const byId = new Map(file.evidence.map((item) => [item.id, item]))
  const factsByKey = new Map(file.facts.map((fact) => [fact.key, fact]))
  const tone = ASSESSMENT_TONE[file.assessment]
  const app = file.application

  function label(id: string): string {
    return byId.get(id)?.reading?.label ?? id
  }

  function Cite({ citations }: { citations: Citation[] }) {
    if (citations.length === 0) return null
    return (
      <span className="cites">
        {citations.map((c, index) => {
          const item = byId.get(c.evidenceId)
          return (
            <button
              key={`${c.evidenceId}-${c.locator}-${index}`}
              type="button"
              className="cite"
              disabled={!item}
              onClick={() => item && setOpen({ item, locator: c.locator })}
            >
              {label(c.evidenceId)}, {c.locator}
            </button>
          )
        })}
      </span>
    )
  }

  const memoFigures = file.memo.figures
    .map((key) => factsByKey.get(key))
    .filter((fact) => fact !== undefined)

  return (
    <article className="credit-file">
      <header className="file-sheet">
        <div className="file-head">
          <span>LedgerLens credit file</span>
          <span className="mono">{file.fileNumber}</span>
        </div>
        <div className="file-title">
          <div>
            <h1>{app.alias}</h1>
            <p className="file-sub">
              {app.businessType}, {app.city} · {app.yearsOperating} years trading · requests{' '}
              {rp(app.amount)} over {app.tenorMonths} months
            </p>
          </div>
          <div className="outcome-box">
            <span className={`stamp static ${tone}`}>{ASSESSMENT_LABEL[file.assessment]}</span>
            <span className="prov-badge">Outcome set by policy rules in code</span>
          </div>
        </div>
        <p className="file-headline">{file.memo.headline}</p>
        <div className="file-figures-row">
          <RevenueRange low={file.cashflow.revenueLow} high={file.cashflow.revenueHigh} />
          <div className="instalment">
            <h2 className="range-title">Largest instalment the policy allows</h2>
            {file.policy.maxInstallment === null ? (
              <p className="instalment-none">
                No instalment suggested; the lender’s normal process applies.
              </p>
            ) : (
              <>
                <p className="instalment-value mono">
                  {rp(file.policy.maxInstallment)} <span>/month</span>
                </p>
                <p className="fine">
                  30% of net cash flow after a {HAIRCUT[file.assessment] ?? 'policy haircut'}
                  {file.policy.capacityBasis !== null && (
                    <> ({rp(file.policy.capacityBasis)} a month after the haircut)</>
                  )}
                  .
                </p>
              </>
            )}
            <p className="instalment-request">
              Requested <span className="mono">{rp(file.policy.requestedInstallment)}</span>
              <span className={file.policy.withinPolicy ? 'within' : 'outside'}>
                {file.policy.withinPolicy ? 'within policy' : 'not supported'}
              </span>
            </p>
          </div>
        </div>
        <ul className="reasons">
          {file.policy.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </header>

      <div className="file-columns">
        <div className="file-main">
          <section aria-labelledby="findings-heading">
            <h2 id="findings-heading">Findings</h2>
            {file.findings.length === 0 && <p className="fine">The sources raised no findings.</p>}
            <ol className="findings">
              {file.findings.map((finding, index) => (
                <li key={index} className={`finding ${finding.severity}`}>
                  <span className="severity">
                    {SEVERITY_LABEL[finding.severity]}
                    {finding.source === 'code' && ' · arithmetic check'}
                    {finding.resolved && <span className="resolved"> · explained by the owner</span>}
                  </span>
                  <p>{finding.text}</p>
                  {finding.followUpQuestion && (
                    <blockquote className="ask">
                      <p lang="id">{finding.followUpQuestion}</p>
                      {finding.followUpQuestionEn && <p className="fine">{finding.followUpQuestionEn}</p>}
                    </blockquote>
                  )}
                  {finding.answer && (
                    <p className="answer">
                      <strong>Owner’s answer{finding.answerAudio ? ' (spoken, transcribed by Gemini)' : ''}:</strong>{' '}
                      {finding.declined ? (
                        <em>prefers not to answer (recorded neutrally)</em>
                      ) : (
                        <span lang="id">{finding.answer}</span>
                      )}
                      {finding.answerEn && !finding.declined && (
                        <span className="fine answer-en"> {finding.answerEn}</span>
                      )}
                    </p>
                  )}
                  <Cite citations={finding.citations} />
                  {findingExtra?.(finding, index)}
                </li>
              ))}
            </ol>
            {file.confirmations.length > 0 && (
              <>
                <h3>Where the sources agree</h3>
                <ul className="agrees">
                  {file.confirmations.map((c, index) => (
                    <li key={index}>
                      {c.text} <Cite citations={c.citations} />
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <section aria-labelledby="cashflow-heading">
            <h2 id="cashflow-heading">Cash flow by month</h2>
            <div className="table-scroll">
              <table className="register figures-table">
                <thead>
                  <tr>
                    <th scope="col">Month</th>
                    <th scope="col" className="num">
                      Proven by QRIS
                    </th>
                    <th scope="col" className="num">
                      Claimed in notebook
                    </th>
                    <th scope="col" className="num">
                      Purchases on receipts
                    </th>
                    <th scope="col" className="num">
                      Expenses in notebook
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {file.cashflow.months.map((m) => (
                    <tr key={m.month}>
                      <th scope="row">{month(m.month)}</th>
                      <td className="num">{rupiah.format(m.provenInflows)}</td>
                      <td className="num">{rupiah.format(m.claimedSales)}</td>
                      <td className="num">{rupiah.format(m.receiptPurchases)}</td>
                      <td className="num">{rupiah.format(m.claimedExpenses)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fine">
              Amounts in rupiah, added up by code from the dated lines of each piece of evidence.
            </p>
          </section>

          <section aria-labelledby="memo-heading">
            <div className="memo-head">
              <h2 id="memo-heading">Credit memo</h2>
              <span className="prov-badge">Narrative by Gemini · Figures by Python</span>
            </div>
            {FIVE_C.map(([key, title]) => (
              <div className="memo-section" key={key}>
                <h3>{title}</h3>
                <p>{file.memo[key].text}</p>
                <Cite citations={file.memo[key].citations} />
              </div>
            ))}
            <div className="memo-section">
              <h3>Next steps for the officer</h3>
              <ul>
                {file.memo.officerNextSteps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </div>
          </section>

          {memoFigures.length > 0 && (
            <section aria-labelledby="figures-heading">
              <h2 id="figures-heading">Every figure in this file</h2>
              <div className="table-scroll">
                <table className="register figures-table">
                  <thead>
                    <tr>
                      <th scope="col">Figure</th>
                      <th scope="col" className="num">
                        Value
                      </th>
                      <th scope="col">Computed from</th>
                    </tr>
                  </thead>
                  <tbody>
                    {memoFigures.map((fact) => (
                      <tr key={fact.key}>
                        <td>{fact.label}</td>
                        <td className="num">{fact.display}</td>
                        <td>
                          {fact.sources.length
                            ? fact.sources.map(label).join(', ')
                            : origin(fact.key)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section aria-labelledby="owner-heading" lang="id">
            <h2 id="owner-heading">
              Ringkasan untuk pemilik <span className="fine" lang="en">(summary for the owner)</span>
            </h2>
            <p>
              <strong>Terverifikasi.</strong> {file.memo.ownerSummary.verified}
            </p>
            <p>
              <strong>Belum lengkap.</strong> {file.memo.ownerSummary.missing}
            </p>
            <ul>
              {file.memo.ownerSummary.tips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          </section>
        </div>

        <aside className="file-aside" aria-labelledby="evidence-heading">
          <h2 id="evidence-heading">Evidence ({file.evidence.length})</h2>
          <ul className="evidence-list">
            {file.evidence.map((item) => (
              <li key={item.id}>
                <button type="button" onClick={() => setOpen({ item, locator: null })}>
                  {item.type === 'interview_audio' ? (
                    <span className="audio-tile" aria-hidden="true">
                      ▶ Recording
                    </span>
                  ) : (
                    <img src={item.image} alt="" loading="lazy" />
                  )}
                  <span>
                    {label(item.id)}
                    {item.submittedBy === 'owner' && <span className="tag owner-tag">sent by owner</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="fine">
            Read by {file.models.join(', ')}. Evidence strength {file.policy.evidenceStrength} out of
            100.
          </p>
        </aside>
      </div>

      <EvidenceViewer
        item={open?.item ?? null}
        locator={open?.locator ?? null}
        onClose={() => setOpen(null)}
      />
    </article>
  )
}
