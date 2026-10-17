// The pilot dashboard's data: the API counts and times the officer's own files (api/app/routers/
// pilot.py) and the page only lays the figures out. Nothing here is estimated.
import { apiFetch, ApiError } from './api.ts'
import { ensureSignedIn } from './firebase.ts'
import type { Assessment, EvidenceType, Finding } from './types.ts'

export type FindingKind = Finding['kind']

export type PilotFile = {
  applicationId: string
  fileNumber: string
  alias: string
  demo: boolean
  origin: 'owner' | 'officer'
  status: string | null
  outcome: Assessment | null
  evidenceCount: number
  missingEvidence: EvidenceType[]
  findings: number
  findingsByKind: Record<FindingKind, number>
  minutesToAnalysis: number | null
  minutesToDecision: number | null
  decision: 'approve' | 'request_more' | 'decline' | null
  decisionState: 'recommended' | 'returned' | 'final' | null
  assessmentAgreed: boolean | null
  disagreementReason: string | null
}

export type PilotReport = {
  includeDemo: boolean
  files: number
  demoFiles: number
  byStatus: Record<string, number>
  byOutcome: Record<string, number>
  byOrigin: Record<string, number>
  medianMinutesToAnalysis: number | null
  timedToAnalysis: number
  medianMinutesToDecision: number | null
  timedToDecision: number
  findingsByKind: Record<FindingKind, number>
  filesWithFraudSignal: number
  decided: number
  agreed: number
  disagreed: number
  agreedPct: number | null
  checkedFiles: number
  missingEvidence: { type: EvidenceType; files: number }[]
  rows: PilotFile[]
}

export function getPilot(includeDemo: boolean): Promise<PilotReport> {
  return apiFetch<PilotReport>(`/api/pilot?includeDemo=${includeDemo}`)
}

/** Download the dashboard's table as CSV; the API needs the sign-in token, so no plain link. */
export async function downloadPilotCsv(includeDemo: boolean): Promise<void> {
  const user = await ensureSignedIn()
  const base = import.meta.env.VITE_API_BASE ?? ''
  const response = await fetch(`${base}/api/pilot/export.csv?includeDemo=${includeDemo}`, {
    headers: { Authorization: `Bearer ${await user.getIdToken()}` },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? response.statusText)
  }
  const name =
    /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1] ??
    'ledgerlens-pilot.csv'
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Minutes as a person reads them: "45 min", "2 h 10 min", "3 days". */
export function duration(minutes: number | null): string {
  if (minutes === null) return '—'
  const whole = Math.round(minutes)
  if (whole < 60) return `${whole} min`
  const hours = Math.floor(whole / 60)
  if (hours < 48) {
    const rest = whole - hours * 60
    return rest ? `${hours} h ${rest} min` : `${hours} h`
  }
  return `${Math.round(hours / 24)} days`
}
