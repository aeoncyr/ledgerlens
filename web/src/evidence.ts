// Small helpers for reading what was extracted from a piece of evidence, shared by the evidence
// viewer and the citation previews.
import type { EvidenceItem } from './types.ts'

export type Row = Record<string, unknown>

const rupiahFormat = new Intl.NumberFormat('id-ID')

export function money(value: unknown): string {
  return typeof value === 'number' ? rupiahFormat.format(value) : '—'
}

export function rowsOf(reading: Row | null, key: string): Row[] {
  const value = reading?.[key]
  return Array.isArray(value) ? (value as Row[]) : []
}

// The number in a locator such as "line 4" or "row 2", to find that row.
export function locatedNumber(locator: string | null, word: string): number | null {
  const match = locator?.match(new RegExp(`${word} (\\d+)`))
  return match ? Number(match[1]) : null
}

// Does a QRIS total match the locator: "total…", or the period itself ("August 2026")?
export function isLocatedTotal(locator: string | null, periodText: unknown): boolean {
  if (!locator) return false
  return locator.startsWith('total') || (typeof periodText === 'string' && periodText === locator)
}

export type Excerpt = {
  // What is written or said at the locator, as read.
  text: string
  // The language of `text` when it is quoted from the owner's records.
  lang?: string
  // A translation or a short explanation, in English.
  note?: string
  // The amount read there, already formatted.
  amount?: string
}

function str(value: unknown): string {
  return value == null ? '' : String(value)
}

// An amount as written and as read: "1,7jt → Rp 1.700.000", or just "Rp 300.000" when the
// writing already says it.
function asRead(written: unknown, rupiah: unknown): string {
  const text = str(written)
  const plain = `Rp ${money(rupiah)}`
  if (!text || text.replace(/\D/g, '') === String(rupiah)) return plain
  return `${text} → ${plain}`
}

// What the reader extracted at one locator of one piece of evidence, for a short preview.
export function excerptAt(item: EvidenceItem, locator: string | null): Excerpt | null {
  const reading = item.reading
  if (!reading) return null

  if (item.type === 'ledger_page') {
    const n = locatedNumber(locator, 'line')
    const line = rowsOf(reading, 'lines').find((l) => l.line === n)
    if (!line) return null
    return {
      text: `“${str(line.description)}”`,
      lang: 'id',
      note: line.dateText && line.dateText !== line.description ? `Dated ${str(line.dateText)}` : undefined,
      amount: line.amountText ? asRead(line.amountText, line.amountRp) : undefined,
    }
  }

  if (item.type === 'receipt') {
    const merchant = str(reading.merchant) || 'Supplier receipt'
    if (locator?.startsWith('item')) {
      const items = rowsOf(reading, 'items')
      return {
        text: merchant,
        note: `${items.length} item${items.length === 1 ? '' : 's'}${reading.dateText ? `, dated ${str(reading.dateText)}` : ''}`,
        amount: `Items add up to Rp ${money(reading.itemsSumRp)}`,
      }
    }
    return {
      text: merchant,
      note: reading.dateText ? `Dated ${str(reading.dateText)}` : undefined,
      amount: `Total ${asRead(reading.totalText, reading.totalRp)}`,
    }
  }

  if (item.type === 'qris_history') {
    const n = locatedNumber(locator, 'row')
    if (n !== null) {
      const row = rowsOf(reading, 'rows').find((r) => r.row === n)
      if (row) {
        return {
          text: `${str(row.label) || 'Payment'}, ${str(row.dateText)} ${str(row.timeText)}`.trim(),
          amount: `Rp ${money(row.amountRp)}`,
        }
      }
    }
    const totals = rowsOf(reading, 'totals')
    const total = totals.find((t) => isLocatedTotal(locator, t.periodText)) ?? totals[0]
    if (!total) return null
    return {
      text: `Total for ${str(total.periodText)}`,
      note: [str(reading.appName), total.count ? `${str(total.count)} payments` : '']
        .filter(Boolean)
        .join(' · '),
      amount: `Rp ${money(total.amountRp)}`,
    }
  }

  if (item.type === 'interview_audio') {
    const claim = rowsOf(reading, 'claims').find((c) => c.timeText === locator)
    if (!claim) return null
    return {
      text: `“${str(claim.quote)}”`,
      lang: 'id',
      note: str(claim.statementEn) || undefined,
      amount: claim.amountRp == null ? undefined : `Rp ${money(claim.amountRp)}${claim.period ? ` a ${str(claim.period)}` : ''}`,
    }
  }

  if (item.type === 'shop_photo') {
    const first = rowsOf(reading, 'observations')[0]
    return first ? { text: str(first) } : null
  }

  return null
}
