import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api.ts'
import { useInviteStrings } from '../../i18n/invite.ts'
import { useLang } from '../../i18n/owner.ts'
import { getInvite, type InvitePublic } from '../../lender.ts'
import { ArrowIcon } from './icons.tsx'
import OwnerShell from './OwnerShell.tsx'
import '../../lender.css'

// /owner/invite/:code: a lender asks this owner to send their records. The owner sees who is
// asking and what agreeing means, then fills in the usual short form (/owner/new?invite=CODE),
// which starts a file already shared with that lender.
export default function OwnerInvite() {
  const { code = '' } = useParams()
  const { t, lang } = useLang()
  const { it } = useInviteStrings()
  const [invite, setInvite] = useState<InvitePublic | null>(null)
  const [missing, setMissing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getInvite(code)
      .then(setInvite)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) setMissing(true)
        else setError(e instanceof Error ? e.message : String(e))
      })
  }, [code])

  const date = invite
    ? new Intl.DateTimeFormat(lang === 'id' ? 'id-ID' : 'en-GB', { dateStyle: 'long' }).format(
        new Date(invite.expiresAt),
      )
    : ''

  // Why the invite can't be used, if it can't.
  const blocked = missing
    ? it.notFound
    : invite?.own
      ? it.own
      : invite?.state === 'used' && !invite.applicationId
        ? it.used
        : invite?.state === 'expired'
          ? it.expired
          : null

  return (
    <OwnerShell>
      {error && (
        <p className="ow-error" role="alert">
          {t.somethingWrong}: {error}
        </p>
      )}
      {!invite && !missing && !error && <p className="ow-fine">{t.loading}</p>}
      {blocked && (
        <>
          <h1 className="ow-title">{invite ? it.title(invite.lenderName) : it.kicker}</h1>
          <p className="ow-error" role="alert">
            {blocked}
          </p>
          <Link to="/owner" className="ow-button ow-button-light">
            {it.goHome}
          </Link>
        </>
      )}
      {invite && !blocked && (
        <>
          <p className="ow-kicker">{it.kicker}</p>
          <h1 className="ow-title">{it.title(invite.lenderName)}</h1>
          <p className="ow-lead">{it.lead(invite.lenderName)}</p>
          {invite.lenderType && (
            <p className="ow-fine">{it.isA(invite.lenderName, it.lenderKind[invite.lenderType])}</p>
          )}
          {invite.applicationId ? (
            <>
              <p className="ow-note">{it.usedMine}</p>
              <Link to={`/owner/${invite.applicationId}`} className="ow-button ow-button-wide">
                {it.openMine}
                <ArrowIcon size={20} />
              </Link>
            </>
          ) : (
            <>
              <section className="ow-section" aria-labelledby="ow-invite-what">
                <h2 id="ow-invite-what" className="ow-h2">
                  {it.whatTitle}
                </h2>
                <ul className="ow-scope-yes ow-invite-list">
                  {it.what(invite.lenderName).map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
                <p className="ow-fine">{it.expires(date)}</p>
                <p className="ow-fine">{it.fictional}</p>
              </section>
              <Link
                to={`/owner/new?invite=${encodeURIComponent(invite.code)}`}
                className="ow-button ow-button-wide"
              >
                {it.agree}
                <ArrowIcon size={20} />
              </Link>
              <p className="ow-center">
                <Link to="/owner">{it.notNow}</Link>
              </p>
            </>
          )}
        </>
      )}
    </OwnerShell>
  )
}
