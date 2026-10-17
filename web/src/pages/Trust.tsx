// Trust and data: what runs where today, what changes before a lender uses real data, the owner's
// rights, the security already built, a model card for every Gemini agent and a map of the rules
// that apply. Everything in the "today" columns describes the deployed system; plans say so.
import { Link } from 'react-router-dom'
import SiteNav from '../components/SiteNav.tsx'
import { READERS, WRITERS } from '../models.ts'
import '../ai-page.css'
import '../trust-page.css'

type Layer = { part: string; today: string; production: string }

const LAYERS: Layer[] = [
  {
    part: 'AI model',
    today:
      'Gemini Developer API (Google AI Studio), free tier, on Google’s global endpoint. Google may use free-tier inputs to improve its products, so the prototype processes only synthetic data.',
    production:
      'The paid Gemini API or Vertex AI, where inputs are not used that way; the code already supports both. Processing in Jakarta, or the nearest region Google offers for the chosen model, agreed with each lender.',
  },
  {
    part: 'API',
    today: 'Cloud Run in Jakarta (asia-southeast2). It scales to zero when nobody uses it.',
    production: 'Cloud Run in Jakarta, with uptime and support hours agreed with each lender.',
  },
  {
    part: 'Records',
    today:
      'Firestore in Jakarta: files, readings, findings, decisions, share codes and the audit log.',
    production: 'Firestore in Jakarta, unchanged.',
  },
  {
    part: 'Photos and voice notes',
    today: 'Cloud Storage for Firebase in the United States (us-east1). The consent screen says so.',
    production: 'A storage bucket in Jakarta.',
  },
  {
    part: 'Sign-in',
    today:
      'Anonymous Firebase sign-in, so judges meet no login wall. Each browser is its own user.',
    production:
      'Named accounts per lender: officers, supervisors and an administrator, with branches.',
  },
  {
    part: 'Data',
    today: 'Synthetic only: every business, notebook, receipt and interview is fictional.',
    production:
      'Real records under a data processing agreement with each lender, with retention and deletion rules agreed in writing.',
  },
]

const RIGHTS = [
  {
    title: 'Consent comes first',
    text: 'Nothing is captured before the owner agrees, on their own phone or on the officer’s screen during a visit, in Bahasa Indonesia or English. The text says who will see the file, where it is stored, that Gemini reads it and that a person decides. The agreement and its time are stored with the file.',
  },
  {
    title: 'One lender at a time',
    text: 'A file the owner starts is seen by nobody until they share a link or code, and then by one lender only: a second officer opening the same link is refused. There is no marketplace and no lender directory.',
  },
  {
    title: 'Stop sharing',
    text: 'The owner can stop sharing at any time from their phone. The code stops working and the lender loses access to the file in LedgerLens. A copy the lender already exported or printed stays with the lender.',
  },
  {
    title: 'Delete my file',
    text: 'The owner can delete the file for good: every record, reading, check, memo, decision, code and stored photo or recording. It is refused only while a lender is deciding on it or after the owner accepted a loan on it, and the owner is told why.',
  },
  {
    title: 'Each side sees its part',
    text: 'The owner reads their own records, the progress of a check, a summary written for them and the lender’s final decision. The lender’s findings, memo and audit log are for the lender only.',
  },
  {
    title: 'No identity numbers',
    text: 'LedgerLens stores a business alias, never an owner’s legal name or national ID number (NIK). It never reads contacts or anything else on the phone.',
  },
]

const SECURITY = [
  {
    title: 'Browsers only read',
    text: 'Firestore security rules let a browser read only the files it is on, and write nothing. Every write goes through the API, so results can’t be changed from the browser.',
  },
  {
    title: 'Uploads into your own folder',
    text: 'Storage rules let each user upload only into their own folder of a file, only images or audio under 15 MB, and never overwrite or delete.',
  },
  {
    title: 'Signed webhooks',
    text: 'Every delivery to a lender’s Google Sheet or webhook carries an HMAC-SHA256 signature (X-LedgerLens-Signature) made with a secret only that lender sees.',
  },
  {
    title: 'SSRF guard',
    text: 'A webhook address must be https; its host is resolved and every address must be public; the connection goes to the address that was checked, redirects are not followed and nothing waits longer than five seconds.',
  },
  {
    title: 'Audit log',
    text: 'Every step is recorded with who did it and when: creation, consent, evidence, each check, sharing, opening by a lender, the decision and its sign-off, and the owner’s reply.',
  },
  {
    title: 'Four-eyes decisions',
    text: 'An approval or a decline needs a second person at the lender to sign off through their own link. On the judges’ demo copies one browser may play both, and only there.',
  },
  {
    title: 'Figure guard',
    text: 'Gemini may mention a figure only by its name, which code fills in. A sentence with any other amount is sent back once, and the amount is removed if it comes back again.',
  },
  {
    title: 'Limits and secrets',
    text: 'Daily limits per visitor and for the site protect the free tier. The Gemini key lives only in Cloud Run’s settings; the public repository holds no secrets.',
  },
]

const NOT_YET = [
  'An independent penetration test.',
  'A security certification (for example ISO/IEC 27001) and the vendor due-diligence pack lenders must collect from IT providers.',
  'Named accounts with roles per lender, instead of anonymous sign-in.',
  'A data processing agreement, a retention schedule, a breach-notification procedure and a named data protection officer.',
]

type Card = {
  name: string
  purpose: string
  model: string
  inputs: string
  outputs: string
  guardrail: string
  limits: string
  human: string
}

const CARDS: Card[] = [
  {
    name: 'Notebook reader',
    purpose: 'Copy every line of a handwritten notebook page, exactly as written.',
    model: READERS,
    inputs: 'A photo of one notebook page, often in Indonesian shorthand (“1,5jt”, “kasbon”).',
    outputs:
      'Each line’s date, words, amount as written, kind (sale, purchase, credit, expense), confidence and crossed-out text; or that the page is not legible.',
    guardrail:
      'Each page is read twice with different instructions and the readings are compared. Amounts stay as text; code turns them into rupiah.',
    limits:
      'Measured only on synthetic pages in eight handwriting fonts (162 of 162 amounts exact). Real handwriting is being measured next. Crossed-out corrections caused the earlier misses.',
    human: 'Lines where the two readings disagree go to the officer to confirm on the photo.',
  },
  {
    name: 'Receipt reader',
    purpose: 'Read supplier receipts (nota), printed or handwritten.',
    model: READERS,
    inputs: 'A photo of one receipt.',
    outputs: 'Merchant, date, items, subtotal, discount and the total, each as written.',
    guardrail: 'Code adds up the items and compares them with the printed total.',
    limits:
      'Measured on real printed receipts from the public CORD dataset (28 of 29 totals exact). Handwritten nota are measured only on our synthetic samples.',
    human: 'Every citation opens the receipt photo beside what was read.',
  },
  {
    name: 'QRIS reader',
    purpose: 'Read QRIS and e-wallet payment history from screenshots.',
    model: READERS,
    inputs: 'Screenshots of the merchant app’s history.',
    outputs: 'Each payment row, the printed totals and any visible signs of editing.',
    guardrail:
      'Code checks that the rows can add up to the printed total; if they don’t, only the listed rows count and the screenshot is flagged as possibly edited.',
    limits:
      'An edit that keeps rows and total consistent can’t be seen in an image. A screenshot is weaker than history read at the source.',
    human:
      'When the owner sent the only QRIS history, code asks the officer to confirm it in the merchant app before the file can be more than partially verified.',
  },
  {
    name: 'Interview listener',
    purpose: 'List what the owner says about the business in a short recorded interview.',
    model: READERS,
    inputs:
      'Audio in Bahasa Indonesia; also the owner’s spoken answers to questions, which it transcribes and translates.',
    outputs: 'Each claim in the owner’s own words, with the minute and second it was said.',
    guardrail: 'Amounts stay as spoken; code converts per-day and per-week claims into months.',
    limits:
      'Tested on interviews voiced with Gemini’s text-to-speech, not on real voices, regional accents, Javanese or Sundanese, or noisy markets.',
    human: 'The officer can play the recording beside the timestamped claims.',
  },
  {
    name: 'Photo assessor',
    purpose: 'Test whether the shop and its stock look like the business described.',
    model: READERS,
    inputs: 'Photos of the shop and its stock.',
    outputs: 'What kind of business it shows, how well stocked it is and anything that looks staged.',
    guardrail: 'It never estimates money: photos test plausibility only.',
    limits: 'Borrowed stock or a staged photo can look real; a photo says nothing about sales.',
    human: 'The officer’s field visit is where stock is seen in person.',
  },
  {
    name: 'Verifier',
    purpose: 'Cross-check every source against the others and explain what doesn’t fit.',
    model: WRITERS,
    inputs:
      'The whole case file: each reading with its locator, who captured each item, the computed figures, the arithmetic checks, declared other debts and the owner’s answers.',
    outputs:
      'Findings, each cited to a page and line or a moment in the recording, and polite questions for the owner in Bahasa Indonesia and English.',
    guardrail:
      'Figures only by name, behind the figure guard. Code keeps the final say on the severity of its own checks, and an owner’s answer can never clear a material contradiction in the figures.',
    limits:
      'It can miss a contradiction or raise one that isn’t there. When every Flash model is busy, Flash-Lite writes the findings, and the trace shows which model did.',
    human: 'The officer reads each finding beside its evidence before deciding.',
  },
  {
    name: 'Memo writer',
    purpose: 'Write the credit memo for the lender and a summary for the owner.',
    model: WRITERS,
    inputs: 'The case file, the findings and the outcome that the lender’s policy (code) set.',
    outputs:
      'A 5C memo (Character, Capacity, Capital, Collateral, Conditions) and an owner summary in English and Bahasa Indonesia.',
    guardrail: 'It explains the outcome and cannot change it. Figures only by name.',
    limits: 'Wording can be generic, and a Flash-Lite memo is lighter than a Flash one.',
    human: 'The officer, and for an approval or decline a second person, read it before deciding.',
  },
  {
    name: 'Decision letter writer',
    purpose: 'Tell the owner in plain words what the lender decided and what happens next.',
    model: READERS,
    inputs: 'The decision, its reason and the offer or conditions, with every figure by name.',
    outputs: 'A short letter in English and Bahasa Indonesia.',
    guardrail:
      'The figure guard checks every sentence. If Gemini is busy or slow (over 25 seconds), a fixed template says the same thing.',
    limits: 'The tone can be stiff, and the template is plainer still.',
    human: 'It is written only after people have made and signed off the decision.',
  },
]

type Rule = { name: string; asks: string; built: string; needed: string }

const RULES: Rule[] = [
  {
    name: 'UU PDP (Law 27 of 2022 on Personal Data Protection)',
    asks: 'A lawful basis such as consent, collecting only what is needed, the right to withdraw and to delete, security, and clear roles for whoever controls and processes data.',
    built:
      'Consent before capture, stored with its time; withdraw by stopping sharing; delete my file; a business alias instead of a name or NIK.',
    needed:
      'Agreeing with each lender who controls and who processes the data, a data processing agreement, retention rules, breach notification and a named data protection officer.',
  },
  {
    name: 'OJK’s 2025 guideline on AI in Indonesian banking',
    asks: 'Accountability, human oversight and reliability of AI used in banking.',
    built:
      'A person makes every decision with a written reason, two people for approvals and declines, an audit log, cited findings and a model card per agent.',
    needed:
      'A model-governance document a lender’s risk team can adopt, and validation on the lender’s own files during a pilot.',
  },
  {
    name: 'POJK 29/2024 on alternative credit rating',
    asks: 'A licence for rating creditworthiness from alternative data and sharing those ratings.',
    built:
      'LedgerLens produces no score or rating; it verifies evidence for one lender, chosen by the owner, one file at a time.',
    needed:
      'A licensed partner, or our own licence, before any file or fraud signal is reused across lenders.',
  },
  {
    name: 'Credit bureau check (SLIK, run by OJK)',
    asks: 'Lenders check a borrower’s existing loans with SLIK before lending.',
    built: 'LedgerLens does not query SLIK and never replaces the check.',
    needed: 'Nothing changes: the lender runs SLIK as it does today.',
  },
  {
    name: 'OJK rules on banks’ IT vendors',
    asks: 'Banks vet and oversee the IT providers they rely on.',
    built: 'This page, the public code repository and the security listed above.',
    needed: 'A security pack: penetration test, access controls, an uptime commitment and a certification plan.',
  },
]

export default function Trust() {
  return (
    <>
      <SiteNav />
      <main className="ai-page trust-page">
        <header className="ai-hero">
          <div className="container">
            <h1>Trust and data</h1>
            <p>
              Where LedgerLens runs today, what changes before a lender uses it with real people’s
              records, the owner’s rights, the security already built, and a model card for each
              Gemini agent. This is a hackathon prototype: where something isn’t done yet, this page
              says so.
            </p>
          </div>
        </header>

        <section className="container ai-section" aria-labelledby="where-heading">
          <h2 id="where-heading">What runs where: today, and in production</h2>
          <p className="ai-lead">
            The prototype is built to be free to run for the judging period. A lender pilot changes
            three things: the paid Gemini tier, storage in Jakarta and named accounts.
          </p>
          <div className="table-scroll">
            <table className="register trust-table">
              <thead>
                <tr>
                  <th scope="col">Part</th>
                  <th scope="col">Today (this prototype)</th>
                  <th scope="col">Before real data (the plan)</th>
                </tr>
              </thead>
              <tbody>
                {LAYERS.map((layer) => (
                  <tr key={layer.part}>
                    <th scope="row">{layer.part}</th>
                    <td>{layer.today}</td>
                    <td>{layer.production}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="ai-band" aria-labelledby="rights-heading">
          <div className="container ai-section">
            <h2 id="rights-heading">The owner’s rights, as built</h2>
            <div className="ai-grid trust-grid">
              {RIGHTS.map((right) => (
                <div key={right.title}>
                  <h3>{right.title}</h3>
                  <p>{right.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="container ai-section" aria-labelledby="security-heading">
          <h2 id="security-heading">Security already built</h2>
          <div className="ai-grid trust-grid">
            {SECURITY.map((item) => (
              <div key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>
            ))}
          </div>
          <div className="trust-not-yet">
            <h3>Not done yet</h3>
            <ul className="ai-list muted">
              {NOT_YET.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="ai-band" aria-labelledby="cards-heading">
          <div className="container ai-section">
            <h2 id="cards-heading">Model cards</h2>
            <p className="ai-lead">
              One card for each agent that calls Gemini. The calculator and the lender’s policy are
              plain, unit-tested Python, not AI: they compute every number and set the outcome.{' '}
              <Link to="/ai">See how the agents fit together</Link>.
            </p>
            <div className="ai-agents trust-cards">
              {CARDS.map((card) => (
                <article key={card.name} className="ai-agent">
                  <header>
                    <h3>{card.name}</h3>
                    <span className="ai-kind">Gemini</span>
                  </header>
                  <dl>
                    <dt>Purpose</dt>
                    <dd>{card.purpose}</dd>
                    <dt>Model chain</dt>
                    <dd className="mono">{card.model}</dd>
                    <dt>Inputs</dt>
                    <dd>{card.inputs}</dd>
                    <dt>Outputs</dt>
                    <dd>{card.outputs} JSON that must match a schema.</dd>
                    <dt>Guardrail</dt>
                    <dd>{card.guardrail}</dd>
                    <dt>Known limits</dt>
                    <dd>{card.limits}</dd>
                    <dt>Human check</dt>
                    <dd>{card.human}</dd>
                  </dl>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="container ai-section" aria-labelledby="rules-heading">
          <h2 id="rules-heading">The rules that apply, and where we stand</h2>
          <p className="ai-lead">
            A map, not a compliance claim: no lawyer or regulator has reviewed LedgerLens yet. It
            shows what each rule asks, what the prototype already does about it and what is still
            needed.
          </p>
          <div className="table-scroll">
            <table className="register trust-table">
              <thead>
                <tr>
                  <th scope="col">Rule</th>
                  <th scope="col">What it asks</th>
                  <th scope="col">Built in the prototype</th>
                  <th scope="col">Still needed</th>
                </tr>
              </thead>
              <tbody>
                {RULES.map((rule) => (
                  <tr key={rule.name}>
                    <th scope="row">{rule.name}</th>
                    <td>{rule.asks}</td>
                    <td>{rule.built}</td>
                    <td>{rule.needed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="ai-lead">
            Running a pilot? <Link to="/lenders">See how a shadow pilot works</Link>.
          </p>
        </section>
      </main>
      <footer className="footer">
        <div className="container">
          <span>Built with Gemini, Firebase, Firestore and Cloud Run</span>
          <span>
            <Link to="/ai">How the AI works</Link> · <Link to="/">Back to LedgerLens</Link>
          </span>
        </div>
      </footer>
    </>
  )
}
