import { Link } from 'react-router-dom'
import Logo from '../components/Logo.tsx'
import {
  SPECIMEN_LINES,
  SPECIMEN_MATCHED,
  SPECIMEN_MODEL,
  SPECIMEN_TRUE_AMOUNTS,
  type SpecimenLine,
} from '../specimen.ts'

type Outcome = 'verified' | 'partial' | 'insufficient' | 'inconsistent'

const OUTCOME_LABEL: Record<Outcome, string> = {
  verified: 'Verified',
  partial: 'Partially verified',
  insufficient: 'Insufficient evidence',
  inconsistent: 'Inconsistent',
}

const KIND_LABEL: Record<SpecimenLine['kind'], string> = {
  sale: 'sale',
  purchase: 'purchase',
  receivable: 'customer credit',
  expense: 'expense',
  other: '',
}

// The three demo businesses are fictional. Their full files open here once the officer app is live.
const SAMPLES: { name: string; trade: string; evidence: string; finding: string; outcome: Outcome }[] =
  [
    {
      name: 'Warung Bu Sari',
      trade: 'Grocery stall, Bekasi',
      evidence: 'Notebook, QRIS history, supplier receipts',
      finding: 'The three sources agree once the cash-only Saturday market is explained.',
      outcome: 'verified',
    },
    {
      name: 'Penjahit Pak Joko',
      trade: 'Tailor, Yogyakarta',
      evidence: 'Notebook, fabric receipts, interview',
      finding: 'No QRIS history, so the lower cash-flow estimate rests on receipts alone.',
      outcome: 'partial',
    },
    {
      name: 'Warung Makan Hendra',
      trade: 'Food stall, Bandung',
      evidence: 'Notebook, QRIS history, market receipts',
      finding: 'The notebook claims about three times what QRIS and the stall’s purchases can support.',
      outcome: 'inconsistent',
    },
  ]

type Actor = 'Officer' | 'Gemini' | 'Code'

const STEPS: { title: string; actor: Actor; text: string }[] = [
  {
    title: 'Capture',
    actor: 'Officer',
    text: 'With the owner’s consent, photographs the notebook, QRIS history, receipts and the shop, and records a two-minute interview in Bahasa Indonesia.',
  },
  {
    title: 'Read',
    actor: 'Gemini',
    text: 'One reader per kind of evidence copies what is written, exactly, with a confidence for every value. Each page is read twice with different instructions; where the readings disagree, the value is flagged.',
  },
  {
    title: 'Calculate',
    actor: 'Code',
    text: 'Turns “1,2jt” into Rp 1.200.000, adds up the months, and works out the instalment the business can carry under the lender’s own policy. The model never does arithmetic.',
  },
  {
    title: 'Cross-check',
    actor: 'Gemini',
    text: 'Compares the sources against each other, cites every discrepancy to its page and line, and writes polite follow-up questions for the owner.',
  },
  {
    title: 'Decide',
    actor: 'Officer',
    text: 'Approves, declines or asks for more, always with a written reason that goes into the audit log.',
  },
]

const rupiah = new Intl.NumberFormat('id-ID')

function total(kind: SpecimenLine['kind']): number {
  return SPECIMEN_LINES.filter((line) => line.kind === kind).reduce(
    (sum, line) => sum + (line.rupiah ?? 0),
    0,
  )
}

function isHeading(line: SpecimenLine): boolean {
  return line.written === null && line.kind === 'other'
}

export default function Landing() {
  return (
    <>
      <nav className="masthead" aria-label="Main">
        <div className="container">
          <Link to="/" className="brand">
            <Logo />
            LedgerLens
          </Link>
          <div className="nav-links">
            <a href="#how">How it works</a>
            <a href="#accuracy">Accuracy</a>
            <a href="#safeguards">Safeguards</a>
          </div>
        </div>
      </nav>

      <main>
        <header className="container hero">
          <h1>Credit files for businesses that keep their books in a notebook.</h1>
          <div className="hero-text">
            <p className="lead">
              Millions of Indonesia’s micro businesses (UMKM) run on a handwritten notebook, QRIS
              payments (Indonesia’s national QR payments) and a drawer of receipts. LedgerLens reads
              that evidence with Gemini, checks the sources against each other, and gives the credit
              officer a file in which every figure points back to where it was written.
            </p>
            <p>
              It is built for rural banks, cooperatives and microfinance lenders that can’t build
              tools like this themselves. It is <strong>not a credit score</strong>: it verifies
              evidence, says how strong it is, and never rejects anyone on its own.
            </p>
          </div>
        </header>

        <section className="container specimen" aria-labelledby="specimen-heading">
          <h2 id="specimen-heading" className="visually-hidden">
            A notebook page and what the reader made of it
          </h2>
          <figure>
            <div className="specimen-grid">
              <img
                className="specimen-photo"
                src="/specimen/bu-sari-page-1.webp"
                width={720}
                height={1018}
                alt="A photographed notebook page: two weeks of daily sales, two supplier purchases, a customer credit and an arisan payment, with one amount crossed out and rewritten."
              />
              <table className="ledger">
                <thead>
                  <tr>
                    <th scope="col" className="col-line">
                      Line
                    </th>
                    <th scope="col">As written</th>
                    <th scope="col" className="num written">
                      Amount
                    </th>
                    <th scope="col" className="num">
                      Rupiah
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {SPECIMEN_LINES.map((line) =>
                    isHeading(line) ? (
                      <tr key={line.line} className="ledger-heading">
                        <td className="col-line">{line.line}</td>
                        <th scope="rowgroup">{line.description}</th>
                        <td className="written" />
                        <td />
                      </tr>
                    ) : (
                      <tr key={line.line}>
                        <td className="col-line">{line.line}</td>
                        <td>
                          {line.date && <span className="date">{line.date} </span>}
                          {line.description}
                          {KIND_LABEL[line.kind] && (
                            <span className="kind"> · {KIND_LABEL[line.kind]}</span>
                          )}
                        </td>
                        <td className="num written">{line.written}</td>
                        <td className="num">
                          {line.rupiah === null ? '—' : rupiah.format(line.rupiah)}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
                <tfoot>
                  <tr>
                    <td className="col-line" />
                    <th scope="row" colSpan={2}>
                      Sales on this page
                    </th>
                    <td className="num">{rupiah.format(total('sale'))}</td>
                  </tr>
                  <tr>
                    <td className="col-line" />
                    <th scope="row" colSpan={2}>
                      Supplier purchases
                    </th>
                    <td className="num">{rupiah.format(total('purchase'))}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <figcaption>
              <span>
                Left, a notebook page photographed at an angle. Right, what {SPECIMEN_MODEL} copied
                from it, unedited: {SPECIMEN_MATCHED} of {SPECIMEN_TRUE_AMOUNTS} amounts match the
                page exactly, and on the last line it took the rewritten 200rb, not the crossed-out
                1200rb. The rupiah column and the totals are computed by code.
              </span>
              <span className="fine">
                The page is synthetic, made by our generator so that its true amounts are known.
              </span>
            </figcaption>
          </figure>
        </section>

        <section className="container section" aria-labelledby="samples-heading">
          <div className="section-head">
            <h2 id="samples-heading">Three sample files</h2>
            <p>
              Every file ends in one of four outcomes: verified, partially verified, insufficient
              evidence or inconsistent. A weak file sends the owner back to the lender’s usual
              process, no worse off than today.
            </p>
          </div>
          <div className="table-scroll">
            <table className="register">
              <thead>
                <tr>
                  <th scope="col">Business</th>
                  <th scope="col">Evidence on file</th>
                  <th scope="col">What the analyst found</th>
                  <th scope="col">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLES.map((sample) => (
                  <tr key={sample.name}>
                    <th scope="row">
                      {sample.name}
                      <span className="sub">{sample.trade}</span>
                    </th>
                    <td data-label="Evidence on file">{sample.evidence}</td>
                    <td data-label="What the analyst found">{sample.finding}</td>
                    <td data-label="Outcome">
                      <span className={`outcome ${sample.outcome}`}>
                        {OUTCOME_LABEL[sample.outcome]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="fine">
            These businesses are fictional. Their full files open here once the officer app is live.
          </p>
        </section>

        <section id="how" className="container section" aria-labelledby="how-heading">
          <div className="section-head">
            <h2 id="how-heading">Who does what</h2>
            <p>
              Gemini reads and reasons; plain, tested code does every calculation; a person makes
              every decision.
            </p>
          </div>
          <ol className="steps">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <span className="step-number">{index + 1}</span>
                <h3>{step.title}</h3>
                <span className={`actor ${step.actor.toLowerCase()}`}>{step.actor}</span>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="accuracy" className="container section" aria-labelledby="accuracy-heading">
          <div className="section-head">
            <h2 id="accuracy-heading">Measured, not claimed</h2>
            <p>
              Each reader is tested on evidence whose true values we know. The harness and its data
              are in the repository, so anyone can run it again.
            </p>
          </div>
          <div className="table-scroll">
            <table className="register">
              <thead>
                <tr>
                  <th scope="col">Test</th>
                  <th scope="col">What was read</th>
                  <th scope="col">Result</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Notebook pages, synthetic</th>
                  <td data-label="What was read">
                    9 pages from three fictional businesses in eight handwriting fonts, photographed
                    with tilt, blur and uneven light
                  </td>
                  <td data-label="Result">
                    <span className="figure">162</span> of 162 amounts read exactly. The other
                    prompt wording got 160; both misses were crossed-out corrections, since fixed.
                  </td>
                </tr>
                <tr>
                  <th scope="row">Receipts, real</th>
                  <td data-label="What was read">
                    30 receipts photographed in Indonesian shops and restaurants, from the public
                    CORD dataset
                  </td>
                  <td data-label="Result">
                    Total paid read exactly on <span className="figure">28</span> of 29; all{' '}
                    <span className="figure">69</span> item amounts found.
                  </td>
                </tr>
                <tr>
                  <th scope="row">Notebook pages, real handwriting</th>
                  <td data-label="What was read">Pages written by hand by our team</td>
                  <td data-label="Result" className="pending">In progress</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="safeguards" className="container section" aria-labelledby="safeguards-heading">
          <div className="section-head">
            <h2 id="safeguards-heading">Made for a regulated lender</h2>
            <p>
              The questions a lender’s risk and compliance team asks first, answered before they
              ask.
            </p>
          </div>
          <dl className="safeguards">
            <div>
              <dt>Not a credit score</dt>
              <dd>
                Predicting repayment needs real repayment history, which these businesses don’t
                have yet. LedgerLens verifies evidence and says how strong it is.
              </dd>
            </div>
            <div>
              <dt>Consent first</dt>
              <dd>
                The owner agrees on screen before anything is captured and can withdraw at any
                time. We keep a business alias, never a legal name or national ID number.
              </dd>
            </div>
            <div>
              <dt>Where data lives</dt>
              <dd>
                Records stay in Google Cloud’s Jakarta region and photos in the United States.
                Gemini reads them through Google’s global endpoint.
              </dd>
            </div>
            <div>
              <dt>A person decides</dt>
              <dd>
                There are no automatic rejections. Every decision needs a credit officer and a
                written reason, kept in an audit log.
              </dd>
            </div>
          </dl>
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
