import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import WhatsAppButton from '../../components/WhatsAppButton.tsx'
import {
  LENDER_TYPES,
  PRODUCT_RATE,
  createInvite,
  getProfile,
  invitePath,
  listInvites,
  profileProblem,
  saveProfile,
  type Invite,
  type LenderPolicyForm,
  type LenderProfile,
  type LenderType,
  type Product,
} from '../../lender.ts'
import '../../lender.css'
import OfficerShell from './OfficerShell.tsx'

const rupiah = new Intl.NumberFormat('id-ID')
const rp = (value: number) => `Rp ${rupiah.format(Math.round(value))}`
const when = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' })

// An illustrative business, so the officer sees what their numbers do. Not a real file.
const EXAMPLE_NET = 5_000_000

const STATE_LABEL: Record<Invite['state'], string> = {
  open: 'Waiting for the owner',
  used: 'File started',
  expired: 'Expired',
}

function PercentField({
  label,
  hint,
  value,
  onChange,
  min,
  max,
}: {
  label: string
  hint: string
  value: number
  onChange: (value: number) => void
  min: number
  max: number
}) {
  const id = label.replace(/\W+/g, '-').toLowerCase()
  return (
    <label>
      {label}
      <span className="unit-input">
        <input
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          step={1}
          required
          value={Number.isNaN(value) ? '' : value}
          onChange={(e) => onChange(e.target.valueAsNumber)}
          aria-describedby={`${id}-hint`}
        />
        <span aria-hidden="true">%</span>
      </span>
      <span id={`${id}-hint`} className="hint">
        {hint}
      </span>
    </label>
  )
}

// What the officer's policy allows for an illustrative business, computed here as the API does.
function Example({ form }: { form: LenderPolicyForm }) {
  const allowed = (haircut: number) =>
    Math.max(0, Math.round(EXAMPLE_NET * (1 - haircut / 100) * (form.maxInstallmentRatioPct / 100)))
  if (profileProblem({ ...form, name: form.name || 'x', type: form.type ?? 'other' })) return null
  return (
    <div className="policy-example" aria-live="polite">
      <p>
        <strong>Example (illustrative).</strong> For a business with {rp(EXAMPLE_NET)} net cash flow
        a month and no other loans, this policy allows an instalment of up to{' '}
        <span className="mono">{rp(allowed(form.haircutVerifiedPct))}</span> a month on a verified
        file and <span className="mono">{rp(allowed(form.haircutPartialPct))}</span> on a partly
        verified one. Files with too little evidence get no suggested instalment.
      </p>
    </div>
  )
}

function InviteSection({ profile }: { profile: LenderProfile | null }) {
  const [invites, setInvites] = useState<Invite[]>([])
  const [latest, setLatest] = useState<Invite | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const ready = !!profile?.saved && !!profile.name

  useEffect(() => {
    if (!ready) return
    listInvites()
      .then(setInvites)
      .catch(() => undefined)
  }, [ready])

  async function create() {
    setBusy(true)
    setError(null)
    try {
      const made = await createInvite()
      setLatest(made)
      setInvites((list) => [made, ...list])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  const url = latest ? `${window.location.origin}${invitePath(latest.code)}` : ''
  const message = latest
    ? `Halo, ${latest.lenderName} mengundang Anda mengirim catatan usaha lewat LedgerLens untuk pengajuan pinjaman. Berkas tetap milik Anda dan Anda bisa berhenti berbagi kapan saja. Buka: ${url} (berlaku 14 hari)`
    : ''

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="integration" id="invite" aria-labelledby="invite-heading">
      <h2 id="invite-heading">Invite a business owner</h2>
      <p>
        Send an owner a link with your lender’s name on it. When they open it they see who is
        asking, agree, and start a file that is already shared with you; they send their records
        from their own phone. The file stays theirs: they can stop sharing it or delete it at any
        time. Each link works once, for 14 days.
      </p>
      {!ready ? (
        <p className="notice">Save your lender’s name above first, so the owner knows who is asking.</p>
      ) : (
        <div className="webhook-form">
          <div className="form-actions">
            <button type="button" className="button" disabled={busy} onClick={create}>
              {busy ? 'Creating…' : 'Create an invite link'}
            </button>
          </div>
          {latest && (
            <>
              <label>
                Invite link for one business
                <input readOnly value={url} onFocus={(e) => e.target.select()} />
              </label>
              <div className="form-actions">
                <button type="button" className="button quiet" onClick={copy}>
                  <span aria-live="polite">{copied ? 'Copied' : 'Copy link'}</span>
                </button>
                <WhatsAppButton
                  className="button whatsapp"
                  text={message}
                  label="Send on WhatsApp (in Bahasa)"
                />
              </div>
              <p className="fine">
                The owner sees “{latest.lenderName} asks you to send your records”, in English or
                Bahasa Indonesia, and never your name. Expires {when.format(new Date(latest.expiresAt))}.
              </p>
            </>
          )}
          {error && <p className="error">{error}</p>}
        </div>
      )}
      {invites.length > 0 && (
        <div className="table-scroll">
          <table className="register invites-table">
            <caption className="visually-hidden">Your recent invites</caption>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Created</th>
                <th scope="col">Expires</th>
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {invites.map((invite) => (
                <tr key={invite.code}>
                  <td className="mono" data-label="Code">{invite.code}</td>
                  <td data-label="Created">{when.format(new Date(invite.createdAt))}</td>
                  <td data-label="Expires">{when.format(new Date(invite.expiresAt))}</td>
                  <td data-label="State">
                    {invite.state === 'used' && invite.applicationId ? (
                      <Link to={`/app/${invite.applicationId}`}>{STATE_LABEL.used}</Link>
                    ) : (
                      STATE_LABEL[invite.state]
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// /app/settings: who the lender is, the credit policy LedgerLens applies for them, and invites.
export default function Settings() {
  const [profile, setProfile] = useState<LenderProfile | null>(null)
  const [form, setForm] = useState<LenderPolicyForm | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    getProfile()
      .then((loaded) => {
        setProfile(loaded)
        setForm(loaded)
      })
      .catch((e: Error) => setMessage({ ok: false, text: e.message }))
  }, [])

  function set<K extends keyof LenderPolicyForm>(key: K, value: LenderPolicyForm[K]) {
    setForm((f) => (f ? { ...f, [key]: value } : f))
    setMessage(null)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!form) return
    const problem = profileProblem(form)
    if (problem) {
      setMessage({ ok: false, text: problem })
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      const saved = await saveProfile({ ...form, name: (form.name ?? '').trim() })
      setProfile(saved)
      setForm(saved)
      setMessage({
        ok: true,
        text: 'Saved. New checks use this policy. A file you already checked keeps its policy until you press “Re-apply my policy” on it; that needs no AI call.',
      })
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) })
    }
    setBusy(false)
  }

  function chooseProduct(product: Product) {
    setForm((f) =>
      f ? { ...f, product, annualRatePct: PRODUCT_RATE[product] ?? f.annualRatePct } : f,
    )
    setMessage(null)
  }

  const defaults = profile?.defaults

  return (
    <OfficerShell title="Settings" crumbs={<> / Settings</>}>
      <p className="lead-text">
        Tell LedgerLens who your lender is and how it judges a loan. Every file you check, and every
        file an owner shares with you, uses this policy. Code applies it; the AI never sets a figure.
      </p>
      {!form ? (
        message ? (
          <p className="error">{message.text}</p>
        ) : (
          <p className="fine">Loading…</p>
        )
      ) : (
        <form className="form settings-form" onSubmit={save} noValidate>
          <h2>Your lender</h2>
          <div className="form-row">
            <label>
              Lender name
              <input
                required
                maxLength={80}
                autoComplete="organization"
                value={form.name ?? ''}
                onChange={(e) => set('name', e.target.value)}
                placeholder="BPR Sejahtera"
                aria-describedby="name-hint"
              />
              <span id="name-hint" className="hint">
                Owners see it on your invites and on their file once you hold it.
              </span>
            </label>
            <label>
              Kind of lender
              <select
                required
                value={form.type ?? ''}
                onChange={(e) => set('type', (e.target.value || null) as LenderType | null)}
              >
                <option value="">Choose…</option>
                {LENDER_TYPES.map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <h2>Your credit policy</h2>
          <p className="fine">
            {profile?.saved
              ? `Saved ${profile.updatedAt ? when.format(new Date(profile.updatedAt)) : ''}.`
              : 'These are LedgerLens’s starting values, not industry standards. Change them to match your credit policy.'}
          </p>
          <fieldset className="settings-product">
            <legend>Product the offer is priced at</legend>
            <div className="choice-row">
              <button
                type="button"
                className={`choice ${form.product === 'kur_micro' ? 'chosen' : ''}`}
                aria-pressed={form.product === 'kur_micro'}
                onClick={() => chooseProduct('kur_micro')}
              >
                KUR micro
                <span>6% a year, the government-set rate</span>
              </button>
              <button
                type="button"
                className={`choice ${form.product === 'own' ? 'chosen' : ''}`}
                aria-pressed={form.product === 'own'}
                onClick={() => chooseProduct('own')}
              >
                Your own product
                <span>At the rate you set below</span>
              </button>
            </div>
          </fieldset>
          <div className="form-row">
            {form.product === 'own' && (
              <PercentField
                label="Interest a year"
                hint="Prices the requested instalment and is the starting rate of your offers."
                value={form.annualRatePct}
                onChange={(v) => set('annualRatePct', v)}
                min={0}
                max={60}
              />
            )}
            <PercentField
              label="Share of net cash flow for repayments"
              hint={`The most of a month’s net cash flow that all loan instalments may take. Starting value ${defaults?.maxInstallmentRatioPct ?? 30}%.`}
              value={form.maxInstallmentRatioPct}
              onChange={(v) => set('maxInstallmentRatioPct', v)}
              min={5}
              max={60}
            />
          </div>
          <div className="form-row">
            <PercentField
              label="Haircut on a verified file"
              hint={`Taken off net cash flow when the sources agree. Starting value ${defaults?.haircutVerifiedPct ?? 20}%.`}
              value={form.haircutVerifiedPct}
              onChange={(v) => set('haircutVerifiedPct', v)}
              min={0}
              max={90}
            />
            <PercentField
              label="Haircut on a partly verified file"
              hint={`A larger discount when hard evidence is missing or questioned. Starting value ${defaults?.haircutPartialPct ?? 40}%.`}
              value={form.haircutPartialPct}
              onChange={(v) => set('haircutPartialPct', v)}
              min={0}
              max={90}
            />
            <label>
              Longest term
              <span className="unit-input">
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={60}
                  required
                  value={Number.isNaN(form.maxTenorMonths) ? '' : form.maxTenorMonths}
                  onChange={(e) => set('maxTenorMonths', e.target.valueAsNumber)}
                  aria-describedby="tenor-hint"
                />
                <span aria-hidden="true">months</span>
              </span>
              <span id="tenor-hint" className="hint">
                A longer request is marked outside your policy.
              </span>
            </label>
          </div>
          <Example form={form} />
          {message && (
            <p className={message.ok ? 'notice' : 'error'} role={message.ok ? 'status' : 'alert'}>
              {message.text}
            </p>
          )}
          <div className="form-actions">
            <button className="button" disabled={busy}>
              {busy ? 'Saving…' : 'Save settings'}
            </button>
            {defaults && (
              <button
                type="button"
                className="button quiet"
                disabled={busy}
                onClick={() => {
                  setForm((f) => (f ? { ...defaults, name: f.name, type: f.type } : f))
                  setMessage(null)
                }}
              >
                Use the starting values
              </button>
            )}
          </div>
        </form>
      )}
      <InviteSection profile={profile} />
    </OfficerShell>
  )
}
