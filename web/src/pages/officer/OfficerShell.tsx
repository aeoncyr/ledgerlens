import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Logo from '../../components/Logo.tsx'

// The officer's workspace: a plain header, the page, and a reminder that this is a prototype.
export default function OfficerShell({
  title,
  crumbs,
  children,
}: {
  title: string
  crumbs?: ReactNode
  children: ReactNode
}) {
  return (
    <>
      <nav className="masthead" aria-label="Officer workspace">
        <div className="container">
          <Link to="/" className="brand">
            <Logo />
            LedgerLens
          </Link>
          <div className="nav-links">
            <Link to="/app">Applications</Link>
            <Link to="/app/new">New application</Link>
            <Link to="/">About</Link>
          </div>
        </div>
      </nav>
      <div className="prototype-note">
        <div className="container">
          Prototype: use fictional businesses only. Photos are read by Gemini’s free tier.
        </div>
      </div>
      <main className="container officer-page">
        <p className="crumbs">
          <Link to="/app">Applications</Link>
          {crumbs}
        </p>
        <h1 className="page-title">{title}</h1>
        {children}
      </main>
    </>
  )
}
