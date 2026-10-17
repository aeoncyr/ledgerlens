// The officer's decision and everything after it: recommend, wait for a second sign-off, see what
// the owner was sent and how they answered. The reviewer's sign-off panel lives here too, because
// it shows the same recommendation.
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import OfferSchedule from '../../components/OfferSchedule.tsx'
import WhatsAppButton from '../../components/WhatsAppButton.tsx'
import {
  answerOffer,
  markConditionMet,
  previewInstalment,
  recordDecision,
  signOff,
  signoffPath,
  useOwnerDecision,
  type Condition,
  type DecisionAction,
  type DecisionResult,
  type Offer,
  type OwnerDecision,
  type RecordedDecision,
} from '../../decision.ts'
import type { Application } from '../../officer.ts'
import { stressDropPct } from '../../stress.ts'
import { EVIDENCE_LABEL, type CreditFileData, type EvidenceType } from '../../types.ts'
import '../../decision.css'

const number = new Intl.NumberFormat('id-ID')
const rp = (value: number) => `Rp ${number.format(Math.round(value || 0))}`

// KUR micro loans are priced at 6% a year; the officer can change it.
const DEFAULT_RATE_PCT = 6

const ACTIONS: { key: DecisionAction; label: string; note: string }[] = [
  { key: 'approve', label: 'Approve', note: 'A second person signs it off' },
  { key: 'request_more', label: 'Ask for more evidence', note: 'Goes to the owner now' },
  { key: 'decline', label: 'Decline', note: 'A second person signs it off' },
]

const ACTION_LABEL: Record<DecisionAction, string> = {
  approve: 'Approve',
  request_more: 'Ask for more evidence',
  decline: 'Decline',
}

// Records an officer often asks for, one tap each.
const ASK_FOR: { text: string; evidenceType: EvidenceType }[] = [
  { text: 'Screenshots of three months of QRIS history', evidenceType: 'qris_history' },
  { text: 'Receipts from your suppliers for the last month', evidenceType: 'receipt' },
  { text: 'Photos of the notebook pages for another month', evidenceType: 'ledger_page' },
]

const OWNER_STATE_TEXT: Record<OwnerDecision['state'], string> = {
  offered: 'Waiting for the owner to accept or decline the offer.',
  accepted: 'The owner accepted the offer.',
  declined_by_owner: 'The owner declined the offer.',
  declined: 'The owner has the decline and its reasons.',
  requested: 'Waiting for the owner to send the records.',
  sent: 'The owner says they have sent what you asked for.',
}

type Policy = CreditFileData['policy'] | undefined

type DraftCondition = { text: string; evidenceType: EvidenceType | '' }

function ConditionsEditor({
  action,
  rows,
  onChange,
}: {
  action: DecisionAction
  rows: DraftCondition[]
  onChange: (rows: DraftCondition[]) => void
}) {
  const asking = action === 'request_more'
  const update = (index: number, patch: Partial<DraftCondition>) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  return (
    <fieldset className="decision-conditions">
      <legend>{asking ? 'Records to ask for' : 'Conditions before the money is paid out'}</legend>
      <p className="hint">
        {asking
          ? 'The owner sees each one as a line to tick off, in their own app.'
          : 'Optional. The owner marks each one done; one met by a record needs a new record sent.'}
      </p>
      {asking && (
        <div className="decision-suggest" role="group" aria-label="Common requests">
          {ASK_FOR.filter((s) => !rows.some((row) => row.text === s.text)).map((s) => (
            <button
              key={s.text}
              type="button"
              className="button quiet"
              onClick={() => onChange([...rows.filter((r) => r.text.trim()), s])}
            >
              + {EVIDENCE_LABEL[s.evidenceType]}
            </button>
          ))}
        </div>
      )}
      <ol>
        {rows.map((row, index) => (
          <li key={index}>
            <label>
              <span className="visually-hidden">
                {asking ? 'Record' : 'Condition'} {index + 1}
              </span>
              <input
                value={row.text}
                maxLength={200}
                placeholder={
                  asking ? 'What should the owner send?' : 'e.g. A photo of the new stock shelf'
                }
                onChange={(e) => update(index, { text: e.target.value })}
              />
            </label>
            <label>
              <span className="visually-hidden">Met by a record of type</span>
              <select
                value={row.evidenceType}
                onChange={(e) => update(index, { evidenceType: e.target.value as EvidenceType })}
              >
                <option value="">No record needed</option>
                {(Object.keys(EVIDENCE_LABEL) as EvidenceType[]).map((type) => (
                  <option key={type} value={type}>
                    Met by: {EVIDENCE_LABEL[type]}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="button quiet"
              aria-label={`Remove ${asking ? 'record' : 'condition'} ${index + 1}`}
              onClick={() => onChange(rows.filter((_, i) => i !== index))}
            >
              Remove
            </button>
          </li>
        ))}
      </ol>
      {rows.length < 10 && (
        <button
          type="button"
          className="button quiet"
          onClick={() => onChange([...rows, { text: '', evidenceType: '' }])}
        >
          {asking ? 'Add a record to ask for' : 'Add a condition'}
        </button>
      )}
    </fieldset>
  )
}

// The instalment the officer is about to offer, next to the largest one the policy allows.
function InstalmentPreview({
  amount,
  months,
  rate,
  policy,
}: {
  amount: number
  months: number
  rate: number
  policy: Policy
}) {
  const instalment = previewInstalment(amount, months, rate)
  const limit = policy?.maxInstallment ?? null
  const within = limit !== null && instalment <= limit
  // The same stress test as on the credit file, for the instalment on offer (see stress.ts).
  const stress = policy && within ? stressDropPct(policy, instalment) : null
  const room =
    stress === null
      ? ''
      : stress > 0
        ? `, and still within it if sales fall by up to ${stress}% (assuming costs move with sales)`
        : ', with no room for any fall in sales'
  return (
    <div className={`instalment-preview ${limit === null ? '' : within ? 'within' : 'above'}`}>
      <dl aria-live="polite">
        <div>
          <dt>Monthly instalment</dt>
          <dd className="mono">{rp(instalment)}</dd>
        </div>
        <div>
          <dt>Largest instalment the policy allows</dt>
          <dd className="mono">{limit === null ? 'None set' : rp(limit)}</dd>
        </div>
      </dl>
      <p className="fine">
        {limit === null
          ? 'The evidence was too thin for the policy to set a limit, so this offer rests on your judgement alone. The second person will see that.'
          : within
            ? `Within the policy${room}. `
            : 'Above what the verified cash flow supports. You can still recommend it; the second person will see it is above the policy. '}
        {limit !== null &&
          'Computed by code with the standard annuity formula; the API recomputes it and the schedule when you send.'}
      </p>
    </div>
  )
}

function DecisionForm({
  app,
  policy,
  onSent,
}: {
  app: Application
  policy: Policy
  onSent: (result: DecisionResult) => void
}) {
  const previous = app.decision
  // After a sign-off sends the recommendation back, start from what was recommended.
  const returned = previous?.state === 'returned' ? previous : undefined
  const [action, setAction] = useState<DecisionAction>(returned?.action ?? 'approve')
  const [reason, setReason] = useState(returned?.reason ?? '')
  const [amount, setAmount] = useState(String(returned?.offer?.amountRp ?? app.request.amount))
  const [months, setMonths] = useState(
    String(returned?.offer?.tenorMonths ?? app.request.tenorMonths),
  )
  const [rate, setRate] = useState(String(returned?.offer?.annualRatePct ?? DEFAULT_RATE_PCT))
  const [conditions, setConditions] = useState<DraftCondition[]>(
    (returned?.conditions ?? []).map((c) => ({ text: c.text, evidenceType: c.evidenceType ?? '' })),
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const amountRp = Number(amount) || 0
  const tenor = Number(months) || 0
  const ratePct = Number(rate)
  const offerValid = amountRp > 0 && tenor >= 1 && tenor <= 60 && ratePct >= 0 && ratePct <= 60
  const filled = conditions.filter((c) => c.text.trim())
  const conditionsValid = filled.every((c) => c.text.trim().length >= 5)
  const ready =
    reason.trim().length >= 5 &&
    conditionsValid &&
    (action !== 'approve' || offerValid) &&
    (action !== 'request_more' || filled.length > 0)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await recordDecision(app.id, {
        action,
        reason: reason.trim(),
        offer:
          action === 'approve'
            ? { amountRp, tenorMonths: tenor, annualRatePct: ratePct }
            : undefined,
        conditions:
          action === 'decline'
            ? []
            : filled.map((c) => ({ text: c.text.trim(), evidenceType: c.evidenceType || null })),
      })
      onSent(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  return (
    <form className="decision" onSubmit={submit} aria-labelledby="decision-heading">
      <h2 id="decision-heading">Your decision</h2>
      {returned?.signoff && (
        <div className="decision-returned" role="status">
          <strong>Sent back by the second person.</strong> “{returned.signoff.note}” Change what
          they asked for, then recommend again.
        </div>
      )}
      {previous?.action === 'request_more' && previous.state === 'final' && (
        <p className="decision-earlier">
          Earlier you asked the owner for more evidence: “{previous.reason}” The file has been
          checked again since.
        </p>
      )}
      <p className="fine">
        LedgerLens recommends; you decide. An approval or a decline is checked by a second person at
        your lender before the owner hears about it.
      </p>
      <fieldset className="choice-row">
        <legend className="visually-hidden">Decision</legend>
        {ACTIONS.map(({ key, label, note }) => (
          <label key={key} className={`choice ${action === key ? 'chosen' : ''}`}>
            <input
              type="radio"
              name="action"
              value={key}
              checked={action === key}
              onChange={() => setAction(key)}
            />
            {label}
            <span>{note}</span>
          </label>
        ))}
      </fieldset>

      {action === 'approve' && (
        <fieldset className="decision-offer">
          <legend>The offer</legend>
          <div className="form-row">
            <label>
              Amount (Rp)
              <input
                inputMode="numeric"
                required
                value={amount}
                onChange={(e) => setAmount(e.target.value.replace(/\D/g, ''))}
              />
              <span className="hint">The owner asked for {rp(app.request.amount)}.</span>
            </label>
            <label>
              Months
              <input
                type="number"
                min={1}
                max={60}
                required
                value={months}
                onChange={(e) => setMonths(e.target.value)}
              />
            </label>
            <label>
              Annual rate (%)
              <input
                type="number"
                min={0}
                max={60}
                step={0.1}
                required
                value={rate}
                onChange={(e) => setRate(e.target.value)}
              />
              <span className="hint">KUR micro loans: 6% a year.</span>
            </label>
          </div>
          {offerValid && (
            <InstalmentPreview amount={amountRp} months={tenor} rate={ratePct} policy={policy} />
          )}
        </fieldset>
      )}

      {action !== 'decline' && (
        <ConditionsEditor action={action} rows={conditions} onChange={setConditions} />
      )}

      <label>
        Reason
        <textarea
          required
          minLength={5}
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          aria-describedby="decision-reason-hint"
        />
        <span className="hint" id="decision-reason-hint">
          Goes into the audit log. The owner’s letter is written from it, so write it as you would
          explain it to them.
        </span>
      </label>
      {error && <p className="error">{error}</p>}
      <button className="button" disabled={busy || !ready}>
        {busy
          ? 'Sending…'
          : action === 'request_more'
            ? 'Send the request to the owner'
            : 'Send for a second sign-off'}
      </button>
    </form>
  )
}

function OfferFigures({ offer }: { offer: Offer }) {
  return (
    <>
      <dl className="offer-figures">
        <div>
          <dt>Amount</dt>
          <dd className="mono">{rp(offer.amountRp)}</dd>
        </div>
        <div>
          <dt>Months</dt>
          <dd className="mono">{offer.tenorMonths}</dd>
        </div>
        <div>
          <dt>Annual rate</dt>
          <dd className="mono">{offer.annualRatePct}%</dd>
        </div>
        <div>
          <dt>Monthly instalment</dt>
          <dd className="mono">{rp(offer.instalmentRp)}</dd>
        </div>
        <div>
          <dt>Total repaid</dt>
          <dd className="mono">{rp(offer.totalRp)}</dd>
        </div>
        <div>
          <dt>Largest instalment the policy allows</dt>
          <dd className={`mono ${offer.withinPolicy ? 'within' : 'above'}`}>
            {offer.maxInstallmentRp == null ? 'None set' : rp(offer.maxInstallmentRp)}
            <span className="offer-flag">
              {offer.withinPolicy
                ? 'The offer is within it'
                : offer.maxInstallmentRp == null
                  ? 'The evidence was too thin to set one'
                  : 'The offer is above it'}
            </span>
          </dd>
        </div>
      </dl>
      <OfferSchedule offer={offer} />
    </>
  )
}

function ConditionList({ conditions, title }: { conditions: Condition[]; title: string }) {
  if (conditions.length === 0) return null
  return (
    <>
      <h3>{title}</h3>
      <ul className="decision-condition-list">
        {conditions.map((c, index) => (
          <li key={index} className={c.met ? 'met' : undefined}>
            <span aria-hidden="true">{c.met ? '✓' : '○'}</span> {c.text}
            {c.evidenceType && (
              <span className="fine"> · met by: {EVIDENCE_LABEL[c.evidenceType]}</span>
            )}
            <span className="visually-hidden">{c.met ? ' (met)' : ' (not met yet)'}</span>
          </li>
        ))}
      </ul>
    </>
  )
}

// What was recommended, for the waiting panel and the reviewer.
function Recommendation({ decision }: { decision: RecordedDecision }) {
  return (
    <>
      <p>
        <strong>{ACTION_LABEL[decision.action]}.</strong> “{decision.reason}”
      </p>
      {decision.offer && <OfferFigures offer={decision.offer} />}
      <ConditionList
        conditions={decision.conditions ?? []}
        title={decision.action === 'approve' ? 'Conditions before payout' : 'Records asked for'}
      />
    </>
  )
}

function CopyLink({ url, code }: { url: string; code: string }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      ;(document.getElementById('signoff-url') as HTMLInputElement | null)?.select()
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="signoff-link">
      <label htmlFor="signoff-url">Sign-off link</label>
      <div className="answer-actions">
        <input id="signoff-url" readOnly value={url} onFocus={(e) => e.target.select()} />
        <button type="button" className="button" onClick={() => void copy()}>
          <span aria-live="polite">{copied ? 'Copied' : 'Copy link'}</span>
        </button>
      </div>
      <p className="fine">
        Or read out the code{' '}
        <strong className="mono" aria-label={code.split('').join(' ')}>
          {code}
        </strong>
        .
      </p>
    </div>
  )
}

function WaitingForSignoff({ app, code }: { app: Application; code: string }) {
  const url = `${window.location.origin}${signoffPath(code)}`
  return (
    <section className="decision waiting" aria-labelledby="decision-heading">
      <h2 id="decision-heading">Waiting for a second sign-off</h2>
      <p>
        Your recommendation is saved. Before the owner hears about it, a second person at your
        lender checks it: send them this link. They see the file without changing it, then sign it
        off or send it back to you with a note.
      </p>
      <CopyLink url={url} code={code} />
      <WhatsAppButton
        className="button whatsapp"
        label="Send to a colleague on WhatsApp"
        text={`Mohon sign-off kedua untuk berkas kredit ${app.business.alias} di LedgerLens. Second sign-off needed, please: ${url} (kode/code ${code})`}
      />
      {app.demo ? (
        <p>
          <Link className="button quiet" to={signoffPath(code)}>
            Play the supervisor: open the sign-off
          </Link>
        </p>
      ) : (
        <p className="fine">
          Trying LedgerLens alone? Open the link in a private window: it signs in as a different
          person.
        </p>
      )}
      {app.decision && <Recommendation decision={app.decision} />}
    </section>
  )
}

// The final decision, what the owner was sent, and the owner's answers as they come in.
function DecisionOutcome({ app, readOnly }: { app: Application; readOnly?: boolean }) {
  const decision = app.decision!
  const sent = useOwnerDecision(app.id)
  const [lang, setLang] = useState<'en' | 'id'>('en')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // On a file the officer started there is no owner in the app, so the officer records the
  // owner's answers, as they do the answers to questions.
  const standIn = !readOnly && !app.ownerUid

  async function act(work: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  return (
    <section className="decision done" aria-labelledby="decision-heading">
      <h2 id="decision-heading">Decision</h2>
      <p>
        <strong>{ACTION_LABEL[decision.action]}.</strong> {decision.reason}
      </p>
      {decision.signoff?.approved && (
        <p className="fine">
          Signed off by a second person
          {decision.signoff.note ? `: “${decision.signoff.note}”` : '.'} Both are in the audit log.
        </p>
      )}
      {decision.offer && <OfferFigures offer={decision.offer} />}

      {sent && (
        <div className="decision-sent">
          <h3>Sent to the owner</h3>
          <p className="fine">
            {OWNER_STATE_TEXT[sent.state]}
            {sent.state === 'sent' && sent.sentCount
              ? ` ${sent.sentCount} new record${sent.sentCount > 1 ? 's' : ''} on file; check the file again to see what they show.`
              : ''}
          </p>
          <div className="decision-letter">
            <div className="decision-letter-head">
              <span>
                Letter{' '}
                {sent.letter.source === 'gemini'
                  ? `written by ${sent.letter.model ?? 'Gemini'}, figures filled in by code`
                  : 'from the fixed template (Gemini was unavailable)'}
              </span>
              <div className="decision-letter-lang" role="group" aria-label="Letter language">
                <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>
                  English
                </button>
                <button type="button" aria-pressed={lang === 'id'} onClick={() => setLang('id')}>
                  Bahasa
                </button>
              </div>
            </div>
            <p lang={lang}>{sent.letter[lang]}</p>
          </div>
          <WhatsAppButton
            className="button whatsapp"
            label="Tell the owner on WhatsApp"
            text={
              app.ownerUid
                ? `Halo, keputusan pinjaman untuk ${app.business.alias} sudah ada di LedgerLens. Silakan buka berkas Anda: ${window.location.origin}/owner/${app.id}\n\n(Your loan decision is ready in LedgerLens.)`
                : `${sent.letter.id}\n\n${sent.letter.en}`
            }
          />
          <ConditionList
            conditions={sent.conditions}
            title={sent.action === 'approve' ? 'Conditions before payout' : 'Records asked for'}
          />
          {standIn && sent.state === 'offered' && (
            <div className="answer-actions">
              <span className="fine">Record the owner’s answer:</span>
              <button
                className="button quiet"
                disabled={busy}
                onClick={() => void act(() => answerOffer(app.id, true))}
              >
                The owner accepts
              </button>
              <button
                className="button quiet"
                disabled={busy}
                onClick={() => void act(() => answerOffer(app.id, false))}
              >
                The owner declines
              </button>
            </div>
          )}
          {standIn && sent.state === 'accepted' && (
            <div className="answer-actions">
              {sent.conditions.map((c, index) =>
                c.met ? null : (
                  <button
                    key={index}
                    className="button quiet"
                    disabled={busy}
                    onClick={() => void act(() => markConditionMet(app.id, index))}
                  >
                    Mark met: {c.text}
                  </button>
                ),
              )}
            </div>
          )}
          {error && <p className="error">{error}</p>}
        </div>
      )}
    </section>
  )
}

// The reviewer: the recommendation, then sign it off or send it back with a note.
export function SignoffPanel({ app }: { app: Application }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<null | 'approve' | 'return'>(null)
  const [error, setError] = useState<string | null>(null)
  const decision = app.decision

  if (app.status !== 'awaiting_signoff' || decision?.state !== 'recommended') {
    if (decision?.state === 'final') return <DecisionOutcome app={app} readOnly />
    return (
      <section className="decision done" aria-labelledby="decision-heading">
        <h2 id="decision-heading">Sign-off</h2>
        <p>
          {decision?.state === 'returned'
            ? 'You sent this back to the officer with your note. They will recommend again.'
            : 'There is no recommendation waiting for your sign-off on this file.'}
        </p>
      </section>
    )
  }

  async function decide(approve: boolean) {
    setBusy(approve ? 'approve' : 'return')
    setError(null)
    try {
      await signOff(app.id, approve, note.trim())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(null)
  }

  return (
    <section className="decision signoff" aria-labelledby="decision-heading">
      <h2 id="decision-heading">Your sign-off</h2>
      <p className="fine">
        The officer recommends this decision. Read the file above (you can’t change it), then sign
        it off or send it back. Signing off sends the decision and a letter to the owner.
      </p>
      <Recommendation decision={decision} />
      {decision.offer && !decision.offer.withinPolicy && (
        <p className="decision-returned">
          The instalment is{' '}
          {decision.offer.maxInstallmentRp == null
            ? 'not backed by a policy limit'
            : 'above the policy limit'}
          . Sign it off only if you agree with the officer’s reason.
        </p>
      )}
      <label>
        Note for the officer
        <textarea
          rows={2}
          maxLength={500}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          aria-describedby="signoff-note-hint"
        />
        <span className="hint" id="signoff-note-hint">
          Optional when you sign off; needed when you send it back, so the officer knows what to
          change.
        </span>
      </label>
      {error && <p className="error">{error}</p>}
      <div className="answer-actions">
        <button className="button" disabled={!!busy} onClick={() => void decide(true)}>
          {busy === 'approve' ? 'Signing off…' : 'Sign off and send to the owner'}
        </button>
        <button
          className="button quiet"
          disabled={!!busy || note.trim().length < 5}
          onClick={() => void decide(false)}
        >
          {busy === 'return' ? 'Sending back…' : 'Send back to the officer'}
        </button>
      </div>
    </section>
  )
}

/** The officer's decision step, in whichever state the file is. */
export default function Decision({ app, policy }: { app: Application; policy: Policy }) {
  const [justSent, setJustSent] = useState<DecisionResult | null>(null)
  const decision = app.decision
  const code = decision?.signoffCode ?? justSent?.signoffCode ?? null

  if (app.status === 'awaiting_signoff' && code) return <WaitingForSignoff app={app} code={code} />
  const final = decision?.state === 'final'
  if (final && (app.status === 'decided' || app.status === 'collecting')) {
    return <DecisionOutcome app={app} />
  }
  return (
    <DecisionForm
      key={decision?.signoff?.note ?? ''}
      app={app}
      policy={policy}
      onSent={setJustSent}
    />
  )
}
