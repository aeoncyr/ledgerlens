import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CONSENT_VERSION, recordConsent, useApplication } from '../../officer.ts'
import OfficerShell from './OfficerShell.tsx'

// Plain-language consent, read to the owner before anything is captured. It says only what the
// prototype actually does.
export default function Consent() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { data: app } = useApplication(id)
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function decide(given: boolean) {
    setBusy(true)
    setError(null)
    try {
      await recordConsent(id, given)
      navigate(given ? `/app/${id}/evidence` : '/app')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  const alias = app?.business.alias ?? 'this business'
  return (
    <OfficerShell
      title="The owner’s consent"
      crumbs={
        <>
          {' '}
          / <Link to={`/app/${id}`}>{alias}</Link> / Consent
        </>
      }
    >
      <p className="lead-text">
        Read this to the owner, in Bahasa Indonesia, before taking any photo or recording.
      </p>
      <div className="consent">
        <section lang="id" aria-labelledby="consent-id">
          <h2 id="consent-id">Persetujuan pemilik usaha</h2>
          <p>
            Untuk menilai pengajuan pinjaman {alias}, petugas akan memotret buku catatan, riwayat
            QRIS, nota belanja dan tempat usaha, serta merekam wawancara singkat.
          </p>
          <p>
            Catatan disimpan di pusat data Google Cloud di Jakarta. Foto dan rekaman disimpan di
            Amerika Serikat. Isinya dibaca oleh Gemini, kecerdasan buatan milik Google.
          </p>
          <p>
            Hasilnya membantu petugas, bukan memutuskan. Keputusan selalu diambil oleh petugas
            kredit, dengan alasan tertulis. Bapak/Ibu boleh menarik persetujuan ini kapan saja.
          </p>
        </section>
        <section lang="en" aria-labelledby="consent-en">
          <h2 id="consent-en">The owner’s consent</h2>
          <p>
            To assess {alias}’s loan application, the officer will photograph the notebook, QRIS
            history, supplier receipts and the shop, and record a short interview.
          </p>
          <p>
            Records are stored in Google Cloud’s Jakarta region. Photos and recordings are stored in
            the United States. Their contents are read by Gemini, Google’s AI.
          </p>
          <p>
            The result helps the officer; it does not decide. A credit officer always makes the
            decision, with a written reason. The owner may withdraw this consent at any time.
          </p>
        </section>
      </div>
      <label className="check">
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        The owner has heard this and agrees.
      </label>
      {error && <p className="error">{error}</p>}
      <div className="page-actions">
        <button className="button" disabled={!agreed || busy} onClick={() => decide(true)}>
          Record consent and continue
        </button>
        <button className="button quiet" disabled={busy} onClick={() => decide(false)}>
          The owner declines
        </button>
      </div>
      <p className="fine">Consent text version {CONSENT_VERSION}. The time is recorded with it.</p>
    </OfficerShell>
  )
}
