import { useEffect, useState } from 'react'
import { api } from '../lib.js'
import { Icon, Pill, Spinner } from '../ui.jsx'

// Registrar / advisor: what does a course from another school count as here?
// Uses the equivalency lookup and flag endpoints (specs/03) unchanged.
const MEANING = {
  confirmed: 'On file. Counts toward the degree now.',
  proposed: 'A person must confirm this before it counts.',
  unknown: 'No match on file. Flag it for a professor.',
}

export default function Transfer() {
  const [schools, setSchools] = useState([])
  const [schoolId, setSchoolId] = useState('')
  const [code, setCode] = useState('CISP 1020')
  const [result, setResult] = useState(null)
  const [fills, setFills] = useState(null)
  const [recent, setRecent] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [flagMsg, setFlagMsg] = useState('')

  useEffect(() => {
    api('/api/schools').then((s) => {
      setSchools(s)
      const first = s.find((x) => x.name.startsWith('Nashville State')) ?? s[0]
      if (first) setSchoolId(String(first.id))
    })
      .catch(() => setError('Could not reach the Visor API.'))
  }, [])

  async function lookup(sid = schoolId, c = code) {
    const m = c.trim().toUpperCase().match(/^([A-Z]+)\s*([\w-]+)$/)
    if (!sid || !m) { setError('Enter a course code like CISP 1020.'); return }
    setBusy(true); setError(''); setFlagMsg(''); setFills(null)
    try {
      const r = await api('/api/equivalencies/lookup', { method: 'POST', body: { school_id: Number(sid), subject: m[1], number: m[2] } })
      setResult(r)
      const school = schools.find((s) => String(s.id) === String(sid))
      setRecent((prev) => [{ sid, code: `${m[1]} ${m[2]}`, school: school?.name, status: r.status },
        ...prev.filter((x) => !(x.sid === sid && x.code === `${m[1]} ${m[2]}`))].slice(0, 5))
      const lip = r.equivalency?.course?.code
      if (lip) api(`/api/courses/${encodeURIComponent(lip)}/info`).then((i) => setFills(i.fills)).catch(() => setFills([]))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function flag() {
    const ext = result.external_course
    try {
      await api('/api/equivalencies/lookup/flag', { method: 'POST', body: {
        school_id: ext.school_id, subject: ext.subject, number: ext.number, reviewer: 'CS faculty', requested_by: 'registrar' } })
      setFlagMsg('Flagged for professor review.')
    } catch (e) {
      setFlagMsg(e.status === 409 ? 'Already confirmed; nothing to review.' : `Could not flag: ${e.message}`)
    }
  }

  const ext = result?.external_course
  const lip = result?.equivalency?.course
  const kind = result?.equivalency?.kind

  return (
    <div className="wrap">
      <div>
        <h1 className="h1">Transfer credit</h1>
        <p className="muted" style={{ margin: '6px 0 0' }}>Look up a course from another school and see what it counts as at Lipscomb.</p>
      </div>
      <div className="xfer">
        <form className="card xfer-form" onSubmit={(e) => { e.preventDefault(); lookup() }}>
          <label><span className="lbl">School</span>
            <select className="field" value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
              {schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label><span className="lbl">Course code</span>
            <input className="field mono" value={code} onChange={(e) => setCode(e.target.value)} placeholder="CISP 1020" />
          </label>
          <button className="btn" type="submit" disabled={busy}>{busy ? <Spinner /> : null}Look up</button>
          {recent.length > 0 && (
            <div className="recent">
              <span className="small muted" style={{ fontWeight: 600 }}>Recent lookups</span>
              {recent.map((x) => (
                <button key={x.sid + x.code} type="button" aria-pressed={ext && `${ext.subject} ${ext.number}` === x.code}
                  onClick={() => { setSchoolId(x.sid); setCode(x.code); lookup(x.sid, x.code) }}>
                  <span><span className="mono">{x.code}</span><br /><span className="small muted">{x.school?.replace(' Community College', '')}</span></span>
                  <Pill status={x.status} />
                </button>
              ))}
            </div>
          )}
        </form>

        <div className="stack">
          {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}
          {!result && !error && (
            <div className="card" style={{ padding: 24 }}>
              <p className="muted" style={{ margin: 0 }}>Try <span className="mono">CISP 1020</span> (confirmed), <span className="mono">CSCI 1020</span> at
                Columbia State (proposed), or <span className="mono">HIST 2010</span> at Nashville State (unknown).</p>
            </div>
          )}
          {result && (
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="result-head"><span className="muted">{ext.school}</span><Pill status={result.status} /></div>
              <div className="result-map">
                <div>
                  <span className="small muted">Their course</span>
                  <div className="bigcode">{ext.subject} {ext.number}</div>
                  <span className="muted">{ext.title}{ext.credits ? ` · ${ext.credits} hrs` : ''}</span>
                </div>
                <div className="to">
                  <span className="small muted">Counts at Lipscomb as</span>
                  <div className="bigcode">{lip ? lip.code : kind === 'elective' ? 'Elective' : kind === 'none' ? 'No credit' : '—'}</div>
                  <span className="muted">{lip ? lip.title : kind === 'elective' ? 'General elective hours' : kind === 'none' ? 'Does not transfer' : 'Not on file'}</span>
                </div>
              </div>
              <div className="result-meta">
                <div><span className="small muted">What this means</span><div>{MEANING[result.status]}</div></div>
                <div><span className="small muted">Source</span><div>
                  {result.equivalency?.decided_by ? `${result.equivalency.decided_by}${result.equivalency.decided_at ? `, ${result.equivalency.decided_at}` : ''}`
                    : result.equivalency?.source ? `Equivalency table (${result.equivalency.source})` : 'No row on file'}</div></div>
                <div><span className="small muted">Requirement</span><div>{fills === null ? (lip ? '…' : '—') : fills[0]?.name ?? 'Elective credit'}</div></div>
              </div>
              <div className="result-foot">
                {result.status !== 'confirmed'
                  ? <button type="button" className="btn2" onClick={flag}><Icon name="flag" />Flag for review</button>
                  : <span className="small muted">Confirmed answers are not re-flagged.</span>}
                <span className="small muted" role="status">{flagMsg || (result.equivalency?.pending_reviews ? `${result.equivalency.pending_reviews} review pending` : 'Last checked just now')}</span>
              </div>
            </div>
          )}
          <p className="small muted" style={{ margin: 0 }}>
            Confirmed: on file, counts now. Proposed: a person must confirm before it counts. Unknown: no match on file; flag it for a professor.
            Demo equivalencies are illustrative.
          </p>
        </div>
      </div>
    </div>
  )
}
