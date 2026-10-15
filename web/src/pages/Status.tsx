// A small diagnostics page: is the API reachable, and does anonymous sign-in work?
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHealth, type Health } from '../api.ts'
import { ensureSignedIn } from '../firebase.ts'

type Check<T> = { state: 'loading' } | { state: 'ok'; value: T } | { state: 'error'; error: string }

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export default function Status() {
  const [health, setHealth] = useState<Check<Health>>({ state: 'loading' })
  const [user, setUser] = useState<Check<string>>({ state: 'loading' })

  useEffect(() => {
    getHealth()
      .then((value) => setHealth({ state: 'ok', value }))
      .catch((error: unknown) => setHealth({ state: 'error', error: describe(error) }))
    ensureSignedIn()
      .then((signedIn) => setUser({ state: 'ok', value: signedIn.uid }))
      .catch((error: unknown) => setUser({ state: 'error', error: describe(error) }))
  }, [])

  return (
    <main className="container section">
      <h2>System status</h2>
      <ul className="status-list">
        <li>
          <span>API</span>
          <span className="mono">
            {health.state === 'loading' && 'Checking…'}
            {health.state === 'ok' && `Online · v${health.value.version} · ${health.value.model}`}
            {health.state === 'error' && `Unavailable · ${health.error}`}
          </span>
        </li>
        <li>
          <span>Anonymous sign-in</span>
          <span className="mono">
            {user.state === 'loading' && 'Signing in…'}
            {user.state === 'ok' && `Signed in · ${user.value}`}
            {user.state === 'error' && `Failed · ${user.error}`}
          </span>
        </li>
      </ul>
      <p className="note">
        <Link to="/">Back to LedgerLens</Link>
      </p>
    </main>
  )
}
