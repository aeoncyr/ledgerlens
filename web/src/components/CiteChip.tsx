import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { excerptAt } from '../evidence.ts'
import type { EvidenceItem } from '../types.ts'

type Placement = 'below' | 'above' | 'below-end' | 'above-end' | 'sheet'

const PREVIEW_WIDTH = 300
const PREVIEW_HEIGHT = 230

// Where the preview fits: under the chip if there is room, otherwise above it; right-aligned near
// the right edge; a sheet along the bottom of a phone screen.
function placementFor(button: HTMLElement): Placement {
  if (window.innerWidth < 560) return 'sheet'
  const rect = button.getBoundingClientRect()
  const vertical = rect.bottom + PREVIEW_HEIGHT + 12 > window.innerHeight ? 'above' : 'below'
  const end = rect.left + PREVIEW_WIDTH + 16 > window.innerWidth
  return end ? `${vertical}-end` : vertical
}

// A citation chip. Clicking it opens the evidence viewer; hovering it, or reaching it with the
// keyboard, shows a short preview of what was read at that place. On a touch screen the first tap
// shows the preview and a second tap opens the evidence.
export default function CiteChip({
  item,
  locator,
  label,
  onOpen,
}: {
  item: EvidenceItem | undefined
  locator: string
  label: string
  onOpen: (item: EvidenceItem, locator: string) => void
}) {
  const [placement, setPlacement] = useState<Placement | null>(null)
  const [via, setVia] = useState<'mouse' | 'touch' | 'keyboard'>('mouse')
  const button = useRef<HTMLButtonElement>(null)
  const wrap = useRef<HTMLSpanElement>(null)
  const lastPointer = useRef<string>('mouse')
  const tipId = useId()

  function show(how: 'mouse' | 'touch' | 'keyboard') {
    if (!item || !button.current) return
    setVia(how)
    setPlacement(placementFor(button.current))
  }

  function hide() {
    setPlacement(null)
  }

  // A tap anywhere else closes a preview opened by touch.
  useEffect(() => {
    if (!placement) return
    function away(event: Event) {
      if (!wrap.current?.contains(event.target as Node)) setPlacement(null)
    }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [placement])

  function onPointerDown(event: PointerEvent) {
    lastPointer.current = event.pointerType
  }

  function onClick() {
    if (!item) return
    if (lastPointer.current === 'touch' && !placement) {
      show('touch')
      return
    }
    hide()
    onOpen(item, locator)
  }

  function onKeyDown(event: KeyboardEvent) {
    lastPointer.current = 'keyboard'
    if (event.key === 'Escape' && placement) {
      event.stopPropagation()
      hide()
    }
  }

  const excerpt = item && placement ? excerptAt(item, locator) : null

  return (
    <span className="cite-wrap" ref={wrap}>
      <button
        ref={button}
        type="button"
        className="cite"
        disabled={!item}
        aria-describedby={placement ? tipId : undefined}
        onClick={onClick}
        onPointerDown={onPointerDown}
        onPointerEnter={(e) => e.pointerType === 'mouse' && show('mouse')}
        onPointerLeave={(e) => e.pointerType === 'mouse' && hide()}
        onFocus={(e) => e.currentTarget.matches(':focus-visible') && show('keyboard')}
        onBlur={hide}
        onKeyDown={onKeyDown}
      >
        {label}, {locator}
      </button>
      {item && placement && (
        <span id={tipId} role="tooltip" className={`cite-preview ${placement}`}>
          {item.type === 'interview_audio' ? (
            <span className="cite-thumb audio" aria-hidden="true">
              ▶
            </span>
          ) : (
            item.image && <img className="cite-thumb" src={item.image} alt="" />
          )}
          <span className="cite-body">
            <span className="cite-where">
              {label} · {locator}
            </span>
            {excerpt ? (
              <>
                <span className="cite-text" lang={excerpt.lang}>
                  {excerpt.text}
                </span>
                {excerpt.note && <span className="cite-note">{excerpt.note}</span>}
                {excerpt.amount && <span className="cite-amount">{excerpt.amount}</span>}
              </>
            ) : (
              <span className="cite-note">The whole item is cited.</span>
            )}
            <span className="cite-hint">
              {via === 'touch'
                ? 'Tap again to open the evidence.'
                : via === 'keyboard'
                  ? 'Press Enter to open the evidence.'
                  : 'Click to open the evidence.'}
            </span>
          </span>
        </span>
      )}
    </span>
  )
}
