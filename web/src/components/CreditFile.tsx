import { useState } from 'react'
import {
  ASSESSMENT_LABEL,
  ASSESSMENT_TONE,
  type Citation,
  type CreditFileData,
  type EvidenceItem,
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
  return value === null ? '—' : `Rp ${rupiah.format(value)}`
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

// A credit file as LedgerLens produces it: outcome, figures, findings, the 5C memo and the evidence,
// with every citation opening the evidence it points to.
export default function CreditFile({ file }: { file: CreditFileData }) {
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
          <span className={`stamp static ${tone}`}>{ASSESSMENT_LABEL[file.assessment]}</span>
        </div>
        <p className="file-headline">{file.memo.headline}</p>
        <dl className="key-figures">
          <div>
            <dt>Monthly revenue, proven (QRIS)</dt>
            <dd>{rp(file.cashflow.revenueLow)}</dd>
          </div>
          <div>
            <dt>Monthly revenue, claimed (notebook)</dt>
            <dd>{rp(file.cashflow.revenueHigh)}</dd>
          </div>
          <div>
            <dt>Largest instalment the policy allows</dt>
            <dd>{rp(file.policy.maxInstallment)}</dd>
          </div>
          <div>
            <dt>Instalment requested</dt>
            <dd>
              {rp(file.policy.requestedInstallment)}
              <span className={file.policy.withinPolicy ? 'within' : 'outside'}>
                {file.policy.withinPolicy ? 'within policy' : 'not supported'}
              </span>
            </dd>
          </div>
        </dl>
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
                  </span>
                  <p>{finding.text}</p>
                  {finding.followUpQuestion && (
                    <blockquote className="ask">
                      <p lang="id">{finding.followUpQuestion}</p>
                      {finding.followUpQuestionEn && <p className="fine">{finding.followUpQuestionEn}</p>}
                    </blockquote>
                  )}
                  <Cite citations={finding.citations} />
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
            <h2 id="memo-heading">Credit memo</h2>
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
                  <img src={item.image} alt="" loading="lazy" />
                  <span>{label(item.id)}</span>
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
