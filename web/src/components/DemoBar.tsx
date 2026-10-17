// The slim bar on a demo file: which role the visitor is playing, where the story stands, and one
// click to the next step in the right role. It says plainly that one person plays every role here,
// which a real file never allows.
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { signoffPath, useOwnerDecision } from '../decision.ts'
import {
  ROLE_LABEL,
  storyStage,
  type DemoFile,
  type DemoRole,
  type StoryStage,
} from '../demo.ts'
import { auth } from '../firebase.ts'
import { sharePath, shareFile } from '../owner.ts'
import '../demo.css'

const STEPS: { label: string; stages: StoryStage[] }[] = [
  { label: 'Owner shares', stages: ['share'] },
  { label: 'Officer decides', stages: ['open', 'decide'] },
  { label: 'Supervisor signs off', stages: ['signoff'] },
  { label: 'Owner answers', stages: ['answer'] },
]
const ORDER: StoryStage[] = ['share', 'open', 'decide', 'signoff', 'answer', 'done']

function scrollTo(id: string) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  document.getElementById(id)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth' })
}

type Next = { text: string; label: string; go: () => void | Promise<void> }

export default function DemoBar({ app, playing }: { app: DemoFile; playing: DemoRole }) {
  const navigate = useNavigate()
  const sent = useOwnerDecision(app.id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const me = auth.currentUser?.uid
  const stage = storyStage(app, sent)
  const decision = app.decision
  const code = decision?.state === 'recommended' ? decision.signoffCode : null
  // Asking for more records goes to the owner without a sign-off.
  const noSignoff = decision?.state === 'final' && decision.action === 'request_more'

  const ownerPage = `/owner/${app.id}`
  const officerPage = app.officerUid ? `/app/${app.id}` : null
  const reviewerPage =
    app.reviewerUid === me && app.reviewerUid
      ? `/app/${app.id}?as=reviewer`
      : code
        ? signoffPath(code)
        : null
  const pages: Record<DemoRole, { to: string | null; why: string }> = {
    owner: { to: ownerPage, why: '' },
    officer: { to: officerPage, why: 'The owner shares the file first.' },
    reviewer: { to: reviewerPage, why: 'The officer recommends a decision first.' },
  }

  const next: Next | null = (() => {
    switch (stage) {
      case 'share':
        return playing === 'owner'
          ? {
              text: 'As the owner, share the file with a lender: this makes the link a loan officer opens.',
              label: 'Share the file',
              go: async () => {
                await shareFile(app.id)
              },
            }
          : {
              text: 'The owner shares the file first.',
              label: 'Switch to the owner',
              go: () => navigate(ownerPage),
            }
      case 'open':
        return {
          text: 'The file is shared. Open it as the loan officer, with the owner’s link.',
          label: 'Open it as the officer',
          go: () => navigate(sharePath(app.shareCode!)),
        }
      case 'decide':
        return playing === 'officer'
          ? {
              text:
                decision?.state === 'returned'
                  ? 'The supervisor sent the recommendation back with a note. Recommend again.'
                  : 'Read the file, then recommend a decision with a written reason, under Your decision.',
              label: 'Go to the decision',
              go: () => scrollTo('decision-heading'),
            }
          : {
              text: 'The loan officer reads the file and recommends a decision.',
              label: 'Switch to the officer',
              go: () => navigate(officerPage!),
            }
      case 'signoff':
        return playing === 'reviewer'
          ? {
              text: 'Read the recommendation, then sign it off or send it back with a note.',
              label: 'Go to the sign-off',
              go: () => scrollTo('decision-heading'),
            }
          : {
              text: 'A second person at the lender signs off the recommendation before the owner hears.',
              label: 'Switch to the supervisor',
              go: () => navigate(reviewerPage!),
            }
      case 'answer':
        return playing === 'owner'
          ? {
              text: 'The decision and its letter have reached the owner. Read them and answer.',
              label: 'Read the decision',
              go: () => scrollTo('ow-decision-title'),
            }
          : {
              text: 'The decision is final and a letter is on its way to the owner.',
              label: 'Switch to the owner',
              go: () => navigate(ownerPage),
            }
      case 'done':
        return playing === 'officer'
          ? {
              text: 'The story is complete. Every step is in the audit log, with its time.',
              label: 'See the audit log',
              go: () => scrollTo('audit-heading'),
            }
          : {
              text: 'The story is complete. The officer’s audit log shows every step.',
              label: 'See the audit log',
              go: () => navigate(`/app/${app.id}`),
            }
    }
  })()

  async function act(work: () => void | Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  const reached = ORDER.indexOf(stage)
  return (
    <aside className="demo-bar" aria-labelledby="demo-bar-title" lang="en">
      <div className="demo-bar-head">
        <p id="demo-bar-title" className="demo-bar-title">
          <span className="demo-tag">Demo story</span> You are playing:{' '}
          <strong>{ROLE_LABEL[playing]}</strong>
        </p>
        <nav className="demo-roles" aria-label="Switch role">
          {(Object.keys(ROLE_LABEL) as DemoRole[]).map((role) => {
            const { to, why } = pages[role]
            if (role === playing) {
              return (
                <span key={role} className="demo-role current" aria-current="page">
                  {ROLE_LABEL[role]}
                </span>
              )
            }
            return to ? (
              <Link key={role} className="demo-role" to={to}>
                {ROLE_LABEL[role]}
              </Link>
            ) : (
              <span key={role} className="demo-role unavailable" title={why}>
                {ROLE_LABEL[role]}
                <span className="visually-hidden"> (not yet: {why})</span>
              </span>
            )
          })}
        </nav>
      </div>
      <ol className="demo-steps" aria-label="The story">
        {STEPS.map((step, index) => {
          const first = ORDER.indexOf(step.stages[0])
          const last = ORDER.indexOf(step.stages.at(-1)!)
          const skipped = index === 2 && noSignoff
          const state = skipped
            ? 'skipped'
            : reached > last
              ? 'done'
              : reached >= first
                ? 'current'
                : 'todo'
          return (
            <li
              key={step.label}
              className={state}
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <span className="demo-step-mark" aria-hidden="true">
                {state === 'done' ? '✓' : state === 'skipped' ? '–' : index + 1}
              </span>
              {step.label}
              {skipped && <span className="visually-hidden"> (not needed to ask for records)</span>}
            </li>
          )
        })}
      </ol>
      {next && (
        <div className="demo-next">
          <p>
            <strong>Next:</strong> {next.text}
          </p>
          <button
            type="button"
            className="demo-go"
            disabled={busy}
            onClick={() => void act(next.go)}
          >
            {busy ? 'One moment…' : next.label}
          </button>
        </div>
      )}
      {error && (
        <p className="demo-error" role="alert">
          {error}
        </p>
      )}
      <p className="demo-fine">
        One person plays every role here, so you can try the whole loop alone. A real file needs
        three people, and nobody can sign off their own decision. This copy is never checked
        again: no Gemini calls except the owner’s letter.
      </p>
    </aside>
  )
}
