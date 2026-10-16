import { useEffect, type ReactNode } from 'react'
import AppBar from '../../components/AppBar.tsx'
import { useLang } from '../../i18n/owner.ts'
import '../../owner.css'

// The owner's pages: the shared app bar with a language switch, then one narrow column sized for a
// phone held in one hand.
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
      <AppBar
        app="owner"
        appName={t.appName}
        appHome="/owner"
        homeLabel={t.home}
        notice={t.prototype}
      >
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
      </AppBar>
      <main className="ow-main">{children}</main>
    </div>
  )
}
