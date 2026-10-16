import { ASSESSMENT_LABEL, ASSESSMENT_TONE, type SampleSummary } from '../types.ts'

const rupiah = new Intl.NumberFormat('id-ID')
const oneDecimal = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 })
const dateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

function millions(value: number): string {
  return oneDecimal.format(value / 1_000_000)
}

function findingsNote(sample: SampleSummary): string {
  const count = sample.findings.length
  const open = sample.findings.filter((f) => f.severity !== 'low').length
  if (count === 0) return 'no findings'
  if (open === 0) return `${count} minor finding${count > 1 ? 's' : ''}`
  return `${count} findings, ${open} needing an answer`
}

// The first page of a credit file, set as a document an officer would sign. Every figure on it
// was computed by code from cited evidence.
export default function CreditFileCard({
  sample,
  compact = false,
}: {
  sample: SampleSummary
  compact?: boolean
}) {
  const tone = ASSESSMENT_TONE[sample.assessment]
  return (
    <figure className="file-figure">
      <article className="file-card" aria-label={`Credit file for ${sample.alias}`}>
        <div className="file-head">
          <span>LedgerLens credit file</span>
          <span className="mono">{sample.fileNumber}</span>
        </div>
        <span className={`stamp ${tone}`}>{ASSESSMENT_LABEL[sample.assessment]}</span>
        <h2>{sample.alias}</h2>
        <p className="file-sub">
          {sample.businessType}, {sample.city} · {sample.yearsOperating} years trading
          <br />
          Requests Rp {rupiah.format(sample.amount)} over {sample.tenorMonths} months
        </p>
        <dl className="file-figures">
          <div>
            <dt>Monthly revenue, proven to claimed</dt>
            <dd>
              Rp {millions(sample.revenueLow)}–{millions(sample.revenueHigh)} juta
            </dd>
          </div>
          <div>
            <dt>Largest instalment the policy allows</dt>
            <dd>
              {sample.maxInstallment === null ? '—' : `Rp ${rupiah.format(sample.maxInstallment)}`}
            </dd>
          </div>
          <div>
            <dt>Instalment requested</dt>
            <dd>
              Rp {rupiah.format(sample.requestedInstallment)}
              {sample.withinPolicy && <span className="within">within policy</span>}
            </dd>
          </div>
          <div>
            <dt>Evidence strength</dt>
            <dd className="strength">
              <span className="strength-bar" aria-hidden="true">
                <span style={{ width: `${sample.evidenceStrength}%` }} />
              </span>
              {sample.evidenceStrength} / 100
            </dd>
          </div>
        </dl>
        <div className="file-foot">
          <span>
            {sample.evidenceCount} pieces of evidence · {findingsNote(sample)}
            <br />
            Prepared {dateFormat.format(new Date(sample.preparedAt))}
          </span>
          <span className="signature">
            <span className="sig-line">awaiting review</span>
            Credit officer
          </span>
        </div>
      </article>
      {!compact && (
      <figcaption className="file-caption">
        A real file for a fictional business. Gemini read the evidence; code computed every figure;
        the decision is left to a person.
      </figcaption>
      )}
    </figure>
  )
}
