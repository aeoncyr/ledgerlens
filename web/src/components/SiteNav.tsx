import { Link, NavLink } from 'react-router-dom'
import Logo from './Logo.tsx'

// The public site's header: one page to read, and the two apps as a matched pair of doors. Sections
// of the landing page are reached by scrolling it, not from here.
export default function SiteNav() {
  return (
    <nav className="masthead" aria-label="Main">
      <div className="container">
        <Link to="/" className="brand">
          <Logo />
          LedgerLens
        </Link>
        <div className="nav-links">
          <NavLink to="/ai">How the AI works</NavLink>
          <Link className="nav-cta nav-cta-owner" to="/owner">
            Business owner app
          </Link>
          <Link className="nav-cta" to="/app">
            Officer app
          </Link>
        </div>
      </div>
    </nav>
  )
}
