// A recorded run of the analysis, played back faster than it happened, in the same trace an
// officer watches live. Nothing is sent to Gemini: every step, model and output excerpt is what the
// real run wrote to Firestore (exported by eval/export_runs.py).
import type { Timestamp } from 'firebase/firestore'
import { useEffect, useState } from 'react'
import type { RecordedRun } from '../demo.ts'
import type { Run } from '../officer.ts'
import { ASSESSMENT_LABEL, type Assessment } from '../types.ts'
import LiveTrace from './LiveTrace.tsx'
import '../demo.css'

// The replay's clock starts at an arbitrary second; LiveTrace only compares seconds.
const ORIGIN = 1_000_000
const TICK_MS = 100

const dateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })

// LiveTrace reads only `seconds` from a timestamp.
const at = (seconds: number) => ({ seconds }) as Timestamp

// Fast enough to watch in well under a minute, slow enough to read: six to ten times.
function replaySpeed(run: RecordedRun): number {
  const seconds = (run.latencyMs ?? 0) / 1000 || run.steps.at(-1)?.t || 0
  return Math.min(10, Math.max(6, Math.round(seconds / 25)))
}

function outcomeLabel(outcome: string | null): string | null {
  return outcome && outcome in ASSESSMENT_LABEL ? ASSESSMENT_LABEL[outcome as Assessment] : null
}

export default function TraceReplay({
  run,
  assessment,
  onFinished,
}: {
  run: RecordedRun
  // The outcome of the file shown with the replay, to say so when this run ended differently.
  assessment?: Assessment
  onFinished?: () => void
}) {
  const speed = replaySpeed(run)
  const duration = (run.latencyMs ?? 0) / 1000 || (run.steps.at(-1)?.t ?? 0)
  // Real milliseconds since the replay started, and whether it is playing.
  const [elapsed, setElapsed] = useState(0)
  const [playing, setPlaying] = useState(true)
  const seconds = Math.min(duration, (elapsed / 1000) * speed)
  const finished = seconds >= duration

  useEffect(() => {
    if (!playing) return
    const started = performance.now() - elapsed
    const timer = window.setInterval(() => {
      const now = performance.now() - started
      setElapsed(now)
      if ((now / 1000) * speed >= duration) setPlaying(false)
    }, TICK_MS)
    return () => window.clearInterval(timer)
    // The replay restarts its timer only when it is started or stopped.
  }, [playing]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (finished) onFinished?.()
  }, [finished]) // eslint-disable-line react-hooks/exhaustive-deps

  const shown: Run = {
    id: run.id,
    state: finished ? 'done' : 'running',
    startedAt: at(ORIGIN),
    latencyMs: finished ? (run.latencyMs ?? undefined) : undefined,
    models: run.models,
    steps: run.steps
      .filter((step) => step.t <= seconds)
      .map((step) => ({ ...step, at: at(ORIGIN + Math.round(step.t)) })),
  }
  const ranAs = outcomeLabel(run.outcome)
  const fileAs = assessment ? ASSESSMENT_LABEL[assessment] : null

  return (
    <section className="replay" aria-label="Replay of a real check">
      <p className="replay-note">
        <span className="replay-tag">Replay</span> A real run on this business’s records in the
        live app, on {dateFormat.format(new Date(run.recordedAt))}, played back {speed}× faster.
        Nothing is sent to Gemini now.
      </p>
      <LiveTrace run={shown} replayClock={ORIGIN + seconds} replay={speed} />
      <div className="replay-actions">
        {finished ? (
          <button
            type="button"
            className="button quiet"
            onClick={() => {
              setElapsed(0)
              setPlaying(true)
            }}
          >
            Watch it again
          </button>
        ) : (
          <button
            type="button"
            className="button quiet"
            onClick={() => {
              setPlaying(false)
              setElapsed((duration / speed) * 1000)
            }}
          >
            Skip to the end
          </button>
        )}
      </div>
      {finished && ranAs && fileAs && ranAs !== fileAs && (
        <p className="fine replay-differs">
          This run ended <strong>{ranAs}</strong>; the finished file comes from another run on the
          same records, which ended <strong>{fileAs}</strong>.{' '}
          {run.ownerLed
            ? 'This run was the business owner’s own check: QRIS screenshots an owner sends count as weaker evidence until an officer confirms them on a visit, so the file can be at most partially verified until then.'
            : 'Readings of handwriting vary a little from run to run, which is why the officer confirms disputed lines and a person decides.'}
        </p>
      )}
    </section>
  )
}
