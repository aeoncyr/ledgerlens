// The ledger reader's real output for the synthetic page in public/specimen, as returned by
// gemini-3.8-flash during the handwriting test on 2026-10-15 (prompt variant 0). Amounts in rupiah were
// parsed from amountText by code, not by the model.
export type SpecimenLine = {
  line: number
  date: string | null
  description: string
  written: string | null
  rupiah: number | null
  kind: 'sale' | 'purchase' | 'receivable' | 'expense' | 'other'
}

export const SPECIMEN_MODEL = 'gemini-3.8-flash'

export const SPECIMEN_LINES: SpecimenLine[] = [
  { line: 1, date: null, description: 'Sep - minggu 1', written: null, rupiah: null, kind: 'other' },
  { line: 2, date: '1/9', description: 'laku', written: 'Rp 585.000', rupiah: 585000, kind: 'sale' },
  { line: 3, date: '2/9', description: 'jual', written: '510rb', rupiah: 510000, kind: 'sale' },
  { line: 4, date: null, description: 'kulakan minyak', written: '2.9jt', rupiah: 2900000, kind: 'purchase' },
  { line: 5, date: '3/9', description: 'jual', written: '535rb', rupiah: 535000, kind: 'sale' },
  { line: 6, date: '4/9', description: 'jual + pulsa', written: '540rb', rupiah: 540000, kind: 'sale' },
  { line: 7, date: '5/9', description: 'Sabtu pasar', written: '2.1jt', rupiah: 2100000, kind: 'sale' },
  { line: 8, date: '6/9', description: 'jual + pulsa', written: '675.000', rupiah: 675000, kind: 'sale' },
  { line: 9, date: '7/9', description: 'jual', written: '575 rb', rupiah: 575000, kind: 'sale' },
  { line: 10, date: null, description: 'Sep - minggu 2', written: null, rupiah: null, kind: 'other' },
  { line: 11, date: '8/9', description: 'jual + pulsa', written: '490rb', rupiah: 490000, kind: 'sale' },
  { line: 12, date: '9/9', description: 'jual', written: '580rb', rupiah: 580000, kind: 'sale' },
  { line: 13, date: null, description: 'kasbon Bu Tini', written: '50rb', rupiah: 50000, kind: 'receivable' },
  { line: 14, date: '10/9', description: 'laku', written: '575rb', rupiah: 575000, kind: 'sale' },
  { line: 15, date: '11/9', description: 'jual', written: '570 rb', rupiah: 570000, kind: 'sale' },
  { line: 16, date: '12/9', description: 'Sabtu pasar', written: '2,3 jt', rupiah: 2300000, kind: 'sale' },
  { line: 17, date: null, description: 'kulakan minyak', written: '2,9jt', rupiah: 2900000, kind: 'purchase' },
  { line: 18, date: '13/9', description: 'jual', written: 'Rp 535.000', rupiah: 535000, kind: 'sale' },
  { line: 19, date: '14/9', description: 'laku', written: 'Rp 585.000', rupiah: 585000, kind: 'sale' },
  { line: 20, date: null, description: 'bayar arisan', written: '200rb', rupiah: 200000, kind: 'expense' },
]

// The page's true amounts are known because the page was generated; the reader matched all of them.
export const SPECIMEN_TRUE_AMOUNTS = 18
export const SPECIMEN_MATCHED = 18
