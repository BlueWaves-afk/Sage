// Inline stroke icons (no icon-font dependency). 20px default, currentColor.
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = (p: P) => ({
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...p,
});

export const IconDashboard = (p: P) => (
  <svg {...base(p)}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </svg>
);

export const IconGlobe = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
  </svg>
);

export const IconFlask = (p: P) => (
  <svg {...base(p)}>
    <path d="M9 3h6M10 3v6l-5 9a1.5 1.5 0 0 0 1.3 2.2h11.4A1.5 1.5 0 0 0 19 18l-5-9V3" />
    <path d="M7.5 14h9" />
  </svg>
);

export const IconShield = (p: P) => (
  <svg {...base(p)}>
    <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
    <path d="M12 8v4M12 15.5h.01" />
  </svg>
);

export const IconBot = (p: P) => (
  <svg {...base(p)}>
    <rect x="4" y="8" width="16" height="12" rx="2.5" />
    <path d="M12 8V4M8 4h8" />
    <circle cx="9" cy="14" r="1" fill="currentColor" stroke="none" />
    <circle cx="15" cy="14" r="1" fill="currentColor" stroke="none" />
  </svg>
);

export const IconGear = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" />
  </svg>
);

export const IconRss = (p: P) => (
  <svg {...base(p)}>
    <path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16" />
    <circle cx="5" cy="19" r="1.5" fill="currentColor" stroke="none" />
  </svg>
);

export const IconAnchor = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v13M5 12H3a9 9 0 0 0 18 0h-2M12 12H8m8 0h-4" />
  </svg>
);

export const IconChart = (p: P) => (
  <svg {...base(p)}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M7 15l3-3 2 2 5-5" />
  </svg>
);

export const IconAlert = (p: P) => (
  <svg {...base(p)}>
    <path d="M12 3l9 16H3z" />
    <path d="M12 10v4M12 17h.01" />
  </svg>
);

export const IconSend = (p: P) => (
  <svg {...base(p)}>
    <path d="M4 12l16-8-6 16-3-6-7-2z" />
  </svg>
);

export const IconBrain = (p: P) => (
  <svg {...base(p)}>
    <path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8V15a3 3 0 0 0 4 2.8V4zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 1 5.8V15a3 3 0 0 1-4 2.8V4z" />
  </svg>
);

export const IconUser = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </svg>
);

export const IconPlay = (p: P) => (
  <svg {...base(p)}>
    <path d="M7 4l13 8-13 8z" fill="currentColor" stroke="none" />
  </svg>
);

export const IconCheck = (p: P) => (
  <svg {...base(p)}>
    <path d="M20 6L9 17l-5-5" />
  </svg>
);

export const IconSun = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
  </svg>
);

export const IconMoon = (p: P) => (
  <svg {...base(p)}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
);

export const IconExternal = (p: P) => (
  <svg {...base(p)}>
    <path d="M14 4h6v6M20 4l-8 8M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" />
  </svg>
);

export const IconLogo = (p: P) => (
  <svg
    width={p.width ?? 20}
    height={p.height ?? 20}
    viewBox="0 0 476 601"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...p}
  >
    <circle cx="227" cy="41" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="35" cy="143" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="35" cy="283" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="174" cy="406" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="35" cy="462" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="238" cy="566" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="441" cy="462" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="441" cy="342" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="287" cy="203" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <circle cx="441" cy="143" r="32.5" stroke="currentColor" strokeWidth="15"/>
    <line x1="227.132" y1="43.229" x2="36.132" y2="140.229" stroke="currentColor" strokeWidth="15"/>
    <line x1="37.5" y1="143" x2="37.5" y2="283" stroke="currentColor" strokeWidth="15"/>
    <line x1="36.6863" y1="281.154" x2="175.686" y2="408.154" stroke="currentColor" strokeWidth="15"/>
    <path d="M224.855 43.3038L442.076 140.743" stroke="currentColor" strokeWidth="15"/>
    <line x1="35" y1="140.5" x2="441" y2="140.5" stroke="currentColor" strokeWidth="15"/>
    <line x1="36.517" y1="282.987" x2="131.517" y2="212.987" stroke="currentColor" strokeWidth="15"/>
    <line x1="37.4966" y1="139.997" x2="132.497" y2="210.997" stroke="currentColor" strokeWidth="15"/>
    <path d="M130 210.521L334 408.5" stroke="currentColor" strokeWidth="15"/>
    <line x1="285.436" y1="203.439" x2="332.436" y2="407.439" stroke="currentColor" strokeWidth="15"/>
    <path d="M442.298 345.137L332 407" stroke="currentColor" strokeWidth="15"/>
    <path d="M129 211.638L176.128 140.45" stroke="currentColor" strokeWidth="15"/>
    <line x1="176.778" y1="140.855" x2="226.778" y2="43.8546" stroke="currentColor" strokeWidth="15"/>
    <line x1="286.776" y1="205.18" x2="172.776" y2="141.18" stroke="currentColor" strokeWidth="15"/>
    <line x1="131.438" y1="211.446" x2="176.438" y2="409.446" stroke="currentColor" strokeWidth="15"/>
    <line x1="35.0246" y1="459.5" x2="441.025" y2="463.5" stroke="currentColor" strokeWidth="15"/>
    <line x1="36.1486" y1="459.779" x2="239.149" y2="564.779" stroke="currentColor" strokeWidth="15"/>
    <line x1="445.083" y1="464.253" x2="237.083" y2="564.253" stroke="currentColor" strokeWidth="15"/>
    <line x1="443.5" y1="343" x2="443.5" y2="466" stroke="currentColor" strokeWidth="15"/>
  </svg>
);

