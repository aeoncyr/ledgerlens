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
import OfficerShell from './OfficerShell.tsx'

const KINDS: {
  type: EvidenceType
  title: string
  tier: string
  points: number
  hint: string
  accept: string
}[] = [
  {
    type: 'qris_history',
    title: 'QRIS or e-wallet history',
    tier: 'Hard evidence',
    points: 35,
    hint: 'Screenshots of the merchant app’s history, one per month if possible.',
    accept: 'image/*',
  },
  {
    type: 'receipt',
    title: 'Supplier receipts',
    tier: 'Medium',
    points: 20,
    hint: 'Notas from suppliers, for the purchases the notebook records.',
    accept: 'image/*',
  },
  {
    type: 'ledger_page',
    title: 'Notebook pages',
    tier: 'Soft',
    points: 15,
    hint: 'One photo per page, flat and in good light. Two months or more is best.',
    accept: 'image/*',
  },
  {
    type: 'interview_audio',
    title: 'Owner interview',
    tier: 'Soft',
    points: 10,
    hint: 'One or two minutes in Bahasa Indonesia: sales, purchases, what the loan is for.',
    accept: 'audio/*',
  },
  {
    type: 'shop_photo',
    title: 'Shop and stock',
    tier: 'Physical',
    points: 10,
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
  const strength = Math.min(
    100,
    KINDS.filter((k) => counts.has(k.type)).reduce((sum, k) => sum + k.points, 0) +
      ((counts.get('ledger_page') ?? 0) >= 4 ? 10 : 0),
  )

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
      <OfficerShell title="Analysing the evidence" crumbs={crumbs}>
        <LiveTrace run={run} />
        {error && <p className="error">{error}</p>}
      </OfficerShell>
    )
  }

  return (
    <OfficerShell title="Collect the evidence" crumbs={crumbs}>
      {app && !app.consent?.given && (
        <p className="error">
          Record the owner’s consent first. <Link to={`/app/${id}/consent`}>Go to consent</Link>
        </p>
      )}
      <div className="strength-meter">
        <span>Evidence strength</span>
        <span className="strength-bar" aria-hidden="true">
          <span style={{ width: `${strength}%` }} />
        </span>
        <strong>{strength} / 100</strong>
        <span className="fine">
          {counts.has('qris_history')
            ? 'Hard evidence on file.'
            : 'Without QRIS history the file can be at most partly verified.'}
        </span>
      </div>

      <ul className="evidence-kinds">
        {KINDS.map((kind) => (
          <li key={kind.type}>
            <div>
              <h2>{kind.title}</h2>
              <span className="tier">{kind.tier}</span>
              <p className="fine">{kind.hint}</p>
            </div>
            <div className="kind-actions">
              <span className="count">{counts.get(kind.type) ?? 0} on file</span>
              <label className="button quiet">
                Add
                <input
                  type="file"
                  accept={kind.accept}
                  capture={kind.accept === 'image/*' ? 'environment' : undefined}
                  multiple
                  hidden
                  disabled={!!progress}
                  onChange={(e) => upload(kind.type, e)}
                />
              </label>
            </div>
          </li>
        ))}
      </ul>

      <section className="sample-picker" aria-labelledby="sample-evidence">
        <h2 id="sample-evidence">Or add a sample business’s records</h2>
        <p className="fine">
          Two months of photographed notebook pages, receipts, QRIS screenshots and a short
          interview with the owner of a fictional business, uploaded as if you had just taken them.
        </p>
        <div className="page-actions">
          <select value={sample} onChange={(e) => setSample(e.target.value)} disabled={!!progress}>
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
