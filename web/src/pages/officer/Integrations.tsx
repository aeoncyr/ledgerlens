import { useEffect, useState } from 'react'
import {
  APPS_SCRIPT,
  EVENT_LABEL,
  SAMPLE_BODY,
  getLenderSettings,
  saveLenderSettings,
  sendTest,
  type LenderSettings,
  type WebhookKind,
} from '../../integrations.ts'
import OfficerShell from './OfficerShell.tsx'

const KINDS: [WebhookKind, string, string][] = [
  ['sheets', 'Google Sheets', 'A row in your loan-book spreadsheet'],
  ['generic', 'Another app', 'Zapier, Make, n8n or your own system'],
]

const when = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' })

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button type="button" className="button quiet" onClick={copy}>
      <span aria-live="polite">{copied ? 'Copied' : label}</span>
    </button>
  )
}

function Deliveries({ settings }: { settings: LenderSettings }) {
  if (settings.recentDeliveries.length === 0) {
    return <p className="fine">Nothing sent yet. Save an address and send a test row.</p>
  }
  return (
    <div className="table-scroll">
      <table className="register deliveries">
        <thead>
          <tr>
            <th scope="col">Sent</th>
            <th scope="col">Event</th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          {settings.recentDeliveries.map((d, index) => (
            <tr key={`${d.at}-${index}`}>
              <td>{when.format(new Date(d.at))}</td>
              <td>{EVENT_LABEL[d.event] ?? d.event}</td>
              <td className={d.ok ? 'within' : 'outside'}>
                {d.ok ? 'Delivered' : (d.error ?? 'Not delivered')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// The officer connects LedgerLens to the tools their lender already uses. Most BPRs and koperasi
// keep their loan book in a spreadsheet, so Google Sheets comes first and needs no developer.
export default function Integrations() {
  const [settings, setSettings] = useState<LenderSettings | null>(null)
  const [kind, setKind] = useState<WebhookKind>('sheets')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState<'save' | 'test' | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    getLenderSettings()
      .then((loaded) => {
        setSettings(loaded)
        setKind(loaded.kind)
        setUrl(loaded.webhookUrl ?? '')
      })
      .catch((e: Error) => setMessage({ ok: false, text: e.message }))
  }, [])

  async function save(event: { preventDefault(): void }, address = url) {
    event.preventDefault()
    setBusy('save')
    setMessage(null)
    try {
      const saved = await saveLenderSettings(address.trim(), kind)
      setSettings(saved)
      setUrl(saved.webhookUrl ?? '')
      setMessage({
        ok: true,
        text: saved.webhookUrl ? 'Saved. Send a test row to check it works.' : 'Stopped sending.',
      })
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) })
    }
    setBusy(null)
  }

  async function test() {
    setBusy('test')
    setMessage(null)
    try {
      const delivery = await sendTest()
      setMessage(
        delivery.ok
          ? { ok: true, text: 'Test sent. Look for it in your sheet or app.' }
          : { ok: false, text: delivery.error ?? 'The test was not delivered.' },
      )
      setSettings(await getLenderSettings())
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) })
    }
    setBusy(null)
  }

  const saved = Boolean(settings?.webhookUrl) && settings?.webhookUrl === url.trim()
  const sheets = kind === 'sheets'

  return (
    <OfficerShell title="Integrations" crumbs={<> / Integrations</>}>
      <p className="lead-text">
        Send each step of a loan to the place your team already keeps its loan book. LedgerLens
        sends an update when you recommend or finalise a decision, when the owner accepts or
        declines an offer, when a condition is met, and when the owner sends records you asked for.
      </p>

      <section className="integration" aria-labelledby="where-heading">
        <h2 id="where-heading">Where should updates go?</h2>
        <div className="choice-row">
          {KINDS.map(([key, label, hint]) => (
            <button
              key={key}
              type="button"
              className={`choice ${kind === key ? 'chosen' : ''}`}
              aria-pressed={kind === key}
              onClick={() => {
                setKind(key)
                setMessage(null)
              }}
            >
              {label}
              <span>{hint}</span>
            </button>
          ))}
        </div>

        {sheets ? (
          <ol className="setup-steps">
            <li>
              <h3>Paste the script into your spreadsheet</h3>
              <p>
                Open your loan-book spreadsheet in Google Sheets and choose{' '}
                <strong>Extensions → Apps Script</strong>. Delete what is in the editor, paste the
                script below, and press <strong>Save</strong>.
              </p>
              <div className="code-block">
                <CopyButton text={APPS_SCRIPT} label="Copy the script" />
                <pre tabIndex={0} aria-label="Apps Script for Google Sheets">
                  <code>{APPS_SCRIPT}</code>
                </pre>
              </div>
            </li>
            <li>
              <h3>Deploy it as a web app</h3>
              <p>
                Choose <strong>Deploy → New deployment</strong>, click the gear next to “Select
                type” and pick <strong>Web app</strong>. Set “Execute as” to <strong>Me</strong> and
                “Who has access” to <strong>Anyone</strong>, then press Deploy. The first time,
                Google asks you to allow the script to edit your spreadsheet; allow it.
              </p>
            </li>
            <li>
              <h3>Paste the web app URL here</h3>
              <p>
                Copy the <strong>Web app URL</strong> that Google shows (it ends in{' '}
                <code>/exec</code>), paste it below and save. Then send a test row: a tab called
                “LedgerLens” appears in your spreadsheet with the first row.
              </p>
            </li>
          </ol>
        ) : (
          <div className="setup-generic">
            <p>
              Paste a webhook address from <strong>Zapier</strong> (Webhooks by Zapier, Catch
              Hook), <strong>Make</strong> (Custom webhook), <strong>n8n</strong> (Webhook node) or
              your own system. LedgerLens posts JSON like this, one request per update:
            </p>
            <pre tabIndex={0} aria-label="Example of what LedgerLens sends" className="code-sample">
              <code>{JSON.stringify(SAMPLE_BODY, null, 2)}</code>
            </pre>
            {settings?.secret && (
              <p className="fine">
                To check a request came from LedgerLens, compute the HMAC-SHA256 of the body with
                your signing secret <code className="mono">{settings.secret}</code> and compare it
                with the <code>X-LedgerLens-Signature</code> header (<code>sha256=…</code>).
              </p>
            )}
          </div>
        )}

        <form className="webhook-form" onSubmit={save}>
          <label>
            {sheets ? 'Web app URL' : 'Webhook URL'}
            <input
              type="url"
              inputMode="url"
              required
              placeholder={
                sheets ? 'https://script.google.com/macros/s/…/exec' : 'https://hooks.zapier.com/…'
              }
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                setMessage(null)
              }}
            />
          </label>
          <div className="form-actions">
            <button className="button" disabled={busy !== null || !url.trim()}>
              {busy === 'save' ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className="button quiet"
              disabled={busy !== null || !saved}
              onClick={test}
            >
              {busy === 'test' ? 'Sending…' : sheets ? 'Send a test row' : 'Send a test'}
            </button>
            {settings?.webhookUrl && (
              <button
                type="button"
                className="button quiet"
                disabled={busy !== null}
                onClick={(e) => save(e, '')}
              >
                Stop sending
              </button>
            )}
          </div>
          {message && (
            <p className={message.ok ? 'notice' : 'error'} role="status">
              {message.text}
            </p>
          )}
          <p className="fine">
            LedgerLens only sends to public https addresses, waits at most five seconds, and never
            lets a failed delivery hold up a loan. Updates carry the business alias, never the
            owner’s name.
          </p>
        </form>
      </section>

      <section className="integration" aria-labelledby="sent-heading">
        <h2 id="sent-heading">Recently sent</h2>
        {settings ? <Deliveries settings={settings} /> : <p className="fine">Loading…</p>}
      </section>

      <section className="integration" aria-labelledby="file-heading">
        <h2 id="file-heading">On every credit file</h2>
        <p>
          Open an application to download it as CSV (for Excel or Sheets) or JSON (for your loan
          system), print it or save it as a PDF memo, and put a field visit in Google Calendar
          with a list of what to check on site.
        </p>
      </section>
    </OfficerShell>
  )
}
