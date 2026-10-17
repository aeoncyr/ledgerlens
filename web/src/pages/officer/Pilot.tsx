// /app/pilot: what LedgerLens did on this workspace's files, as a lender running a shadow pilot
// would measure it. The API counts and times the files in code; this page lays the figures out and
// says plainly what they are not: a market study, or anyone else's files.
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { STATUS_LABEL, type ApplicationStatus } from '../../officer.ts'
import { downloadPilotCsv, duration, getPilot, type FindingKind, type PilotReport } from '../../pilot.ts'
import { ASSESSMENT_LABEL, ASSESSMENT_TONE, EVIDENCE_LABEL, type Assessment } from '../../types.ts'
import OfficerShell from './OfficerShell.tsx'
import '../../pilot.css'

const FINDING_LABEL: Record<FindingKind, string> = {
  fraud_signal: 'Fraud signals',
  discrepancy: 'Records that disagree',
  missing_evidence: 'Evidence missing behind a claim',
  low_confidence: 'Hard-to-read records',
  credit_history: 'Credit history (SLIK) concerns',
}

const DECISION_LABEL = { approve: 'Approve', request_more: 'Ask for more', decline: 'Decline' }

// Which order to list statuses and outcomes in: the order a file moves through them.
const STATUSES = Object.keys(STATUS_LABEL) as ApplicationStatus[]
const OUTCOMES: (Assessment | 'not_checked')[] = [
  'verified',
  'partially_verified',
  'insufficient_evidence',
  'inconsistent',
  'not_checked',
]

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

function Panel({ title, children }: { title: string; children: ReactNode }) {
  const id = `pilot-${title.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section className="pilot-panel" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  )
}

function outcomeLabel(outcome: Assessment | 'not_checked'): ReactNode {
  if (outcome === 'not_checked') return <span className="fine">Not checked yet</span>
  return <span className={`outcome ${ASSESSMENT_TONE[outcome]}`}>{ASSESSMENT_LABEL[outcome]}</span>
}

// A short ruled list of counts, with an empty line when there is nothing to count.
function Counts({ rows, empty }: { rows: [ReactNode, number][]; empty: string }) {
  const shown = rows.filter(([, n]) => n > 0)
  if (shown.length === 0) return <p className="fine">{empty}</p>
  return (
    <dl className="pilot-counts">
      {shown.map(([label, n], index) => (
        <div key={index}>
          <dt>{label}</dt>
          <dd className="mono">{n}</dd>
        </div>
      ))}
    </dl>
  )
}

// What a pilot would measure, for a workspace with no files yet.
function EmptyPilot({ demoHidden }: { demoHidden: boolean }) {
  return (
    <div className="empty pilot-empty">
      <p>
        <strong>
          {demoHidden ? 'No files of your own yet.' : 'No files in this workspace yet.'}
        </strong>{' '}
        In a shadow pilot, your officers run their
        usual files through LedgerLens next to their own process for three months, and this page
        fills in from those files:
      </p>
      <ul>
        <li>how many files went through, and how LedgerLens assessed them;</li>
        <li>the median time from the first record to a checked file, and to a decision;</li>
        <li>what the checks caught, fraud signals included;</li>
        <li>how often your officers agreed with LedgerLens’s assessment, and why they didn’t;</li>
        <li>which records were most often missing;</li>
        <li>how many files owners started themselves, and how many your officers started.</li>
      </ul>
      <p className="fine">
        Start a <Link to="/app/new">new application</Link> for a fictional business, or play a{' '}
        <Link to="/#samples">demo story</Link>, to see it work.
      </p>
    </div>
  )
}

function Dashboard({ report }: { report: PilotReport }) {
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const answered = report.agreed + report.disagreed
  const disagreements = report.rows.filter((r) => r.decision && r.assessmentAgreed === false)

  async function exportCsv() {
    setExporting(true)
    setError(null)
    try {
      await downloadPilotCsv(report.includeDemo)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setExporting(false)
  }

  return (
    <>
      <dl className="stats pilot-stats">
        <div>
          <dt>Files</dt>
          <dd>{report.files}</dd>
          <dd className="pilot-note">
            {report.includeDemo && report.demoFiles
              ? `${plural(report.demoFiles, 'demo copy', 'demo copies')} included`
              : 'Your own files only'}
          </dd>
        </div>
        <div>
          <dt>Median time from first record to a checked file</dt>
          <dd>{duration(report.medianMinutesToAnalysis)}</dd>
          <dd className="pilot-note">
            {report.timedToAnalysis
              ? `Over ${plural(report.timedToAnalysis, 'file')}`
              : 'No file has been checked after its records arrived yet'}
          </dd>
        </div>
        <div>
          <dt>Median time from first record to a decision</dt>
          <dd>{duration(report.medianMinutesToDecision)}</dd>
          <dd className="pilot-note">
            {report.timedToDecision
              ? `Over ${plural(report.timedToDecision, 'file')}`
              : 'No decision recorded yet'}
          </dd>
        </div>
        <div>
          <dt>Decisions where the officer agreed with LedgerLens</dt>
          <dd>{report.agreedPct === null ? '—' : `${report.agreedPct}%`}</dd>
          <dd className="pilot-note">
            {answered
              ? `${report.agreed} of ${plural(answered, 'decision')}`
              : 'Asked with every decision'}
          </dd>
        </div>
      </dl>

      <div className="pilot-grid">
        <Panel title="Files by status">
          <Counts
            rows={STATUSES.map((s) => [STATUS_LABEL[s], report.byStatus[s] ?? 0])}
            empty="No files yet."
          />
        </Panel>
        <Panel title="How LedgerLens assessed them">
          <Counts
            rows={OUTCOMES.map((o) => [outcomeLabel(o), report.byOutcome[o] ?? 0])}
            empty="No file has been checked yet."
          />
        </Panel>
        <Panel title="What the checks caught">
          <Counts
            rows={(Object.keys(FINDING_LABEL) as FindingKind[]).map((k) => [
              FINDING_LABEL[k],
              report.findingsByKind[k] ?? 0,
            ])}
            empty="No findings yet. They appear once files are checked."
          />
          {report.filesWithFraudSignal > 0 && (
            <p className="fine">
              {plural(report.filesWithFraudSignal, 'file')} with at least one fraud signal, each
              for an officer to look into; a signal is a reason to ask, not a verdict.
            </p>
          )}
        </Panel>
        <Panel title="Agreement with LedgerLens">
          {answered === 0 ? (
            <p className="fine">
              With every decision, the officer says whether they agree with LedgerLens’s
              assessment. The answers, and the reasons for disagreeing, collect here.
            </p>
          ) : (
            <>
              <Counts
                rows={[
                  ['Agreed', report.agreed],
                  ['Disagreed', report.disagreed],
                ]}
                empty=""
              />
              {disagreements.length > 0 && (
                <>
                  <h3>Why officers disagreed</h3>
                  <ul className="pilot-reasons">
                    {disagreements.map((r) => (
                      <li key={r.applicationId}>
                        <Link to={`/app/${r.applicationId}`}>{r.alias}</Link>
                        {r.outcome && ` (${ASSESSMENT_LABEL[r.outcome]})`}: “{r.disagreementReason}”
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
          {report.decided > answered && (
            <p className="fine">
              {plural(report.decided - answered, 'decision')} recorded before this question was
              asked.
            </p>
          )}
        </Panel>
        <Panel title="Records most often missing">
          {report.missingEvidence.length === 0 ? (
            <p className="fine">
              {report.checkedFiles
                ? 'Every checked file had every kind of record.'
                : 'Once files are checked, the kinds of record they lacked are counted here.'}
            </p>
          ) : (
            <>
              <Counts
                rows={report.missingEvidence.map((m) => [EVIDENCE_LABEL[m.type], m.files])}
                empty=""
              />
              <p className="fine">
                Files without that kind of record, of {plural(report.checkedFiles, 'checked file')}.
              </p>
            </>
          )}
        </Panel>
        <Panel title="Who started the files">
          <Counts
            rows={[
              ['The business owner, then shared it', report.byOrigin.owner ?? 0],
              ['An officer at your lender', report.byOrigin.officer ?? 0],
            ]}
            empty="No files yet."
          />
        </Panel>
      </div>

      <section className="pilot-table" aria-labelledby="pilot-files">
        <div className="pilot-table-head">
          <h2 id="pilot-files">The files behind these figures</h2>
          <button className="button quiet" onClick={() => void exportCsv()} disabled={exporting}>
            {exporting ? 'Preparing…' : 'Export CSV'}
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="table-scroll">
          <table className="register">
            <thead>
              <tr>
                <th scope="col">Business</th>
                <th scope="col">Outcome</th>
                <th scope="col" className="num">
                  Findings
                </th>
                <th scope="col" className="num">
                  To checked file
                </th>
                <th scope="col" className="num">
                  To decision
                </th>
                <th scope="col">Decision</th>
                <th scope="col">Officer and LedgerLens</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((r) => (
                <tr key={r.applicationId}>
                  <th scope="row">
                    <Link to={`/app/${r.applicationId}`}>{r.alias}</Link>
                    <span className="sub">
                      {r.fileNumber}
                      {r.origin === 'owner' && <span className="tag owner-tag">Shared by owner</span>}
                      {r.demo && <span className="tag">Demo copy</span>}
                    </span>
                  </th>
                  <td data-label="Outcome">
                    {r.outcome ? (
                      <span className={`outcome ${ASSESSMENT_TONE[r.outcome]}`}>
                        {ASSESSMENT_LABEL[r.outcome]}
                      </span>
                    ) : (
                      <span className="fine">Not checked</span>
                    )}
                  </td>
                  <td className="num" data-label="Findings">
                    {r.findings}
                    {r.findingsByKind.fraud_signal > 0 && (
                      <span className="sub">{plural(r.findingsByKind.fraud_signal, 'fraud signal')}</span>
                    )}
                  </td>
                  <td className="num" data-label="To checked file">
                    {duration(r.minutesToAnalysis)}
                  </td>
                  <td className="num" data-label="To decision">
                    {duration(r.minutesToDecision)}
                  </td>
                  <td data-label="Decision">
                    {r.decision ? DECISION_LABEL[r.decision] : <span className="fine">None yet</span>}
                  </td>
                  <td data-label="Officer and LedgerLens">
                    {!r.decision ? (
                      <span className="fine">—</span>
                    ) : r.assessmentAgreed === null ? (
                      <span className="fine">Not asked</span>
                    ) : r.assessmentAgreed ? (
                      'Agreed'
                    ) : (
                      'Disagreed'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

export default function Pilot() {
  const [includeDemo, setIncludeDemo] = useState(true)
  const [report, setReport] = useState<PilotReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getPilot(includeDemo)
      .then((r) => {
        if (!cancelled) {
          setReport(r)
          setError(null)
        }
      })
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [includeDemo])

  return (
    <OfficerShell title="Pilot dashboard" crumbs={<> / Pilot</>}>
      <p className="lead-text">
        What LedgerLens did on the files in this workspace, counted by code from those files. These
        are your files, not a market study, and no figure here is estimated.
      </p>
      {report && report.demoFiles > 0 && (
        <label className="pilot-demo-toggle">
          <input
            type="checkbox"
            checked={includeDemo}
            onChange={(e) => setIncludeDemo(e.target.checked)}
          />
          Include demo copies of the sample files ({report.demoFiles})
        </label>
      )}
      {error && <p className="error">The dashboard could not be loaded: {error}</p>}
      {!report && !error && <p className="fine">Counting your files…</p>}
      {report &&
        (report.files === 0 ? (
          <EmptyPilot demoHidden={report.demoFiles > 0} />
        ) : (
          <Dashboard report={report} />
        ))}
    </OfficerShell>
  )
}
