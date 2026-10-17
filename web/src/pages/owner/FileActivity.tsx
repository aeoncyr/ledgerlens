// "Who has seen your file": the owner's own timeline of their file. The API reads the lender's
// audit log through an allowlist and returns fixed event keys, which this card words in English or
// Bahasa Indonesia; no names, notes or figures from the lender's side reach it.
import { useEffect, useState } from 'react'
import type { Lang, OwnerStrings } from '../../i18n/owner.ts'
import { getActivity, type ActivityEvent } from '../../owner.ts'

export default function FileActivity({
  id,
  version,
  lang,
  t,
}: {
  id: string
  // Changes whenever the file moves on (shared, opened, decided), so the list loads again.
  version: string
  lang: Lang
  t: OwnerStrings
}) {
  const [events, setEvents] = useState<ActivityEvent[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getActivity(id)
      .then((list) => {
        if (!cancelled) {
          setEvents(list)
          setFailed(false)
        }
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [id, version])

  const time = new Intl.DateTimeFormat(lang === 'id' ? 'id-ID' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
  // Newest first: what a lender did last is what the owner wants to know.
  const shown = (events ?? []).filter((e) => t.activityEvents[e.event]).reverse()

  return (
    <section className="ow-card ow-activity" aria-labelledby="ow-activity-title">
      <h2 id="ow-activity-title" className="ow-h3">
        {t.activityTitle}
      </h2>
      <p className="ow-fine">{t.activityLead}</p>
      {failed && !events && <p className="ow-fine">{t.activityFailed}</p>}
      {events && shown.length === 0 && <p className="ow-fine">{t.activityEmpty}</p>}
      {shown.length > 0 && (
        <ol className="ow-activity-list">
          {shown.map((e, index) => (
            <li key={`${e.event}-${e.at ?? index}`} className={`ow-activity-${e.event}`}>
              <span className="ow-activity-what">
                {t.activityEvents[e.event]}
                {e.count > 1 && <span className="ow-fine"> · {t.activityTimes(e.count)}</span>}
              </span>
              {e.at && (
                <time className="ow-activity-when" dateTime={e.at}>
                  {time.format(new Date(e.at))}
                </time>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
