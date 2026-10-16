import { useEffect, useState } from 'react'
import type { Run, RunStep } from '../officer.ts'

const AGENT_LABEL: Record<string, string> = {
  intake: 'Intake',
  ledger_reader: 'Notebook reader',
  receipt_reader: 'Receipt reader',
  qris_reader: 'QRIS reader',
  photo_assessor: 'Photo assessor',
  interview_listener: 'Interview listener',
  calculator: 'Calculator',
  verifier: 'Verifier',
  policy: 'Lender policy',
  memo_writer: 'Memo writer',
}

// The agents that are plain code; every other agent is a Gemini call.
const PYTHON_AGENTS = new Set(['intake', 'calculator', 'policy'])

const SAMPLE_LINES = 12

// Seconds without a new step before the trace says, calmly, that the run is still going.
const QUIET_SECONDS = 30

// A step that started is hidden once a later step reports on the same item or stage, so the trace
// reads as a list of what has been done, plus what is happening now.
function visibleSteps(steps: RunStep[]): RunStep[] {
  return steps.filter((step, index) => {
    if (step.state !== 'running') return true
    const subject = step.message.replace(/^Reading /, '').toLowerCase()
    return !steps.slice(index + 1).some(
      (later) =>
        later.agent === step.agent &&
        later.state !== 'running' &&
        (later.message.toLowerCase().includes(subject) || !step.message.startsWith('Reading ')),
    )
  })
}

function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

// The first lines of a structured output, pretty-printed and cut to fit the trace.
function excerpt(sample: unknown): string {
  const lines = JSON.stringify(sample, null, 2).split('\n')
  return lines.length > SAMPLE_LINES
    ? [...lines.slice(0, SAMPLE_LINES - 1), '  …'].join('\n')
    : lines.join('\n')
}

// Wall-clock seconds, ticking once a second while the run is in progress.
function useNow(ticking: boolean): number {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    if (!ticking) return
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => window.clearInterval(timer)
  }, [ticking])
  return now
}

export default function LiveTrace({ run }: { run: Run | null }) {
  const running = run?.state === 'running'
  const now = useNow(running)
  if (!run) return <p className="fine">Starting the analysis…</p>

  const all = run.steps ?? []
  const steps = visibleSteps(all)
  const start = run.startedAt?.seconds ?? all[0]?.at?.seconds ?? 0
  const last = all.at(-1)?.at?.seconds ?? start
  const elapsed = !start
    ? 0
    : running
      ? Math.max(now, last) - start
      : run.latencyMs
        ? run.latencyMs / 1000
        : last - start
  // No new step for a while: say so, so a slow free-tier call doesn't look like a stall.
  const quiet = running && start > 0 && now - Math.max(last, start) >= QUIET_SECONDS

  return (
    <div className="trace">
      <div className="trace-head">
        <span className="trace-title">
          Agent trace
          {run.id && <span className="trace-run mono">run {run.id.slice(0, 8)}</span>}
        </span>
        <span className="trace-clock mono" role="timer" aria-label="Time elapsed">
          {clock(elapsed)}
        </span>
      </div>
      <ol aria-live="polite">
        {steps.map((step, index) => {
          const python = PYTHON_AGENTS.has(step.agent)
          const model = !python ? step.detail?.model : null
          return (
            <li key={index} className={`trace-step ${step.state}`}>
              <span className="trace-time">
                {start ? `${Math.max(0, (step.at?.seconds ?? start) - start)}s` : ''}
              </span>
              <span className="trace-agent">
                {AGENT_LABEL[step.agent] ?? step.agent}
                <span className={`engine ${python ? 'python' : 'gemini'}`}>
                  {python ? 'Python' : 'Gemini'}
                </span>
              </span>
              <span className="trace-message">
                {step.message}
                {model && <span className="trace-model mono">{model}</span>}
              </span>
              <span className="trace-state">
                {step.state === 'done' ? 'done' : step.state === 'failed' ? 'failed' : 'working…'}
              </span>
              {step.detail?.sample != null && (
                <details className="trace-sample">
                  <summary>
                    Sample of Gemini’s structured output
                    {step.detail.sampleLabel && (
                      <span className="fine"> · {step.detail.sampleLabel}</span>
                    )}
                  </summary>
                  <pre>
                    <code>{excerpt(step.detail.sample)}</code>
                  </pre>
                  <p className="fine">Schema-validated. Totals are left to Python.</p>
                </details>
              )}
            </li>
          )
        })}
      </ol>
      {quiet && (
        <p className="trace-quiet" role="status">
          <span className="trace-quiet-dot" aria-hidden="true" />
          Still working. Gemini’s free tier is busy at times; LedgerLens waits and moves to another
          model when one is slow.
        </p>
      )}
      {run.state === 'running' && (
        <p className="fine">
          Gemini reads every item in parallel; arithmetic is done by code. On the free tier this
          takes one to three minutes.
        </p>
      )}
      {run.state === 'failed' && (
        <div className="error" role="alert">
          <p>
            {/quota|RESOURCE_EXHAUSTED|429/i.test(run.error ?? '')
              ? 'Gemini’s free daily quota ran out, so the check stopped. It comes back at midnight Pacific time (early afternoon in Jakarta). Nothing is lost; the sample files stay open meanwhile.'
              : 'The check stopped partway, usually because Gemini was busy. Nothing is lost: run it again in a minute.'}
          </p>
          {run.error && (
            <details>
              <summary>Technical detail</summary>
              <code>{run.error}</code>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
