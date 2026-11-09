import type { ReactNode } from "react";
const shapes: Record<string, ReactNode> = {
  camera: (
    <>
      <rect x="3" y="6" width="13" height="12" rx="3" />
      <path d="m16 10 5-3v10l-5-3" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  shield: (
    <>
      <path d="m12 3 8 3v6c0 5-8 9-8 9S4 17 4 12V6l8-3Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 21v-3a7 7 0 0 1 14 0v3H5Z" />
    </>
  ),
  logout: (
    <>
      <path d="M9 4H4v16h5m5-12 4 4-4 4m-6-4h13" />
    </>
  ),
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  refresh: (
    <>
      <path d="M20 7v5h-5M4 17v-5h5" />
      <path d="M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1" />
    </>
  ),
  stop: <rect x="5" y="5" width="14" height="14" rx="2" />,
  volume: (
    <>
      <path d="m11 5-6 4H2v6h3l6 4V5Z" />
      <path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" />
    </>
  ),
  "volume-off": (
    <>
      <path d="m11 5-6 4H2v6h3l6 4V5Z" />
      <path d="m16 9 6 6m0-6-6 6" />
    </>
  ),
  expand: <path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6" />,
  play: <path d="m8 4 13 8-13 8V4Z" />,
  download: (
    <>
      <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />
    </>
  ),
  drive: (
    <>
      <path d="m5 4-2 12v4h18v-4L19 4H5Zm-2 12h18" />
      <circle cx="12" cy="10" r="2" />
    </>
  ),
  plus: <path d="M12 4v16M4 12h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  left: <path d="m15 5-7 7 7 7" />,
  right: <path d="m9 5 7 7-7 7" />,
  check: <path d="m5 12 4 4L19 6" />,
  eye: (
    <>
      <path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6Z" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),
  "eye-off": (
    <>
      <path d="M4.8 8.3A14 14 0 0 0 2 12s3.6 6 10 6c1.5 0 2.9-.3 4.1-.9M9 6.4a10.8 10.8 0 0 1 3-.4c6.4 0 10 6 10 6a14 14 0 0 1-2.7 3.5" />
      <path d="m3 3 18 18" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="3" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" />
    </>
  ),
};
export function Icon({
  name,
  className = "",
}: {
  name: keyof typeof shapes;
  className?: string;
}) {
  return (
    <svg
      className={`icon ${className}`}
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {shapes[name]}
    </svg>
  );
}
