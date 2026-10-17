import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { rupiah, useLang } from '../../i18n/owner.ts'
import { createOwnerFile, errorText, rememberSample, type NewOwnerFile } from '../../owner.ts'
import { SAMPLES } from '../../samples.ts'
import OwnerShell from './OwnerShell.tsx'

const EMPTY: NewOwnerFile = {
  alias: '',
  businessType: '',
  city: '',
  yearsOperating: 1,
  amount: 10_000_000,
  tenorMonths: 12,
  existingMonthlyDebt: 0,
}

const AMOUNTS = [5_000_000, 10_000_000, 25_000_000, 50_000_000]
const TENORS = [6, 12, 18, 24, 36]

function fromSample(slug: string | null): NewOwnerFile | null {
  const s = SAMPLES.find((x) => x.slug === slug)
  if (!s) return null
  return {
    alias: s.alias,
    businessType: s.businessType,
    city: s.city,
    yearsOperating: s.yearsOperating,
    amount: s.amount,
    tenorMonths: s.tenorMonths,
    existingMonthlyDebt: 0,
  }
}

// /owner/new: a short form about the business and the loan, then on to the file.
// Accepts ?sample=<slug> to prefill one of the fictional sample businesses.
export default function OwnerNew() {
  const { t } = useLang()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const sampleSlug = params.get('sample')
  const sample = SAMPLES.find((s) => s.slug === sampleSlug) ?? null
  const [form, setForm] = useState<NewOwnerFile>(() => fromSample(sampleSlug) ?? EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof NewOwnerFile>(key: K, value: NewOwnerFile[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const id = await createOwnerFile({
        ...form,
        alias: form.alias.trim(),
        businessType: form.businessType.trim(),
        city: form.city.trim(),
      })
      if (sample) rememberSample(id, sample.slug)
      navigate(`/owner/${id}`)
    } catch (e) {
      setError(errorText(e))
      setBusy(false)
    }
  }

  return (
    <OwnerShell>
      <p className="ow-back">
        <Link to="/owner">← {t.back}</Link>
      </p>
      <h1 className="ow-title">{t.newTitle}</h1>
      <p className="ow-lead">{t.newLead}</p>
      {sample && <p className="ow-note">{t.sampleUsed(sample.alias)}</p>}

      <form className="ow-form" onSubmit={submit}>
        <label className="ow-field">
          <span className="ow-label">{t.aliasLabel}</span>
          <input
            required
            maxLength={80}
            autoComplete="organization"
            value={form.alias}
            onChange={(e) => set('alias', e.target.value)}
            placeholder={t.aliasPlaceholder}
            aria-describedby="ow-alias-hint"
          />
          <span id="ow-alias-hint" className="ow-hint">
            {t.aliasHint}
          </span>
        </label>

        <label className="ow-field">
          <span className="ow-label">{t.typeLabel}</span>
          <input
            required
            maxLength={80}
            list="ow-type-list"
            value={form.businessType}
            onChange={(e) => set('businessType', e.target.value)}
            placeholder={t.typePlaceholder}
          />
          <datalist id="ow-type-list">
            {t.typeSuggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </label>

        <div className="ow-field-row">
          <label className="ow-field">
            <span className="ow-label">{t.cityLabel}</span>
            <input
              required
              maxLength={80}
              value={form.city}
              onChange={(e) => set('city', e.target.value)}
              placeholder={t.cityPlaceholder}
            />
          </label>
          <label className="ow-field ow-field-narrow">
            <span className="ow-label">{t.yearsLabel}</span>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={80}
              required
              value={form.yearsOperating}
              onChange={(e) => set('yearsOperating', Number(e.target.value))}
            />
          </label>
        </div>

        <fieldset className="ow-field">
          <legend className="ow-label">{t.amountLabel}</legend>
          <div className="ow-chips">
            {AMOUNTS.map((amount) => (
              <button
                key={amount}
                type="button"
                className="ow-chip"
                aria-pressed={form.amount === amount}
                onClick={() => set('amount', amount)}
              >
                {rupiah(amount)}
              </button>
            ))}
          </div>
          <div className="ow-money">
            <span aria-hidden="true">Rp</span>
            <input
              type="number"
              inputMode="numeric"
              min={100_000}
              step={100_000}
              required
              aria-label={`${t.amountLabel} ${t.amountHint}`}
              value={form.amount}
              onChange={(e) => set('amount', Number(e.target.value))}
            />
          </div>
          <span className="ow-hint" aria-live="polite">
            {rupiah(form.amount)}
          </span>
        </fieldset>

        <fieldset className="ow-field">
          <legend className="ow-label">{t.tenorLabel}</legend>
          <div className="ow-chips">
            {TENORS.map((months) => (
              <button
                key={months}
                type="button"
                className="ow-chip"
                aria-pressed={form.tenorMonths === months}
                onClick={() => set('tenorMonths', months)}
              >
                {months} {t.monthsUnit}
              </button>
            ))}
          </div>
        </fieldset>

        <label className="ow-field">
          <span className="ow-label">{t.otherDebtsLabel}</span>
          <div className="ow-money">
            <span aria-hidden="true">Rp</span>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              step={10_000}
              value={form.existingMonthlyDebt ?? 0}
              onChange={(e) => set('existingMonthlyDebt', Math.max(0, Number(e.target.value) || 0))}
              aria-describedby="ow-debts-hint"
            />
          </div>
          <span id="ow-debts-hint" className="ow-hint">
            {t.otherDebtsHint}
          </span>
        </label>

        {error && (
          <p className="ow-error" role="alert">
            {error}
          </p>
        )}
        <button className="ow-button ow-button-wide" type="submit" disabled={busy}>
          {busy ? t.creating : t.createButton}
        </button>
      </form>
    </OwnerShell>
  )
}
