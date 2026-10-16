import { Link } from 'react-router-dom'
import Logo from './Logo.tsx'

export default function SiteNav({ home = false }: { home?: boolean }) {
  const prefix = home ? '' : '/'
  return (
    <nav className="masthead" aria-label="Main">
      <div className="container">
        <Link to="/" className="brand">
          <Logo />
          LedgerLens
        </Link>
        <div className="nav-links">
          <a href={`${prefix}#how`}>How it works</a>
          <a href={`${prefix}#samples`}>Sample files</a>
          <a href={`${prefix}#accuracy`}>Accuracy</a>
          <Link to="/owner">For business owners</Link>
          <Link className="nav-cta" to="/app">
            Officer app
          </Link>
        </div>
      </div>
    </nav>
  )
}
