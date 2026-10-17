// Small line icons for the owner's pages, drawn in the same hand as the logo: ink strokes, with the
// notebook's red margin and the verified green as the only colours.
import type { ReactNode } from 'react'
import type { EvidenceType } from '../../types.ts'

type IconProps = { size?: number }

function Svg({ size = 24, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

export function NotebookIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="4.5" y="2.5" width="15" height="19" rx="1.2" />
      <path d="M4.5 8h15M4.5 12h15M4.5 16h15" stroke="var(--rule-blue)" />
      <path d="M8.5 2.5v19" stroke="var(--margin-red)" />
    </Svg>
  )
}

export function ReceiptIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 2.5h12v19l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4-2 1.4z" />
      <path d="M9 7.5h6M9 11h6M9 14.5h3.5" />
    </Svg>
  )
}

export function QrisIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="6" y="1.8" width="12" height="20.4" rx="2" />
      <rect x="8.6" y="6" width="3" height="3" />
      <rect x="12.4" y="6" width="3" height="3" />
      <rect x="8.6" y="9.8" width="3" height="3" />
      <path d="M12.4 9.8h3v3M12.4 12.8h1" />
      <path d="M10.5 18.5h3" />
    </Svg>
  )
}

export function MicIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="9" y="2.5" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5v4M8.5 21.5h7" />
    </Svg>
  )
}

export function ShopIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 9.5 4.8 4h14.4L21 9.5" />
      <path d="M3 9.5c0 1.4 1 2.3 2.25 2.3S7.5 10.9 7.5 9.5c0 1.4 1 2.3 2.25 2.3S12 10.9 12 9.5c0 1.4 1 2.3 2.25 2.3s2.25-.9 2.25-2.3c0 1.4 1 2.3 2.25 2.3S21 10.9 21 9.5" />
      <path d="M4.5 12v9.5h15V12M10 21.5v-5h4v5" />
    </Svg>
  )
}

export function TickIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m5 12.5 4.5 4.5L19 7.5" strokeWidth={2.2} />
    </Svg>
  )
}

export function LockIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="5" y="10.5" width="14" height="10" rx="1.5" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </Svg>
  )
}

export function PinIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 21.5s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z" />
      <circle cx="12" cy="10.5" r="2.3" />
    </Svg>
  )
}

export function PersonIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="7.5" r="3.5" />
      <path d="M4.5 21c.8-4 3.8-6.5 7.5-6.5s6.7 2.5 7.5 6.5" />
    </Svg>
  )
}

export function UndoIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8.5 5 4 9.5 8.5 14" />
      <path d="M4 9.5h10a6 6 0 0 1 0 12h-3" />
    </Svg>
  )
}

export function ChatIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3a9 9 0 0 0-7.8 13.5L3 21l4.6-1.2A9 9 0 1 0 12 3z" />
      <path d="M8.5 10.5h7M8.5 13.5h4.5" />
    </Svg>
  )
}

export function CopyIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="8.5" y="8.5" width="12" height="12" rx="1.5" />
      <path d="M15.5 8.5v-4a1 1 0 0 0-1-1h-10a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h4" />
    </Svg>
  )
}

export function CalendarIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="1.5" />
      <path d="M3.5 9.5h17M8 3v4M16 3v4" />
      <path d="M8 14h3" />
    </Svg>
  )
}

export function ArrowIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 12h15M13.5 6l6 6-6 6" />
    </Svg>
  )
}

export function KindIcon({ type, size }: { type: EvidenceType; size?: number }) {
  switch (type) {
    case 'ledger_page':
      return <NotebookIcon size={size} />
    case 'receipt':
      return <ReceiptIcon size={size} />
    case 'qris_history':
      return <QrisIcon size={size} />
    case 'interview_audio':
      return <MicIcon size={size} />
    case 'shop_photo':
      return <ShopIcon size={size} />
  }
}
