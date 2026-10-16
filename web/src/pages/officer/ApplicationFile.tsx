import { getDownloadURL, ref } from 'firebase/storage'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import CreditFile from '../../components/CreditFile.tsx'
import LiveTrace from '../../components/LiveTrace.tsx'
import { storage } from '../../firebase.ts'
import {
  STATUS_LABEL,
  recordDecision,
  useApplication,
  useCreditFileDoc,
  useEvidence,
  useRun,
  type Application,
  type StoredEvidence,
} from '../../officer.ts'
import type { CreditFileData } from '../../types.ts'
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
      <CreditFile file={file} />
      <Decision app={app} />
    </OfficerShell>
  )
}
