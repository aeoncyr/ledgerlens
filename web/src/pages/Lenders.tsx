// For lenders: how a three-month shadow pilot works and what it measures, how results reach the
// lender's own tools, an illustrative time-and-cost calculator and a form to request a pilot.
// Nothing here claims a customer, a partner or a measured saving; the calculator only multiplies
// the visitor's own assumptions.
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api.ts'
import SiteNav from '../components/SiteNav.tsx'
import {
  computeRoi,
  formatHours,
  formatRupiah,
  LENDER_TYPES,
  PROVINCES,
  ROI_DEFAULTS,
  sendPilotRequest,
  type LenderType,
  type PilotRequestSaved,
  type RoiInputs,
} from '../pilot.ts'
import { SAMPLES } from '../samples.ts'
import '../ai-page.css'
import '../trust-page.css'

const PILOT_STEPS = [
  {
    when: 'Week 1',
    title: 'Set up',
    text: 'We agree which kinds of files take part, enter your policy (the largest instalment ratio, haircuts, the longest tenor) and name who signs off approvals and declines.',
  },
  {
    when: 'Months 1 to 3',
    title: 'Run beside your officers',
    text: 'Your officers work exactly as today. For the same files, the owner or the officer also sends the records to LedgerLens. Your decision never depends on it: that is what “shadow” means.',
  },
  {
    when: 'Each decision',
    title: 'Agree or disagree',
    text: 'The officer records whether they agree with LedgerLens’s assessment, and why not when they don’t. Those answers are the most honest test of whether it helps.',
  },
  {
    when: 'At the end',
    title: 'A one-page result',
    text: 'Your own numbers from your own files: time per file, what was caught, how often your officers agreed. You decide whether to continue.',
  },
]

const MEASURES = [
  { title: 'Files and outcomes', text: 'How many files went through, by status and by outcome.' },
  {
    title: 'Time to a decision',
    text: 'Median minutes from the first evidence to the finished analysis, and to the decision.',
  },
  {
    title: 'What was caught',
    text: 'Findings by kind, including fraud signals such as an edited QRIS screenshot or a notebook that claims more than purchases support.',
  },
  {
    title: 'Officer agreement',
    text: 'The share of files where the officer agreed with LedgerLens’s assessment.',
  },
  {
    title: 'Missing documents',
    text: 'Which records owners most often could not provide, so you know what to ask for up front.',
  },
  {
    title: 'Who started the file',
    text: 'Files the owner sent from their phone against files the officer captured on a visit.',
  },
]

const CONNECTIONS = [
  {
    title: 'Google Sheets',
    status: 'Built',
    text: 'Paste the address of a small Apps Script web app once, and each decision, accepted offer and met condition arrives as a row in your loan sheet.',
  },
  {
    title: 'Webhook',
    status: 'Built',
    text: 'The same events as JSON to Zapier, Make, n8n or your own server, each signed with HMAC-SHA256 so you can check it came from LedgerLens.',
  },
  {
    title: 'Exports',
    status: 'Built',
    text: 'Download the credit file as JSON or CSV for your loan system or credit committee pack.',
  },
  {
    title: 'Printed memo',
    status: 'Built',
    text: 'A print layout of the credit file, to save as PDF or file on paper.',
  },
  {
    title: 'WhatsApp and Calendar',
    status: 'Built',
    text: 'A prefilled WhatsApp message at every hand-off, and one click to put the field visit, with what to check on site, in Google Calendar.',
  },
  {
    title: 'An API for your loan system',
    status: 'Later',
    text: 'Not built yet. The JSON export is its base; we would build it with your core-banking or loan-system vendor.',
  },
]

type RoiField = { key: keyof RoiInputs; label: string; hint: string; step: string }

const ROI_FIELDS: RoiField[] = [
  { key: 'filesPerMonth', label: 'Files a month', hint: 'Micro loans you assess', step: '1' },
  {
    key: 'hoursPerFileToday',
    label: 'Officer hours per file today',
    hint: 'Visit, collecting records, adding up, the memo',
    step: '0.5',
  },
  {
    key: 'hoursPerFileWith',
    label: 'Officer hours per file with LedgerLens',
    hint: 'The visit stays; the adding up and the memo draft don’t',
    step: '0.5',
  },
  {
    key: 'hourlyCost',
    label: 'Cost of an officer hour (Rp)',
    hint: 'Salary and overheads per working hour',
    step: '5000',
  },
  {
    key: 'feePerFile',
    label: 'Fee per file (Rp)',
    hint: 'No price is set yet; try your own',
    step: '5000',
  },
]

type RoiText = Record<keyof RoiInputs, string>

const asText = (inputs: RoiInputs): RoiText =>
  Object.fromEntries(Object.entries(inputs).map(([key, value]) => [key, String(value)])) as RoiText

function Calculator() {
  const [values, setValues] = useState<RoiText>(() => asText(ROI_DEFAULTS))
  const inputs = Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, Number(value)]),
  ) as RoiInputs
  const result = computeRoi(inputs)
  const rows: [string, string][] = [
    ['Officer hours a month today', formatHours(result.hoursToday)],
    ['Officer hours a month with LedgerLens', formatHours(result.hoursWith)],
    ['Officer hours freed a month', formatHours(result.hoursFreed)],
    ['Officer time today', formatRupiah(result.costToday)],
    ['Officer time with LedgerLens', formatRupiah(result.costWith)],
    ['LedgerLens fees', formatRupiah(result.fees)],
  ]

  return (
    <div className="roi">
      <form className="roi-inputs" onSubmit={(event) => event.preventDefault()}>
        <p className="roi-flag">Illustrative: replace every number with your own</p>
        {ROI_FIELDS.map((field) => (
          <label key={field.key}>
            {field.label}
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step={field.step}
              value={values[field.key]}
              onChange={(event) => setValues({ ...values, [field.key]: event.target.value })}
            />
            <span className="hint">{field.hint}</span>
          </label>
        ))}
        <button
          type="button"
          className="button quiet"
          onClick={() => setValues(asText(ROI_DEFAULTS))}
        >
          Reset to the illustration
        </button>
      </form>
      <div className="roi-result" aria-live="polite">
        <table className="roi-table">
          <caption className="visually-hidden">A month under these assumptions</caption>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td className="mono">{value}</td>
              </tr>
            ))}
            <tr className="roi-total">
              <th scope="row">Saved a month, after fees</th>
              <td className="mono">{formatRupiah(result.netMonthly)}</td>
            </tr>
            <tr>
              <th scope="row">Saved a year, after fees</th>
              <td className="mono">{formatRupiah(result.netYearly)}</td>
            </tr>
          </tbody>
        </table>
        <p className="fine">
          It pays for itself while the fee per file stays under{' '}
          <strong className="mono">{formatRupiah(result.breakEvenFee)}</strong>, the officer time
          it frees per file. These are your assumptions multiplied out, not results we have
          measured; the time saved is exactly what a pilot measures.
        </p>
      </div>
    </div>
  )
}

type FormState = {
  lenderName: string
  lenderType: LenderType | ''
  province: string
  filesPerMonth: string
  contactName: string
  email: string
  whatsapp: string
  consent: boolean
}

const EMPTY_FORM: FormState = {
  lenderName: '',
  lenderType: '',
  province: '',
  filesPerMonth: '',
  contactName: '',
  email: '',
  whatsapp: '',
  consent: false,
}

/** The first thing to fix, in plain words, or null when the form can be sent. */
function problem(form: FormState): string | null {
  if (form.lenderName.trim().length < 2) return 'Add the name of your institution.'
  if (!form.lenderType) return 'Choose what kind of lender you are.'
  if (!form.province) return 'Choose the province where a pilot would run.'
  const files = Number(form.filesPerMonth)
  if (!Number.isInteger(files) || files < 1)
    return 'Add roughly how many micro-loan files you assess a month, as a whole number.'
  if (form.contactName.trim().length < 2) return 'Add the name of the person we should reply to.'
  const email = form.email.trim()
  const whatsapp = form.whatsapp.trim()
  if (!email && !whatsapp) return 'Add an email address or a WhatsApp number, so we can reply.'
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
    return 'That email address doesn’t look complete.'
  if (whatsapp && !/^\+?[0-9][0-9 ()-]{6,22}[0-9]$/.test(whatsapp))
    return 'That WhatsApp number doesn’t look right. Use digits, for example 0812 3456 7890.'
  if (!form.consent) return 'Tick the box to let us keep these details, so we can reply.'
  return null
}

function RequestForm() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [saved, setSaved] = useState<PilotRequestSaved | null>(null)
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const found = problem(form)
    setError(found)
    if (found || !form.lenderType) return
    setSending(true)
    try {
      setSaved(
        await sendPilotRequest({
          lenderName: form.lenderName.trim(),
          lenderType: form.lenderType,
          province: form.province,
          filesPerMonth: Number(form.filesPerMonth),
          contactName: form.contactName.trim(),
          email: form.email.trim() || null,
          whatsapp: form.whatsapp.trim() || null,
          consent: form.consent,
        }),
      )
    } catch (err) {
      // The API answers in plain words; anything else (a network failure, a field it refused in
      // its own format) gets one calm sentence instead of raw text.
      const plain = err instanceof ApiError && typeof err.message === 'string' && err.status < 500
      setError(
        plain && !err.message.startsWith('[')
          ? err.message
          : 'We couldn’t send your request just now. Check your connection and try again.',
      )
    } finally {
      setSending(false)
    }
  }

  if (saved) {
    return (
      <div className="form pilot-done" role="status">
        <h3>Thank you, your request is saved</h3>
        <p>
          We’ll reply by {saved.replyBy === 'email' ? 'email' : 'WhatsApp'} to arrange a first
          conversation. LedgerLens is a hackathon prototype today, so a pilot starts with that
          conversation and the production changes listed on{' '}
          <Link to="/trust">Trust and data</Link>, not with a contract.
        </p>
        <p className="fine">Reference: {saved.id}</p>
      </div>
    )
  }

  return (
    <form className="form pilot-form" onSubmit={submit} noValidate>
      <div className="form-row">
        <label>
          Institution
          <input
            value={form.lenderName}
            onChange={(event) => set('lenderName', event.target.value)}
            maxLength={120}
            autoComplete="organization"
            placeholder="BPR …"
          />
        </label>
        <label>
          Kind of lender
          <select
            value={form.lenderType}
            onChange={(event) => set('lenderType', event.target.value as LenderType | '')}
          >
            <option value="">Choose…</option>
            {LENDER_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="form-row">
        <label>
          Province
          <select value={form.province} onChange={(event) => set('province', event.target.value)}>
            <option value="">Choose…</option>
            {PROVINCES.map((province) => (
              <option key={province}>{province}</option>
            ))}
          </select>
        </label>
        <label>
          Micro-loan files a month
          <input
            type="number"
            inputMode="numeric"
            min="1"
            step="1"
            value={form.filesPerMonth}
            onChange={(event) => set('filesPerMonth', event.target.value)}
          />
          <span className="hint">A rough number is fine</span>
        </label>
      </div>
      <label>
        Your name
        <input
          value={form.contactName}
          onChange={(event) => set('contactName', event.target.value)}
          maxLength={120}
          autoComplete="name"
        />
      </label>
      <div className="form-row">
        <label>
          Email
          <input
            type="email"
            value={form.email}
            onChange={(event) => set('email', event.target.value)}
            maxLength={200}
            autoComplete="email"
          />
        </label>
        <label>
          or WhatsApp
          <input
            type="tel"
            value={form.whatsapp}
            onChange={(event) => set('whatsapp', event.target.value)}
            maxLength={30}
            autoComplete="tel"
            placeholder="0812 3456 7890"
          />
        </label>
      </div>
      <label className="pilot-consent">
        <input
          type="checkbox"
          checked={form.consent}
          onChange={(event) => set('consent', event.target.checked)}
        />
        <span>
          LedgerLens may store these details and use them only to reply about a pilot. Ask us and
          we delete them.
        </span>
      </label>
      {error && (
        <div className="error" role="alert">
          <p>{error}</p>
        </div>
      )}
      <button className="button" type="submit" disabled={sending}>
        {sending ? 'Sending…' : 'Request a pilot'}
      </button>
      <p className="fine">
        We only store what you type here, and nobody else can read it. We’ll reply by email or
        WhatsApp.
      </p>
    </form>
  )
}

export default function Lenders() {
  return (
    <>
      <SiteNav />
      <main className="ai-page trust-page">
        <header className="ai-hero">
          <div className="container">
            <h1>LedgerLens for lenders</h1>
            <p>
              For rural banks (BPR and BPRS), cooperatives and microfinance lenders that lend to
              micro businesses without bank statements and can’t build their own tools. Try it
              beside your officers for three months, on your own files, before deciding anything.
            </p>
            <div className="hero-actions">
              <a className="button on-dark" href="#request">
                Request a pilot
              </a>
              <Link className="button ghost-on-dark" to={`/demo/${SAMPLES[0].slug}`}>
                Play the demo story
              </Link>
            </div>
          </div>
        </header>

        <section className="container ai-section" aria-labelledby="pilot-heading">
          <h2 id="pilot-heading">How a three-month shadow pilot works</h2>
          <p className="ai-lead">
            LedgerLens runs alongside your officers without affecting a single decision, so you can
            compare its files with your own judgment at no risk. The pilot is free. Before the first
            real file, LedgerLens moves to the paid Gemini tier and to storage in Jakarta, as{' '}
            <Link to="/trust">Trust and data</Link> describes.
          </p>
          <ol className="ai-stages pilot-steps">
            {PILOT_STEPS.map((step, index) => (
              <li key={step.title}>
                <h3>
                  <span className="ai-stage-number">{index + 1}</span>
                  {step.title}
                  <span className="pilot-when">{step.when}</span>
                </h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="ai-band" aria-labelledby="measure-heading">
          <div className="container ai-section">
            <h2 id="measure-heading">What the pilot measures</h2>
            <p className="ai-lead">
              The officer app counts these from your workspace’s own files, so the result is about
              your lending, not a market study. Later, with consent, the question that matters most:
              do files LedgerLens verified repay as well as your usual ones?
            </p>
            <div className="ai-grid trust-grid">
              {MEASURES.map((measure) => (
                <div key={measure.title}>
                  <h3>{measure.title}</h3>
                  <p>{measure.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="container ai-section" aria-labelledby="connect-heading">
          <h2 id="connect-heading">Results land in the tools you already use</h2>
          <p className="ai-lead">
            No IT project is needed to start. The officer sets these up on the Integrations page of
            the officer app.
          </p>
          <div className="ai-agents">
            {CONNECTIONS.map((item) => (
              <article
                key={item.title}
                className={`ai-agent ${item.status === 'Built' ? 'python' : 'later'}`}
              >
                <header>
                  <h3>{item.title}</h3>
                  <span className="ai-kind">{item.status}</span>
                </header>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="ai-band" aria-labelledby="roi-heading">
          <div className="container ai-section">
            <h2 id="roi-heading">What it could save you: try your own numbers</h2>
            <p className="ai-lead">
              Officer time is the cost LedgerLens is meant to cut. The starting numbers below are an
              illustration, not a measurement and not a price; put in your own.
            </p>
            <Calculator />
          </div>
        </section>

        <section className="container ai-section" id="request" aria-labelledby="request-heading">
          <h2 id="request-heading">Request a pilot</h2>
          <p className="ai-lead">
            Tell us a little about your institution. We start narrow: one province, one or two
            lenders and the kinds of businesses you lend to most.
          </p>
          <RequestForm />
        </section>
      </main>
      <footer className="footer">
        <div className="container">
          <span>Built with Gemini, Firebase, Firestore and Cloud Run</span>
          <span>
            <Link to="/trust">Trust and data</Link> · <Link to="/">Back to LedgerLens</Link>
          </span>
        </div>
      </footer>
    </>
  )
}
