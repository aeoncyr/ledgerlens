// A notebook page: ruled lines in blue, the red margin rule, and an ink tick where a line is verified.
export default function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true">
      <rect x="3.5" y="2.5" width="21" height="23" rx="1.5" fill="#FBFAF6" stroke="#1B201C" />
      <path d="M4 9h20M4 14h20M4 19h20" stroke="#C3D1DE" strokeWidth="1.2" />
      <path d="M9 3v22" stroke="#B23F36" strokeWidth="1.4" />
      <path
        d="M12.5 13.5l2.6 2.6 5.4-6"
        stroke="#0D5C50"
        strokeWidth="2.2"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
