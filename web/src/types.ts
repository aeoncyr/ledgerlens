// Shapes of the credit file as the API stores it and as the sample files are published.

export type Assessment =
  | 'verified'
  | 'partially_verified'
  | 'insufficient_evidence'
  | 'inconsistent'

export type Severity = 'low' | 'medium' | 'high'

export type SampleSummary = {
  slug: string
  fileNumber: string
  alias: string
  businessType: string
  city: string
  yearsOperating: number
  amount: number
  tenorMonths: number
  assessment: Assessment
  revenueLow: number
  revenueHigh: number
  maxInstallment: number | null
  requestedInstallment: number
  withinPolicy: boolean
  evidenceStrength: number
  evidenceCount: number
  findings: { severity: Severity; text: string }[]
  headline: string
  preparedAt: string
}

export const ASSESSMENT_LABEL: Record<Assessment, string> = {
  verified: 'Verified',
  partially_verified: 'Partially verified',
  insufficient_evidence: 'Insufficient evidence',
  inconsistent: 'Inconsistent',
}

// The CSS class for each outcome's colour.
export const ASSESSMENT_TONE: Record<Assessment, string> = {
  verified: 'verified',
  partially_verified: 'partial',
  insufficient_evidence: 'insufficient',
  inconsistent: 'inconsistent',
}

export type Citation = { evidenceId: string; locator: string }

export type Finding = {
  // credit_history comes only from the SLIK check a lender records, never from the evidence.
  kind: 'discrepancy' | 'low_confidence' | 'missing_evidence' | 'fraud_signal' | 'credit_history'
  severity: Severity
  text: string
  citations: Citation[]
  followUpQuestion: string | null
  followUpQuestionEn: string | null
  figures: string[]
  source: 'code' | 'verifier'
  answer: string | null
  answerEn?: string | null
  answerAudio?: string | null
  declined?: boolean
  resolved: boolean
}

export type Fact = {
  key: string
  label: string
  kind: 'rupiah' | 'percent' | 'ratio' | 'count'
  value: number
  sources: string[]
  display: string
}

export type MonthFigures = {
  month: string
  provenInflows: number
  claimedSales: number
  receiptPurchases: number
  claimedPurchases: number
  claimedExpenses: number
}

export type MemoSection = { text: string; citations: Citation[] }

export type Memo = {
  headline: string
  character: MemoSection
  capacity: MemoSection
  capital: MemoSection
  collateral: MemoSection
  conditions: MemoSection
  officerNextSteps: string[]
  ownerSummary: { verified: string; missing: string; tips: string[] }
  figures: string[]
}

export type EvidenceType = 'ledger_page' | 'qris_history' | 'receipt' | 'shop_photo' | 'interview_audio'

export type EvidenceItem = {
  id: string
  type: EvidenceType
  image: string
  capturedAt: string
  submittedBy?: 'owner' | 'officer'
  // What the reader extracted; its shape depends on the type of evidence.
  reading: (Record<string, unknown> & { label?: string }) | null
}

export type CreditFileData = {
  slug: string
  fileNumber: string
  application: {
    alias: string
    businessType: string
    city: string
    yearsOperating: number
    amount: number
    tenorMonths: number
    // Other loan instalments a month the application declares, including online loans. Files
    // started before the field existed don't have it.
    existingMonthlyDebt?: number
  }
  evidence: EvidenceItem[]
  assessment: Assessment
  policy: {
    evidenceStrength: number
    capacityBasis: number | null
    maxInstallment: number | null
    requestedInstallment: number
    withinPolicy: boolean
    // How far sales could fall before the request is above the limit (see stress.ts). Older files
    // and the samples don't store it.
    stressDropPct?: number | null
    reasons: string[]
    // What was applied (api/app/tools/policy.py). Files checked before these were stored, and the
    // samples, don't have them; null lenderName means LedgerLens's starting values.
    lenderName?: string | null
    maxInstallmentRatio?: number | null
    haircut?: number | null
    annualRatePct?: number | null
    maxTenorMonths?: number | null
    existingMonthlyDebt?: number | null
    debtSource?: 'declared' | 'slik' | null
  }
  cashflow: {
    months: MonthFigures[]
    revenueLow: number
    revenueHigh: number
    netHigh: number
    avgCosts: number
    hardCoverage: number | null
    salesToPurchases: number | null
  }
  findings: Finding[]
  confirmations: { text: string; figures: string[]; citations: Citation[] }[]
  memo: Memo
  facts: Fact[]
  models: string[]
  round?: number
  // Set when a lender's policy was applied after the memo was written and changed more than its
  // figures (api/app/analysis/reapply.py).
  memoNote?: string | null
}

export const EVIDENCE_LABEL: Record<EvidenceType, string> = {
  ledger_page: 'Notebook page',
  qris_history: 'QRIS history',
  receipt: 'Receipt',
  shop_photo: 'Shop photo',
  interview_audio: 'Interview',
}
