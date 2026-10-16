// The officer's data: applications, evidence and analysis runs. Writes go through the API, which
// checks ownership and keeps the audit log; reads come straight from Firestore, live.
import {
  collection,
  doc,
  onSnapshot,
  query,
  where,
  type DocumentData,
  type Timestamp,
} from 'firebase/firestore'
import { ref, uploadBytes } from 'firebase/storage'
import { useEffect, useState } from 'react'
import { apiFetch } from './api.ts'
import { db, ensureSignedIn, storage } from './firebase.ts'
import type { Assessment, EvidenceType } from './types.ts'

export type ApplicationStatus =
  | 'draft'
  | 'collecting'
  | 'analyzing'
  | 'needs_follow_up'
  | 'ready'
  | 'in_review'
  | 'decided'

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  draft: 'Waiting for consent',
  collecting: 'Collecting evidence',
  analyzing: 'Analysing',
  needs_follow_up: 'Questions for the owner',
  ready: 'Ready for decision',
  in_review: 'In review',
  decided: 'Decided',
}

export type Application = {
  id: string
  officerUid: string
  business: { alias: string; type: string; city: string; yearsOperating: number }
  request: { amount: number; tenorMonths: number }
  status: ApplicationStatus
  assessment: Assessment | null
  evidenceStrength?: number
  flagCount?: number
  currentRunId?: string
  consent: { given: boolean } | null
  decision?: { action: string; reason: string }
  createdAt?: Timestamp
}

export type StoredEvidence = {
  id: string
  type: EvidenceType
  storagePath: string
  label?: string
  extraction?: Record<string, unknown> | null
}

export type RunStep = { agent: string; message: string; state: string; at: Timestamp }
export type Run = { state: 'running' | 'done' | 'failed'; steps: RunStep[]; error?: string }

export type NewApplication = {
  alias: string
  businessType: string
  city: string
  yearsOperating: number
  amount: number
  tenorMonths: number
}

export async function createApplication(body: NewApplication): Promise<string> {
  const created = await apiFetch<{ applicationId: string }>('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return created.applicationId
}

export const CONSENT_VERSION = '2026-10-v1'

export async function recordConsent(id: string, given: boolean): Promise<void> {
  await apiFetch(`/api/applications/${id}/consent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ consentVersion: CONSENT_VERSION, given }),
  })
}

/** Upload a photo or recording into the officer's own folder, then register it with the API. */
export async function addEvidence(
  id: string,
  type: EvidenceType,
  file: Blob,
  name: string,
  capturedAt = new Date(),
): Promise<void> {
  const user = await ensureSignedIn()
  const safeName = `${Date.now()}-${name.replace(/[^\w.-]+/g, '_')}`
  const path = `evidence/${id}/${user.uid}/${safeName}`
  await uploadBytes(ref(storage, path), file, { contentType: file.type || 'image/jpeg' })
  await apiFetch(`/api/applications/${id}/evidence`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, storagePath: path, capturedAt: capturedAt.toISOString() }),
  })
}

/** Run the analysis on Cloud Run directly; it lasts longer than Firebase Hosting allows. */
export async function runAnalysis(id: string): Promise<void> {
  const base = import.meta.env.VITE_ANALYZE_BASE || ''
  await apiFetch(`/api/applications/${id}/analyze`, { method: 'POST' }, base)
}

export async function answerQuestion(id: string, index: number, text: string): Promise<void> {
  await apiFetch(`/api/applications/${id}/findings/${index}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
}

/** Check the file again with the owner's answers; only the verifier and memo writer run. */
export async function recheck(id: string): Promise<void> {
  const base = import.meta.env.VITE_ANALYZE_BASE || ''
  await apiFetch(`/api/applications/${id}/reverify`, { method: 'POST' }, base)
}

export async function recordDecision(id: string, action: string, reason: string): Promise<void> {
  await apiFetch(`/api/applications/${id}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, reason }),
  })
}

/** Remember which sample business an application was started from, for the evidence step. */
export function rememberSample(applicationId: string, slug: string) {
  try {
    sessionStorage.setItem(`ledgerlens-sample-${applicationId}`, slug)
  } catch {
    // Storage can be unavailable (private windows); the evidence step then offers every sample.
  }
}

export function rememberedSample(applicationId: string): string | null {
  try {
    return sessionStorage.getItem(`ledgerlens-sample-${applicationId}`)
  } catch {
    return null
  }
}

// --- Live reads -----------------------------------------------------------------------------------

type Live<T> = { data: T; loading: boolean; error: string | null }

function useLive<T>(
  initial: T,
  subscribe: (set: (value: T) => void, fail: (error: Error) => void) => () => void,
  deps: unknown[],
): Live<T> {
  const [state, setState] = useState<Live<T>>({ data: initial, loading: true, error: null })
  useEffect(() => {
    let stop = () => {}
    let cancelled = false
    ensureSignedIn()
      .then(() => {
        if (cancelled) return
        stop = subscribe(
          (data) => setState({ data, loading: false, error: null }),
          (error) => setState({ data: initial, loading: false, error: error.message }),
        )
      })
      .catch((error: Error) => setState({ data: initial, loading: false, error: error.message }))
    return () => {
      cancelled = true
      stop()
    }
    // Each caller passes the values its subscription depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}

function withId<T>(id: string, data: DocumentData): T {
  return { id, ...data } as T
}

export function useApplications(uid: string | null): Live<Application[]> {
  return useLive<Application[]>(
    [],
    (set, fail) => {
      if (!uid) return () => {}
      const mine = query(collection(db, 'applications'), where('officerUid', '==', uid))
      return onSnapshot(
        mine,
        (snapshot) =>
          set(
            snapshot.docs
              .map((d) => withId<Application>(d.id, d.data()))
              .sort((a, b) => (b.createdAt?.seconds ?? 0) - (a.createdAt?.seconds ?? 0)),
          ),
        fail,
      )
    },
    [uid],
  )
}

export function useApplication(id: string): Live<Application | null> {
  return useLive<Application | null>(
    null,
    (set, fail) =>
      onSnapshot(
        doc(db, 'applications', id),
        (snapshot) => set(snapshot.exists() ? withId(snapshot.id, snapshot.data()) : null),
        fail,
      ),
    [id],
  )
}

export function useEvidence(id: string): Live<StoredEvidence[]> {
  return useLive<StoredEvidence[]>(
    [],
    (set, fail) =>
      onSnapshot(
        collection(db, 'applications', id, 'evidence'),
        (snapshot) => set(snapshot.docs.map((d) => withId<StoredEvidence>(d.id, d.data()))),
        fail,
      ),
    [id],
  )
}

export function useRun(id: string, runId: string | undefined): Live<Run | null> {
  return useLive<Run | null>(
    null,
    (set, fail) => {
      if (!runId) return () => {}
      return onSnapshot(
        doc(db, 'applications', id, 'runs', runId),
        (snapshot) => set(snapshot.exists() ? (snapshot.data() as Run) : null),
        fail,
      )
    },
    [id, runId],
  )
}

export function useCreditFileDoc(id: string, version: string | undefined): Live<DocumentData | null> {
  return useLive<DocumentData | null>(
    null,
    (set, fail) =>
      onSnapshot(
        doc(db, 'applications', id, 'memo', 'current'),
        (snapshot) => set(snapshot.exists() ? snapshot.data() : null),
        fail,
      ),
    [id, version],
  )
}
