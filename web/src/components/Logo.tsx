export default function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true">
      <rect x="3" y="3" width="22" height="22" rx="6" fill="#0B6E5F" />
      <path
        d="M9 9v10h10"
        stroke="#fff"
        strokeWidth="2.4"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="17" cy="12" r="2.4" fill="#fff" />
    </svg>
  )
}
