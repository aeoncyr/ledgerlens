import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Landing from './pages/Landing.tsx'

// Pages that use Firebase load on demand, so the landing page stays small and fast.
const Status = lazy(() => import('./pages/Status.tsx'))
const SampleFile = lazy(() => import('./pages/SampleFile.tsx'))
// The officer's workspace uses Firebase, so it loads only when opened.
const Applications = lazy(() => import('./pages/officer/Applications.tsx'))
const NewApplication = lazy(() => import('./pages/officer/NewApplication.tsx'))
const Consent = lazy(() => import('./pages/officer/Consent.tsx'))
const Evidence = lazy(() => import('./pages/officer/Evidence.tsx'))
const ApplicationFile = lazy(() => import('./pages/officer/ApplicationFile.tsx'))
const OpenShared = lazy(() => import('./pages/officer/OpenShared.tsx'))

export default function App() {
  return (
    <Suspense fallback={<main className="container section">Loading…</main>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/status" element={<Status />} />
        <Route path="/samples/:slug" element={<SampleFile />} />
        <Route path="/app" element={<Applications />} />
        <Route path="/app/new" element={<NewApplication />} />
        <Route path="/app/:id" element={<ApplicationFile />} />
        <Route path="/app/:id/consent" element={<Consent />} />
        <Route path="/app/:id/evidence" element={<Evidence />} />
        <Route path="/app/shared/:code" element={<OpenShared />} />
        <Route path="*" element={<Landing />} />
      </Routes>
    </Suspense>
  )
}
