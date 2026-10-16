import type { Run, RunStep } from '../officer.ts'

const AGENT_LABEL: Record<string, string> = {
  intake: 'Intake',
  ledger_reader: 'Notebook reader',
  receipt_reader: 'Receipt reader',
  qris_reader: 'QRIS reader',
  photo_assessor: 'Photo assessor',
  interview_listener: 'Interview listener',
  calculator: 'Calculator (code)',
  verifier: 'Verifier',
  policy: 'Lender policy (code)',
  memo_writer: 'Memo writer',
}

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

export default function LiveTrace({ run }: { run: Run | null }) {
  if (!run) return <p className="fine">Starting the analysis…</p>
  const steps = visibleSteps(run.steps ?? [])
  const start = run.steps?.[0]?.at?.seconds ?? 0
  return (
    <div className="trace" aria-live="polite">
      <ol>
        {steps.map((step, index) => (
          <li key={index} className={`trace-step ${step.state}`}>
            <span className="trace-time">
              {start ? `${Math.max(0, (step.at?.seconds ?? start) - start)}s` : ''}
            </span>
            <span className="trace-agent">{AGENT_LABEL[step.agent] ?? step.agent}</span>
            <span className="trace-message">{step.message}</span>
            <span className="trace-state">
              {step.state === 'done' ? 'done' : step.state === 'failed' ? 'failed' : 'working…'}
            </span>
          </li>
        ))}
      </ol>
      {run.state === 'running' && (
        <p className="fine">
          Gemini reads every item in parallel; arithmetic is done by code. On the free tier this
          takes one to three minutes.
        </p>
      )}
      {run.state === 'failed' && <p className="error">The analysis failed: {run.error}</p>}
    </div>
  )
}
