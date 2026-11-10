import { useEffect, useState } from 'react'
import { api, cleanName, keyStore, termName } from '../lib.js'
import { toStudent } from '../transcript.js'
import { Icon, Spinner } from '../ui.jsx'

// Start from a transcript (spec 05, US-5.7). Claude reads one of the fictional transcripts into a
// course list; the person checks and edits it, and nothing runs until they press "Use this record".
// The public demo only offers the bundled fictional transcripts (no file picker).
export default function Transcript({ onUse, onCancel }) {
  const [demos, setDemos] = useState([])
  const [shared, setShared] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [read, setRead] = useState(null) // { record, unreadable, unknown_codes }
  const [taken, setTaken] = useState([])
  const [transfer, setTransfer] = useState([])

  useEffect(() => {
    api('/api/transcript/demos').then(setDemos).catch(() => setError('Could not reach the Visor API.'))
    api('/api/chat/config').then((c) => setShared(c.shared_key)).catch(() => setShared(false))
  }, [])

  async function readDemo(id) {
    setBusy(id); setError(''); setRead(null)
    const key = keyStore.get()
    try {
      const r = await api('/api/transcript', { method: 'POST', body: { demo: id },
        headers: key && !shared ? { 'X-Anthropic-Key': key } : {} })
      setRead(r)
      setTaken(r.record.taken)
      setTransfer(r.record.transfer)
    } catch (e) {
      setError(e.code === 'no_key' ? 'Reading a transcript uses Claude. Connect a key on the Ask Visor tab first.' : e.message)
    } finally { setBusy('') }
  }

  const { student, problems } = read ? toStudent(read.record, taken, transfer) : { student: null, problems: [] }
  const unknown = new Set(read?.unknown_codes ?? [])
  const edit = (setRows) => (i, field) => (e) => setRows((rows) => rows.map((r, k) => (k === i ? { ...r, [field]: e.target.value } : r)))
  const editTaken = edit(setTaken)
  const editTransfer = edit(setTransfer)

  return (
    <div className="wrap">
      <button type="button" className="linkbtn row small" onClick={onCancel} style={{ alignSelf: 'flex-start', gap: 6 }}>
        <Icon name="left" /> Back to My Plan
      </button>
      <div className="pagehead">
        <div style={{ flex: '1 1 420px' }}>
          <h1 className="h1">Start from a transcript</h1>
          <p className="muted" style={{ margin: '6px 0 0' }}>
            Claude reads the transcript into a course list. You check it, then Visor runs the audit and plan on it.
          </p>
        </div>
      </div>

      <div className="notice warn" role="note">
        <Icon name="alert" />
        <span style={{ flex: '1 1 0', minWidth: 220 }}><strong>Demo: fictional transcripts only.</strong> Uploading your own transcript is turned off on the
          public site; real transcripts are protected student records. Nothing you read here is saved.
          {shared && ' Each read uses 4 units of your Ask Visor allowance.'}</span>
      </div>

      <section className="card" style={{ padding: 20 }} aria-label="Fictional transcripts">
        <h2 style={{ margin: '0 0 12px', fontSize: 18 }}>Pick a fictional transcript</h2>
        <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
          {demos.map((d) => (
            <div key={d.id} className="card" style={{ padding: 16, flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <strong>{cleanName(d.name)}</strong>
              <span className="small muted">{d.label}</span>
              <div className="row" style={{ gap: 12, marginTop: 'auto' }}>
                <button type="button" className="btn" disabled={!!busy} onClick={() => readDemo(d.id)}>
                  {busy === d.id ? <><Spinner /> Reading…</> : 'Read it'}
                </button>
                <a className="small" href={`/api/transcript/demos/${d.id}.pdf`} target="_blank" rel="noreferrer">View PDF</a>
              </div>
            </div>
          ))}
        </div>
      </section>

      {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}

      {read && (
        <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }} aria-label="Check the course list">
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>Check what Claude read for {cleanName(read.record.name.replace(' (from transcript)', ''))}</h2>
            <p className="small muted" style={{ margin: '4px 0 0' }}>
              Fix anything that's wrong. Clear a row to remove it. Leave the grade blank (or IP) for a course in progress.
            </p>
          </div>
          {(read.unreadable.length > 0 || unknown.size > 0) && (
            <div className="notice warn" role="status">
              <Icon name="alert" />
              <ul style={{ margin: 0, paddingLeft: 18, flex: '1 1 0', minWidth: 220 }}>
                {[...unknown].map((c) => <li key={c}>{c} is not in the 2026-27 catalog. It will count toward hours only, and an advisor should check it.</li>)}
                {read.unreadable.map((u) => <li key={u}>{u}</li>)}
              </ul>
            </div>
          )}

          <div className="table-card">
            <table className="tbl">
              <caption className="sr">Lipscomb courses</caption>
              <thead><tr><th>Course</th><th>Title</th><th>Hours</th><th>Grade</th><th>Term</th></tr></thead>
              <tbody>
                {taken.map((t, i) => (
                  <tr key={i}>
                    <td><input className="field mono" style={{ width: 110 }} aria-label={`Course ${i + 1} code`} value={t.code ?? ''} onChange={editTaken(i, 'code')} />
                      {unknown.has(t.code) && <span className="small" style={{ display: 'block', color: 'var(--rvF)' }}>Not in catalog</span>}</td>
                    <td>{t.title}</td>
                    <td><input className="field" style={{ width: 64 }} aria-label={`Course ${i + 1} hours`} value={t.credits ?? ''} onChange={editTaken(i, 'credits')} /></td>
                    <td><input className="field" style={{ width: 64 }} aria-label={`Course ${i + 1} grade`} value={t.grade ?? ''} placeholder="IP" onChange={editTaken(i, 'grade')} /></td>
                    <td className="small muted">{t.term ? termName(t.term) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" className="linkbtn small" style={{ alignSelf: 'flex-start' }}
            onClick={() => setTaken((rows) => [...rows, { code: '', title: '', credits: '', grade: '', term: null }])}>Add a course</button>

          {transfer.length > 0 && (
            <div className="table-card">
              <table className="tbl">
                <caption className="sr">Transfer credit</caption>
                <thead><tr><th>Transfer school</th><th>Subject</th><th>Number</th><th>Title</th><th>Grade</th></tr></thead>
                <tbody>
                  {transfer.map((t, i) => (
                    <tr key={i}>
                      <td className="small">{t.school}</td>
                      <td><input className="field mono" style={{ width: 80 }} aria-label={`Transfer ${i + 1} subject`} value={t.subject ?? ''} onChange={editTransfer(i, 'subject')} /></td>
                      <td><input className="field mono" style={{ width: 80 }} aria-label={`Transfer ${i + 1} number`} value={t.number ?? ''} onChange={editTransfer(i, 'number')} /></td>
                      <td className="small">{t.title}</td>
                      <td><input className="field" style={{ width: 64 }} aria-label={`Transfer ${i + 1} grade`} value={t.grade ?? ''} onChange={editTransfer(i, 'grade')} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {problems.length > 0 && (
            <div className="notice err" role="alert"><Icon name="alert" />
              <ul style={{ margin: 0, paddingLeft: 18, flex: '1 1 0', minWidth: 220 }}>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}
          <div className="row" style={{ gap: 12 }}>
            <button type="button" className="btn" disabled={problems.length > 0} onClick={() => onUse(student)}>
              <Icon name="check" /> Use this record
            </button>
            <button type="button" className="btn2" onClick={() => setRead(null)}>Start over</button>
          </div>
        </section>
      )}
    </div>
  )
}
