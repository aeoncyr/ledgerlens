import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ensureSignedIn } from '../../firebase.ts'
import { STATUS_LABEL, useApplications } from '../../officer.ts'
import { ASSESSMENT_LABEL, ASSESSMENT_TONE } from '../../types.ts'
import OfficerShell from './OfficerShell.tsx'

const rupiah = new Intl.NumberFormat('id-ID')

export default function Applications() {
  const [uid, setUid] = useState<string | null>(null)
  useEffect(() => {
    ensureSignedIn().then((user) => setUid(user.uid))
  }, [])
  const { data: applications, loading, error } = useApplications(uid)
  const navigate = useNavigate()
  const [code, setCode] = useState('')

  function openShared(event: FormEvent) {
    event.preventDefault()
    const clean = code.trim().split('/').pop() ?? ''
    if (clean) navigate(`/app/shared/${clean}`)
  }

  return (
    <OfficerShell title="Applications">
      <div className="page-actions">
        <Link className="button" to="/app/new">
          New application
        </Link>
        <form className="share-open" onSubmit={openShared}>
          <label htmlFor="share-code">A business owner shared a file with you?</label>
          <input
            id="share-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Share code or link"
          />
          <button className="button quiet" disabled={!code.trim()}>
            Open
          </button>
        </form>
      </div>
      <p className="fine">
        Each visitor has a private workspace, so your applications are visible only to you.
      </p>
      {error && <p className="error">Could not load applications: {error}</p>}
      {loading && <p className="fine">Loading…</p>}
      {!loading && applications.length === 0 && (
        <div className="empty">
          <p>No applications yet.</p>
          <p className="fine">
            Start one for a fictional business, or open one of the{' '}
            <Link to="/#samples">finished sample files</Link>.
          </p>
        </div>
      )}
      {applications.length > 0 && (
        <div className="table-scroll">
          <table className="register">
            <thead>
              <tr>
                <th scope="col">Business</th>
                <th scope="col" className="num">
                  Requested
                </th>
                <th scope="col">Status</th>
                <th scope="col">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((app) => (
                <tr key={app.id}>
                  <th scope="row">
                    <Link to={`/app/${app.id}`}>{app.business.alias}</Link>
                    <span className="sub">
                      {app.business.type}, {app.business.city}
                      {app.origin === 'owner' && <span className="tag owner-tag">Shared by owner</span>}
                      {app.demo && <span className="tag">Demo story</span>}
                    </span>
                  </th>
                  <td className="num" data-label="Requested">
                    Rp {rupiah.format(app.request.amount)}
                    <span className="sub">{app.request.tenorMonths} months</span>
                  </td>
                  <td data-label="Status">{STATUS_LABEL[app.status]}</td>
                  <td data-label="Outcome">
                    {app.assessment ? (
                      <span className={`outcome ${ASSESSMENT_TONE[app.assessment]}`}>
                        {ASSESSMENT_LABEL[app.assessment]}
                      </span>
                    ) : (
                      <span className="fine">Not analysed</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </OfficerShell>
  )
}
