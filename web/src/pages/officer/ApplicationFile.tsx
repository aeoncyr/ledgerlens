import { getDownloadURL, ref } from 'firebase/storage'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import CreditFile from '../../components/CreditFile.tsx'
import LiveTrace from '../../components/LiveTrace.tsx'
import { storage } from '../../firebase.ts'
import {
  STATUS_LABEL,
  answerQuestion,
  recheck,
  recordDecision,
  useApplication,
  useCreditFileDoc,
  useEvidence,
  useRun,
  type Application,
  type StoredEvidence,
} from '../../officer.ts'
import type { CreditFileData, Finding } from '../../types.ts'
import OfficerShell from './OfficerShell.tsx'

function useImageUrls(evidence: StoredEvidence[]): Map<string, string> {
  const [urls, setUrls] = useState(new Map<string, string>())
  const key = evidence.map((e) => e.id).join(',')
  useEffect(() => {
    let cancelled = false
    Promise.all(
      evidence.map(async (e) => [e.id, await getDownloadURL(ref(storage, e.storagePath))] as const),
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
  const [text, setText] = useState(finding.answer ?? '')
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  if (!finding.followUpQuestion || finding.resolved) return null

  async function save(event: FormEvent) {
    event.preventDefault()
    setState('saving')
    try {
      await answerQuestion(id, index, text)
      setState('saved')
    } catch {
      setState('error')
    }
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
      <button className="button quiet" disabled={!text.trim() || state === 'saving'}>
        {state === 'saving' ? 'Saving…' : 'Save answer'}
      </button>
      {state === 'saved' && <span className="fine">Saved.</span>}
      {state === 'error' && <span className="error">Could not save; try again.</span>}
    </form>
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

const ACTIONS = [
  ['approve', 'Approve'],
  ['request_more', 'Ask for more evidence'],
  ['decline', 'Decline'],
] as const

function Decision({ app }: { app: Application }) {
  const [action, setAction] = useState<string>('approve')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (app.decision) {
    const label = ACTIONS.find(([key]) => key === app.decision?.action)?.[1] ?? app.decision.action
    return (
      <section className="decision done" aria-labelledby="decision-heading">
        <h2 id="decision-heading">Decision</h2>
        <p>
          <strong>{label}.</strong> {app.decision.reason}
        </p>
        <p className="fine">Recorded in the audit log with the officer and the time.</p>
      </section>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await recordDecision(app.id, action, reason)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  return (
    <form className="decision" onSubmit={submit} aria-labelledby="decision-heading">
      <h2 id="decision-heading">Your decision</h2>
      <p className="fine">
        LedgerLens recommends; you decide. Every decision needs a written reason, which goes into
        the audit log.
      </p>
      <div className="choice-row">
        {ACTIONS.map(([key, label]) => (
          <label key={key} className={`choice ${action === key ? 'chosen' : ''}`}>
            <input
              type="radio"
              name="action"
              value={key}
              checked={action === key}
              onChange={() => setAction(key)}
            />
            {label}
          </label>
        ))}
      </div>
      <label>
        Reason
        <textarea
          required
          minLength={5}
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button className="button" disabled={busy || reason.trim().length < 5}>
        Record the decision
      </button>
    </form>
  )
}

export default function ApplicationFile() {
  const { id = '' } = useParams()
  const { data: app, loading } = useApplication(id)
  const { data: evidence } = useEvidence(id)
  const { data: run } = useRun(id, app?.currentRunId)
  const { data: stored } = useCreditFileDoc(id, app?.currentRunId)
  const urls = useImageUrls(evidence)

  const title = app?.business.alias ?? (loading ? 'Loading…' : 'Application not found')
  const crumbs = <> / {app?.business.alias ?? '…'}</>

  if (!app) {
    return (
      <OfficerShell title={title} crumbs={crumbs}>
        {!loading && <p>This application doesn’t exist, or it belongs to someone else.</p>}
      </OfficerShell>
    )
  }

  if (app.status === 'draft' || app.status === 'collecting' || !stored) {
    const next =
      app.status === 'draft'
        ? { to: `/app/${id}/consent`, label: 'Record the owner’s consent' }
        : { to: `/app/${id}/evidence`, label: 'Collect the evidence' }
    return (
      <OfficerShell title={title} crumbs={crumbs}>
        <p className="lead-text">{STATUS_LABEL[app.status]}.</p>
        {app.status === 'analyzing' ? (
          <LiveTrace run={run} />
        ) : (
          <Link className="button" to={next.to}>
            {next.label}
          </Link>
        )}
      </OfficerShell>
    )
  }

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
    <OfficerShell title={title} crumbs={crumbs}>
      <div className="page-actions">
        <span className="status-label">{STATUS_LABEL[app.status]}</span>
        {app.status !== 'decided' && (
          <Link className="button quiet" to={`/app/${id}/evidence`}>
            Add evidence and run again
          </Link>
        )}
      </div>
      {app.status === 'analyzing' && <LiveTrace run={run} />}
      {app.status !== 'analyzing' && app.status !== 'decided' && (
        <FollowUp id={id} findings={file.findings} round={file.round ?? 0} />
      )}
      <CreditFile
        file={file}
        findingExtra={
          app.status === 'decided' || app.status === 'analyzing' || (file.round ?? 0) >= 2
            ? undefined
            : (finding, index) => <AnswerBox id={id} index={index} finding={finding} />
        }
      />
      <Decision app={app} />
    </OfficerShell>
  )
}
