import { getDownloadURL, ref } from 'firebase/storage'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import CreditFile from '../../components/CreditFile.tsx'
import DemoBar from '../../components/DemoBar.tsx'
import LiveTrace from '../../components/LiveTrace.tsx'
import VoiceRecorder from '../../components/VoiceRecorder.tsx'
import { auth, storage } from '../../firebase.ts'
import {
  STATUS_LABEL,
  answerByVoice,
  answerQuestion,
  confirmReading,
  declineQuestion,
  recheck,
  useApplication,
  useAudit,
  useCreditFileDoc,
  useEvidence,
  useRun,
  type Application,
  type AuditEntry,
  type StoredEvidence,
} from '../../officer.ts'
import {
  ASSESSMENT_LABEL,
  EVIDENCE_LABEL,
  type Assessment,
  type CreditFileData,
  type EvidenceType,
  type Finding,
} from '../../types.ts'
import Decision, { SignoffPanel } from './Decision.tsx'
import HandOff from './HandOff.tsx'
import OfficerShell, { type OfficerStep } from './OfficerShell.tsx'

function useImageUrls(evidence: StoredEvidence[]): Map<string, string> {
  const [urls, setUrls] = useState(new Map<string, string>())
  const key = evidence.map((e) => e.id).join(',')
  useEffect(() => {
    let cancelled = false
    Promise.all(
      evidence.map(
        async (e) =>
          [
            e.id,
            // A demo copy of a sample points at the public photos the web app serves.
            e.storagePath.startsWith('/samples/')
              ? e.storagePath
              : await getDownloadURL(ref(storage, e.storagePath)),
          ] as const,
      ),
    )
      .then((pairs) => !cancelled && setUrls(new Map(pairs)))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
    // The evidence list is identified by its ids.
  }, [key]) // eslint-disable-line
  return urls
}

function AnswerBox({ id, index, finding }: { id: string; index: number; finding: Finding }) {
  const [text, setText] = useState(finding.declined ? '' : (finding.answer ?? ''))
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  if (!finding.followUpQuestion || finding.resolved) return null

  async function send(action: () => Promise<void>, done: string) {
    setState('saving')
    setMessage(null)
    try {
      await action()
      setState('saved')
      setMessage(done)
    } catch (e) {
      setState('error')
      setMessage(e instanceof Error ? e.message : 'Could not save; try again.')
    }
  }

  function save(event: FormEvent) {
    event.preventDefault()
    void send(() => answerQuestion(id, index, text), 'Saved.')
  }

  return (
    <form className="answer-box" onSubmit={save}>
      <label>
        The owner’s answer, as you heard it
        <textarea
          rows={2}
          lang="id"
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setState('idle')
          }}
          placeholder="Tulis jawaban pemilik…"
        />
      </label>
      <div className="answer-actions">
        <button className="button quiet" disabled={!text.trim() || state === 'saving'}>
          {state === 'saving' ? 'Saving…' : 'Save answer'}
        </button>
        <VoiceRecorder
          label="Record the owner’s answer"
          busy={state === 'saving'}
          onRecorded={(audio) =>
            void send(
              () => answerByVoice(id, index, audio),
              'Recorded. Gemini transcribed it; the transcript appears above.',
            )
          }
        />
        <button
          type="button"
          className="link-button"
          disabled={state === 'saving'}
          onClick={() =>
            void send(() => declineQuestion(id, index), 'Recorded neutrally: prefers not to answer.')
          }
        >
          The owner prefers not to answer
        </button>
      </div>
      {message && <span className={state === 'error' ? 'error' : 'fine'}>{message}</span>}
    </form>
  )
}

type Disputed = {
  evidence: StoredEvidence
  line: number
  first: number | null
  second: number | null
}

const rupiahText = new Intl.NumberFormat('id-ID')

function disputedLines(evidence: StoredEvidence[]): Disputed[] {
  const found: Disputed[] = []
  for (const item of evidence) {
    const extraction = item.extraction as
      | { lines?: { line: number; confirmedByOfficer?: boolean }[]; disagreements?: Disputed[] }
      | null
      | undefined
    const confirmed = new Set(
      (extraction?.lines ?? []).filter((l) => l.confirmedByOfficer).map((l) => l.line),
    )
    for (const d of extraction?.disagreements ?? []) {
      if (!confirmed.has(d.line)) found.push({ ...d, evidence: item })
    }
  }
  return found
}

// When the two readings of a notebook page disagree, the officer looks at the photo and settles it.
function ConfirmReadings({
  id,
  evidence,
  urls,
}: {
  id: string
  evidence: StoredEvidence[]
  urls: Map<string, string>
}) {
  const open = disputedLines(evidence)
  const [confirmedCount, setConfirmedCount] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [other, setOther] = useState<Record<string, string>>({})
  if (open.length === 0 && confirmedCount === 0) return null

  async function confirm(item: Disputed, amount: number) {
    setBusy(true)
    setError(null)
    try {
      await confirmReading(id, item.evidence.id, item.line, amount)
      setConfirmedCount((n) => n + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  async function rerun() {
    setBusy(true)
    setError(null)
    try {
      await recheck(id)
      setConfirmedCount(0)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  return (
    <section className="confirm-readings" aria-labelledby="confirm-heading">
      <h2 id="confirm-heading">Readings to confirm</h2>
      <p>
        Gemini read each notebook page twice with different instructions. Where the two readings
        disagree, look at the photo and choose what is written. Code then recomputes the cash flow
        with your answer.
      </p>
      <ul>
        {open.map((item) => {
          const key = `${item.evidence.id}-${item.line}`
          const label = item.evidence.label ?? 'Notebook page'
          return (
            <li key={key}>
              {urls.get(item.evidence.id) && (
                <a href={urls.get(item.evidence.id)} target="_blank" rel="noreferrer">
                  <img src={urls.get(item.evidence.id)} alt={`${label}, photographed`} />
                </a>
              )}
              <div>
                <strong>
                  {label}, line {item.line}
                </strong>
                <span className="fine"> Which amount is written?</span>
                <div className="answer-actions">
                  {[item.first, item.second]
                    .filter((v): v is number => v !== null)
                    .map((value) => (
                      <button
                        key={value}
                        type="button"
                        className="button quiet mono"
                        disabled={busy}
                        onClick={() => void confirm(item, value)}
                      >
                        Rp {rupiahText.format(value)}
                      </button>
                    ))}
                  <input
                    inputMode="numeric"
                    placeholder="Something else (Rp)"
                    aria-label={`Another amount for ${label}, line ${item.line}`}
                    value={other[key] ?? ''}
                    onChange={(e) => setOther({ ...other, [key]: e.target.value.replace(/\D/g, '') })}
                  />
                  <button
                    type="button"
                    className="button quiet"
                    disabled={busy || !other[key]}
                    onClick={() => void confirm(item, Number(other[key]))}
                  >
                    Use this
                  </button>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
      {confirmedCount > 0 && (
        <div className="answer-actions">
          <button className="button" disabled={busy} onClick={() => void rerun()}>
            {busy ? 'Checking…' : 'Re-check with the confirmed readings'}
          </button>
          <span className="fine">
            Only the verifier, the policy and the memo writer run; this does not use up a question
            for the owner.
          </span>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  )
}

function FollowUp({ id, findings, round }: { id: string; findings: Finding[]; round: number }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const open = findings.filter((f) => f.followUpQuestion && !f.resolved)
  if (open.length === 0 || round >= 2) return null

  async function run() {
    setBusy(true)
    setError(null)
    try {
      await recheck(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  return (
    <section className="follow-up" aria-labelledby="follow-up-heading">
      <h2 id="follow-up-heading">Questions for the owner</h2>
      <p>
        The analysis has {open.length} question{open.length > 1 ? 's' : ''} that the owner may be
        able to answer. Read {open.length > 1 ? 'them' : 'it'} to the owner in Bahasa Indonesia,
        type each answer under its finding below, then check the file again. Only the verifier and
        the memo writer run; the evidence is not read again.
      </p>
      <p className="fine">
        An answer can explain a gap or a misfiled line. It cannot stand in for missing evidence
        behind a figure. The owner can be asked {round === 0 ? 'twice' : 'once more'}.
      </p>
      {error && <p className="error">{error}</p>}
      <button className="button" disabled={busy} onClick={run}>
        {busy ? 'Checking…' : 'Re-check with the owner’s answers'}
      </button>
    </section>
  )
}

const AUDIT_LABEL: Record<string, string> = {
  created: 'Application opened',
  created_by_owner: 'File started by the business owner',
  consent_given: 'Consent recorded',
  consent_withdrawn: 'Consent withdrawn',
  evidence_added: 'Evidence added',
  analysis_completed: 'Analysis completed',
  reverified_with_answers: 'Re-checked with the owner’s answers',
  follow_up_answered: 'Answer to a question recorded',
  reading_confirmed: 'A reading confirmed on the photo',
  decision_approve: 'Decision signed off: approve',
  decision_decline: 'Decision signed off: decline',
  decision_request_more: 'Decision: ask for more evidence',
  recommended_approve: 'Recommended: approve',
  recommended_decline: 'Recommended: decline',
  signoff_opened: 'Opened for a second sign-off',
  signoff_returned: 'Sent back to the officer',
  decision_sent_to_owner: 'Decision and letter sent to the owner',
  offer_accepted: 'Offer accepted',
  offer_declined: 'Offer declined',
  condition_met: 'Condition marked as met',
  requested_records_sent: 'Records asked for were sent',
  follow_up_declined: 'The owner preferred not to answer a question',
  share_link_created: 'Share link created',
  opened_by_lender: 'Opened from the owner’s share link',
  share_withdrawn: 'Share withdrawn',
  demo_story_started: 'Demo copy made from a finished sample file',
}

const auditTime = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

type AuditRow = { entry: AuditEntry; label: string; detail: string | null }

// Consecutive uploads by the same person read as one line: "14 pieces of evidence added".
function auditRows(entries: AuditEntry[]): AuditRow[] {
  const rows: AuditRow[] = []
  let i = 0
  while (i < entries.length) {
    const entry = entries[i]
    if (entry.action === 'evidence_added') {
      let j = i
      const kinds = new Map<string, number>()
      while (
        j < entries.length &&
        entries[j].action === 'evidence_added' &&
        entries[j].actor === entry.actor
      ) {
        const type = entries[j].details?.type as EvidenceType | undefined
        const name = (type && EVIDENCE_LABEL[type]) ?? 'Other'
        kinds.set(name, (kinds.get(name) ?? 0) + 1)
        j++
      }
      const count = j - i
      rows.push({
        entry: entries[j - 1],
        label: count === 1 ? 'Evidence added' : `${count} pieces of evidence added`,
        detail: [...kinds].map(([name, n]) => (n > 1 ? `${name} ×${n}` : name)).join(' · '),
      })
      i = j
      continue
    }
    const details = entry.details ?? {}
    const assessment = details.assessment as Assessment | undefined
    const question = typeof details.question === 'string' ? details.question : null
    const text = typeof details.text === 'string' ? details.text : null
    const count = typeof details.count === 'number' ? details.count : null
    const letter =
      details.letter === 'gemini'
        ? `Letter by ${typeof details.model === 'string' ? details.model : 'Gemini'}`
        : details.letter === 'template'
          ? 'Letter from the fixed template'
          : null
    const detail = entry.reason
      ? `“${entry.reason}”`
      : assessment && ASSESSMENT_LABEL[assessment]
        ? `Outcome: ${ASSESSMENT_LABEL[assessment]}`
        : (question ??
          text ??
          letter ??
          (count !== null ? `${count} new record${count > 1 ? 's' : ''}` : null))
    rows.push({ entry, label: AUDIT_LABEL[entry.action] ?? entry.action, detail })
    i++
  }
  return rows
}

function AuditLog({ app }: { app: Application }) {
  const { data: entries, error } = useAudit(app.id)
  const me = auth.currentUser?.uid
  if (entries.length === 0 && !error) return null

  function who(actor: string): string {
    if (actor === me) return 'you'
    if (app.ownerUid && actor === app.ownerUid) return 'owner'
    if (actor === app.officerUid) return 'the officer'
    if (app.reviewerUid && actor === app.reviewerUid) return 'the second person'
    return 'another officer'
  }

  return (
    <section className="audit" aria-labelledby="audit-heading">
      <h2 id="audit-heading">Audit log</h2>
      <p className="fine">Written by the API on every action; nobody can edit it from the app.</p>
      {error && <p className="error">The audit log could not be loaded.</p>}
      <ol className="audit-log">
        {auditRows(entries).map(({ entry, label, detail }) => {
          const actor = who(entry.actor)
          return (
            <li
              key={entry.id}
              className={`audit-row by-${actor.replace(/^the /, '').replace(' ', '-')}`}
            >
              <time className="audit-time mono" dateTime={entry.at?.toDate().toISOString()}>
                {entry.at ? auditTime.format(entry.at.toDate()) : 'just now'}
              </time>
              <span className="audit-body">
                <span className="audit-label">{label}</span>
                <span className="audit-actor">by {actor}</span>
                {detail && (
                  <span
                    className="audit-detail"
                    lang={entry.action === 'follow_up_answered' ? 'id' : undefined}
                  >
                    {detail}
                  </span>
                )}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

// Where the application stands in the officer's four steps.
function stepOf(app: Application): OfficerStep {
  if (app.status === 'draft' || app.status === 'collecting') return 1
  if (app.status === 'analyzing') return 2
  if (app.status === 'needs_follow_up') return 3
  return 4
}

export default function ApplicationFile() {
  const { id = '' } = useParams()
  const { data: app, loading } = useApplication(id)
  const { data: evidence } = useEvidence(id)
  const { data: run } = useRun(id, app?.currentRunId)
  const { data: stored } = useCreditFileDoc(id, app?.currentRunId)
  const urls = useImageUrls(evidence)
  const [search] = useSearchParams()

  const title = app?.business.alias ?? (loading ? 'Loading…' : 'Application not found')
  const crumbs = <> / {app?.business.alias ?? '…'}</>

  if (!app) {
    return (
      <OfficerShell title={title} crumbs={crumbs}>
        {!loading && <p>This application doesn’t exist, or it belongs to someone else.</p>}
      </OfficerShell>
    )
  }

  // A second person at the lender, signing off the officer's recommendation: they read the file
  // and cannot change it.
  const me = auth.currentUser?.uid
  // On a demo file the same person is the officer and the supervisor; ?as=reviewer says which
  // one is looking (and api.ts tells the API the same).
  const actingReviewer = !!app.demo && search.get('as') === 'reviewer' && app.reviewerUid === me
  const reviewing =
    actingReviewer || (!!app.reviewerUid && app.reviewerUid === me && app.officerUid !== me)
  const demoBar = app.demo ? (
    <DemoBar app={app} playing={reviewing ? 'reviewer' : 'officer'} />
  ) : null
  const asked = app.decision?.action === 'request_more' && app.decision.state === 'final'

  if (app.status === 'draft' || app.status === 'collecting' || !stored) {
    const next =
      app.status === 'draft'
        ? { to: `/app/${id}/consent`, label: 'Record the owner’s consent' }
        : {
            to: `/app/${id}/evidence`,
            label: asked ? 'Add evidence and check again' : 'Collect the evidence',
          }
    return (
      <OfficerShell title={title} crumbs={crumbs} step={stepOf(app)}>
        {demoBar}
        <p className="lead-text">{STATUS_LABEL[app.status]}.</p>
        {app.status === 'analyzing' ? (
          <LiveTrace run={run} />
        ) : (
          !reviewing && (
            <Link className="button" to={next.to}>
              {next.label}
            </Link>
          )
        )}
        {asked && app.status === 'collecting' && <Decision app={app} policy={stored?.policy} />}
      </OfficerShell>
    )
  }

  // Once a decision is recommended or made, the file stays as it was decided on.
  const editable = !reviewing && app.status !== 'decided' && app.status !== 'awaiting_signoff'

  const file: CreditFileData = {
    slug: id,
    fileNumber: `LL-${id.slice(0, 8).toUpperCase()}`,
    application: {
      alias: app.business.alias,
      businessType: app.business.type,
      city: app.business.city,
      yearsOperating: app.business.yearsOperating,
      amount: app.request.amount,
      tenorMonths: app.request.tenorMonths,
    },
    evidence: evidence.map((e) => ({
      id: e.id,
      type: e.type,
      image: urls.get(e.id) ?? '',
      capturedAt: '',
      submittedBy: e.submittedBy,
      reading: (e.extraction as CreditFileData['evidence'][number]['reading']) ?? {
        label: e.label,
      },
    })),
    assessment: stored.assessment,
    policy: stored.policy,
    cashflow: stored.cashflow,
    findings: stored.findings,
    confirmations: stored.confirmations,
    memo: stored.memo,
    facts: stored.facts,
    models: stored.models,
    round: stored.round ?? 0,
  }

  return (
    <OfficerShell
      title={title}
      crumbs={crumbs}
      step={stepOf(app)}
      done={app.status === 'decided'}
      titleHidden
    >
      {demoBar}
      <div className="page-actions">
        <span className="status-label">{STATUS_LABEL[app.status]}</span>
        {reviewing && <span className="fine">You are the second person: read-only.</span>}
        {editable && !app.demo && (
          <Link className="button quiet" to={`/app/${id}/evidence`}>
            Add evidence and run again
          </Link>
        )}
      </div>
      <HandOff id={id} file={file} />
      {app.status === 'analyzing' && <LiveTrace run={run} />}
      {editable && !app.demo && app.status !== 'analyzing' && (
        <FollowUp id={id} findings={file.findings} round={file.round ?? 0} />
      )}
      {editable && app.status !== 'analyzing' && (
        <ConfirmReadings id={id} evidence={evidence} urls={urls} />
      )}
      <CreditFile
        file={file}
        titleLevel={2}
        findingExtra={
          !editable || app.status === 'analyzing' || (file.round ?? 0) >= 2
            ? undefined
            : (finding, index) => <AnswerBox id={id} index={index} finding={finding} />
        }
      />
      {reviewing ? <SignoffPanel app={app} /> : <Decision app={app} policy={stored.policy} />}
      <AuditLog app={app} />
    </OfficerShell>
  )
}
