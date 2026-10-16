// Hand-offs from LedgerLens to the lender's own tools: a webhook into their Google Sheet (or
// Zapier, Make, n8n), downloads of the credit file, and a field visit in Google Calendar.
import { apiFetch, ApiError } from './api.ts'
import { ensureSignedIn } from './firebase.ts'
import { EVIDENCE_LABEL, type CreditFileData, type EvidenceType } from './types.ts'

export type WebhookKind = 'sheets' | 'generic'

export type Delivery = {
  event: string
  applicationId: string | null
  ok: boolean
  status: number | null
  error: string | null
  ms: number | null
  at: string
}

export type LenderSettings = {
  webhookUrl: string | null
  kind: WebhookKind
  secret: string | null
  recentDeliveries: Delivery[]
}

export function getLenderSettings(): Promise<LenderSettings> {
  return apiFetch<LenderSettings>('/api/lender/settings')
}

export function saveLenderSettings(webhookUrl: string, kind: WebhookKind): Promise<LenderSettings> {
  return apiFetch<LenderSettings>('/api/lender/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ webhookUrl, kind }),
  })
}

export function sendTest(): Promise<Delivery> {
  return apiFetch<Delivery>('/api/lender/test', { method: 'POST' })
}

/** Download the credit file as JSON or CSV; the API needs the sign-in token, so no plain link. */
export async function downloadExport(id: string, format: 'json' | 'csv'): Promise<void> {
  const user = await ensureSignedIn()
  const base = import.meta.env.VITE_API_BASE ?? ''
  const response = await fetch(`${base}/api/applications/${id}/export.${format}`, {
    headers: { Authorization: `Bearer ${await user.getIdToken()}` },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? response.statusText)
  }
  const name =
    /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1] ??
    `ledgerlens-${id}.${format}`
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// --- Google Calendar -----------------------------------------------------------------------------

// What an officer can do on site when a kind of evidence is missing from the file.
const ON_SITE: Record<EvidenceType, string> = {
  shop_photo: 'No shop photo yet: photograph the shop front, the stock and the price list',
  receipt: 'No receipts yet: ask to see recent supplier receipts and photograph them',
  ledger_page: 'No notebook pages yet: photograph the sales notebook for the last three months',
  qris_history: 'No QRIS history yet: ask the owner to open the QRIS app and show the last 90 days',
  interview_audio: 'No interview yet: record a short talk with the owner about sales and costs',
}

function shorten(text: string, length = 180): string {
  return text.length > length ? `${text.slice(0, length - 1).trimEnd()}…` : text
}

function stamp(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `T${pad(date.getHours())}${pad(date.getMinutes())}00`
  )
}

/** The next working day, 10:00 to 11:00, as a starting point the officer can move. */
function nextVisitSlot(now = new Date()): [Date, Date] {
  const start = new Date(now)
  start.setDate(start.getDate() + 1)
  while (start.getDay() === 0 || start.getDay() === 6) start.setDate(start.getDate() + 1)
  start.setHours(10, 0, 0, 0)
  const end = new Date(start)
  end.setHours(11)
  return [start, end]
}

/** What to verify on site, drawn from the file: open findings first, then evidence not yet seen. */
export function visitChecklist(file: CreditFileData): string[] {
  const items: string[] = []
  for (const finding of file.findings) {
    if (finding.resolved || finding.severity === 'low') continue
    const cited = finding.citations[0]
    const item = cited && file.evidence.find((e) => e.id === cited.evidenceId)
    const source = item ? (item.reading?.label ?? EVIDENCE_LABEL[item.type]) : null
    const where = cited ? ` (see ${source ? `${source}, ` : ''}${cited.locator})` : ''
    items.push(shorten(finding.text) + where)
  }
  const seen = new Set(file.evidence.map((e) => e.type))
  for (const type of Object.keys(ON_SITE) as EvidenceType[]) {
    if (!seen.has(type)) items.push(ON_SITE[type])
  }
  return items.slice(0, 10)
}

export function fieldVisitUrl(file: CreditFileData, fileLink: string, now = new Date()): string {
  const app = file.application
  const checklist = visitChecklist(file)
  const steps = file.memo.officerNextSteps.slice(0, 3)
  const amount = app.amount.toLocaleString('id-ID')
  const details = [
    `${app.alias}: ${app.businessType}, ${app.city}.`,
    `Requests Rp ${amount} over ${app.tenorMonths} months.`,
    '',
    'What to verify on site:',
    ...(checklist.length
      ? checklist.map((item) => `• ${item}`)
      : ['• Nothing open; confirm the shop and the owner.']),
    ...(steps.length
      ? ['', 'Next steps from the credit memo:', ...steps.map((s) => `• ${shorten(s)}`)]
      : []),
    '',
    `Credit file: ${fileLink}`,
  ].join('\n')
  const [start, end] = nextVisitSlot(now)
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: `Field visit: ${app.alias}`,
    details: details.slice(0, 1800),
    location: `${app.alias}, ${app.city}`,
    dates: `${stamp(start)}/${stamp(end)}`,
    ctz: 'Asia/Jakarta',
  })
  return `https://calendar.google.com/calendar/render?${params.toString()}`
}

// --- Google Sheets -------------------------------------------------------------------------------

// Pasted by the lender into their Sheet's Apps Script editor and deployed as a web app.
export const APPS_SCRIPT = `// LedgerLens: adds one row to this spreadsheet for every loan event.
// Paste into Extensions > Apps Script, save, then Deploy > New deployment > Web app.

var HEADERS = ['Received', 'Event', 'Business', 'Action', 'Amount (Rp)',
  'Tenor (months)', 'Instalment (Rp)', 'Reason', 'Link'];

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var data = JSON.parse(e.postData.contents);
    var book = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = book.getSheetByName('LedgerLens') || book.insertSheet('LedgerLens');
    if (sheet.getLastRow() === 0) sheet.appendRow(HEADERS);
    sheet.appendRow([
      new Date(), cell(data.event), cell(data.alias), cell(data.action),
      cell(data.amountRp), cell(data.tenorMonths), cell(data.instalmentRp),
      cell(data.reason), cell(data.link)
    ]);
    return reply({ ok: true, row: sheet.getLastRow() });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

// Text that looks like a formula is stored as text.
function cell(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string' && /^[=+\\-@]/.test(value)) return "'" + value;
  return value;
}

function reply(body) {
  return ContentService.createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}
`

// What a generic webhook receives, for the officer setting up Zapier, Make or n8n.
export const SAMPLE_BODY = {
  event: 'decision.final',
  sentAt: '2026-10-17T09:00:00+00:00',
  at: '2026-10-17T08:59:58+00:00',
  applicationId: 'abc123',
  alias: 'Warung Bu Sari',
  action: 'approve',
  reason: 'QRIS inflows cover the instalment with room to spare.',
  amountRp: 10000000,
  tenorMonths: 12,
  annualRatePct: 6,
  instalmentRp: 860664,
  link: 'https://ledger-lens-511708.web.app/app/abc123',
  data: { '…': 'the full event, including the offer and its schedule' },
}

export const EVENT_LABEL: Record<string, string> = {
  test: 'Test row',
  'decision.recommended': 'Decision recommended',
  'decision.final': 'Decision final',
  'offer.accepted': 'Offer accepted',
  'offer.declined': 'Offer declined',
  'condition.met': 'Condition met',
  'evidence.requested_received': 'Requested records sent',
}
