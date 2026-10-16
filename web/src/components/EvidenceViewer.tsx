import { useEffect, useId, useRef } from 'react'
import { isLocatedTotal, locatedNumber, money, rowsOf } from '../evidence.ts'
import type { EvidenceItem } from '../types.ts'

function Reading({ item, locator }: { item: EvidenceItem; locator: string | null }) {
  const reading = item.reading
  if (!reading) return <p className="fine">This item could not be read.</p>

  if (item.type === 'ledger_page') {
    const marked = locatedNumber(locator, 'line')
    return (
      <table className="ledger compact">
        <thead>
          <tr>
            <th scope="col" className="col-line">
              Line
            </th>
            <th scope="col">As written</th>
            <th scope="col" className="num">
              Amount
            </th>
            <th scope="col" className="num">
              Rupiah
            </th>
          </tr>
        </thead>
        <tbody>
          {rowsOf(reading, 'lines').map((line) => (
            <tr key={String(line.line)} className={line.line === marked ? 'marked' : undefined}>
              <td className="col-line">{String(line.line)}</td>
              <td>{String(line.description)}</td>
              <td className="num">{line.amountText ? String(line.amountText) : ''}</td>
              <td className="num">{line.amountRp == null ? '' : money(line.amountRp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  if (item.type === 'receipt') {
    return (
      <table className="ledger compact">
        <tbody>
          {rowsOf(reading, 'items').map((line, index) => (
            <tr key={index} className={locator?.startsWith('item') ? 'marked' : undefined}>
              <td>
                {line.quantityText ? `${String(line.quantityText)} ` : ''}
                {String(line.name)}
              </td>
              <td className="num">{money(line.amountRp)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className={locator?.startsWith('total') ? 'marked' : undefined}>
            <th scope="row">Total</th>
            <td className="num">{money(reading.totalRp)}</td>
          </tr>
        </tfoot>
      </table>
    )
  }

  if (item.type === 'qris_history') {
    const marked = locatedNumber(locator, 'row')
    return (
      <table className="ledger compact">
        <tbody>
          {rowsOf(reading, 'totals').map((total, index) => (
            <tr
              key={`t${index}`}
              className={isLocatedTotal(locator, total.periodText) ? 'marked' : undefined}
            >
              <th scope="row">Total for {String(total.periodText)}</th>
              <td className="num">{money(total.amountRp)}</td>
            </tr>
          ))}
          {rowsOf(reading, 'rows').map((row) => (
            <tr key={String(row.row)} className={row.row === marked ? 'marked' : undefined}>
              <td>
                {String(row.dateText ?? '')} {String(row.timeText ?? '')}
              </td>
              <td className="num">{money(row.amountRp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  if (item.type === 'interview_audio') {
    return (
      <>
        {reading.summaryEn ? <p className="fine">{String(reading.summaryEn)}</p> : null}
        <table className="ledger compact">
          <thead>
            <tr>
              <th scope="col" className="col-line">
                At
              </th>
              <th scope="col">The owner said</th>
              <th scope="col" className="num">
                Rupiah
              </th>
            </tr>
          </thead>
          <tbody>
            {rowsOf(reading, 'claims').map((claim, index) => (
              <tr
                key={index}
                className={locator && claim.timeText === locator ? 'marked' : undefined}
              >
                <td className="col-line">{String(claim.timeText ?? '')}</td>
                <td>
                  <span lang="id">“{String(claim.quote)}”</span>
                  <span className="kind"> {String(claim.statementEn)}</span>
                </td>
                <td className="num">
                  {claim.amountRp == null ? '' : money(claim.amountRp)}
                  {claim.period ? <span className="kind"> /{String(claim.period)}</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </>
    )
  }

  if (item.type === 'shop_photo') {
    return (
      <ul>
        {rowsOf(reading, 'observations').map((o, index) => (
          <li key={index}>{String(o)}</li>
        ))}
      </ul>
    )
  }

  return <pre className="reading-raw">{JSON.stringify(reading, null, 1)}</pre>
}

export default function EvidenceViewer({
  item,
  locator,
  onClose,
}: {
  item: EvidenceItem | null
  locator: string | null
  onClose: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const player = useRef<HTMLAudioElement>(null)
  // The control that opened the viewer gets the focus back when it closes.
  const opener = useRef<HTMLElement | null>(null)
  const titleId = useId()

  useEffect(() => {
    const box = dialog.current
    if (!box) return
    if (item) {
      if (!box.open) {
        opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
        box.showModal()
      }
      // Bring the cited row into view, so the highlighted reading is seen without scrolling.
      const marked = box.querySelector<HTMLElement>('tr.marked')
      if (marked) requestAnimationFrame(() => marked.scrollIntoView({ block: 'nearest' }))
    } else {
      if (box.open) box.close()
      const back = opener.current
      opener.current = null
      if (back?.isConnected) back.focus()
    }
  }, [item, locator])

  // A citation such as "0:04" plays the recording from just before that moment.
  useEffect(() => {
    const audio = player.current
    const at = locator?.match(/^(\d+):(\d{2})$/)
    if (!audio || !at) return
    const start = Math.max(0, Number(at[1]) * 60 + Number(at[2]) - 1)
    const play = () => {
      audio.currentTime = start
      audio.play().catch(() => undefined)
    }
    if (audio.readyState >= 1) play()
    else audio.addEventListener('loadedmetadata', play, { once: true })
    return () => audio.removeEventListener('loadedmetadata', play)
  }, [item, locator])

  return (
    <dialog ref={dialog} className="viewer" onClose={onClose} aria-labelledby={titleId}>
      {item && (
        <>
          <div className="viewer-head">
            <h3 id={titleId}>
              {item.reading?.label ?? item.id}
              {locator && <span className="viewer-locator"> {locator}</span>}
            </h3>
            <button type="button" className="button quiet" onClick={onClose}>
              Close
            </button>
          </div>
          <div className="viewer-body">
            {item.type === 'interview_audio' ? (
              <div className="recording">
                <p className="fine">The interview as recorded, in Bahasa Indonesia.</p>
                <audio ref={player} controls preload="metadata" src={item.image} />
              </div>
            ) : (
              <img src={item.image} alt={`${item.reading?.label ?? 'Evidence'} as photographed`} />
            )}
            <div>
              <h4>What the reader extracted</h4>
              <Reading item={item} locator={locator} />
            </div>
          </div>
        </>
      )}
    </dialog>
  )
}
