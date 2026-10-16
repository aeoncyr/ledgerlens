// The business owner's data. The owner starts a file, sends evidence, runs a check, answers the
// questions and shares the file with a lender. Writes go through the API; reads are live from
// Firestore. The owner reads only the application, its evidence, its runs and the owner summary,
// never the lender's memo or audit log.
import {
  collection,
  doc,
  onSnapshot,
  query,
  where,
  type Timestamp,
} from 'firebase/firestore'
import { useEffect, useState } from 'react'
import { apiFetch } from './api.ts'
import { db, ensureSignedIn } from './firebase.ts'
import type { Application, StoredEvidence } from './officer.ts'

// The officer's data layer already does these the same way for both sides.
export {
  addEvidence,
  answerQuestion,
  CONSENT_VERSION,
  recheck,
  recordConsent,
  rememberedSample,
  rememberSample,
  useApplication,
  useEvidence,
  useRun,
  type ApplicationStatus,
  type Run,
  type RunStep,
} from './officer.ts'

export type OwnerApplication = Omit<Application, 'officerUid' | 'consent'> & {
  officerUid: string | null
  ownerUid: string | null
  origin?: 'owner' | 'officer'
  consent: { given: boolean; version?: string; by?: 'owner' | 'officer' } | null
  shareCode?: string | null
  sharedAt?: Timestamp | null
}

export type OwnerEvidence = StoredEvidence & {
  submittedBy?: 'owner' | 'officer'
  capturedAt?: string | Timestamp
}

export type OwnerQuestion = {
  index: number
  question: string
  questionEn: string | null
  answer: string | null
  declined?: boolean
}

export type OwnerSummary = {
  status: 'ready' | 'needs_answers'
  verified: string
  missing: string
  tips: string[]
  verifiedEn: string
  missingEn: string
  tipsEn: string[]
  questions: OwnerQuestion[]
  evidenceCount: number
  updatedAt?: Timestamp
}

export type NewOwnerFile = {
  alias: string
  businessType: string
  city: string
  yearsOperating: number
  amount: number
  tenorMonths: number
}

const json = { 'Content-Type': 'application/json' }
const analyzeBase = () => import.meta.env.VITE_ANALYZE_BASE || ''

export async function createOwnerFile(body: NewOwnerFile): Promise<string> {
  const created = await apiFetch<{ applicationId: string }>('/api/owner/files', {
    method: 'POST',
    headers: json,
    body: JSON.stringify(body),
  })
  return created.applicationId
}

/** Run the full check on Cloud Run directly; it lasts longer than Firebase Hosting allows. */
export async function runCheck(id: string): Promise<void> {
  await apiFetch(`/api/applications/${id}/analyze`, { method: 'POST' }, analyzeBase())
}

export type Share = { shareCode: string; path: string }

/** Create (or return the existing) share code. Idempotent. */
export async function shareFile(id: string): Promise<Share> {
  return apiFetch<Share>(`/api/applications/${id}/share`, { method: 'POST' })
}

export async function withdrawShare(id: string): Promise<void> {
  await apiFetch(`/api/applications/${id}/share`, { method: 'DELETE' })
}

export const sharePath = (code: string) => `/app/shared/${code}`

// --- Live reads -----------------------------------------------------------------------------------

type Live<T> = { data: T; loading: boolean; error: string | null }

/** The anonymous user's id, once signed in. */
export function useUid(): string | null {
  const [uid, setUid] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    ensureSignedIn()
      .then((user) => {
        if (!cancelled) setUid(user.uid)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])
  return uid
}

export function useOwnerFiles(uid: string | null): Live<OwnerApplication[]> {
  const [state, setState] = useState<Live<OwnerApplication[]>>({
    data: [],
    loading: true,
    error: null,
  })
  useEffect(() => {
    if (!uid) return
    const mine = query(collection(db, 'applications'), where('ownerUid', '==', uid))
    return onSnapshot(
      mine,
      (snapshot) =>
        setState({
          data: snapshot.docs
            .map((d) => ({ id: d.id, ...d.data() }) as OwnerApplication)
            .sort((a, b) => (b.createdAt?.seconds ?? 0) - (a.createdAt?.seconds ?? 0)),
          loading: false,
          error: null,
        }),
      (error) => setState({ data: [], loading: false, error: error.message }),
    )
  }, [uid])
  return state
}

export function useOwnerSummary(id: string): Live<OwnerSummary | null> {
  const [state, setState] = useState<Live<OwnerSummary | null>>({
    data: null,
    loading: true,
    error: null,
  })
  useEffect(() => {
    let stop = () => {}
    let cancelled = false
    ensureSignedIn()
      .then(() => {
        if (cancelled) return
        stop = onSnapshot(
          doc(db, 'applications', id, 'owner', 'summary'),
          (snapshot) =>
            setState({
              data: snapshot.exists() ? (snapshot.data() as OwnerSummary) : null,
              loading: false,
              error: null,
            }),
          // Before the first check the document may not exist yet, or rules may refuse it; either
          // way the page simply has no summary to show.
          (error) => setState({ data: null, loading: false, error: error.message }),
        )
      })
      .catch((error: Error) => setState({ data: null, loading: false, error: error.message }))
    return () => {
      cancelled = true
      stop()
    }
  }, [id])
  return state
}

/** True when a failed run stopped because Gemini's free daily quota ran out, not a passing error. */
export function isQuotaError(error?: string | null): boolean {
  return !!error && /quota|RESOURCE_EXHAUSTED|429/i.test(error)
}

/** Turn any thrown value into the message the API sent (its `detail`), or a plain one. */
export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
