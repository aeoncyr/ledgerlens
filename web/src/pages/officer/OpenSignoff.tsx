// A second person at the lender opens an officer's recommendation to sign it off, then sees the
// file read-only with the sign-off panel.
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { claimSignoff } from '../../decision.ts'
import OfficerShell from './OfficerShell.tsx'

export default function OpenSignoff() {
  const { code = '' } = useParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    claimSignoff(code)
      .then((applicationId) => navigate(`/app/${applicationId}`, { replace: true }))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [code, navigate])

  return (
    <OfficerShell title="Opening a decision to sign off" crumbs={<> / Sign-off</>}>
      {error ? (
        <>
          <p className="error">{error}</p>
          <p>
            Ask the officer who sent the link for a new one, or go back to your{' '}
            <Link to="/app">applications</Link>.
          </p>
        </>
      ) : (
        <p className="fine">Opening the recommendation for your sign-off…</p>
      )}
    </OfficerShell>
  )
}
