// How LedgerLens uses AI: every agent, the model it runs on, what it returns, and the guardrails
// that keep numbers honest. Everything here describes the deployed system; nothing is aspirational.
import { Link } from 'react-router-dom'
import SiteNav from '../components/SiteNav.tsx'
import { SAMPLES } from '../samples.ts'
import { SPECIMEN_LINES } from '../specimen.ts'
import '../ai-page.css'

type Agent = {
  name: string
  kind: 'Gemini' | 'Python'
  reads: string
  returns: string
  guard: string
}

const READERS = 'gemini-3.5-flash-lite, then gemini-3.1-flash-lite'
const WRITERS = 'gemini-3.8-flash, then 3.7, 3.6 and 3 Flash · low thinking'

const AGENTS: { stage: string; agents: Agent[] }[] = [
  {
    stage: 'Read · in parallel, one reader per kind of evidence',
    agents: [
      {
        name: 'Notebook reader',
        kind: 'Gemini',
        reads: 'Photos of handwritten notebook pages in Indonesian shorthand ("1,5jt", "kasbon").',
        returns: 'Every line: date, words, amount exactly as written, kind (sale, purchase, credit, expense), confidence, crossed-out text.',
        guard: 'Each page is read twice with different instructions. Lines where the two readings disagree go to the officer to confirm on the photo.',
      },
      {
        name: 'Receipt reader',
        kind: 'Gemini',
        reads: 'Printed or handwritten supplier receipts (nota).',
        returns: 'Merchant, date, items, subtotal, discount and the total as written.',
        guard: 'Code adds up the items and compares them with the printed total.',
      },
      {
        name: 'QRIS reader',
        kind: 'Gemini',
        reads: 'Screenshots of QRIS and e-wallet history.',
        returns: 'Each payment row, the printed totals, and any visible signs of editing.',
        guard: 'Code checks the rows can add up to the printed total; if not, the screenshot may have been edited.',
      },
      {
        name: 'Interview listener',
        kind: 'Gemini',
        reads: 'A short recorded interview in Bahasa Indonesia (audio).',
        returns: 'Each claim the owner makes, in their own words, with the minute and second it was said.',
        guard: 'Amounts stay as spoken; code converts per-day and per-week claims into months.',
      },
      {
        name: 'Photo assessor',
        kind: 'Gemini',
        reads: 'Photos of the shop and its stock.',
        returns: 'What kind of business it shows, how well stocked it is, and anything that looks staged.',
        guard: 'It never estimates money; photos test plausibility only.',
      },
    ],
  },
  {
    stage: 'Calculate',
    agents: [
      {
        name: 'Calculator',
        kind: 'Python',
        reads: 'Everything the readers copied.',
        returns: 'Rupiah from "1,5jt", calendar months from "Sep - minggu 1", monthly cash flow by evidence tier, and arithmetic checks.',
        guard: 'Plain, unit-tested code. The model never does arithmetic.',
      },
    ],
  },
  {
    stage: 'Cross-check',
    agents: [
      {
        name: 'Verifier',
        kind: 'Gemini',
        reads: 'The whole case file: every reading with its locator, the computed figures and the arithmetic checks.',
        returns: 'Findings, each cited to a page and line or a moment in the recording, with a polite question for the owner in Bahasa Indonesia and English.',
        guard: 'Code keeps the final say on the severity of its own checks; an owner’s answer can never clear a material contradiction in the figures.',
      },
    ],
  },
  {
    stage: 'Apply the lender’s policy',
    agents: [
      {
        name: 'Policy',
        kind: 'Python',
        reads: 'The cash flow, the findings and the lender’s parameters.',
        returns: 'One of four outcomes, a haircut, and the largest instalment the policy allows.',
        guard: 'No automatic rejection exists in the code. A person decides.',
      },
    ],
  },
  {
    stage: 'Write',
    agents: [
      {
        name: 'Memo writer',
        kind: 'Gemini',
        reads: 'The case file, the findings and the outcome.',
        returns: 'A 5C credit memo (Character, Capacity, Capital, Collateral, Conditions) and a summary for the owner in English and Bahasa Indonesia.',
        guard: 'It explains the outcome; it cannot change it.',
      },
    ],
  },
]

const sample = SPECIMEN_LINES.filter((line) => line.written).slice(0, 3).map((line) => ({
  line: line.line,
  date_text: line.date,
  description: line.description,
  amount_text: line.written,
  kind: line.kind,
}))

const hendra = SAMPLES.find((s) => s.slug === 'pak-hendra')

export default function HowItWorks() {
  return (
    <>
      <SiteNav />
      <main className="ai-page">
        <header className="ai-hero">
          <div className="container">
            <h1>How LedgerLens uses AI</h1>
            <p>
              Gemini reads, listens and reasons. Plain, tested code computes every number. A person
              makes every decision. This page shows each agent, the model it runs on, what it
              returns, and the guardrails between them.
            </p>
          </div>
        </header>

        <section className="container ai-section" aria-labelledby="pipeline-heading">
          <h2 id="pipeline-heading">The pipeline, agent by agent</h2>
          <p className="ai-lead">
            Readers run on <span className="mono">{READERS}</span>; the verifier and the memo
            writer on <span className="mono">{WRITERS}</span>. Every Gemini call returns JSON that
            must match a schema.
          </p>
          <ol className="ai-stages">
            {AGENTS.map((stage, index) => (
              <li key={stage.stage}>
                <h3>
                  <span className="ai-stage-number">{index + 1}</span>
                  {stage.stage}
                </h3>
                <div className="ai-agents">
                  {stage.agents.map((agent) => (
                    <article key={agent.name} className={`ai-agent ${agent.kind.toLowerCase()}`}>
                      <header>
                        <strong>{agent.name}</strong>
                        <span className="ai-kind">{agent.kind}</span>
                      </header>
                      <dl>
                        <dt>Reads</dt>
                        <dd>{agent.reads}</dd>
                        <dt>Returns</dt>
                        <dd>{agent.returns}</dd>
                        <dt>Guardrail</dt>
                        <dd>{agent.guard}</dd>
                      </dl>
                    </article>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="ai-band" aria-labelledby="guard-heading">
          <div className="container ai-section ai-two">
            <div>
              <h2 id="guard-heading">The model never produces a number</h2>
              <p>
                Readers copy amounts exactly as written. Code turns them into rupiah. The verifier and
                the memo writer may mention a figure only by its name, such as{' '}
                <code>[[revenue_low]]</code>; code fills in the value. A guard checks every sentence
                they write: an amount that is neither a named figure nor quoted exactly as the
                evidence writes it is sent back once, and removed if it comes back again.
              </p>
            </div>
            <div className="ai-code">
              <p className="ai-code-label">What the writer returns</p>
              <pre>{`"capacity": "QRIS proves [[revenue_low]] a month;
 the notebook claims [[revenue_high]]."`}</pre>
              <p className="ai-code-label">What the lender reads</p>
              <pre>{`QRIS proves Rp 8.594.500 a month;
 the notebook claims Rp 24.845.000.`}</pre>
              <p className="ai-code-label">Rejected by the guard</p>
              <pre>{`"daily sales of Rp 600"   ← not a named figure,
                            not written that way`}</pre>
            </div>
          </div>
        </section>

        <section className="container ai-section ai-two" aria-labelledby="output-heading">
          <div>
            <h2 id="output-heading">Structured output, not chat</h2>
            <p>
              Each reader answers with JSON that must match a Pydantic schema, so every value has a
              place, a confidence and a locator. This is the notebook reader’s real output for the
              first lines of the sample page on the home page.
            </p>
            <p>
              <Link to="/#how">See the page beside its reading</Link>
            </p>
          </div>
          <div className="ai-code">
            <p className="ai-code-label">Notebook reader · gemini-3.8-flash · first lines</p>
            <pre>{JSON.stringify(sample, null, 1)}</pre>
          </div>
        </section>

        <section className="container ai-section" aria-labelledby="loop-heading">
          <h2 id="loop-heading">People stay in the loop</h2>
          <div className="ai-grid">
            <div>
              <h3>Disputed readings</h3>
              <p>
                When the two readings of a page disagree, the officer sees the photo and picks what
                is written. Code recomputes the cash flow with that answer.
              </p>
            </div>
            <div>
              <h3>Questions for the owner</h3>
              <p>
                The verifier writes polite questions in Bahasa Indonesia. The owner answers by
                typing or by voice, which Gemini transcribes, or prefers not to answer, which is
                recorded neutrally. At most two rounds.
              </p>
            </div>
            <div>
              <h3>A person decides</h3>
              <p>
                The officer approves, declines or asks for more, always with a written reason. Every
                step is kept in an audit log.
              </p>
            </div>
          </div>
        </section>

        <section className="ai-band" aria-labelledby="reliability-heading">
          <div className="container ai-section">
            <h2 id="reliability-heading">Built to stay up on a free tier</h2>
            <div className="ai-grid">
              <div>
                <h3>Model routing</h3>
                <p>
                  Each Gemini model has its own daily quota, so the work is split by role: readers on
                  Flash-Lite, the verifier and memo writer on a chain of Flash models. A busy model
                  hands over to the next at once.
                </p>
              </div>
              <div>
                <h3>Pacing and limits</h3>
                <p>
                  Calls are paced under each model’s per-minute limit, and the demo caps runs a day.
                  The sample files never call Gemini, so they always open.
                </p>
              </div>
              <div>
                <h3>Synthetic evaluation data</h3>
                <p>
                  Test notebooks, receipts and QRIS screenshots are generated with known true values,
                  and the owner interviews are voiced with Gemini’s text-to-speech.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="container ai-section" aria-labelledby="measured-heading">
          <h2 id="measured-heading">Measured, and what is not proven yet</h2>
          <div className="ai-two">
            <ul className="ai-list">
              <li>
                <strong>28 of 29</strong> receipt totals read exactly from real photographed receipts
                (public CORD dataset).
              </li>
              <li>
                <strong>162 of 162</strong> amounts read exactly from synthetic notebook pages in eight
                handwriting fonts.
              </li>
              <li>
                <strong>3 of 3</strong> sample files with every monthly total read exactly and the
                outcome their evidence supports
                {hendra ? `, including ${hendra.alias}, whose own words contradict his notebook` : ''}.
              </li>
            </ul>
            <ul className="ai-list muted">
              <li>Real handwriting from our own notebooks is being measured next.</li>
              <li>All businesses, records and interviews here are fictional.</li>
              <li>
                LedgerLens is not a credit score: predicting repayment needs repayment history these
                businesses don’t have yet.
              </li>
            </ul>
          </div>
        </section>
      </main>
      <footer className="footer">
        <div className="container">
          <span>Built with Gemini, Firebase, Firestore and Cloud Run</span>
          <span>
            <Link to="/">Back to LedgerLens</Link>
          </span>
        </div>
      </footer>
    </>
  )
}
