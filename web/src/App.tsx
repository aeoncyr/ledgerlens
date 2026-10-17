import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Landing from './pages/Landing.tsx'

// Pages that use Firebase load on demand, so the landing page stays small and fast.
const Status = lazy(() => import('./pages/Status.tsx'))
const SampleFile = lazy(() => import('./pages/SampleFile.tsx'))
const HowItWorks = lazy(() => import('./pages/HowItWorks.tsx'))
const Trust = lazy(() => import('./pages/Trust.tsx'))
const Lenders = lazy(() => import('./pages/Lenders.tsx'))
// The demo story: one browser plays the owner, the officer and the supervisor.
const DemoStory = lazy(() => import('./pages/DemoStory.tsx'))
// The officer's workspace uses Firebase, so it loads only when opened.
const Applications = lazy(() => import('./pages/officer/Applications.tsx'))
const NewApplication = lazy(() => import('./pages/officer/NewApplication.tsx'))
const Consent = lazy(() => import('./pages/officer/Consent.tsx'))
const Evidence = lazy(() => import('./pages/officer/Evidence.tsx'))
const ApplicationFile = lazy(() => import('./pages/officer/ApplicationFile.tsx'))
const OpenShared = lazy(() => import('./pages/officer/OpenShared.tsx'))
const OpenSignoff = lazy(() => import('./pages/officer/OpenSignoff.tsx'))
const Integrations = lazy(() => import('./pages/officer/Integrations.tsx'))
const Pilot = lazy(() => import('./pages/officer/Pilot.tsx'))
// The business owner's pages, also loaded on demand.
const OwnerHome = lazy(() => import('./pages/owner/OwnerHome.tsx'))
const OwnerNew = lazy(() => import('./pages/owner/OwnerNew.tsx'))
const OwnerFile = lazy(() => import('./pages/owner/OwnerFile.tsx'))

export default function App() {
  return (
    <Suspense fallback={<main className="container section">Loading…</main>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/status" element={<Status />} />
        <Route path="/samples/:slug" element={<SampleFile />} />
        <Route path="/ai" element={<HowItWorks />} />
        <Route path="/trust" element={<Trust />} />
        <Route path="/lenders" element={<Lenders />} />
        <Route path="/demo/:slug" element={<DemoStory />} />
        <Route path="/app" element={<Applications />} />
        <Route path="/app/new" element={<NewApplication />} />
        <Route path="/app/integrations" element={<Integrations />} />
        <Route path="/app/pilot" element={<Pilot />} />
        <Route path="/app/:id" element={<ApplicationFile />} />
        <Route path="/app/:id/consent" element={<Consent />} />
        <Route path="/app/:id/evidence" element={<Evidence />} />
        <Route path="/app/shared/:code" element={<OpenShared />} />
        <Route path="/app/signoff/:code" element={<OpenSignoff />} />
        <Route path="/owner" element={<OwnerHome />} />
        <Route path="/owner/new" element={<OwnerNew />} />
        <Route path="/owner/:id" element={<OwnerFile />} />
        <Route path="*" element={<Landing />} />
      </Routes>
    </Suspense>
  )
}
