// The lender's own settings and checks: who they are, the credit policy LedgerLens applies for them,
// invites to business owners, and the SLIK check they record on a file. Writes go through the API;
// the SLIK check on a file is read live from Firestore (lender-only, like the memo).
import { doc, onSnapshot } from 'firebase/firestore'
import { useEffect, useState } from 'react'
import { apiFetch } from './api.ts'
import { db, ensureSignedIn } from './firebase.ts'
import type { NewOwnerFile } from './owner.ts'

export type LenderType = 'bpr' | 'bprs' | 'cooperative' | 'microfinance' | 'other'
export type Product = 'kur_micro' | 'own'

export const LENDER_TYPES: [LenderType, string][] = [
  ['bpr', 'BPR (rural bank)'],
  ['bprs', 'BPRS (Islamic rural bank)'],
  ['cooperative', 'Cooperative (koperasi)'],
  ['microfinance', 'Microfinance institution (LKM)'],
  ['other', 'Other lender'],
]

// The rate a preset prices a loan at, in percent a year (the API applies the same).
export const PRODUCT_RATE: Partial<Record<Product, number>> = { kur_micro: 6 }

export type LenderPolicyForm = {
  name: string | null
  type: LenderType | null
  product: Product
  annualRatePct: number
  maxInstallmentRatioPct: number
  haircutVerifiedPct: number
  haircutPartialPct: number
  maxTenorMonths: number
}

export type LenderProfile = LenderPolicyForm & {
  saved: boolean
  updatedAt: string | null
  defaults: LenderPolicyForm
}

const json = { 'Content-Type': 'application/json' }

export function getProfile(): Promise<LenderProfile> {
  return apiFetch<LenderProfile>('/api/lender/profile')
}

export function saveProfile(form: LenderPolicyForm): Promise<LenderProfile> {
  return apiFetch<LenderProfile>('/api/lender/profile', {
    method: 'PUT',
    headers: json,
    body: JSON.stringify(form),
  })
}

/** The same checks the API makes, so the officer sees a problem before saving. */
export function profileProblem(form: LenderPolicyForm): string | null {
  const name = (form.name ?? '').trim()
  if (name.length < 2) return 'Enter your lender’s name, as owners know it (for example BPR Sejahtera).'
  if (name.length > 80) return 'Keep the lender’s name under 80 characters.'
  if (!form.type) return 'Choose what kind of lender you are.'
  const between = (value: number, low: number, high: number) =>
    Number.isFinite(value) && value >= low && value <= high
  if (!between(form.annualRatePct, 0, 60)) return 'The rate should be between 0% and 60% a year.'
  if (!between(form.maxInstallmentRatioPct, 5, 60))
    return 'The share of cash flow for repayments should be between 5% and 60%.'
  if (!between(form.haircutVerifiedPct, 0, 90))
    return 'The haircut for a verified file should be between 0% and 90%.'
  if (!between(form.haircutPartialPct, 0, 90))
    return 'The haircut for a partly verified file should be between 0% and 90%.'
  if (form.haircutPartialPct < form.haircutVerifiedPct)
    return 'A partly verified file should be discounted at least as much as a verified one: make its haircut the same or larger.'
  if (!Number.isInteger(form.maxTenorMonths) || !between(form.maxTenorMonths, 1, 60))
    return 'The longest term should be between 1 and 60 months.'
  return null
}

// --- Invites -------------------------------------------------------------------------------------

export type InviteState = 'open' | 'used' | 'expired'

export type Invite = {
  code: string
  path: string
  lenderName: string
  createdAt: string
  expiresAt: string
  state: InviteState
  applicationId: string | null
}

export type InvitePublic = {
  code: string
  lenderName: string
  lenderType: LenderType | null
  expiresAt: string
  state: InviteState
  // Set when the person asking already used this invite: the file it started.
  applicationId: string | null
  // The invite comes from this browser's own lender workspace.
  own: boolean
}

export function createInvite(): Promise<Invite> {
  return apiFetch<Invite>('/api/invites', { method: 'POST' })
}

export function listInvites(): Promise<Invite[]> {
  return apiFetch<Invite[]>('/api/invites')
}

export function getInvite(code: string): Promise<InvitePublic> {
  return apiFetch<InvitePublic>(`/api/invites/${encodeURIComponent(code)}`)
}

/** The owner agrees: a new file, theirs, already shared with the lender who invited them. */
export async function acceptInvite(code: string, body: NewOwnerFile): Promise<string> {
  const created = await apiFetch<{ applicationId: string }>(
    `/api/invites/${encodeURIComponent(code)}/accept`,
    { method: 'POST', headers: json, body: JSON.stringify(body) },
  )
  return created.applicationId
}

export const invitePath = (code: string) => `/owner/invite/${code}`

// --- The lender's checks on a file ---------------------------------------------------------------

export type SlikRecord = {
  checkedOn: string
  activeFacilities: number
  monthlyInstalments: number
  worstCollectibility: number
  recordedAt?: string
}

// OJK's five grades of collectibility (kolektibilitas).
export const COLLECTIBILITY: [number, string][] = [
  [1, '1 · Current (lancar)'],
  [2, '2 · Special mention (dalam perhatian khusus)'],
  [3, '3 · Substandard (kurang lancar)'],
  [4, '4 · Doubtful (diragukan)'],
  [5, '5 · Loss (macet)'],
]

export type PolicyApplied = {
  applied: boolean
  lenderName: string | null
  maxInstallment: number | null
  withinPolicy: boolean | null
  memoNote: string | null
}

/** Apply the officer's current settings to the file again; Python only, no Gemini. */
export function reapplyPolicy(id: string): Promise<PolicyApplied> {
  return apiFetch<PolicyApplied>(`/api/applications/${id}/policy`, { method: 'POST' })
}

export function recordSlik(id: string, record: SlikRecord): Promise<PolicyApplied> {
  return apiFetch<PolicyApplied>(`/api/applications/${id}/slik`, {
    method: 'PUT',
    headers: json,
    body: JSON.stringify(record),
  })
}

export function removeSlik(id: string): Promise<PolicyApplied> {
  return apiFetch<PolicyApplied>(`/api/applications/${id}/slik`, { method: 'DELETE' })
}

/** The SLIK check recorded on a file, live; null when there is none. */
export function useSlik(id: string): { data: SlikRecord | null; loading: boolean } {
  const [state, setState] = useState<{ data: SlikRecord | null; loading: boolean }>({
    data: null,
    loading: true,
  })
  useEffect(() => {
    let stop = () => {}
    let cancelled = false
    ensureSignedIn()
      .then(() => {
        if (cancelled) return
        stop = onSnapshot(
          doc(db, 'applications', id, 'lender', 'slik'),
          (snapshot) =>
            setState({
              data: snapshot.exists() ? (snapshot.data() as SlikRecord) : null,
              loading: false,
            }),
          () => setState({ data: null, loading: false }),
        )
      })
      .catch(() => setState({ data: null, loading: false }))
    return () => {
      cancelled = true
      stop()
    }
  }, [id])
  return state
}
