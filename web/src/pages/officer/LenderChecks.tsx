import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  COLLECTIBILITY,
  reapplyPolicy,
  recordSlik,
  removeSlik,
  useSlik,
  type PolicyApplied,
  type SlikRecord,
} from '../../lender.ts'
import type { CreditFileData } from '../../types.ts'
import '../../lender.css'

const rupiah = new Intl.NumberFormat('id-ID')
const rp = (value: number) => `Rp ${rupiah.format(Math.round(value))}`
const day = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' })

function today(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// The same checks the API makes, so the officer sees a problem before saving.
function slikProblem(r: SlikRecord): string | null {
  if (!r.checkedOn) return 'Enter the date you ran the SLIK check.'
  if (r.checkedOn > today()) return 'The date of the SLIK check can’t be in the future.'
  if (!Number.isInteger(r.activeFacilities) || r.activeFacilities < 0 || r.activeFacilities > 50)
    return 'The number of active facilities should be between 0 and 50.'
  if (!Number.isFinite(r.monthlyInstalments) || r.monthlyInstalments < 0)
    return 'Enter the monthly instalments in rupiah, 0 if there are none.'
  if (r.activeFacilities === 0 && r.monthlyInstalments > 0)
    return 'With no active facilities there are no instalments to pay. Check the two figures.'
  return null
}

function outcomeText(result: PolicyApplied): string {
  if (!result.applied) return 'Saved. The policy is applied when the file is checked.'
  const limit =
    result.maxInstallment === null
      ? 'no instalment is suggested'
      : `the largest instalment is now ${rp(result.maxInstallment)} a month, ${result.withinPolicy ? 'and the request is within policy' : 'and the request is outside policy'}`
  return `Applied ${result.lenderName ? `${result.lenderName}’s` : 'the starting'} policy: ${limit}. No AI call was made.`
}

// The lender's own steps on a checked file: apply their saved policy again, and record the SLIK
// check they ran in their own system. Both are code only.
export default function LenderChecks({
  id,
  policy,
  editable,
}: {
  id: string
  policy: CreditFileData['policy']
  editable: boolean
}) {
  const { data: slik } = useSlik(id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<SlikRecord>({
    checkedOn: today(),
    activeFacilities: 0,
    monthlyInstalments: 0,
    worstCollectibility: 1,
  })
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  async function run(work: () => Promise<PolicyApplied>) {
    setBusy(true)
    setMessage(null)
    try {
      setMessage({ ok: true, text: outcomeText(await work()) })
      setEditing(false)
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) })
    }
    setBusy(false)
  }

  function save(event: FormEvent) {
    event.preventDefault()
    const problem = slikProblem(draft)
    if (problem) {
      setMessage({ ok: false, text: problem })
      return
    }
    void run(() => recordSlik(id, draft))
  }

  function set<K extends keyof SlikRecord>(key: K, value: SlikRecord[K]) {
    setDraft((d) => ({ ...d, [key]: value }))
    setMessage(null)
  }

  const whose =
    policy.lenderName === undefined
      ? 'a policy from before lenders could set their own'
      : policy.lenderName
        ? `${policy.lenderName}’s policy`
        : 'LedgerLens’s starting policy'

  return (
    <section className="lender-checks" aria-labelledby="lender-checks-heading">
      <h2 id="lender-checks-heading">Your policy and SLIK check</h2>
      <p>
        This file was checked with {whose}.{' '}
        {editable && (
          <>
            Change your terms in <Link to="/app/settings">Settings</Link>, then apply them here.
          </>
        )}
      </p>
      {editable && (
        <div className="form-actions">
          <button
            type="button"
            className="button quiet"
            disabled={busy}
            onClick={() => void run(() => reapplyPolicy(id))}
          >
            {busy && !editing ? 'Applying…' : 'Re-apply my policy'}
          </button>
          <span className="fine">Code only: the evidence isn’t read again and no AI is called.</span>
        </div>
      )}

      <h3>SLIK check</h3>
      <p className="fine">
        LedgerLens does not query SLIK. Your lender runs the check in OJK’s SLIK, with the owner’s
        consent, and you record the result here. Its monthly instalments then replace the ones the
        application declares, and a facility in arrears is listed for you to weigh. It never changes
        how well the evidence is verified.
      </p>
      {slik ? (
        <dl className="slik-figures">
          <div>
            <dt>Checked on</dt>
            <dd>{day.format(new Date(`${slik.checkedOn}T00:00:00`))}</dd>
          </div>
          <div>
            <dt>Active facilities</dt>
            <dd className="mono">{slik.activeFacilities}</dd>
          </div>
          <div>
            <dt>Instalments a month</dt>
            <dd className="mono">{rp(slik.monthlyInstalments)}</dd>
          </div>
          <div>
            <dt>Worst collectibility</dt>
            <dd>{COLLECTIBILITY.find(([n]) => n === slik.worstCollectibility)?.[1]}</dd>
          </div>
        </dl>
      ) : (
        <p>No SLIK check recorded yet.</p>
      )}
      {editable && !editing && (
        <div className="form-actions">
          <button
            type="button"
            className="button quiet"
            disabled={busy}
            onClick={() => {
              if (slik) setDraft({ ...slik })
              setEditing(true)
              setMessage(null)
            }}
          >
            {slik ? 'Record a new SLIK check' : 'Record the SLIK check'}
          </button>
          {slik && (
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => void run(() => removeSlik(id))}
            >
              Remove it (recorded by mistake)
            </button>
          )}
        </div>
      )}
      {editable && editing && (
        <form className="slik-form" onSubmit={save} noValidate>
          <div className="form-row">
            <label>
              Date of the check
              <input
                type="date"
                required
                max={today()}
                value={draft.checkedOn}
                onChange={(e) => set('checkedOn', e.target.value)}
              />
            </label>
            <label>
              Active facilities
              <input
                type="number"
                inputMode="numeric"
                min={0}
                max={50}
                required
                value={Number.isNaN(draft.activeFacilities) ? '' : draft.activeFacilities}
                onChange={(e) => set('activeFacilities', e.target.valueAsNumber)}
              />
            </label>
            <label>
              Total instalments a month (Rp)
              <input
                type="number"
                inputMode="numeric"
                min={0}
                step={10_000}
                required
                value={Number.isNaN(draft.monthlyInstalments) ? '' : draft.monthlyInstalments}
                onChange={(e) => set('monthlyInstalments', e.target.valueAsNumber)}
              />
            </label>
            <label>
              Worst collectibility
              <select
                value={draft.worstCollectibility}
                onChange={(e) => set('worstCollectibility', Number(e.target.value))}
              >
                {COLLECTIBILITY.map(([n, label]) => (
                  <option key={n} value={n}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="form-actions">
            <button className="button" disabled={busy}>
              {busy ? 'Saving…' : 'Save and re-apply the policy'}
            </button>
            <button
              type="button"
              className="button quiet"
              disabled={busy}
              onClick={() => {
                setEditing(false)
                setMessage(null)
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      {message && (
        <p className={message.ok ? 'notice' : 'error'} role={message.ok ? 'status' : 'alert'}>
          {message.text}
        </p>
      )}
    </section>
  )
}
