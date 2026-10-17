// A link that puts "check my file again" in the owner's Google Calendar a month from now, with the
// tips from their summary, so a file that isn't strong enough yet gets a second try.
import type { OwnerStrings } from '../../i18n/owner.ts'
import { checkAgainUrl } from '../../reminder.ts'
import { CalendarIcon } from './icons.tsx'

export default function RemindMe({
  id,
  tips,
  lead,
  t,
}: {
  id: string
  tips: string[]
  lead: string
  t: OwnerStrings
}) {
  // Files are linked to the browser that started them, so the link only opens here.
  const fileUrl = `${window.location.origin}/owner/${id}`
  const url = checkAgainUrl(t.remindEventTitle, t.remindDetails(tips, fileUrl))
  return (
    <div className="ow-remind">
      <p className="ow-fine">{lead}</p>
      <a
        className="ow-button ow-button-quiet ow-remind-button"
        href={url}
        target="_blank"
        rel="noopener noreferrer"
      >
        <CalendarIcon size={20} />
        <span>
          {t.remindButton}
          <span className="visually-hidden">{t.opensCalendar}</span>
        </span>
      </a>
    </div>
  )
}
