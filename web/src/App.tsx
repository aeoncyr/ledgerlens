import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Landing from './pages/Landing.tsx'

// Pages that use Firebase load on demand, so the landing page stays small and fast.
const Status = lazy(() => import('./pages/Status.tsx'))
const SampleFile = lazy(() => import('./pages/SampleFile.tsx'))

export default function App() {
  return (
    <Suspense fallback={<main className="container section">Loading…</main>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/status" element={<Status />} />
        <Route path="/samples/:slug" element={<SampleFile />} />
        <Route path="*" element={<Landing />} />
      </Routes>
    </Suspense>
  )
}
