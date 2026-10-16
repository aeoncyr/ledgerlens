// One synthetic notebook page beside what the reader copied from it, with the rupiah and the
// totals computed by code.
import {
  SPECIMEN_LINES,
  SPECIMEN_MATCHED,
  SPECIMEN_MODEL,
  SPECIMEN_TRUE_AMOUNTS,
  type SpecimenLine,
} from '../specimen.ts'

const KIND_LABEL: Record<SpecimenLine['kind'], string> = {
  sale: 'sale',
  purchase: 'purchase',
  receivable: 'customer credit',
  expense: 'expense',
  other: '',
}

const rupiah = new Intl.NumberFormat('id-ID')

function total(kind: SpecimenLine['kind']): number {
  return SPECIMEN_LINES.filter((line) => line.kind === kind).reduce(
    (sum, line) => sum + (line.rupiah ?? 0),
    0,
  )
}

function isHeading(line: SpecimenLine): boolean {
  return line.written === null && line.kind === 'other'
}

export default function Specimen() {
  return (
    <figure>
      <div className="specimen-grid">
        <img
          className="specimen-photo"
          src="/specimen/bu-sari-page-1.webp"
          width={720}
          height={1018}
          alt="A photographed notebook page: two weeks of daily sales, two supplier purchases, a customer credit and an arisan payment, with one amount crossed out and rewritten."
        />
        <table className="ledger">
          <thead>
            <tr>
              <th scope="col" className="col-line">
                Line
              </th>
              <th scope="col">As written</th>
              <th scope="col" className="num written">
                Amount
              </th>
              <th scope="col" className="num">
                Rupiah
              </th>
            </tr>
          </thead>
          <tbody>
            {SPECIMEN_LINES.map((line) =>
              isHeading(line) ? (
                <tr key={line.line} className="ledger-heading">
                  <td className="col-line">{line.line}</td>
                  <th scope="rowgroup">{line.description}</th>
                  <td className="written" />
                  <td />
                </tr>
              ) : (
                <tr key={line.line}>
                  <td className="col-line">{line.line}</td>
                  <td>
                    {line.date && <span className="date">{line.date} </span>}
                    {line.description}
                    {KIND_LABEL[line.kind] && (
                      <span className="kind"> · {KIND_LABEL[line.kind]}</span>
                    )}
                  </td>
                  <td className="num written">{line.written}</td>
                  <td className="num">
                    {line.rupiah === null ? '—' : rupiah.format(line.rupiah)}
                  </td>
                </tr>
              ),
            )}
          </tbody>
          <tfoot>
            <tr>
              <td className="col-line" />
              <th scope="row" colSpan={2}>
                Sales on this page
              </th>
              <td className="num">{rupiah.format(total('sale'))}</td>
            </tr>
            <tr>
              <td className="col-line" />
              <th scope="row" colSpan={2}>
                Supplier purchases
              </th>
              <td className="num">{rupiah.format(total('purchase'))}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <figcaption>
        <span>
          Left, a notebook page photographed at an angle. Right, what {SPECIMEN_MODEL} copied
          from it, unedited: {SPECIMEN_MATCHED} of {SPECIMEN_TRUE_AMOUNTS} amounts match the
          page exactly, and on the last line it took the rewritten 200rb, not the crossed-out
          1200rb. The rupiah column and the totals are computed by code.
        </span>
        <span className="fine">
          The page is synthetic, made by our generator so that its true amounts are known.
        </span>
      </figcaption>
    </figure>
  )
}
