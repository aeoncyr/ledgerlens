// "Delete my file": the owner removes the file for good, as Indonesia's personal data protection
// law (UU PDP) lets them. The API refuses while the lender is deciding or once a loan offer is
// accepted; the card says so up front instead of offering a button that would fail.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { OwnerStrings } from '../../i18n/owner.ts'
import { deleteFile, errorText } from '../../owner.ts'

export default function DeleteFile({
  id,
  blocked,
  t,
}: {
  id: string
  // Why the file can't be deleted right now, in plain words, or null when it can.
  blocked: string | null
  t: OwnerStrings
}) {
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      await deleteFile(id)
      navigate('/owner', { replace: true })
    } catch (e) {
      setError(errorText(e))
      setBusy(false)
    }
  }

  return (
    <section className="ow-card ow-delete" aria-labelledby="ow-delete-title">
      <h2 id="ow-delete-title" className="ow-h3">
        {t.deleteTitle}
      </h2>
      <p className="ow-fine">{t.deleteLead}</p>
      {blocked ? (
        <p className="ow-fine ow-delete-blocked">{blocked}</p>
      ) : !confirming ? (
        <button
          type="button"
          className="ow-button ow-button-danger"
          onClick={() => setConfirming(true)}
        >
          {t.deleteButton}
        </button>
      ) : (
        <div className="ow-confirm" role="alertdialog" aria-labelledby="ow-delete-q">
          <p id="ow-delete-q">{t.deleteConfirm}</p>
          <div className="ow-share-actions">
            <button
              type="button"
              className="ow-button ow-button-danger"
              onClick={() => void remove()}
              disabled={busy}
            >
              {busy ? t.deleting : t.deleteYes}
            </button>
            <button
              type="button"
              className="ow-button ow-button-quiet"
              onClick={() => setConfirming(false)}
              disabled={busy}
            >
              {t.deleteNo}
            </button>
          </div>
        </div>
      )}
      {error && (
        <p className="ow-error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
