// /demo/:slug: the start of the demo story. While the visitor watches a replay of the real check on
// the sample, the API makes their own demo copy of the finished file; then they open it as the
// owner and play every role from there (components/DemoBar.tsx).
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import SiteNav from '../components/SiteNav.tsx'
import TraceReplay from '../components/TraceReplay.tsx'
import { startDemoStory, useRecordedRun } from '../demo.ts'
import { SAMPLES } from '../samples.ts'
import '../demo.css'

const ROLES = [
  { who: 'The owner', does: 'shares the finished file with a lender.' },
  { who: 'The loan officer', does: 'opens it and recommends a decision with a reason.' },
  { who: 'The supervisor', does: 'signs the recommendation off, or sends it back.' },
  { who: 'The owner', does: 'reads the decision and its letter, and answers.' },
]

export default function DemoStory() {
  const { slug = '' } = useParams()
  const navigate = useNavigate()
  const sample = SAMPLES.find((s) => s.slug === slug)
  const recorded = useRecordedRun(sample ? slug : undefined)
  const [fileId, setFileId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [watched, setWatched] = useState(false)
  // One copy per visit, even when React runs the effect twice in development.
  const started = useRef(false)

  useEffect(() => {
    if (!sample || started.current) return
    started.current = true
    startDemoStory(sample.slug)
      .then(setFileId)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [sample])

  return (
    <>
      <SiteNav />
      <main className="container story-page">
        <p className="crumbs">
          <Link to="/">LedgerLens</Link> /{' '}
          <Link to={`/samples/${slug}`}>{sample?.alias ?? 'Sample files'}</Link> / The whole story
        </p>
        {!sample ? (
          <p>There is no sample file with that name.</p>
        ) : (
          <>
            <h1>The whole story, in one browser</h1>
            <p className="lead-text">
              A loan decision on LedgerLens passes through three people. Here you play all of them
              on your own demo copy of {sample.alias}’s finished file. A real file never lets one
              person do this: nobody can sign off their own recommendation.
            </p>
            <ol className="story-roles">
              {ROLES.map((role, index) => (
                <li key={index}>
                  <strong>
                    {index + 1}. {role.who}
                  </strong>
                  {role.does}
                </li>
              ))}
            </ol>
            {recorded && (
              <>
                <h2>First, how this file was checked</h2>
                <TraceReplay
                  run={recorded}
                  assessment={sample.assessment}
                  onFinished={() => setWatched(true)}
                />
              </>
            )}
            <div className="story-start">
              <button
                type="button"
                className="button"
                disabled={!fileId}
                onClick={() => fileId && navigate(`/owner/${fileId}`)}
              >
                {fileId ? 'Start as the owner' : error ? 'Could not start' : 'Making your copy…'}
              </button>
              {recorded && !watched && fileId && (
                <span className="fine">You can start now, or when the replay ends.</span>
              )}
            </div>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <p className="fine">
              The copy is never checked again, so the story uses no Gemini quota except for the
              letter to the owner at the end. Starting the story again replaces your copy.
            </p>
          </>
        )}
      </main>
    </>
  )
}
