import { useEffect, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Logo from '../../components/Logo.tsx'
import { useLang } from '../../i18n/owner.ts'
import '../../owner.css'

// The owner's pages: a slim header that works on a phone, one narrow column, and a reminder that
// this is a prototype for fictional businesses.
export default function OwnerShell({ children }: { children: ReactNode }) {
  const { lang, t, setLang } = useLang()

  useEffect(() => {
    document.documentElement.lang = lang
    return () => {
      document.documentElement.lang = 'en'
    }
  }, [lang])

  return (
    <div className="ow">
      <header className="ow-header">
        <div className="ow-header-inner">
          <Link to="/owner" className="ow-brand">
            <Logo size={26} />
            <span>
              LedgerLens <span className="ow-tagline">{t.tagline}</span>
            </span>
          </Link>
          <div className="ow-lang" role="group" aria-label="Language / Bahasa">
            <button
              type="button"
              aria-pressed={lang === 'en'}
              lang="en"
              onClick={() => setLang('en')}
              title="English"
            >
              EN
            </button>
            <button
              type="button"
              aria-pressed={lang === 'id'}
              lang="id"
              onClick={() => setLang('id')}
              title="Bahasa Indonesia"
            >
              ID
            </button>
          </div>
        </div>
      </header>
      <main className="ow-main">{children}</main>
      <footer className="ow-footer">
        <p>{t.prototype}</p>
        <p>
          <Link to="/">LedgerLens</Link>
        </p>
      </footer>
    </div>
  )
}
