import { useState } from 'react'
import { Link } from 'react-router-dom'
import { downloadExport, fieldVisitUrl } from '../../integrations.ts'
import type { CreditFileData } from '../../types.ts'

// Ways to take the credit file out of LedgerLens: downloads for the lender's systems, a printed
// memo, and a field visit in the officer's calendar with what to check on site.
export default function HandOff({ id, file }: { id: string; file: CreditFileData }) {
  const [busy, setBusy] = useState<'json' | 'csv' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [printed] = useState(() => new Date().toLocaleDateString('en-GB', { dateStyle: 'long' }))
  const link = `${window.location.origin}/app/${id}`

  async function download(format: 'json' | 'csv') {
    setBusy(format)
    setError(null)
    try {
      await downloadExport(id, format)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(null)
  }

  return (
    <>
      <section className="handoff" aria-labelledby="handoff-heading">
        <h2 id="handoff-heading" className="visually-hidden">
          Take this file elsewhere
        </h2>
        <button
          type="button"
          className="button quiet"
          disabled={busy !== null}
          onClick={() => download('csv')}
        >
          {busy === 'csv' ? 'Preparing…' : 'Download CSV (Excel, Sheets)'}
        </button>
        <button
          type="button"
          className="button quiet"
          disabled={busy !== null}
          onClick={() => download('json')}
        >
          {busy === 'json' ? 'Preparing…' : 'Download JSON'}
        </button>
        <button type="button" className="button quiet" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
        <a
          className="button quiet"
          href={fieldVisitUrl(file, link)}
          target="_blank"
          rel="noopener noreferrer"
        >
          Schedule a field visit
          <span className="visually-hidden"> (opens Google Calendar in a new tab)</span>
        </a>
        <Link className="handoff-link" to="/app/integrations">
          Send decisions to your spreadsheet
        </Link>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>
      <p className="print-only print-meta">
        Printed from LedgerLens on {printed}. Figures are computed by code from the evidence;
        every finding cites where it was read. {link}
      </p>
    </>
  )
}
