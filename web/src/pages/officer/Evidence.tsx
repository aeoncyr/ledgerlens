import { useState, type ChangeEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import LiveTrace from '../../components/LiveTrace.tsx'
import {
  addEvidence,
  rememberedSample,
  runAnalysis,
  useApplication,
  useEvidence,
  useRun,
} from '../../officer.ts'
import { SAMPLES } from '../../samples.ts'
import type { CreditFileData, EvidenceType } from '../../types.ts'
import { TIER_LABEL, evidenceStrength, type Tier } from '../../strength.ts'
import OfficerShell from './OfficerShell.tsx'

const KINDS: {
  type: EvidenceType
  title: string
  tier: string
  hint: string
  accept: string
}[] = [
  {
    type: 'qris_history',
    title: 'QRIS or e-wallet history',
    tier: 'Hard evidence',
    hint: 'Screenshots of the merchant app’s history, one per month if possible.',
    accept: 'image/*',
  },
  {
    type: 'receipt',
    title: 'Supplier receipts',
    tier: 'Medium',
    hint: 'Notas from suppliers, for the purchases the notebook records.',
    accept: 'image/*',
  },
  {
    type: 'ledger_page',
    title: 'Notebook pages',
    tier: 'Soft',
    hint: 'One photo per page, flat and in good light. Two months or more is best.',
    accept: 'image/*',
  },
  {
    type: 'interview_audio',
    title: 'Owner interview',
    tier: 'Soft',
    hint: 'One or two minutes in Bahasa Indonesia: sales, purchases, what the loan is for.',
    accept: 'audio/*',
  },
  {
    type: 'shop_photo',
    title: 'Shop and stock',
    tier: 'Physical',
    hint: 'The shop front and shelves, taken on the visit.',
    accept: 'image/*',
  },
]

export default function Evidence() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { data: app } = useApplication(id)
  const { data: evidence } = useEvidence(id)
  const { data: run } = useRun(id, app?.currentRunId)
  const [progress, setProgress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analysing, setAnalysing] = useState(false)
  const [sample, setSample] = useState(rememberedSample(id) ?? SAMPLES[0].slug)

  const counts = new Map<EvidenceType, number>()
  for (const item of evidence) counts.set(item.type, (counts.get(item.type) ?? 0) + 1)
  const strength = evidenceStrength(evidence.map((item) => item.type))

  async function upload(type: EvidenceType, event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    setError(null)
    try {
      for (const [index, file] of files.entries()) {
        setProgress(`Uploading ${index + 1} of ${files.length}…`)
        await addEvidence(id, type, file, file.name)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setProgress(null)
  }

  async function addSample() {
    setError(null)
    try {
      setProgress('Fetching the sample records…')
      const file = (await (await fetch(`/samples/${sample}/file.json`)).json()) as CreditFileData
      for (const [index, item] of file.evidence.entries()) {
        setProgress(`Uploading ${index + 1} of ${file.evidence.length}…`)
        const blob = await (await fetch(item.image)).blob()
        const name = item.image.split('/').pop() ?? item.id
        await addEvidence(id, item.type, blob, name, new Date(item.capturedAt))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setProgress(null)
  }

  async function analyse() {
    setAnalysing(true)
    setError(null)
    try {
      await runAnalysis(id)
      navigate(`/app/${id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setAnalysing(false)
    }
  }

  const alias = app?.business.alias ?? 'Application'
  const crumbs = (
    <>
      {' '}
      / <Link to={`/app/${id}`}>{alias}</Link> / Evidence
    </>
  )

  if (analysing || app?.status === 'analyzing') {
    return (
      <OfficerShell title="Analysing the evidence" crumbs={crumbs} step={2}>
        <LiveTrace run={run} />
        {error && <p className="error">{error}</p>}
      </OfficerShell>
    )
  }

  return (
    <OfficerShell title="Collect the evidence" crumbs={crumbs} step={1}>
      {app && !app.consent?.given && (
        <p className="error">
          Record the owner’s consent first. <Link to={`/app/${id}/consent`}>Go to consent</Link>
        </p>
      )}
      <section className="strength-panel" aria-labelledby="strength-heading">
        <div className="sp-head">
          <h2 id="strength-heading">Evidence strength</h2>
          <span className={`sp-label ${strength.label.toLowerCase()}`}>{strength.label}</span>
          <strong className="sp-score">{strength.score} / 100</strong>
        </div>
        <span
          className="strength-bar sp-bar"
          role="meter"
          aria-label="Evidence strength"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={strength.score}
          aria-valuetext={`${strength.score} out of 100, ${strength.label.toLowerCase()}`}
        >
          <span style={{ width: `${strength.score}%` }} />
        </span>
        <p className="sp-tiers">
          {(Object.keys(TIER_LABEL) as Tier[]).map((tier, index) => (
            <span key={tier} className={strength.tiers[tier] ? 'has' : undefined}>
              {index > 0 && <span aria-hidden="true"> · </span>}
              {TIER_LABEL[tier]}: {strength.tiers[tier]}
            </span>
          ))}
        </p>
        <p className="sp-next">
          {strength.next ? (
            <>
              <span className="sp-next-label">Next best evidence</span> {strength.next.text}
            </>
          ) : (
            'Every kind of evidence is on file.'
          )}
        </p>
      </section>

      <ul className="evidence-kinds">
        {KINDS.map((kind) => {
          const suggested = strength.next?.type === kind.type
          return (
            <li key={kind.type} className={suggested ? 'suggested' : undefined}>
              <div>
                <h2>{kind.title}</h2>
                <span className="tier">{kind.tier}</span>
                {suggested && <span className="tag next-tag">Suggested next</span>}
                <p className="fine">{kind.hint}</p>
              </div>
              <div className="kind-actions">
                <span className="count">{counts.get(kind.type) ?? 0} on file</span>
                <label className="button quiet file-button">
                  Add
                  <input
                    type="file"
                    className="visually-hidden"
                    aria-label={`Add ${kind.title}`}
                    accept={kind.accept}
                    capture={kind.accept === 'image/*' ? 'environment' : undefined}
                    multiple
                    disabled={!!progress}
                    onChange={(e) => upload(kind.type, e)}
                  />
                </label>
              </div>
            </li>
          )
        })}
      </ul>

      <section className="sample-picker" aria-labelledby="sample-evidence">
        <h2 id="sample-evidence">Or add a sample business’s records</h2>
        <p className="fine">
          Two months of photographed notebook pages, receipts, QRIS screenshots and a short
          interview with the owner of a fictional business, uploaded as if you had just taken them.
        </p>
        <div className="page-actions">
          <select
            aria-label="Sample business"
            value={sample}
            onChange={(e) => setSample(e.target.value)}
            disabled={!!progress}
          >
            {SAMPLES.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.alias}
              </option>
            ))}
          </select>
          <button className="button quiet" onClick={addSample} disabled={!!progress}>
            Add these records
          </button>
        </div>
      </section>

      {progress && <p className="progress">{progress}</p>}
      {error && <p className="error">{error}</p>}

      <div className="page-actions run-row">
        <button
          className="button"
          disabled={evidence.length === 0 || !!progress || !app?.consent?.given}
          onClick={analyse}
        >
          Run the analysis on {evidence.length} item{evidence.length === 1 ? '' : 's'}
        </button>
        <span className="fine">Gemini reads the evidence; code does the arithmetic.</span>
      </div>
    </OfficerShell>
  )
}
