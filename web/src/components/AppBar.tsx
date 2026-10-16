import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Logo from './Logo.tsx'

// The one header both apps share: a way back to the public site, the app's name and its own
// controls. The two apps differ in layout on purpose (a phone for owners, a desk for officers), so
// the frame around them is what tells a visitor they are in the same product.
export default function AppBar({
  app,
  appName,
  appHome,
  homeLabel,
  notice,
  children,
}: {
  app: 'owner' | 'officer'
  appName: string
  // Where the brand leads: the app's own start page.
  appHome: string
  // The label of the way back to the landing page ("Home").
  homeLabel: string
  notice: ReactNode
  children?: ReactNode
}) {
  return (
    <>
      <header className={`appbar appbar-${app}`}>
        <div className="container appbar-inner">
          <Link to="/" className="appbar-home" aria-label={homeLabel}>
            <span aria-hidden="true">←</span>
            <span className="appbar-home-label" aria-hidden="true">
              {homeLabel}
            </span>
          </Link>
          <Link to={appHome} className="appbar-brand">
            <Logo size={24} />
            <span className="appbar-name">LedgerLens</span>
            <span className="appbar-chip">{appName}</span>
          </Link>
          <div className="appbar-tools">{children}</div>
        </div>
      </header>
      <aside className="prototype-note" aria-label="Prototype notice">
        <div className="container">{notice}</div>
      </aside>
    </>
  )
}
