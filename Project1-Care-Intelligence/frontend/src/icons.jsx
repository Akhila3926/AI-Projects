const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };

export const CalendarIcon = (p) => (
  <svg {...base} {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M16 3v4M8 3v4M3 10h18" />
  </svg>
);

export const DollarIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M12 2v20M17 6.5c0-1.9-2.2-3.5-5-3.5s-5 1.4-5 3.5 2.2 3 5 3.5 5 1.6 5 3.5-2.2 3.5-5 3.5-5-1.6-5-3.5" />
  </svg>
);

export const CheckCircleIcon = (p) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12.5l2.3 2.3L16 9.5" />
  </svg>
);

export const ClockIcon = (p) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3.5 2" />
  </svg>
);

export const ChatIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
  </svg>
);

export const CloseIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

export const SendIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" />
  </svg>
);

export const PatientsIcon = (p) => (
  <svg {...base} {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 9a3 3 0 1 0 0-6M19.5 20a5.5 5.5 0 0 0-4-5.3" />
  </svg>
);

export const ClaimsIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M7 3h8l4 4v14H7z" />
    <path d="M15 3v4h4M9 12h6M9 16h6M9 8h2" />
  </svg>
);

export const PayersIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M12 2 3 6v6c0 5 3.8 8.7 9 10 5.2-1.3 9-5 9-10V6z" />
  </svg>
);

export const ActivityIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M3 12h4l2 7 4-14 2 7h6" />
  </svg>
);

export const RefreshIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M21 12a9 9 0 1 1-2.6-6.4M21 4v6h-6" />
  </svg>
);

export const PlayIcon = (p) => (
  <svg {...base} {...p}>
    <path d="M6 4l14 8-14 8z" />
  </svg>
);
