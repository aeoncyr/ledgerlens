// The demo story and the replay, for a visitor trying LedgerLens alone in one browser.
//
// A real file needs three people: the owner who shares it, the officer who recommends a decision
// and a supervisor who signs it off. The demo story copies a finished sample into a file marked
// `demo` (POST /api/demo/story), on which one person plays every role: the page they are on says
// which (see actingRole in api.ts), and the API honours it on demo files only. The replay plays
// back a real run of the analysis on a sample, recorded from Firestore by eval/export_runs.py.
import { useEffect, useState } from 'react'
import { apiFetch } from './api.ts'
import type { OwnerDecision } from './decision.ts'
import type { Application } from './officer.ts'

export type DemoRole = 'owner' | 'officer' | 'reviewer'

export const ROLE_LABEL: Record<DemoRole, string> = {
  owner: 'Owner',
  officer: 'Officer',
  reviewer: 'Supervisor',
}

/** Copy a finished sample into a new demo file the visitor owns; returns its id. */
export async function startDemoStory(sample: string): Promise<string> {
  const created = await apiFetch<{ applicationId: string }>('/api/demo/story', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sample }),
  })
  return created.applicationId
}

// Where the story stands, from the file itself: the owner shares it, the officer opens it and
// recommends, the supervisor signs off, the owner answers.
export type StoryStage = 'share' | 'open' | 'decide' | 'signoff' | 'answer' | 'done'

// What both apps know of a file, as far as the story needs it.
type StoryFields = 'id' | 'status' | 'decision' | 'shareCode' | 'reviewerUid'
export type DemoFile = Pick<Application, StoryFields> & { officerUid: string | null }

export function storyStage(app: DemoFile, sent: OwnerDecision | null): StoryStage {
  const decision = app.decision
  if (!app.officerUid) return app.shareCode ? 'open' : 'share'
  if (app.status === 'awaiting_signoff' && decision?.state === 'recommended') return 'signoff'
  if (decision?.state === 'final') {
    // The letter is written as the decision becomes final; until it is there, the owner waits.
    if (!sent || sent.state === 'offered' || sent.state === 'requested') return 'answer'
    return 'done'
  }
  return 'decide'
}

// --- The replay ---------------------------------------------------------------------------------

export type RecordedStep = {
  agent: string
  message: string
  state: string
  // Seconds after the run started.
  t: number
  detail?: { model?: string | null; sample?: unknown; sampleLabel?: string }
}

export type RecordedRun = {
  id: string
  recordedAt: string
  latencyMs: number | null
  models: string[]
  // The run's own outcome, e.g. "partially_verified"; it can differ from the published file.
  outcome: string | null
  // The run was the owner's own check (owner-sent QRIS counts as weaker evidence).
  ownerLed?: boolean
  steps: RecordedStep[]
}

/** The recorded run of a sample, or null when it has none (the replay is then hidden). */
export function useRecordedRun(slug: string | undefined): RecordedRun | null {
  // Kept with the slug it belongs to, so another sample's run never shows while this one loads.
  const [loaded, setLoaded] = useState<{ slug: string; run: RecordedRun | null } | null>(null)
  useEffect(() => {
    if (!slug) return
    let cancelled = false
    const setRun = (run: RecordedRun | null) => setLoaded({ slug, run })
    fetch(`/samples/${slug}/run.json`)
      .then(async (response) => {
        // Hosting answers a missing file with the app's own page, so check that this is JSON.
        const json = response.headers.get('Content-Type')?.includes('json')
        if (!response.ok || !json) return null
        const data = (await response.json()) as RecordedRun
        return Array.isArray(data.steps) && data.steps.length > 0 ? data : null
      })
      .then((data) => !cancelled && setRun(data))
      .catch(() => !cancelled && setRun(null))
    return () => {
      cancelled = true
    }
  }, [slug])
  return loaded && loaded.slug === slug ? loaded.run : null
}
