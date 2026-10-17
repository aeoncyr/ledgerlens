import { Link } from 'react-router-dom'
import CreditFileCard from '../components/CreditFileCard.tsx'
import SiteNav from '../components/SiteNav.tsx'
import Specimen from '../components/Specimen.tsx'
import { SAMPLES } from '../samples.ts'
import { ASSESSMENT_LABEL, ASSESSMENT_TONE } from '../types.ts'

type Actor = 'Owner' | 'Officer' | 'Gemini' | 'Code'

const JOURNEY: { title: string; actor: Actor[]; text: string }[] = [
  {
    title: 'Capture',
    actor: ['Owner', 'Officer'],
    text: 'Photos of the notebook, supplier receipts and QRIS history, plus a short voice interview in Bahasa Indonesia, taken by the owner on their phone or by the officer on a visit.',
  },
  {
    title: 'Read',
    actor: ['Gemini'],
    text: 'One reader per kind of evidence copies what is written and what is said, exactly, with where it is: page and line, or the moment in the recording.',
  },
  {
    title: 'Calculate',
    actor: ['Code'],
    text: 'Plain, tested code turns “1,5jt” into Rp 1.500.000, builds monthly cash flow and applies the lender’s own policy. The model never does arithmetic.',
  },
  {
    title: 'Cross-check',
    actor: ['Gemini'],
    text: 'A verifier compares every source with the others, cites each finding, and writes polite questions the owner can answer.',
  },
  {
    title: 'Decide',
    actor: ['Officer'],
    text: 'The lender reads a file where every figure points to its evidence, and decides with a written reason in an audit log.',
  },
]

const GOOGLE_CLOUD: { name: string; where?: string; text: string }[] = [
  {
    name: 'Gemini',
    text: 'Reads handwriting, receipts, QRIS screenshots and interviews in Bahasa Indonesia, cross-checks the sources, and writes the memo.',
  },
  {
    name: 'Cloud Run',
    where: 'Jakarta',
    text: 'Runs the API and the agent pipeline that turns evidence into a credit file.',
  },
  {
    name: 'Firestore',
    where: 'Jakarta',
    text: 'Holds the applications, the live progress of every analysis, and the audit log.',
  },
  {
    name: 'Firebase',
    text: 'Hosting for this site, anonymous sign-in, Storage for photos and recordings, and the security rules that keep each file private.',
  },
]

const SAMPLE_NOTE: Record<string, string> = {
  'bu-sari': 'Notebook, receipts and QRIS agree, and so does the owner’s interview.',
  'pak-joko': 'Honest books but no QRIS history, so only part of the cash flow is proven.',
  'pak-hendra': 'The notebook claims three times what the owner says out loud.',
  'bu-wati': 'An edited QRIS screenshot, caught: its payments don’t add up to its total.',
}

function HeroVisual() {
  return (
    <div className="hero-visual" aria-hidden="true">
      <div className="hv-page">
        <img src="/specimen/bu-sari-page-1.webp" width={720} height={1018} alt="" />
        {/* A pen mark, as an officer checking the page would make: drawn in the photo's own
            coordinates so it stays on line 16 whatever the size. */}
        <svg className="hv-mark" viewBox="0 0 720 1018" preserveAspectRatio="none">
          <path
            className="hv-loop"
            pathLength={100}
            d="M 140 726 C 300 712, 640 714, 700 740 C 730 756, 690 782, 520 784 C 330 788, 110 786, 88 762 C 72 744, 110 728, 200 722"
          />
          <path className="hv-pen" d="M 74 742 C 40 700, 34 580, 56 500" />
          <path className="hv-pen" d="M 56 500 L 40 522 M 56 500 L 68 524" />
        </svg>
      </div>
      <div className="hv-chip hv-chip-a">
        <span className="hv-written">“2,3 jt”</span>
        <span className="hv-arrow">→</span>
        <strong>Rp 2.300.000</strong>
        <small>Notebook page 1 · line 16</small>
      </div>
      <div className="hv-chip hv-chip-b">
        <span className="hv-wave" />
        <span lang="id">“Sehari biasanya laku…”</span>
        <small>Interview · 0:04</small>
      </div>
      <div className="hv-file">
        <CreditFileCard sample={SAMPLES[0]} compact />
      </div>
    </div>
  )
}

export default function Landing() {
  return (
    <>
      <SiteNav />

      <main>
        <div className="hero-band">
          <header className="container hero">
            <div className="hero-copy">
              <h1>Turn a notebook into a credit file a lender can trust.</h1>
              <p className="lead">
                Most Indonesian micro businesses (UMKM) keep their books by hand, so banks can’t
                judge them. LedgerLens reads the notebook, receipts, QRIS payments (Indonesia’s
                national QR payments) and the owner’s own words with Gemini, checks them against
                each other, and gives the lender a file in which every figure is cited.
              </p>
              <div className="doors-mini">
                <Link className="button on-dark" to="/owner">
                  I run a business
                  <span className="button-sub">Build my file</span>
                </Link>
                <Link className="button ghost-on-dark" to="/app/new">
                  I’m a loan officer
                  <span className="button-sub">Assess a business</span>
                </Link>
              </div>
              <p className="hero-aside">
                Just looking? <Link to={`/samples/${SAMPLES[2].slug}`}>Open a finished file</Link>{' '}
                in one click. It is <strong>not a credit score</strong>: a person always decides.
              </p>
            </div>
            <HeroVisual />
          </header>
        </div>

        <section className="container doors" aria-labelledby="doors-heading">
          <h2 id="doors-heading" className="visually-hidden">
            Who LedgerLens is for
          </h2>
          <article className="door owner-door">
            <span className="door-label">For business owners</span>
            <h3>Show what your business really earns.</h3>
            <ol>
              <li>
                <strong>Photograph your records</strong> on your phone: notebook pages, supplier
                receipts, QRIS history, and a short voice note.
              </li>
              <li>
                <strong>See what was confirmed</strong> and what is missing, with tips to make your
                file stronger, in English or Bahasa Indonesia.
              </li>
              <li>
                <strong>Share it with the lender you choose</strong>, with a link you can withdraw
                at any time.
              </li>
            </ol>
            <Link className="button" to="/owner">
              Start my file
            </Link>
            <p className="fine">Free, no account needed. Use a sample business to try it.</p>
          </article>
          <article className="door lender-door">
            <span className="door-label">For lenders</span>
            <h3>Assess businesses that have no financial statements.</h3>
            <ol>
              <li>
                <strong>Receive a file</strong> an owner shared, or start one on a visit and
                photograph the records yourself.
              </li>
              <li>
                <strong>Watch the agents work</strong>: Gemini reads and cross-checks every source,
                code computes every figure.
              </li>
              <li>
                <strong>Read a cited credit file</strong>, put questions to the owner, and decide
                with a written reason.
              </li>
            </ol>
            <Link className="button" to="/app/new">
              Open the officer app
            </Link>
            <p className="fine">
              For rural banks (BPR), cooperatives and microfinance lenders without their own tools.
            </p>
          </article>
        </section>

        <section className="container cloud-strip" aria-labelledby="cloud-heading">
          <h2 id="cloud-heading" className="cloud-title">
            Powered by Google Cloud
          </h2>
          <dl className="cloud-cells">
            {GOOGLE_CLOUD.map((cell) => (
              <div key={cell.name}>
                <dt>
                  {cell.name}
                  {cell.where && <span className="cloud-where">{cell.where}</span>}
                </dt>
                <dd>{cell.text}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section id="how" className="how-band" aria-labelledby="how-heading">
          <div className="container section">
            <div className="section-head">
              <h2 id="how-heading">How a file is made</h2>
              <p>
                Gemini reads, listens and reasons. Plain, tested code does every calculation. A
                person makes every decision.
              </p>
            </div>
            <ol className="journey">
              {JOURNEY.map((step, index) => (
                <li key={step.title}>
                  <span className="journey-node">{index + 1}</span>
                  <h3>{step.title}</h3>
                  <span className="journey-actors">
                    {step.actor.map((a) => (
                      <span key={a} className={`actor ${a.toLowerCase()}`}>
                        {a}
                      </span>
                    ))}
                  </span>
                  <p>{step.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="samples" className="container section" aria-labelledby="samples-heading">
          <div className="section-head">
            <h2 id="samples-heading">Open a finished file</h2>
            <p>
              Four fictional businesses, each with two months of notebook pages and receipts, and
              where they have them, QRIS history and a short interview with the owner. One of them
              edited a screenshot. These are the files LedgerLens produced, unedited. Click any
              citation to see the evidence behind it.
            </p>
          </div>
          <div className="sample-cards">
            {SAMPLES.map((sample) => (
              <Link key={sample.slug} to={`/samples/${sample.slug}`} className="sample-card">
                <span className="sample-head">
                  <span className="mono">{sample.fileNumber}</span>
                  <span className={`stamp mini ${ASSESSMENT_TONE[sample.assessment]}`}>
                    {ASSESSMENT_LABEL[sample.assessment]}
                  </span>
                </span>
                <strong className="sample-name">{sample.alias}</strong>
                <span className="sub">
                  {sample.businessType}, {sample.city}
                </span>
                <span className="sample-note">{SAMPLE_NOTE[sample.slug]}</span>
                <span className="sample-foot">
                  <span className="strength">
                    <span className="strength-bar" aria-hidden="true">
                      <span style={{ width: `${sample.evidenceStrength}%` }} />
                    </span>
                    Evidence {sample.evidenceStrength}/100
                  </span>
                  <span className="open">Open file →</span>
                </span>
              </Link>
            ))}
          </div>
        </section>

        <section className="container section specimen" aria-labelledby="specimen-heading">
          <div className="section-head">
            <h2 id="specimen-heading">Look inside: how a page is read</h2>
            <p>
              The reader copies what is written, exactly as written. Code turns it into rupiah and
              adds it up, so the arithmetic can be checked line by line.
            </p>
          </div>
          <Specimen />
        </section>

        <section id="accuracy" className="accuracy-band" aria-labelledby="accuracy-heading">
          <div className="container section">
            <div className="section-head">
              <h2 id="accuracy-heading">Measured, not claimed</h2>
              <p>
                Each reader is tested on evidence whose true values are known. The harness and its
                data are in the repository, so anyone can run it again.
              </p>
            </div>
            <dl className="stats">
              <div>
                <dd>28 of 29</dd>
                <dt>receipt totals read exactly from real photographed receipts (CORD dataset)</dt>
              </div>
              <div>
                <dd>162 of 162</dd>
                <dt>notebook amounts read exactly from photographed pages in eight handwriting fonts</dt>
              </div>
              <div>
                <dd>4 of 4</dd>
                <dt>sample files with every monthly total read exactly and the right outcome</dt>
              </div>
            </dl>
            <p className="fine on-dark">
              Real handwriting from our own notebooks is being measured next. All businesses here are
              fictional.
            </p>
          </div>
        </section>

        <section id="safeguards" className="container section" aria-labelledby="safeguards-heading">
          <div className="section-head">
            <h2 id="safeguards-heading">Made for a regulated lender</h2>
            <p>The questions a lender’s risk and compliance team asks first, answered up front.</p>
          </div>
          <dl className="safeguards">
            <div>
              <dt>Not a credit score</dt>
              <dd>
                Predicting repayment needs repayment history these businesses don’t have yet.
                LedgerLens verifies evidence and says how strong it is.
              </dd>
            </div>
            <div>
              <dt>Consent first</dt>
              <dd>
                The owner agrees before anything is captured and can withdraw at any time. We keep a
                business alias, never a legal name or national ID number.
              </dd>
            </div>
            <div>
              <dt>Where data lives</dt>
              <dd>
                Records stay in Google Cloud’s Jakarta region; photos and recordings in the United
                States. Gemini reads them through Google’s global endpoint.
              </dd>
            </div>
            <div>
              <dt>A person decides</dt>
              <dd>
                No automatic rejections. Every decision needs a credit officer and a written reason,
                kept in an audit log.
              </dd>
            </div>
          </dl>
        </section>

        <section className="cta-band" aria-labelledby="cta-heading">
          <div className="container">
            <h2 id="cta-heading">See it work in five minutes.</h2>
            <p>
              Start from a sample business, add its records in one click, and watch Gemini build
              the file.
            </p>
            <div className="doors-mini">
              <Link className="button on-dark" to="/owner">
                I run a business
              </Link>
              <Link className="button ghost-on-dark" to="/app/new">
                I’m a loan officer
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container">
          <span>Built with Gemini, Firebase, Firestore and Cloud Run</span>
          <span>
            Google Cloud AI Builder Cup 2026 · <Link to="/status">System status</Link>
          </span>
        </div>
      </footer>
    </>
  )
}
