// The decision loop, shared by both apps: the officer recommends, a second person signs off, and
// the owner answers the offer. Writes go through the API; the owner's copy of the decision
// (applications/{id}/owner/decision) is read live from Firestore by the owner, the officer and
// the reviewer.
import { doc, onSnapshot, type Timestamp } from 'firebase/firestore'
import { useEffect, useState } from 'react'
import { apiFetch } from './api.ts'
import { db, ensureSignedIn } from './firebase.ts'
import type { EvidenceType } from './types.ts'

export type ScheduleRow = {
  month: number
  instalmentRp: number
  interestRp: number
  principalRp: number
  balanceRp: number
}

export type Offer = {
  amountRp: number
  tenorMonths: number
  annualRatePct: number
  instalmentRp: number
  totalRp: number
  withinPolicy: boolean
  maxInstallmentRp?: number | null
  schedule: ScheduleRow[]
}

export type Condition = {
  text: string
  evidenceType: EvidenceType | null
  met?: boolean
  metAt?: Timestamp | null
  evidenceBefore?: number
}

export type DecisionAction = 'approve' | 'request_more' | 'decline'

// The decision as the officer recorded it, on the application document.
export type RecordedDecision = {
  action: DecisionAction
  reason: string
  offer?: Offer | null
  conditions?: Condition[]
  state?: 'recommended' | 'returned' | 'final'
  signoffCode?: string | null
  by?: string
  signoff?: { approved: boolean; note: string; by: string } | null
}

export type OwnerDecisionState =
  'offered' | 'accepted' | 'declined_by_owner' | 'declined' | 'requested' | 'sent'

// The owner's copy of a final decision.
export type OwnerDecision = {
  action: DecisionAction
  offer: Offer | null
  conditions: Condition[]
  letter: { en: string; id: string; source: 'gemini' | 'template'; model?: string | null }
  state: OwnerDecisionState
  evidenceCountAtDecision?: number
  answeredBy?: 'owner' | 'officer'
  sentCount?: number
  decidedAt?: Timestamp
}

// --- Loan arithmetic: the same formula as api/app/loan.py, for a live preview ----------------

/** The level monthly payment, rounded half up to whole rupiah. The API recomputes it. */
export function previewInstalment(amountRp: number, tenorMonths: number, annualRatePct: number) {
  const rate = annualRatePct / 100 / 12
  if (!amountRp || !tenorMonths) return 0
  if (rate === 0) return Math.round(amountRp / tenorMonths)
  return Math.round((amountRp * rate) / (1 - (1 + rate) ** -tenorMonths))
}

// --- Writes ---------------------------------------------------------------------------------

const json = { 'Content-Type': 'application/json' }

export type DecisionBody = {
  action: DecisionAction
  reason: string
  offer?: { amountRp: number; tenorMonths: number; annualRatePct: number }
  conditions?: { text: string; evidenceType: EvidenceType | null }[]
}

export type DecisionResult = {
  state: 'recommended' | 'final'
  signoffCode: string | null
  path: string | null
}

export async function recordDecision(id: string, body: DecisionBody): Promise<DecisionResult> {
  return apiFetch<DecisionResult>(`/api/applications/${id}/decision`, {
    method: 'POST',
    headers: json,
    body: JSON.stringify(body),
  })
}

export const signoffPath = (code: string) => `/app/signoff/${code}`

/** A second person opens a recommendation; the first to open it holds it. */
export async function claimSignoff(code: string): Promise<string> {
  const claimed = await apiFetch<{ applicationId: string }>(
    `/api/signoff/${encodeURIComponent(code)}`,
    { method: 'POST' },
  )
  return claimed.applicationId
}

export async function signOff(id: string, approve: boolean, note: string): Promise<void> {
  await apiFetch(`/api/applications/${id}/signoff`, {
    method: 'POST',
    headers: json,
    body: JSON.stringify({ approve, note }),
  })
}

export async function answerOffer(id: string, accept: boolean): Promise<void> {
  await apiFetch(`/api/applications/${id}/offer`, {
    method: 'POST',
    headers: json,
    body: JSON.stringify({ accept }),
  })
}

export async function markConditionMet(id: string, index: number): Promise<void> {
  await apiFetch(`/api/applications/${id}/conditions/${index}/met`, { method: 'POST' })
}

export async function sendRequestedRecords(id: string): Promise<void> {
  await apiFetch(`/api/applications/${id}/requested/sent`, { method: 'POST' })
}

// --- Live read ------------------------------------------------------------------------------

export function useOwnerDecision(id: string): OwnerDecision | null {
  const [decision, setDecision] = useState<OwnerDecision | null>(null)
  useEffect(() => {
    let stop = () => {}
    let cancelled = false
    ensureSignedIn()
      .then(() => {
        if (cancelled) return
        stop = onSnapshot(
          doc(db, 'applications', id, 'owner', 'decision'),
          (snapshot) => setDecision(snapshot.exists() ? (snapshot.data() as OwnerDecision) : null),
          // Until a decision is final the document does not exist; there is simply nothing to show.
          () => setDecision(null),
        )
      })
      .catch(() => setDecision(null))
    return () => {
      cancelled = true
      stop()
    }
  }, [id])
  return decision
}
