// A small client for the LedgerLens API. Requests go to /api on the same origin, which Firebase
// Hosting forwards to Cloud Run; locally, Vite forwards /api to the dev server on port 8080.
import { ensureSignedIn } from './firebase'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}, base = BASE): Promise<T> {
  const user = await ensureSignedIn()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${await user.getIdToken()}`)
  const response = await fetch(`${base}${path}`, { ...init, headers })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? response.statusText)
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

export interface Health {
  ok: boolean
  version: string
  model: string
}

export async function getHealth(): Promise<Health> {
  const response = await fetch(`${BASE}/api/health`)
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return (await response.json()) as Health
}
