import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import AppBar from '../../components/AppBar.tsx'

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
  titleHidden,
  children,
}: {
  title: string
  crumbs?: ReactNode
  // The application's step, when the page belongs to one.
  step?: OfficerStep
  // The last step is finished: the decision is recorded.
  done?: boolean
  // The page shows its own visible title (the credit file's business name); the h1 stays for
  // screen readers.
  titleHidden?: boolean
  children: ReactNode
}) {
  return (
    <>
      <AppBar
        app="officer"
        appName="Loan officer app"
        appHome="/app"
        homeLabel="Home"
        notice="Prototype: use fictional businesses only. Photos are read by Gemini’s free tier."
      >
        <nav className="appbar-nav" aria-label="Officer workspace">
          <NavLink to="/app" end>
            Applications
          </NavLink>
          <NavLink to="/app/new" end>
            New<span className="appbar-long"> application</span>
          </NavLink>
          <NavLink to="/app/integrations" end>
            Integrations
          </NavLink>
        </nav>
      </AppBar>
      <main className="container officer-page">
        <p className="crumbs">
          <Link to="/app">Applications</Link>
          {crumbs}
        </p>
        {step && <Progress step={step} done={done} />}
        <h1 className={titleHidden ? 'visually-hidden' : 'page-title'}>{title}</h1>
        {children}
      </main>
    </>
  )
}
