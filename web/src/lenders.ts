// The "For lenders" page: the illustrative time-and-cost calculator and the pilot request form.
import { apiFetch } from './api.ts'

// --- What a month of files costs in officer time, before and with LedgerLens -------------------

/** The calculator's inputs. Every default is an illustration to replace, not a measurement. */
export type RoiInputs = {
  filesPerMonth: number
  hoursPerFileToday: number
  hoursPerFileWith: number
  hourlyCost: number
  feePerFile: number
}

export const ROI_DEFAULTS: RoiInputs = {
  filesPerMonth: 40,
  hoursPerFileToday: 4,
  hoursPerFileWith: 2.5,
  hourlyCost: 40_000,
  feePerFile: 25_000,
}

export type RoiResult = {
  hoursToday: number
  hoursWith: number
  hoursFreed: number
  costToday: number
  costWith: number
  fees: number
  netMonthly: number
  netYearly: number
  /** The fee per file at which LedgerLens stops paying for itself under these assumptions. */
  breakEvenFee: number
}

const clean = (value: number) => (Number.isFinite(value) && value > 0 ? value : 0)

/** Plain arithmetic on the visitor's own assumptions; the page shows every step. */
export function computeRoi(inputs: RoiInputs): RoiResult {
  const files = clean(inputs.filesPerMonth)
  const today = clean(inputs.hoursPerFileToday)
  const withLens = Math.min(clean(inputs.hoursPerFileWith), today)
  const rate = clean(inputs.hourlyCost)
  const fee = clean(inputs.feePerFile)
  const hoursToday = files * today
  const hoursWith = files * withLens
  const costToday = hoursToday * rate
  const costWith = hoursWith * rate
  const fees = files * fee
  const netMonthly = costToday - costWith - fees
  return {
    hoursToday,
    hoursWith,
    hoursFreed: hoursToday - hoursWith,
    costToday,
    costWith,
    fees,
    netMonthly,
    netYearly: netMonthly * 12,
    breakEvenFee: (today - withLens) * rate,
  }
}

const RUPIAH = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 })
const HOURS = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })

/** "Rp 1.290.996", or "−Rp 50.000" for a loss. */
export function formatRupiah(value: number): string {
  const sign = value < 0 ? '−' : ''
  return `${sign}Rp ${RUPIAH.format(Math.abs(Math.round(value)))}`
}

export function formatHours(value: number): string {
  return `${HOURS.format(value)} h`
}

// --- Request a pilot -----------------------------------------------------------------------------

export type LenderType = 'bpr' | 'bprs' | 'cooperative' | 'microfinance' | 'other'

export const LENDER_TYPES: { value: LenderType; label: string }[] = [
  { value: 'bpr', label: 'Rural bank (BPR)' },
  { value: 'bprs', label: 'Sharia rural bank (BPRS)' },
  { value: 'cooperative', label: 'Savings and loan cooperative' },
  { value: 'microfinance', label: 'Microfinance institution (LKM)' },
  { value: 'other', label: 'Other lender' },
]

// Indonesia's 38 provinces, so requests can be grouped by where a pilot would run.
export const PROVINCES = [
  'Aceh',
  'Bali',
  'Banten',
  'Bengkulu',
  'DI Yogyakarta',
  'DKI Jakarta',
  'Gorontalo',
  'Jambi',
  'Jawa Barat',
  'Jawa Tengah',
  'Jawa Timur',
  'Kalimantan Barat',
  'Kalimantan Selatan',
  'Kalimantan Tengah',
  'Kalimantan Timur',
  'Kalimantan Utara',
  'Kepulauan Bangka Belitung',
  'Kepulauan Riau',
  'Lampung',
  'Maluku',
  'Maluku Utara',
  'Nusa Tenggara Barat',
  'Nusa Tenggara Timur',
  'Papua',
  'Papua Barat',
  'Papua Barat Daya',
  'Papua Pegunungan',
  'Papua Selatan',
  'Papua Tengah',
  'Riau',
  'Sulawesi Barat',
  'Sulawesi Selatan',
  'Sulawesi Tengah',
  'Sulawesi Tenggara',
  'Sulawesi Utara',
  'Sumatera Barat',
  'Sumatera Selatan',
  'Sumatera Utara',
]

export type PilotRequest = {
  lenderName: string
  lenderType: LenderType
  province: string
  filesPerMonth: number
  contactName: string
  email: string | null
  whatsapp: string | null
  consent: boolean
}

export type PilotRequestSaved = { id: string; replyBy: 'email' | 'whatsapp' }

export function sendPilotRequest(request: PilotRequest): Promise<PilotRequestSaved> {
  return apiFetch<PilotRequestSaved>('/api/pilot-requests', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
}
