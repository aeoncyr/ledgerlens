import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Logo from '../../components/Logo.tsx'

export type OfficerStep = 1 | 2 | 3 | 4

const STEPS = ['Evidence', 'Analysis', 'Follow-up', 'Credit file'] as const

const NEXT: Record<OfficerStep, string> = {
  1: 'run the analysis',
  2: 'read the findings',
  3: 're-check the file with the owner’s answers',
  4: 'record your decision',
}

// Where the officer is in an application: collect, analyse, follow up, decide.
function Progress({ step, done }: { step: OfficerStep; done?: boolean }) {
  return (
    <nav className="officer-steps" aria-label="Application progress">
      <ol>
        {STEPS.map((label, index) => {
          const n = index + 1
          const state = n < step || (done && n === step) ? 'done' : n === step ? 'current' : 'todo'
          return (
            <li key={label} className={state} aria-current={n === step ? 'step' : undefined}>
              <span className="os-node" aria-hidden="true">
                {state === 'done' ? '✓' : n}
              </span>
              <span className="os-label">{label}</span>
            </li>
          )
        })}
      </ol>
      <p className="os-caption">
        Step {step} of 4 · {done ? 'Decision recorded' : `Next: ${NEXT[step]}`}
      </p>
    </nav>
  )
}

// The officer's workspace: a plain header, the page, and a reminder that this is a prototype.
export default function OfficerShell({
  title,
  crumbs,
  step,
  done,
  children,
}: {
  title: string
  crumbs?: ReactNode
  // The application's step, when the page belongs to one.
  step?: OfficerStep
  // The last step is finished: the decision is recorded.
  done?: boolean
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
        {step && <Progress step={step} done={done} />}
        <h1 className="page-title">{title}</h1>
        {children}
      </main>
    </>
  )
}
