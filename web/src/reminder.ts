// "Remind me to check again": a Google Calendar event a month ahead, for an owner whose file isn't
// strong enough yet or was declined. Like the officer's field visit (integrations.ts), it is a
// plain TEMPLATE link: no Calendar API and no sign-in; the owner saves the event themselves.

export const REMIND_AFTER_DAYS = 30

function day(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`
}

/** A 30-minute event at 09:00 Jakarta time, REMIND_AFTER_DAYS from now. */
export function checkAgainUrl(title: string, details: string, now = new Date()): string {
  const date = new Date(now)
  date.setDate(date.getDate() + REMIND_AFTER_DAYS)
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: title,
    details: details.slice(0, 1800),
    dates: `${day(date)}T090000/${day(date)}T093000`,
    ctz: 'Asia/Jakarta',
  })
  return `https://calendar.google.com/calendar/render?${params.toString()}`
}
