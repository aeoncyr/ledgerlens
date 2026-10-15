import { Link } from 'react-router-dom'
import Logo from '../components/Logo.tsx'

type Outcome = 'verified' | 'partial' | 'inconsistent'

const OUTCOME_LABEL: Record<Outcome, string> = {
  verified: 'Verified',
  partial: 'Partially verified',
  inconsistent: 'Inconsistent',
}

// The three demo businesses are fictional. Their full files open here once analysis is wired up.
const SAMPLES: { name: string; outcome: Outcome; blurb: string }[] = [
  {
    name: 'Warung Bu Sari',
    outcome: 'verified',
    blurb:
      'Grocery stall, Bekasi. Notebook, QRIS and receipts agree once cash-only Saturdays are explained.',
  },
  {
    name: 'Penjahit Pak Joko',
    outcome: 'partial',
    blurb: 'Tailor, Yogyakarta. No QRIS, so the lower cash-flow estimate rests on receipts alone.',
  },
  {
    name: 'Warung Makan Hendra',
    outcome: 'inconsistent',
    blurb:
      'Food stall, Bandung. The notebook claims about 3× what QRIS and supplier receipts support.',
  },
]

const STEPS = [
  {
    title: 'Capture',
    text: 'With the owner’s consent, the officer photographs notebook pages, QRIS history, receipts and the shop, and records a short interview.',
  },
  {
    title: 'Read',
    text: 'Gemini agents read every item in parallel: handwriting, screenshots and spoken Bahasa, with a confidence for every value.',
  },
  {
    title: 'Cross-check',
    text: 'A verifier compares the sources and asks the owner polite follow-up questions about anything that doesn’t add up.',
  },
  {
    title: 'Cite',
    text: 'A 5C credit memo where every figure links to its source. Cash flow is computed by code, never by the model.',
  },
]

export default function Landing() {
  return (
    <>
      <nav className="nav" aria-label="Main">
        <div className="container">
          <Link to="/" className="brand">
            <Logo />
            LedgerLens
          </Link>
          <div className="nav-links">
            <a href="#how">How it works</a>
            <a href="#responsible">Responsible by design</a>
          </div>
        </div>
      </nav>

      <main>
        <header className="container hero">
          <div className="hero-copy">
            <span className="eyebrow">AI credit analyst for informal micro businesses</span>
            <h1>See the businesses banks can’t.</h1>
            <p className="lead">
              LedgerLens turns notebook ledgers, QRIS payment history (Indonesia’s national QR
              payments), receipts and a short interview in Bahasa Indonesia into a verified credit
              file. Every number is cited to its evidence. Built for rural banks, cooperatives and
              microfinance lenders.
            </p>
          </div>
          <aside className="callout">
            <strong>Decision support, not a credit score.</strong>
            It never rejects anyone automatically. When evidence is thin it says so, and the lender’s
            normal process applies.
          </aside>
        </header>

        <section className="container section" aria-labelledby="samples">
          <h2 id="samples">Sample businesses</h2>
          <div className="grid">
            {SAMPLES.map((sample) => (
              <article className="card" key={sample.name}>
                <span className={`chip ${sample.outcome}`}>{OUTCOME_LABEL[sample.outcome]}</span>
                <h3>{sample.name}</h3>
                <p>{sample.blurb}</p>
              </article>
            ))}
          </div>
          <p className="note">
            All businesses, notebooks and recordings shown here are fictional. Their full credit files
            open here as the officer app comes online.
          </p>
        </section>

        <section id="how" className="band" aria-labelledby="how-heading">
          <div className="container section">
            <h2 id="how-heading">How it works</h2>
            <div className="grid">
              {STEPS.map((step, index) => (
                <div key={step.title}>
                  <span className="step-number">{String(index + 1).padStart(2, '0')}</span>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="responsible" className="container section" aria-labelledby="responsible-heading">
          <h2 id="responsible-heading">Responsible by design</h2>
          <div className="grid">
            <div className="card">
              <h3>Consent first</h3>
              <p>
                The owner agrees on screen before anything is captured, and can withdraw consent at
                any time.
              </p>
            </div>
            <div className="card">
              <h3>Where data lives</h3>
              <p>
                Records are stored in Google Cloud’s Jakarta region and photos in the United States.
                AI reading is done by Google Cloud’s Gemini.
              </p>
            </div>
            <div className="card">
              <h3>A human decides</h3>
              <p>
                LedgerLens recommends; a credit officer decides, and every decision needs a written
                reason in the audit log.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container">
          <span>Built with Gemini · Firebase · Firestore · Cloud Run</span>
          <span>Google Cloud AI Builder Cup 2026 · BFSI</span>
        </div>
      </footer>
    </>
  )
}
