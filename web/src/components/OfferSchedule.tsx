// A loan offer's repayment schedule, month by month, as the API computed it. Both apps use it,
// each with its own words.
import type { Offer } from '../decision.ts'
import '../decision.css'

const number = new Intl.NumberFormat('id-ID')
const rp = (value: number) => `Rp ${number.format(value)}`

export type ScheduleLabels = {
  summary: string
  caption: string
  month: string
  instalment: string
  interest: string
  principal: string
  balance: string
}

const SCHEDULE_EN: ScheduleLabels = {
  summary: 'Repayment schedule',
  caption: 'Each month’s payment, the interest in it, and what is still owed afterwards.',
  month: 'Month',
  instalment: 'Payment',
  interest: 'Interest',
  principal: 'Loan repaid',
  balance: 'Still owed',
}

export default function OfferSchedule({
  offer,
  labels = SCHEDULE_EN,
  className = '',
}: {
  offer: Offer
  labels?: ScheduleLabels
  className?: string
}) {
  return (
    <details className={`offer-schedule ${className}`}>
      <summary>
        {labels.summary} ({offer.tenorMonths})
      </summary>
      <div className="offer-schedule-scroll">
        <table>
          <caption>{labels.caption}</caption>
          <thead>
            <tr>
              <th scope="col">{labels.month}</th>
              <th scope="col">{labels.instalment}</th>
              <th scope="col">{labels.interest}</th>
              <th scope="col">{labels.principal}</th>
              <th scope="col">{labels.balance}</th>
            </tr>
          </thead>
          <tbody>
            {offer.schedule.map((row) => (
              <tr key={row.month}>
                <th scope="row">{row.month}</th>
                <td>{rp(row.instalmentRp)}</td>
                <td>{rp(row.interestRp)}</td>
                <td>{rp(row.principalRp)}</td>
                <td>{rp(row.balanceRp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
