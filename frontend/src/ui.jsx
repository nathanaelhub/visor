// Icons, status pills, reason chips and the progress bar from the Visor design system.
import { Fragment } from 'react'

const P = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' }

const PATHS = {
  plan: <><rect x="2.5" y="3" width="11" height="10" rx="1.5" {...P} /><path d="M2.5 6.5h11M6.5 6.5V13" {...P} /></>,
  chat: <path d="M3 3.5h10a1 1 0 011 1v6a1 1 0 01-1 1H7l-3 2.5v-2.5H3a1 1 0 01-1-1v-6a1 1 0 011-1z" {...P} />,
  users: <><circle cx="6" cy="5.5" r="2.3" {...P} /><path d="M2 13c.4-2.2 2-3.4 4-3.4s3.6 1.2 4 3.4M10.5 3.6a2.2 2.2 0 010 4M12 9.8c1.2.4 2 1.4 2.2 3.2" {...P} /></>,
  swap: <path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" {...P} />,
  check: <><circle cx="8" cy="8" r="6.5" {...P} strokeWidth={1.5} /><path d="M5 8.2l2 2 4-4.2" {...P} /></>,
  half: <><circle cx="8" cy="8" r="6" {...P} strokeWidth={1.5} /><path d="M8 2a6 6 0 010 12z" fill="currentColor" /></>,
  dashed: <circle cx="8" cy="8" r="6" {...P} strokeWidth={1.5} strokeDasharray="2.2 2.2" />,
  alert: <><path d="M8 2L14.5 13.5H1.5Z" {...P} strokeWidth={1.5} /><path d="M8 6.5v3.2M8 11.6v.1" {...P} /></>,
  right: <path d="M3 8h9.5M9 4.5L12.5 8 9 11.5" {...P} />,
  left: <path d="M13 8H3.5M7 4.5L3.5 8 7 11.5" {...P} />,
  cal: <><rect x="2.5" y="3.5" width="11" height="10" rx="1.5" {...P} /><path d="M2.5 7h11M5.5 2v3M10.5 2v3" {...P} /></>,
  retake: <path d="M3.2 8a4.8 4.8 0 108.3-3.3M11.8 2v2.9H8.9" {...P} />,
  fills: <><rect x="2.5" y="2.5" width="11" height="11" rx="2" {...P} /><path d="M5.2 8.2l2 2 3.8-4" {...P} /></>,
  lock: <><rect x="3" y="7" width="10" height="7" rx="1.5" {...P} /><path d="M5.5 7V5a2.5 2.5 0 015 0v2" {...P} /></>,
  search: <><circle cx="7" cy="7" r="4.5" {...P} /><path d="M10.5 10.5L14 14" {...P} /></>,
  eye: <><path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" {...P} /><circle cx="8" cy="8" r="2" {...P} /></>,
  eyeoff: <path d="M2 2l12 12M6.6 3.7A6.6 6.6 0 018 3.5c4 0 6.5 4.5 6.5 4.5a11 11 0 01-1.8 2.4M10.3 10.6A3 3 0 015.4 6.3M3.5 5.5A11 11 0 001.5 8s2.5 4.5 6.5 4.5c.9 0 1.7-.2 2.5-.5" {...P} />,
  moon: <path d="M13.5 9.6A5.8 5.8 0 016.4 2.5 5.8 5.8 0 1013.5 9.6z" {...P} />,
  sun: <><circle cx="8" cy="8" r="2.8" {...P} /><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" {...P} /></>,
  flag: <path d="M3.5 14V2.5M3.5 3h8l-1.6 3 1.6 3h-8" {...P} />,
  send: <path d="M8 13V3.5M3.8 7.5L8 3.3l4.2 4.2" {...P} strokeWidth={1.9} />,
  close: <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" {...P} />,
  down: <path d="M4 6l4 4 4-4" {...P} />,
  up: <path d="M4 10l4-4 4 4" {...P} />,
  book: <path d="M2.5 3.5h4a2 2 0 012 2v8a1.5 1.5 0 00-1.5-1.5h-4.5zM13.5 3.5h-4a2 2 0 00-1 .3M13.5 3.5v8.5H9a1.5 1.5 0 00-1.5 1.5" {...P} />,
  table: <><rect x="2.5" y="3" width="11" height="10" rx="1.5" {...P} /><path d="M2.5 6.5h11M2.5 9.8h11M7 6.5V13" {...P} /></>,
  cap: <path d="M1.5 6.5L8 3.5l6.5 3L8 9.5zM4.5 8v3c1 1 2.2 1.5 3.5 1.5s2.5-.5 3.5-1.5V8M14.5 6.5V10" {...P} />,
  advisor: <><circle cx="6" cy="5.5" r="2.5" {...P} /><path d="M1.8 13.5c.4-2.4 2.1-3.7 4.2-3.7 1 0 1.8.2 2.5.7M9.8 11.5l1.5 1.5 3-3" {...P} /></>,
  key: <><circle cx="5" cy="10.5" r="2.8" {...P} /><path d="M7 8.5l6-6M11 4.5l1.5 1.5" {...P} /></>,
  spinner: <path d="M8 2a6 6 0 106 6" {...P} strokeWidth={1.8} />,
}

export function Icon({ name, size = 16, className, style, title }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}
      className={className} style={{ flex: 'none', ...style }}>
      {title && <title>{title}</title>}
      {PATHS[name] ?? <Fragment />}
    </svg>
  )
}

export function Logo({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#331E54" />
      <path d="M8.5 20.5a7.5 7.5 0 0115 0" fill="none" stroke="#F4AA00" strokeWidth="3" strokeLinecap="round" />
      <circle cx="16" cy="20.5" r="2.3" fill="#F4AA00" />
    </svg>
  )
}

const STATUS = {
  met: ['check', 'Met'], in_progress: ['half', 'In progress'], needed: ['dashed', 'Needed'],
  confirmed: ['check', 'Confirmed'], proposed: ['half', 'Proposed'], unknown: ['dashed', 'Unknown'],
  review: ['alert', 'Needs review'], retake: ['retake', 'Retake'], ok: ['check', 'OK'], error: ['alert', 'Error'],
  pending: ['half', 'Transfer pending'],
}

export function Pill({ status, children }) {
  const [icon, label] = STATUS[status] ?? ['dashed', status]
  const cls = status === 'pending' ? 'proposed' : status
  return <span className={`pill pill-${cls}`}><Icon name={icon} size={14} />{children ?? label}</span>
}

const CHIP_ICON = { unlocks: 'right', retake: 'retake', offering: 'cal', needs: 'left', prerequisite: 'left',
  requirement: 'fills', standing: 'cap', deferred: 'cal', pinned: 'lock', held: 'cal' }

export function Chip({ kind, children }) {
  return <span className={`chip chip-${kind}`}><Icon name={CHIP_ICON[kind] ?? 'fills'} size={12} />{children}</span>
}

export function Bar({ done = 0, prog = 0, total = 1, thin, status, label }) {
  const pct = (v) => `${Math.max(0, Math.min(100, (v / (total || 1)) * 100))}%`
  return (
    <div className={`bar${thin ? ' thin' : ''}${status ? ` st-${status}` : ''}`} role="img" aria-label={label}>
      <span className="done" style={{ width: pct(done) }} />
      {!thin && <span className="prog" style={{ width: pct(prog) }} />}
      {thin && prog > done && <span className="done" style={{ width: pct(prog - done), opacity: 0.45 }} />}
    </div>
  )
}

export function Spinner({ size = 16 }) {
  return <Icon name="spinner" size={size} className="spin" />
}
