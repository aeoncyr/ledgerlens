import { Link } from 'react-router-dom'
import CreditFileCard from '../components/CreditFileCard.tsx'
import SiteNav from '../components/SiteNav.tsx'
import { SAMPLES } from '../samples.ts'
import {
  SPECIMEN_LINES,
  SPECIMEN_MATCHED,
  SPECIMEN_MODEL,
  SPECIMEN_TRUE_AMOUNTS,
  type SpecimenLine,
} from '../specimen.ts'
import { ASSESSMENT_LABEL, ASSESSMENT_TONE } from '../types.ts'

const KIND_LABEL: Record<SpecimenLine['kind'], string> = {
  sale: 'sale',
  purchase: 'purchase',
  receivable: 'customer credit',
  expense: 'expense',
  other: '',
}

// What each sample file was built from; the outcome and findings come from the real analysis.
const EVIDENCE_ON_FILE: Record<string, string> = {
  'bu-sari': 'Notebook, QRIS history, supplier receipts',
  'pak-joko': 'Notebook, fabric receipts; no QRIS',
  'pak-hendra': 'Notebook, QRIS history, market receipts',
}

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
      <SiteNav home />

      <main>
        <div className="hero-band">
          <header className="container hero">
            <div>
              <h1>Credit files for businesses that keep their books in a notebook.</h1>
              <p className="lead">
                LedgerLens reads a micro business’s notebook, QRIS payments (Indonesia’s national QR
                payments) and supplier receipts with Gemini, checks them against each other, and
                gives the credit officer a file in which every figure points back to its evidence.
              </p>
              <p>
                For rural banks, cooperatives and microfinance lenders. It is{' '}
                <strong>not a credit score</strong>: it verifies evidence, says how strong it is,
                and leaves every decision to a person.
              </p>
              <div className="hero-actions">
                <Link className="button on-dark" to={`/samples/${SAMPLES[0].slug}`}>
                  Open a sample credit file
                </Link>
                <a className="link-on-dark" href="#how">
                  How a file is made
                </a>
              </div>
            </div>
            <CreditFileCard sample={SAMPLES[0]} />
          </header>
        </div>

        <section className="proof" aria-label="What every file guarantees">
          <ul className="container">
            <li>
              <strong>Every figure cited</strong>
              Each amount links to the page, line or receipt it came from.
            </li>
            <li>
              <strong>Arithmetic by code</strong>
              Gemini reads and reasons; tested code does every calculation.
            </li>
            <li>
              <strong>Four honest outcomes</strong>
              Verified, partly verified, insufficient or inconsistent. Never a score.
            </li>
            <li>
              <strong>On Google Cloud</strong>
              Gemini, Firebase, Firestore and Cloud Run, with records in Jakarta.
            </li>
          </ul>
        </section>

        <section className="container specimen" aria-labelledby="specimen-heading">
          <div className="section-head">
            <h2 id="specimen-heading">How a page is read</h2>
            <p>
              The reader copies what is written, exactly as written. Code turns it into rupiah and
              adds it up, so the arithmetic can be checked line by line.
            </p>
          </div>
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

        <section id="samples" className="container section" aria-labelledby="samples-heading">
          <div className="section-head">
            <h2 id="samples-heading">Three sample files</h2>
            <p>
              Three fictional businesses, each with two months of notebook pages, receipts and,
              where they have it, QRIS history. These are the files LedgerLens produced from them,
              unedited.
            </p>
          </div>
          <div className="table-scroll">
            <table className="register">
              <thead>
                <tr>
                  <th scope="col">Business</th>
                  <th scope="col">Evidence on file</th>
                  <th scope="col">What the analyst concluded</th>
                  <th scope="col">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLES.map((sample) => (
                  <tr key={sample.slug}>
                    <th scope="row">
                      <Link to={`/samples/${sample.slug}`}>{sample.alias}</Link>
                      <span className="sub">
                        {sample.businessType}, {sample.city}
                      </span>
                    </th>
                    <td data-label="Evidence on file">{EVIDENCE_ON_FILE[sample.slug]}</td>
                    <td data-label="What the analyst concluded">{sample.headline}</td>
                    <td data-label="Outcome">
                      <span className={`outcome ${ASSESSMENT_TONE[sample.assessment]}`}>
                        {ASSESSMENT_LABEL[sample.assessment]}
                      </span>
                      <Link className="open-file" to={`/samples/${sample.slug}`}>
                        Open file
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="fine">
            The businesses and their records are fictional, generated so that their true figures
            are known.
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
              <dd>3 of 3</dd>
              <dt>sample files given the outcome their evidence supports, with every total read exactly</dt>
            </div>
          </dl>
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
