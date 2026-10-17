import { Link, NavLink } from 'react-router-dom'
import Logo from './Logo.tsx'

// The public site's header: two pages to read (the AI, and the case for lenders), and the two apps
// as a matched pair of doors. Sections of the landing page are reached by scrolling it, and the
// trust page from the footer, not from here.
export default function SiteNav() {
  return (
    <nav className="masthead" aria-label="Main">
      <div className="container">
        <Link to="/" className="brand">
          <Logo />
          LedgerLens
        </Link>
        <div className="nav-links">
          <NavLink to="/ai">
            <span className="nav-full">How the AI works</span>
            <span className="nav-short">The AI</span>
          </NavLink>
          <NavLink to="/lenders">For lenders</NavLink>
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
