import { useEffect, useState } from 'react'
import { api, cleanName, keyStore, termName } from '../lib.js'
import { streamRead, toStudent } from '../transcript.js'
import { Icon, Spinner } from '../ui.jsx'

// Reading a transcript and checking what Claude read (spec 05 US-5.7, spec 07 US-7.4 and US-7.6).
// Shared by the "Start from a transcript" page and the 📎 in Ask Visor: nothing is used until the
// person presses "Use this record".

export function useTranscriptRead() {
  const [demos, setDemos] = useState([])
  const [shared, setShared] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [read, setRead] = useState(null) // { record, unreadable, unknown_codes }
  const [taken, setTaken] = useState([])
  const [transfer, setTransfer] = useState([])
  const [uploadsOpen, setUploadsOpen] = useState(false)
  const [programs, setPrograms] = useState([])
  const [programId, setProgramId] = useState('')
  const [live, setLive] = useState([]) // rows as Claude reads them (streamed)
  const [preview, setPreview] = useState(null) // { url, kind } of the file being read

  useEffect(() => {
    api('/api/transcript/demos').then(setDemos).catch(() => setError('Could not reach the Visor API.'))
    api('/api/chat/config').then((c) => setShared(c.shared_key)).catch(() => setShared(false))
    api('/api/transcript/config').then((c) => setUploadsOpen(c.uploads_open)).catch(() => setUploadsOpen(false))
    api('/api/programs').then(setPrograms).catch(() => setPrograms([]))
  }, [])

  async function readWith(label, body, previewOf) {
    setBusy(label); setError(''); setRead(null); setLive([]); setPreview(previewOf)
    const key = keyStore.get()
    try {
      const r = await streamRead(body, key && !shared ? { 'X-Anthropic-Key': key } : {},
        (e) => setLive((rows) => [...rows, { section: e.section, ...e.row }]))
      setRead(r)
      setTaken(r.record.taken)
      setTransfer(r.record.transfer)
      setProgramId(r.record.program_id)
    } catch (e) {
      setError(e.code === 'no_key' ? 'Reading a transcript uses Claude. Connect a key on the Ask Visor tab first.' : e.message)
    } finally { setBusy('') }
  }

  const readDemo = (d) => readWith(d.id, { demo: d.id }, { url: `/api/transcript/demos/${d.id}/file`, kind: d.kind ?? 'pdf' })

  function readFile(file) {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    readWith('upload', form, { url: URL.createObjectURL(file), kind: file.type === 'application/pdf' ? 'pdf' : 'image' })
  }

  const { student, problems } = read ? toStudent({ ...read.record, program_id: programId || read.record.program_id }, taken, transfer)
    : { student: null, problems: [] }
  const unknown = new Set(read?.unknown_codes ?? [])
  const edit = (setRows) => (i, field) => (e) => setRows((rows) => rows.map((r, k) => (k === i ? { ...r, [field]: e.target.value } : r)))
  const editTaken = edit(setTaken)
  const editTransfer = edit(setTransfer)

  const reset = () => { setRead(null); setLive([]); setPreview(null); setError('') }
  return { demos, shared, busy, error, read, taken, setTaken, transfer, uploadsOpen, programs, programId, setProgramId,
    live, preview, readDemo, readFile, student, problems, unknown, editTaken, editTransfer, setRead, reset }
}

export function LiveRead({ t }) {
  if (!((t.busy || (t.live.length > 0 && !t.read)) && t.preview)) return null
  return (
        <section className="card live-read" style={{ padding: 20 }} aria-label="Reading the transcript" aria-busy={!!t.busy}>
          <div className="live-file">
            {t.preview.kind === 'image'
              ? <img src={t.preview.url} alt="The transcript being read" style={{ width: '100%', borderRadius: 8 }} />
              : <iframe src={t.preview.url} title="The transcript being read" style={{ width: '100%', height: 420, border: 0, borderRadius: 8 }} />}
          </div>
          <div>
            <p className="row small" style={{ margin: '0 0 8px', gap: 8 }}><Spinner /> Claude is reading it… {t.live.length} row{t.live.length === 1 ? '' : 's'} so far</p>
            <ul className="live-rows" aria-live="polite">
              {t.live.map((r, i) => (
                <li key={i}><span className="mono">{r.code}</span> {r.title} <span className="muted">· {r.grade || 'IP'}{r.school ? ` · ${r.school}` : ''}</span></li>
              ))}
            </ul>
          </div>
        </section>
        )
}

export function TranscriptReview({ t, onUse }) {
  if (!t.read) return null
  return (
        <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }} aria-label="Check the course list">
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>Check what Claude read for {cleanName(t.read.record.name.replace(' (from transcript)', ''))}</h2>
            <p className="small muted" style={{ margin: '4px 0 0' }}>
              Fix anything that's wrong. Clear a row to remove it. Leave the grade blank (or IP) for a course in progress.
            </p>
          </div>
          {t.programs.length > 0 && (
            <label style={{ maxWidth: 420 }}><span className="lbl">Plan for which Lipscomb major?{t.read.needs_program ? ' (this transcript is from another school)' : ''}</span>
              <select className="field" value={t.programId} onChange={(e) => t.setProgramId(e.target.value)}>
                {t.programs.map((p) => <option key={p.id} value={p.id}>{p.degree} {p.name}</option>)}
              </select>
            </label>
          )}
          {t.read.issuing_school && t.read.needs_program && (
            <p className="small muted" style={{ margin: 0 }}>Issued by {t.read.issuing_school}. Everything taken there is listed as transfer credit from {t.read.issuing_school}.</p>
          )}
          {(t.read.unreadable.length > 0 || t.unknown.size > 0) && (
            <div className="notice warn" role="status">
              <Icon name="alert" />
              <ul style={{ margin: 0, paddingLeft: 18, flex: '1 1 0', minWidth: 220 }}>
                {[...unknown].map((c) => <li key={c}>{c} is not in the 2026-27 catalog. It will count toward hours only, and an advisor should check it.</li>)}
                {t.read.unreadable.map((u) => <li key={u}>{u}</li>)}
              </ul>
            </div>
          )}

          {(t.taken.length > 0 || !t.read.needs_program) && <div className="table-card">
            <table className="tbl">
              <caption className="sr">Lipscomb courses</caption>
              <thead><tr><th>Course</th><th>Title</th><th>Hours</th><th>Grade</th><th>Term</th></tr></thead>
              <tbody>
                {t.taken.map((row, i) => (
                  <tr key={i}>
                    <td><input className="field mono" style={{ width: 110 }} aria-label={`Course ${i + 1} code`} value={row.code ?? ''} onChange={t.editTaken(i, 'code')} />
                      {t.unknown.has(row.code) && <span className="small" style={{ display: 'block', color: 'var(--rvF)' }}>Not in catalog</span>}</td>
                    <td>{row.title}</td>
                    <td><input className="field" style={{ width: 64 }} aria-label={`Course ${i + 1} hours`} value={row.credits ?? ''} onChange={t.editTaken(i, 'credits')} /></td>
                    <td><input className="field" style={{ width: 64 }} aria-label={`Course ${i + 1} grade`} value={row.grade ?? ''} placeholder="IP" onChange={t.editTaken(i, 'grade')} /></td>
                    <td className="small muted">{row.term ? termName(row.term) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
          <button type="button" className="linkbtn small" style={{ alignSelf: 'flex-start' }}
            onClick={() => t.setTaken((rows) => [...rows, { code: '', title: '', credits: '', grade: '', term: null }])}>Add a course</button>

          {t.transfer.length > 0 && (
            <div className="table-card">
              <table className="tbl">
                <caption className="sr">Transfer credit</caption>
                <thead><tr><th>Transfer school</th><th>Subject</th><th>Number</th><th>Title</th><th>Grade</th></tr></thead>
                <tbody>
                  {t.transfer.map((row, i) => (
                    <tr key={i}>
                      <td className="small">{row.school}</td>
                      <td><input className="field mono" style={{ width: 80 }} aria-label={`Transfer ${i + 1} subject`} value={row.subject ?? ''} onChange={t.editTransfer(i, 'subject')} /></td>
                      <td><input className="field mono" style={{ width: 80 }} aria-label={`Transfer ${i + 1} number`} value={row.number ?? ''} onChange={t.editTransfer(i, 'number')} /></td>
                      <td className="small">{row.title}</td>
                      <td><input className="field" style={{ width: 64 }} aria-label={`Transfer ${i + 1} grade`} value={row.grade ?? ''} onChange={t.editTransfer(i, 'grade')} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {t.problems.length > 0 && (
            <div className="notice err" role="alert"><Icon name="alert" />
              <ul style={{ margin: 0, paddingLeft: 18, flex: '1 1 0', minWidth: 220 }}>{t.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}
          <div className="row" style={{ gap: 12 }}>
            <button type="button" className="btn" disabled={t.problems.length > 0} onClick={() => onUse(t.student)}>
              <Icon name="check" /> Use this record
            </button>
            <button type="button" className="btn2" onClick={() => t.setRead(null)}>Start over</button>
          </div>
        </section>
        )
}
