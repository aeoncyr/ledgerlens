import { useState, type ChangeEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { rupiah, useLang, type OwnerStrings } from '../../i18n/owner.ts'
import {
  addEvidence,
  answerQuestion,
  errorText,
  isQuotaError,
  recheck,
  recordConsent,
  rememberedSample,
  runCheck,
  sharePath,
  shareFile,
  useApplication,
  useEvidence,
  useOwnerSummary,
  useRun,
  withdrawShare,
  type OwnerApplication,
  type OwnerEvidence,
  type OwnerSummary,
  type Run,
} from '../../owner.ts'
import { SAMPLES } from '../../samples.ts'
import { evidenceStrength } from '../../strength.ts'
import type { CreditFileData, EvidenceType } from '../../types.ts'
import {
  ChatIcon,
  CopyIcon,
  KindIcon,
  LockIcon,
  PersonIcon,
  PinIcon,
  TickIcon,
  UndoIcon,
} from './icons.tsx'
import DecisionCard, { WaitingCard } from './OwnerDecision.tsx'
import DemoBar from '../../components/DemoBar.tsx'
import DeleteFile from './DeleteFile.tsx'
import FileActivity from './FileActivity.tsx'
import OwnerShell from './OwnerShell.tsx'
import RemindMe from './RemindMe.tsx'
import VoiceRecorder from '../../components/VoiceRecorder.tsx'
import { answerByVoice, declineQuestion } from '../../officer.ts'
import { useOwnerDecision } from '../../decision.ts'

const MAX_BYTES = 15 * 1024 * 1024

type Kind = {
  type: EvidenceType
  accept: string
  // How the main tap opens: the rear camera, the microphone, or the gallery (for screenshots).
  capture?: 'environment' | 'user'
  // Whether to offer a second way in, from the gallery or the files.
  alternative: 'gallery' | 'files' | null
}

const KINDS: Kind[] = [
  { type: 'ledger_page', accept: 'image/*', capture: 'environment', alternative: 'gallery' },
  { type: 'receipt', accept: 'image/*', capture: 'environment', alternative: 'gallery' },
  { type: 'qris_history', accept: 'image/*', alternative: null },
  { type: 'interview_audio', accept: 'audio/*', capture: 'user', alternative: 'files' },
  { type: 'shop_photo', accept: 'image/*', capture: 'environment', alternative: 'gallery' },
]

type Busy = null | 'consent' | 'upload' | 'check' | 'recheck'

// /owner/:id: one page that walks the owner from consent to a shared file, following the state of
// the application.
export default function OwnerFile() {
  const { id = '' } = useParams()
  const { t, lang } = useLang()
  const navigate = useNavigate()
  const { data: rawApp, loading, error: loadError } = useApplication(id)
  const app = rawApp as OwnerApplication | null
  const { data: evidence } = useEvidence(id)
  const { data: summary } = useOwnerSummary(id)
  const { data: run } = useRun(id, app?.currentRunId)
  const decision = useOwnerDecision(id)
  const [busy, setBusy] = useState<Busy>(null)
  const [progress, setProgress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (loading) {
    return (
      <OwnerShell>
        <p className="ow-fine ow-loading">{t.loading}</p>
      </OwnerShell>
    )
  }

  if (!app) {
    return (
      <OwnerShell>
        <div className="ow-card ow-notfound">
          <h1 className="ow-title">{t.fileNotFound}</h1>
          <p>{t.fileNotFoundText}</p>
          {loadError && <p className="ow-fine">{loadError}</p>}
          <Link to="/owner" className="ow-button">
            {t.backHome}
          </Link>
        </div>
      </OwnerShell>
    )
  }

  const consented = !!app.consent?.given
  const checking =
    busy === 'check' || busy === 'recheck' || (app.status === 'analyzing' && run?.state !== 'failed')
  // While the lender decides, or with a loan on offer, the file stays as decided on: no new
  // records, no re-check, no more answers to the old questions.
  const locked =
    app.status === 'awaiting_signoff' || (app.status === 'decided' && decision?.action === 'approve')
  const stage = !consented ? 0 : checking ? 2 : summary ? (app.officerUid ? 4 : 3) : 1
  const tips = summary ? tipsIn(summary, lang) : []
  const declined = app.status === 'decided' && decision?.action === 'decline'
  // A file that isn't verified yet gets a reminder to check again; a declined one gets it with the
  // decision instead, so it appears once.
  const remind = !!summary && app.assessment !== 'verified' && !declined
  const deleteBlocked =
    app.status === 'awaiting_signoff'
      ? t.deleteBlockedDeciding
      : decision?.state === 'accepted'
        ? t.deleteBlockedAccepted
        : checking
          ? t.deleteBlockedChecking
          : null

  async function act(kind: Busy, work: () => Promise<void>) {
    setBusy(kind)
    setError(null)
    try {
      await work()
    } catch (e) {
      setError(errorText(e))
    }
    setBusy(null)
    setProgress(null)
  }

  async function sendFiles(type: EvidenceType, files: File[]) {
    for (const file of files) {
      if (file.size > MAX_BYTES) throw new Error(t.tooBig(file.name))
      if (file.type && !/^(image|audio)\//.test(file.type)) throw new Error(t.wrongType(file.name))
    }
    for (const [index, file] of files.entries()) {
      setProgress(t.uploading(index + 1, files.length))
      await addEvidence(id, type, file, file.name || `${type}.jpg`)
    }
  }

  function onPick(type: EvidenceType, event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length) void act('upload', () => sendFiles(type, files))
  }

  async function sendSample(slug: string) {
    setProgress(t.fetchingSample)
    const response = await fetch(`/samples/${slug}/file.json`)
    if (!response.ok) throw new Error(response.statusText)
    const file = (await response.json()) as CreditFileData
    for (const [index, item] of file.evidence.entries()) {
      setProgress(t.uploading(index + 1, file.evidence.length))
      const blob = await (await fetch(item.image)).blob()
      const name = item.image.split('/').pop() ?? item.id
      await addEvidence(id, item.type, blob, name, new Date(item.capturedAt))
    }
  }

  return (
    <OwnerShell wide>
      <p className="ow-back">
        <Link to="/owner">← {t.backHome}</Link>
      </p>
      {app.demo && <DemoBar app={app} playing="owner" />}
      <FileHeader app={app} t={t} />
      <Stepper stage={stage} t={t} />

      {app.officerUid && (
        <div className="ow-banner" role="status">
          <TickIcon size={22} />
          <div>
            <strong>{app.lenderName ? `${t.sharedBanner}: ${app.lenderName}` : t.sharedBanner}</strong>
            <p>{t.sharedBannerText}</p>
          </div>
        </div>
      )}

      {error && (
        <p className="ow-error" role="alert">
          {error}
        </p>
      )}

      {app.status === 'awaiting_signoff' ? (
        <WaitingCard t={t} />
      ) : (
        decision && (
          <DecisionCard
            id={id}
            decision={decision}
            evidence={evidence as OwnerEvidence[]}
            tips={tips}
            lang={lang}
            t={t}
          />
        )
      )}

      {!consented ? (
        <div className="ow-narrow">
          <ConsentCard
            t={t}
            busy={busy === 'consent'}
            onAgree={() => act('consent', () => recordConsent(id, true))}
            onLater={() => navigate('/owner')}
          />
        </div>
      ) : checking ? (
        <div className="ow-narrow">
          <Checking run={run} t={t} />
        </div>
      ) : (
        <div className="ow-board">
          {run?.state === 'failed' && (
            <p className="ow-error" role="alert">
              {isQuotaError(run.error) ? t.checkQuota : t.checkFailed}
            </p>
          )}
          {summary && (
            <>
              <SummaryCard
                id={id}
                summary={summary}
                remind={remind}
                lang={lang}
                t={t}
              />
              {!locked && (
                <Questions
                    key={summary.updatedAt?.seconds ?? 0}
                  id={id}
                  summary={summary}
                  lang={lang}
                  t={t}
                  busy={busy !== null}
                  onRecheck={(answers) =>
                    act('recheck', async () => {
                      setProgress(t.savingAnswers)
                      for (const [index, text] of answers) await answerQuestion(id, index, text)
                      setProgress(null)
                      await recheck(id)
                    })
                  }
                />
              )}
              <ShareCard app={app} t={t} />
            </>
          )}
          <Records
            id={id}
            t={t}
            evidence={evidence as OwnerEvidence[]}
            summary={summary}
            busy={busy}
            progress={progress}
            locked={locked}
            demo={!!app.demo}
            onPick={onPick}
            onSample={(slug) => act('upload', () => sendSample(slug))}
            onCheck={() => act('check', () => runCheck(id))}
          />
          {!summary && (
            <section className="ow-card ow-share-teaser" aria-labelledby="ow-share-later">
              <h2 id="ow-share-later" className="ow-h3">
                {t.shareTitle}
              </h2>
              <p className="ow-fine">{t.shareNeedsCheck}</p>
            </section>
          )}
        </div>
      )}

      <FileActivity
        id={id}
        version={[app.status, app.officerUid, app.shareCode, app.consent?.given, decision?.state]
          .map(String)
          .join('|')}
        lang={lang}
        t={t}
      />
      <DeleteFile id={id} blocked={deleteBlocked} t={t} />
    </OwnerShell>
  )
}

/** The summary's tips in the owner's language, falling back to the Bahasa ones. */
function tipsIn(summary: OwnerSummary, lang: 'en' | 'id'): string[] {
  return (lang === 'en' && summary.tipsEn?.length ? summary.tipsEn : summary.tips) ?? []
}

function FileHeader({ app, t }: { app: OwnerApplication; t: OwnerStrings }) {
  return (
    <header className="ow-file-head">
      <div>
        <h1 className="ow-title">{app.business.alias}</h1>
        <p className="ow-fine">
          {app.business.type} · {app.business.city}
        </p>
        <p className="ow-request">{t.requestLine(rupiah(app.request.amount), app.request.tenorMonths)}</p>
      </div>
      <span className={`ow-pill ow-pill-${app.status}`}>{t.status[app.status] ?? app.status}</span>
    </header>
  )
}

function Stepper({ stage, t }: { stage: number; t: OwnerStrings }) {
  const labels = [t.stageAgree, t.stageSend, t.stageCheck, t.stageShare]
  return (
    <ol className="ow-stepper" aria-label={t.progressLabel}>
      {labels.map((label, index) => {
        const state = index < stage ? 'done' : index === stage ? 'now' : 'next'
        return (
          <li key={label} className={`ow-stepper-${state}`} aria-current={state === 'now' ? 'step' : undefined}>
            <span className="ow-stepper-dot" aria-hidden="true">
              {state === 'done' ? <TickIcon size={14} /> : index + 1}
            </span>
            <span className="ow-stepper-label">{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

function ConsentCard({
  t,
  busy,
  onAgree,
  onLater,
}: {
  t: OwnerStrings
  busy: boolean
  onAgree: () => void
  onLater: () => void
}) {
  const points = [
    { icon: <LockIcon size={22} />, text: t.consentWho },
    { icon: <PinIcon size={22} />, text: t.consentWhere },
    { icon: <PersonIcon size={22} />, text: t.consentDecide },
    { icon: <UndoIcon size={22} />, text: t.consentWithdraw },
  ]
  return (
    <section className="ow-card ow-consent" aria-labelledby="ow-consent-title">
      <h2 id="ow-consent-title" className="ow-h2">
        {t.consentTitle}
      </h2>
      <ul>
        {points.map((point, index) => (
          <li key={index}>
            <span className="ow-consent-icon">{point.icon}</span>
            <p>{point.text}</p>
          </li>
        ))}
      </ul>
      <p className="ow-fine ow-consent-more">
        <Link to="/trust" target="_blank" rel="noopener">
          {t.consentMore}
        </Link>
      </p>
      <button className="ow-button ow-button-wide" onClick={onAgree} disabled={busy}>
        {busy ? t.consentSaving : t.consentButton}
      </button>
      <button className="ow-link-button" onClick={onLater} disabled={busy}>
        {t.consentNotNow}
      </button>
    </section>
  )
}

function fileName(item: OwnerEvidence): string {
  if (item.label) return item.label
  const last = item.storagePath.split('/').pop() ?? ''
  return last.replace(/^\d+-/, '')
}

function Records({
  id,
  t,
  evidence,
  summary,
  busy,
  progress,
  locked,
  demo,
  onPick,
  onSample,
  onCheck,
}: {
  id: string
  t: OwnerStrings
  evidence: OwnerEvidence[]
  summary: OwnerSummary | null
  busy: Busy
  progress: string | null
  locked: boolean
  // A demo copy is never checked again, so sample records would do nothing.
  demo: boolean
  onPick: (type: EvidenceType, event: ChangeEvent<HTMLInputElement>) => void
  onSample: (slug: string) => void
  onCheck: () => void
}) {
  const remembered = rememberedSample(id)
  const [sample, setSample] = useState(remembered ?? SAMPLES[0].slug)
  const counts = new Map<EvidenceType, number>()
  for (const item of evidence) counts.set(item.type, (counts.get(item.type) ?? 0) + 1)
  const disabled = busy !== null
  const newSinceCheck = summary ? evidence.length > summary.evidenceCount : true
  const next = evidenceStrength(evidence.map((item) => item.type)).next

  const samplePicker = (
    <section className="ow-sample-box" aria-labelledby="ow-sample-records">
      <h3 id="ow-sample-records" className="ow-h3">
        {t.sampleTitle}
      </h3>
      <p className="ow-fine">{t.sampleText}</p>
      <div className="ow-sample-row">
        <label className="visually-hidden" htmlFor="ow-sample-select">
          {t.trySample}
        </label>
        <select
          id="ow-sample-select"
          value={sample}
          onChange={(e) => setSample(e.target.value)}
          disabled={disabled}
        >
          {SAMPLES.map((s) => (
            <option key={s.slug} value={s.slug}>
              {s.alias}
            </option>
          ))}
        </select>
        <button className="ow-button ow-button-quiet" onClick={() => onSample(sample)} disabled={disabled}>
          {t.sampleButton}
        </button>
      </div>
    </section>
  )

  return (
    <section className="ow-section" aria-labelledby="ow-records">
      <h2 id="ow-records" className="ow-h2">
        {summary ? t.moreTitle : t.sendTitle}
      </h2>
      <p className="ow-lead">{summary ? t.moreLead : t.sendLead}</p>
      {next && evidence.length > 0 && (
        <p className="ow-next">
          <span className="ow-next-label">{t.nextBestLabel}</span> {t.nextBest[next.key]}
        </p>
      )}

      {remembered && evidence.length === 0 && samplePicker}

      <ul className="ow-tiles">
        {KINDS.map((kind) => {
          const words = t.kinds[kind.type]
          const count = counts.get(kind.type) ?? 0
          return (
            <li key={kind.type} className={`ow-tile ow-tile-${kind.type} ${count ? 'has' : ''}`}>
              <label className="ow-tile-main">
                <span className="ow-tile-icon">
                  <KindIcon type={kind.type} size={30} />
                </span>
                <span className="ow-tile-title">{words.title}</span>
                <span className="ow-tile-hint">{words.hint}</span>
                <span className="ow-tile-foot">
                  <span className="ow-tile-action">{words.action}</span>
                  <span className="ow-tile-count">
                    {count > 0 && <TickIcon size={14} />}
                    {t.countSent(count)}
                  </span>
                </span>
                <input
                  type="file"
                  className="visually-hidden"
                  accept={kind.accept}
                  capture={kind.capture}
                  multiple={kind.type !== 'interview_audio'}
                  disabled={disabled}
                  onChange={(e) => onPick(kind.type, e)}
                />
              </label>
              {kind.alternative && (
                <label className="ow-tile-alt">
                  {kind.alternative === 'gallery' ? t.fromGallery : t.fromFiles}
                  <input
                    type="file"
                    className="visually-hidden"
                    accept={kind.accept}
                    multiple
                    disabled={disabled}
                    onChange={(e) => onPick(kind.type, e)}
                  />
                </label>
              )}
            </li>
          )
        })}
      </ul>

      {progress && (
        <p className="ow-progress" role="status">
          <span className="ow-spinner" aria-hidden="true" />
          {progress}
        </p>
      )}

      <p className="ow-note">{t.visitNote}</p>

      <h3 className="ow-h3">{t.sentTitle}</h3>
      {evidence.length === 0 ? (
        <p className="ow-empty">{t.sentNone}</p>
      ) : (
        <ul className="ow-sent">
          {KINDS.filter((kind) => counts.has(kind.type)).map((kind) => {
            const items = evidence.filter((item) => item.type === kind.type)
            const byOfficer = items.filter((item) => item.submittedBy === 'officer').length
            return (
              <li key={kind.type}>
                <KindIcon type={kind.type} size={20} />
                <details className="ow-sent-group">
                  <summary>
                    <strong>{t.kinds[kind.type].title}</strong>
                    <span className="ow-sent-count">{items.length}</span>
                  </summary>
                  <ul>
                    {items.map((item) => (
                      <li key={item.id}>
                        {fileName(item)}
                        {item.submittedBy === 'officer' && (
                          <span className="ow-sent-by"> · {t.sentByOfficer}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
                {byOfficer > 0 && (
                  <span className="ow-sent-by">
                    {byOfficer} {t.sentByOfficer}
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {!locked && !demo && !(remembered && evidence.length === 0) && samplePicker}

      <div className="ow-sticky">
        {locked && <p className="ow-fine">{t.checkLocked}</p>}
        {!locked && (!summary || newSinceCheck) && (
          <button
            className="ow-button ow-button-wide"
            onClick={onCheck}
            disabled={disabled || evidence.length === 0}
          >
            {summary ? t.checkAgainAll : t.checkButton(evidence.length)}
          </button>
        )}
        {evidence.length === 0 && <p className="ow-fine ow-center">{t.checkNeedsRecords}</p>}
      </div>
    </section>
  )
}

// One line per stage of the check, in plain words; the officer's trace shows the details.
type StageState = 'done' | 'running' | 'failed' | 'next'

function stageStates(run: Run | null): { agent: string; state: StageState }[] {
  const order: string[] = []
  const tally = new Map<string, { started: number; finished: number; failed: boolean }>()
  for (const step of run?.steps ?? []) {
    if (!tally.has(step.agent)) {
      order.push(step.agent)
      tally.set(step.agent, { started: 0, finished: 0, failed: false })
    }
    const entry = tally.get(step.agent)!
    if (step.state === 'running') entry.started += 1
    else entry.finished += 1
    if (step.state === 'failed') entry.failed = true
  }
  const later = ['calculator', 'verifier', 'memo_writer'].filter((agent) => !tally.has(agent))
  const pending =
    run?.state === 'running' ? later.map((agent) => ({ agent, state: 'next' as const })) : []
  const stages = order.map((agent): { agent: string; state: StageState } => {
    const entry = tally.get(agent)!
    const state: StageState = entry.failed
      ? 'failed'
      : run?.state === 'done' || (entry.finished > 0 && entry.finished >= entry.started)
        ? 'done'
        : 'running'
    return { agent, state }
  })
  return [...stages, ...pending]
}

function Checking({ run, t }: { run: Run | null; t: OwnerStrings }) {
  const stages = stageStates(run)
  return (
    <section className="ow-card ow-checking" aria-labelledby="ow-checking-title">
      <h2 id="ow-checking-title" className="ow-h2">
        {t.checkingTitle}
      </h2>
      <p className="ow-lead">{t.checkingLead}</p>
      <div className="ow-bar" aria-hidden="true">
        <span />
      </div>
      <ol className="ow-stages" aria-live="polite">
        {stages.length === 0 && (
          <li className="ow-stage-running">
            <span className="ow-stage-mark" aria-hidden="true" />
            <span>{t.checkingStarting}</span>
          </li>
        )}
        {stages.map(({ agent, state }) => (
          <li key={agent} className={`ow-stage-${state}`}>
            <span className="ow-stage-mark" aria-hidden="true">
              {state === 'done' && <TickIcon size={14} />}
            </span>
            <span>{t.agents[agent] ?? agent}</span>
            <span className="visually-hidden">
              {state === 'done'
                ? t.stepDone
                : state === 'failed'
                  ? t.stepFailed
                  : state === 'next'
                    ? t.stepNext
                    : t.stepWorking}
            </span>
          </li>
        ))}
      </ol>
      {run?.state === 'failed' && (
        <p className="ow-error" role="alert">
          {isQuotaError(run.error) ? t.checkQuota : t.checkFailed}
        </p>
      )}
    </section>
  )
}

function SummaryCard({
  id,
  summary,
  remind,
  lang,
  t,
}: {
  id: string
  summary: OwnerSummary
  // Offer a calendar reminder to check again, for a file that isn't strong enough yet.
  remind: boolean
  lang: 'en' | 'id'
  t: OwnerStrings
}) {
  const en = lang === 'en'
  const verified = (en && summary.verifiedEn) || summary.verified
  const missing = (en && summary.missingEn) || summary.missing
  const tips = tipsIn(summary, lang)
  return (
    <section className="ow-card ow-summary" aria-labelledby="ow-summary-title">
      <h2 id="ow-summary-title" className="ow-h2">
        {t.summaryTitle}
      </h2>
      <p className="ow-fine">{t.summaryLead}</p>
      <div className="ow-summary-block ow-confirmed">
        <h3 className="ow-h3">
          <TickIcon size={18} />
          {t.confirmedTitle}
        </h3>
        <p>{verified}</p>
      </div>
      {missing && (
        <div className="ow-summary-block ow-missing">
          <h3 className="ow-h3">{t.missingTitle}</h3>
          <p>{missing}</p>
        </div>
      )}
      {tips.length > 0 && (
        <div className="ow-summary-block ow-tips">
          <h3 className="ow-h3">{t.tipsTitle}</h3>
          <ol>
            {tips.map((tip, index) => (
              <li key={index}>{tip}</li>
            ))}
          </ol>
          {remind && <RemindMe id={id} tips={tips} lead={t.remindLead} t={t} />}
        </div>
      )}
    </section>
  )
}

function Questions({
  id,
  summary,
  lang,
  t,
  busy,
  onRecheck,
}: {
  id: string
  summary: OwnerSummary
  lang: 'en' | 'id'
  t: OwnerStrings
  busy: boolean
  onRecheck: (answers: [number, string][]) => void
}) {
  const questions = summary.questions ?? []
  const [drafts, setDrafts] = useState<Record<number, string>>(() =>
    Object.fromEntries(questions.map((q) => [q.index, q.answer ?? ''])),
  )
  const [hint, setHint] = useState(false)
  const [voice, setVoice] = useState<Record<number, 'sending' | 'sent' | string>>({})
  if (questions.length === 0) return null

  async function sendVoice(index: number, audio: Blob) {
    setVoice((v) => ({ ...v, [index]: 'sending' }))
    try {
      await answerByVoice(id, index, audio)
      setVoice((v) => ({ ...v, [index]: 'sent' }))
    } catch (e) {
      setVoice((v) => ({ ...v, [index]: e instanceof Error ? e.message : String(e) }))
    }
  }

  async function decline(index: number) {
    try {
      await declineQuestion(id, index)
    } catch (e) {
      setVoice((v) => ({ ...v, [index]: e instanceof Error ? e.message : String(e) }))
    }
  }

  const changed = questions
    .map((q): [number, string] => [q.index, (drafts[q.index] ?? '').trim()])
    .filter(([index, text]) => text && text !== (questions.find((q) => q.index === index)?.answer ?? ''))
  const anyAnswer = questions.some((q) => (drafts[q.index] ?? '').trim() || q.answer)

  function submit() {
    if (!anyAnswer) {
      setHint(true)
      return
    }
    onRecheck(changed)
  }

  return (
    <section className="ow-card ow-questions" aria-labelledby="ow-questions-title">
      <h2 id="ow-questions-title" className="ow-h2">
        {t.questionsTitle}
      </h2>
      <p className="ow-fine">{t.questionsLead}</p>
      <ol>
        {questions.map((q, n) => {
          const shown = lang === 'en' ? (q.questionEn ?? q.question) : q.question
          const fieldId = `ow-answer-${q.index}`
          return (
            <li key={q.index}>
              <p className="ow-question" id={`${fieldId}-q`}>
                {shown}
              </p>
              {lang === 'en' && q.questionEn && (
                <p className="ow-question-original" lang="id">
                  <span>{t.questionOriginal}</span> {q.question}
                </p>
              )}
              <label className="visually-hidden" htmlFor={fieldId}>
                {t.answerLabel(n + 1)}
              </label>
              <textarea
                id={fieldId}
                rows={3}
                maxLength={1000}
                aria-describedby={`${fieldId}-q`}
                placeholder={t.answerPlaceholder}
                value={drafts[q.index] ?? ''}
                disabled={busy}
                onChange={(e) => {
                  setHint(false)
                  setDrafts((d) => ({ ...d, [q.index]: e.target.value }))
                }}
              />
              <div className="ow-answer-more">
                <VoiceRecorder
                  label={t.recordAnswer}
                  busy={busy || voice[q.index] === 'sending'}
                  onRecorded={(audio) => void sendVoice(q.index, audio)}
                />
                <button
                  type="button"
                  className="link-button"
                  disabled={busy}
                  onClick={() => void decline(q.index)}
                >
                  {t.declineAnswer}
                </button>
              </div>
              {voice[q.index] === 'sending' && <p className="ow-fine">{t.sendingVoice}</p>}
              {voice[q.index] === 'sent' && <p className="ow-fine">{t.voiceSent}</p>}
              {voice[q.index] && !['sending', 'sent'].includes(voice[q.index]) && (
                <p className="ow-error">{voice[q.index]}</p>
              )}
              {q.declined ? (
                <p className="ow-fine">{t.declinedNote}</p>
              ) : (
                q.answer && (
                  <p className="ow-answered">
                    {t.answered}: <span lang="id">{q.answer}</span> <TickIcon size={14} />
                  </p>
                )
              )}
            </li>
          )
        })}
      </ol>
      {hint && (
        <p className="ow-error" role="alert">
          {t.recheckNeedsAnswer}
        </p>
      )}
      <button className="ow-button ow-button-wide" onClick={submit} disabled={busy}>
        {t.recheckButton}
      </button>
    </section>
  )
}

function ShareCard({ app, t }: { app: OwnerApplication; t: OwnerStrings }) {
  const [created, setCreated] = useState<{ shareCode: string; path: string } | null>(null)
  const [busy, setBusy] = useState<null | 'share' | 'stop'>(null)
  const [confirming, setConfirming] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // The live document is the truth; the POST result fills the gap until it arrives.
  const code = app.shareCode ?? created?.shareCode ?? null
  const path = code ? (created?.shareCode === code ? created.path : sharePath(code)) : null
  const url = path ? `${window.location.origin}${path}` : ''

  async function create() {
    setBusy('share')
    setError(null)
    try {
      setCreated(await shareFile(app.id))
    } catch (e) {
      setError(errorText(e))
    }
    setBusy(null)
  }

  async function stop() {
    setBusy('stop')
    setError(null)
    try {
      await withdrawShare(app.id)
      setCreated(null)
      setConfirming(false)
    } catch (e) {
      setError(errorText(e))
    }
    setBusy(null)
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      const field = document.getElementById('ow-share-url') as HTMLInputElement | null
      field?.select()
      document.execCommand?.('copy')
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section className="ow-share" aria-labelledby="ow-share-title">
      <h2 id="ow-share-title" className="ow-h2">
        {t.shareTitle}
      </h2>
      <p>{t.shareLead}</p>
      <div className="ow-share-scope">
        <div>
          <h3>{t.shareSeesTitle}</h3>
          <ul className="ow-scope-yes">
            {t.shareSees.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3>{t.shareNotTitle}</h3>
          <ul className="ow-scope-no">
            {t.shareNot.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <p>{t.shareOneLender}</p>
      </div>
      {!code ? (
        <button className="ow-button ow-button-wide ow-button-light" onClick={create} disabled={!!busy}>
          {busy === 'share' ? t.sharing : t.shareButton}
        </button>
      ) : (
        <>
          <label className="ow-share-url" htmlFor="ow-share-url">
            <span>{t.shareLinkLabel}</span>
            <input id="ow-share-url" readOnly value={url} onFocus={(e) => e.target.select()} />
          </label>
          <div className="ow-share-actions">
            <button className="ow-button ow-button-light" onClick={copy}>
              {copied ? <TickIcon size={18} /> : <CopyIcon size={18} />}
              <span aria-live="polite">{copied ? t.copied : t.copy}</span>
            </button>
            <a
              className="ow-button ow-button-whatsapp"
              href={`https://wa.me/?text=${encodeURIComponent(t.whatsappText(url, code))}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ChatIcon size={18} />
              {t.whatsapp}
            </a>
          </div>
          <div className="ow-share-code">
            <span>{t.shareCodeLabel}</span>
            <strong aria-label={code.split('').join(' ')}>{code}</strong>
          </div>
          {!confirming ? (
            <button className="ow-link-button ow-on-dark" onClick={() => setConfirming(true)} disabled={!!busy}>
              {t.stopSharing}
            </button>
          ) : (
            <div className="ow-confirm" role="alertdialog" aria-labelledby="ow-stop-q">
              <p id="ow-stop-q">{t.stopConfirm}</p>
              <div className="ow-share-actions">
                <button className="ow-button ow-button-danger" onClick={stop} disabled={!!busy}>
                  {busy === 'stop' ? t.stopping : t.stopYes}
                </button>
                <button className="ow-button ow-button-light" onClick={() => setConfirming(false)} disabled={!!busy}>
                  {t.stopNo}
                </button>
              </div>
            </div>
          )}
        </>
      )}
      {error && (
        <p className="ow-error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
