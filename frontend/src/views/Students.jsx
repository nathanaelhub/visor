import { useEffect, useMemo, useState } from 'react'
import { api, cleanName, gradName, hrs, initials } from '../lib.js'
import { Icon, Pill, Spinner } from '../ui.jsx'

// Advisor: every advisee with the planner's summary and flags (GET /api/students).
const FILTERS = [
  { id: 'all', label: 'All advisees', test: () => true },
  { id: 'review', label: 'Needs review', test: (s) => s.flags.needs_review },
  { id: 'retake', label: 'Retake', test: (s) => s.flags.retake },
  { id: 'pending', label: 'Transfer pending', test: (s) => s.flags.transfer_pending },
]

export default function Students({ onOpen }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')

  useEffect(() => { api('/api/students').then(setRows).catch((e) => setError(e.message)) }, [])

  const shown = useMemo(() => {
    const f = FILTERS.find((x) => x.id === filter)
    const needle = q.trim().toLowerCase()
    return (rows ?? []).filter(f.test).filter((s) => !needle ||
      [s.name, s.student_number, s.program].some((v) => (v || '').toLowerCase().includes(needle)))
  }, [rows, filter, q])

  const flagged = (rows ?? []).find((s) => s.flags.needs_review)

  return (
    <div className="wrap">
      <div className="pagehead" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 className="h1">Students</h1>
          <p className="muted" style={{ margin: '6px 0 0' }}>Your advisees · Spring 2027 plans · fictional demo students</p>
        </div>
        <label style={{ flex: '0 1 380px' }}>
          <span className="lbl">Search students</span>
          <span className="keyfield" style={{ display: 'block' }}>
            <Icon name="search" style={{ position: 'absolute', left: 14, top: 15, color: 'var(--ink3)' }} />
            <input className="field" style={{ paddingLeft: 40 }} placeholder="Name, ID or program" value={q} onChange={(e) => setQ(e.target.value)} />
          </span>
        </label>
      </div>

      <div className="filters" role="group" aria-label="Filter advisees">
        {FILTERS.map((f) => (
          <button key={f.id} type="button" className="fbtn" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
            {f.label}<span className="n">{(rows ?? []).filter(f.test).length}</span>
          </button>
        ))}
      </div>

      {flagged && (
        <div className="review">
          <strong><Icon name="alert" />Needs advisor review</strong>
          <span style={{ flex: '1 1 300px' }}>{cleanName(flagged.name)}: {flagged.first_warning}</span>
          <button type="button" className="btn" onClick={() => onOpen(flagged.id)}>Review plan</button>
        </div>
      )}

      {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}
      {!rows && !error && <p className="row muted"><Spinner /> Running every advisee’s audit…</p>}

      {rows && (
        <div className="card table-card">
          <table className="tbl">
            <thead><tr><th>Student</th><th className="hidem">Program</th><th>Hours</th><th>Projected graduation</th><th className="hidem">Flags</th><th><span className="sr">Open</span></th></tr></thead>
            <tbody>
              {shown.map((s) => (
                <tr key={s.id}>
                  <td>
                    <div className="row" style={{ flexWrap: 'nowrap' }}>
                      <span className="avatar" aria-hidden="true">{initials(s.name)}</span>
                      <div><strong>{cleanName(s.name)}</strong><div className="mono small muted">{s.student_number}</div></div>
                    </div>
                  </td>
                  <td className="hidem">{s.program}</td>
                  <td>{hrs(s.hours_done + s.hours_in_progress)} of {s.hours_required}</td>
                  <td>{s.complete ? 'Requirements met' : s.projected_term ? gradName(s.projected_term) : 'Not yet known'}</td>
                  <td className="hidem">
                    <span className="row" style={{ gap: 6 }}>
                      {s.flags.needs_review && <Pill status="review" />}
                      {s.flags.retake && <Pill status="retake" />}
                      {s.flags.transfer_pending && (
                        <span title={`Waiting: ${(s.pending_transfer ?? []).join(', ')}`}>
                          <Pill status="pending" />
                          {s.pending_transfer?.length > 0 && <span className="small muted mono" style={{ display: 'block', marginTop: 4 }}>{s.pending_transfer.join(', ')}</span>}
                        </span>
                      )}
                      {!Object.values(s.flags).some(Boolean) && <span className="small muted">No flags</span>}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}><button type="button" className="btn2" onClick={() => onOpen(s.id)}>Open plan</button></td>
                </tr>
              ))}
              {shown.length === 0 && <tr><td colSpan={6} className="muted">No advisees match.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
