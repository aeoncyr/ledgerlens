import { useEffect, type ReactNode } from 'react'
import AppBar from '../../components/AppBar.tsx'
import { useLang } from '../../i18n/owner.ts'
import '../../owner.css'

// The owner's pages: the shared app bar with a language switch, then the page. Every page is one
// column on a phone; `wide` pages spread into two columns on a laptop instead of staying phone-sized.
export default function OwnerShell({
  children,
  wide = false,
}: {
  children: ReactNode
  wide?: boolean
}) {
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
      <main className={wide ? 'ow-main ow-main-wide' : 'ow-main'}>{children}</main>
    </div>
  )
}
