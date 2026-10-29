import { useEffect, useState } from 'react'

// Degree Progress tab (spec 05). Pick a fictional demo student; the backend runs the transfer
// lookup, the degree audit, and the semester forecast, and nothing is stored.
const STATUS_LABEL = { met: 'Met', in_progress: 'In progress', needed: 'Needed' }

export default function DegreeProgress() {
  const [students, setStudents] = useState([])
  const [studentId, setStudentId] = useState('')
  const [summer, setSummer] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/demo/students')
      .then((r) => r.json())
      .then((s) => { setStudents(s); if (s.length) setStudentId(s[0].id) })
      .catch(() => setError('Could not reach the API. Is the backend running and seeded with the demo data?'))
  }, [])

  const student = students.find((s) => s.id === studentId)

  useEffect(() => {
    if (!student) return
    setLoading(true)
    setError('')
    fetch('/api/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...student, settings: { include_summer: summer } }),
    })
      .then(async (r) => {
        const body = await r.json()
        if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`)
        setResult(body)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [student, summer])

  return (
    <section className="degree">
      <p className="banner">Demo: every student here is fictional. The catalog is the real 2026–27 Lipscomb catalog.</p>

      <div className="lookup-form">
        <label>
          Student
          <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
            {students.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label className="inline">
          <input type="checkbox" checked={summer} onChange={(e) => setSummer(e.target.checked)} />
          Plan summers
        </label>
      </div>
      {student && <p className="hint">{student.story}</p>}
      {error && <p className="error">{error}</p>}
      {loading && <p className="hint">Planning…</p>}
      {result && !loading && <Result r={result} />}
    </section>
  )
}

function Result({ r }) {
  const plan = r.plan
  const done = r.hours_done
  const inProgress = r.hours_in_progress
  const pct = (h) => `${Math.min(100, (h / r.hours_required) * 100)}%`
  return (
    <>
      {r.needs_review && (
        <div className="review-flag" role="alert">
          <strong>Needs advisor review.</strong> The forecast couldn’t place everything; see the warnings below.
        </div>
      )}

      <div className="summary">
        <div>
          <div className="big">{plan?.complete ? 'Done' : (r.projected_term ? termName(r.projected_term) : '—')}</div>
          <div className="hint">{plan?.complete ? 'Complete pending final grades' : 'Projected graduation'}</div>
        </div>
        <div className="hours">
          <div className="bar" aria-label={`${done} of ${r.hours_required} hours done`}>
            <span className="done" style={{ width: pct(done) }} />
            <span className="progress" style={{ width: pct(inProgress) }} />
          </div>
          <div className="hint">
            {done} done · {inProgress} in progress · {r.hours_required} required
            {plan && plan.free_elective_hours > 0 && <> · <strong>{plan.free_elective_hours} hour{plan.free_elective_hours === 1 ? '' : 's'} of free electives</strong> still to choose</>}
          </div>
        </div>
      </div>

      {r.transfer.length > 0 && <TransferTable rows={r.transfer} />}

      <h2>Requirements</h2>
      <ul className="groups">
        {r.groups.map((g) => (
          <li key={g.id} className={`group status-${g.status}`}>
            <details>
              <summary>
                <span className={`pill pill-${g.status}`}>{STATUS_LABEL[g.status]}</span>
                <span className="group-name">{g.name}</span>
                {g.status !== 'met' && <span className="hint"> — {g.remaining}</span>}
              </summary>
              {g.used.length ? (
                <ul className="used">
                  {g.used.map((u) => (
                    <li key={u.code}>
                      {u.code} <span className="hint">({u.via.replace('_', ' ')}{u.detail ? `: ${u.detail}` : ''})</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="hint">Nothing counted here yet.</p>}
            </details>
          </li>
        ))}
      </ul>

      {r.warnings.length > 0 && (
        <>
          <h2>Warnings</h2>
          <ul className="warnings">{r.warnings.map((w, i) => <li key={i}>{w.message}</li>)}</ul>
        </>
      )}

      {plan && plan.terms.length > 0 && (
        <>
          <h2>Semester plan</h2>
          <div className="terms">
            {plan.terms.map((t, i) => (
              <article key={t.term} className={`term${i === 0 ? ' next' : ''}`}>
                <header>
                  <h3>{i === 0 ? `Next term · ${t.name}` : t.name}</h3>
                  <span className="hint">{t.hours} hrs{t.light ? ' · light' : ''}</span>
                </header>
                <ul>
                  {t.courses.map((c) => (
                    <li key={c.code}>
                      <div><strong>{c.code}</strong> {c.title} <span className="hint">({c.credits})</span></div>
                      <div className="reasons">
                        {c.reasons.map((x, k) => <span key={k} className={`chip chip-${x.kind}`}>{x.text}</span>)}
                        {c.deferred_from && !c.reasons.some((x) => x.kind === 'offering') && (
                          <span className="chip chip-deferred">Not offered {termName(c.deferred_from)}</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </>
      )}
    </>
  )
}

function TransferTable({ rows }) {
  return (
    <>
      <h2>Transfer credit</h2>
      <table>
        <thead><tr><th>School</th><th>Course</th><th>Status</th><th>Counts as</th></tr></thead>
        <tbody>
          {rows.map((t, i) => (
            <tr key={i} className={t.counted ? '' : 'not-counted'}>
              <td>{t.school ?? '—'}</td>
              <td>{t.external}</td>
              <td><span className={`pill pill-${t.status}`}>{t.status}</span></td>
              <td>{t.counts_as ?? '—'}{t.note && <div className="hint">{t.note}</div>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

const SEASON = { SP: 'Spring', SU: 'Summer', FA: 'Fall' }
function termName(code) {
  return `${SEASON[code.slice(4)] ?? code.slice(4)} ${code.slice(0, 4)}`
}
