import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createApplication, rememberSample, type NewApplication as Form } from '../../officer.ts'
import { SAMPLES } from '../../samples.ts'
import OfficerShell from './OfficerShell.tsx'

const EMPTY: Form = {
  alias: '',
  businessType: '',
  city: '',
  yearsOperating: 1,
  amount: 10_000_000,
  tenorMonths: 12,
  existingMonthlyDebt: 0,
}

export default function NewApplication() {
  const navigate = useNavigate()
  const [form, setForm] = useState<Form>(EMPTY)
  const [sample, setSample] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function chooseSample(slug: string) {
    const s = SAMPLES.find((x) => x.slug === slug)
    if (!s) return
    setSample(slug)
    setForm({
      alias: s.alias,
      businessType: s.businessType,
      city: s.city,
      yearsOperating: s.yearsOperating,
      amount: s.amount,
      tenorMonths: s.tenorMonths,
      existingMonthlyDebt: 0,
    })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const id = await createApplication(form)
      if (sample) rememberSample(id, sample)
      navigate(`/app/${id}/consent`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  function field<K extends keyof Form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: typeof EMPTY[key] === 'number' ? Number(value) : value }))
  }

  return (
    <OfficerShell title="New application" crumbs={<> / New</>}>
      <section className="sample-picker" aria-labelledby="sample-heading">
        <h2 id="sample-heading">Start from a sample business</h2>
        <p className="fine">
          No notebook to hand? Pick a fictional business and you can add its photographed records
          in one click on the evidence step.
        </p>
        <div className="choice-row">
          {SAMPLES.map((s) => (
            <button
              key={s.slug}
              type="button"
              className={`choice ${sample === s.slug ? 'chosen' : ''}`}
              onClick={() => chooseSample(s.slug)}
            >
              <strong>{s.alias}</strong>
              <span>
                {s.businessType}, {s.city}
              </span>
            </button>
          ))}
        </div>
      </section>

      <form className="form" onSubmit={submit}>
        <h2>The business and the request</h2>
        <label>
          Business alias
          <input
            required
            maxLength={80}
            value={form.alias}
            onChange={(e) => field('alias', e.target.value)}
            placeholder="Warung Bu Sari"
          />
          <span className="hint">
            A trading name, never the owner’s legal name or national ID number.
          </span>
        </label>
        <div className="form-row">
          <label>
            Type of business
            <input
              required
              maxLength={80}
              value={form.businessType}
              onChange={(e) => field('businessType', e.target.value)}
              placeholder="Grocery stall (warung sembako)"
            />
          </label>
          <label>
            City
            <input
              required
              maxLength={80}
              value={form.city}
              onChange={(e) => field('city', e.target.value)}
              placeholder="Bekasi"
            />
          </label>
          <label>
            Years trading
            <input
              type="number"
              min={0}
              max={80}
              required
              value={form.yearsOperating}
              onChange={(e) => field('yearsOperating', e.target.value)}
            />
          </label>
        </div>
        <div className="form-row">
          <label>
            Loan amount (Rp)
            <input
              type="number"
              min={100_000}
              step={100_000}
              required
              value={form.amount}
              onChange={(e) => field('amount', e.target.value)}
            />
          </label>
          <label>
            Term (months)
            <input
              type="number"
              min={1}
              max={60}
              required
              value={form.tenorMonths}
              onChange={(e) => field('tenorMonths', e.target.value)}
            />
          </label>
        </div>
        <label>
          Other loan instalments a month (Rp)
          <input
            type="number"
            inputMode="numeric"
            min={0}
            step={10_000}
            value={form.existingMonthlyDebt ?? 0}
            onChange={(e) => field('existingMonthlyDebt', e.target.value)}
            aria-describedby="other-debts-hint"
          />
          <span id="other-debts-hint" className="hint">
            Optional. Including online loans (pinjol); 0 if none. The policy takes it off the
            instalment it allows, and the check compares it with what the owner says.
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <button className="button" type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create and continue to consent'}
        </button>
      </form>
    </OfficerShell>
  )
}
