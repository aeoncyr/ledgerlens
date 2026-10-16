// A lender's officer opens a file a business owner shared with them, then sees it like any other.
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../../api.ts'
import OfficerShell from './OfficerShell.tsx'

export default function OpenShared() {
  const { code = '' } = useParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ applicationId: string }>(`/api/shared/${encodeURIComponent(code)}`, {
      method: 'POST',
    })
      .then(({ applicationId }) => navigate(`/app/${applicationId}`, { replace: true }))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [code, navigate])

  return (
    <OfficerShell title="Opening a shared file" crumbs={<> / Shared file</>}>
      {error ? (
        <>
          <p className="error">{error}</p>
          <p>
            Ask the business owner for a new link, or go back to your{' '}
            <Link to="/app">applications</Link>.
          </p>
        </>
      ) : (
        <p className="fine">Opening the file the owner shared with you…</p>
      )}
    </OfficerShell>
  )
}
