import { useState } from 'react'
import { termName } from '../lib.js'
import { approvalState, approveBlockers, clearCourse, hold, pin, setSetting, termsFrom } from '../planEdits.js'
import { Icon } from '../ui.jsx'

// Advisor edits and approval (spec 06). The planner still builds the plan; these controls only
// change its inputs (settings, pins, holds) and record an approval of one exact plan.

const NAME = 'visor.advisorName'
const savedName = () => { try { return sessionStorage.getItem(NAME) || '' } catch { return '' } }
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '')

/** Approved / changed since approval / not yet approved, for both advisor and student. */
export function ApprovalBanner({ edit, r, mode }) {
  const a = edit?.approval
  const state = approvalState(a, r.fingerprint)
  if (state === 'current') {
    return (
      <div className="notice ok-notice" role="status">
        <Icon name="check" />
        <span style={{ flex: '1 1 0', minWidth: 220 }}>
          <strong>Approved by {a.approved_by}</strong> on {fmtDate(a.approved_at)}{a.note ? `: “${a.note}”` : ''}
          {a.local && <span className="muted"> (in this tab only; not saved in the demo)</span>}
        </span>
      </div>
    )
  }
  if (state === 'stale') {
    return (
      <div className="notice warn" role="status">
        <Icon name="alert" />
        <span style={{ flex: '1 1 0', minWidth: 220 }}>
          <strong>Plan changed since approval · needs re-approval.</strong> {a.approved_by} approved an earlier
          version on {fmtDate(a.approved_at)}.
        </span>
      </div>
    )
  }
  return mode === 'student'
    ? <p className="small muted" style={{ margin: 0 }}>Your advisor hasn’t approved this plan yet.</p>
    : null
}

/** Advisor only: approve this exact plan, or see why it can't be approved yet. */
export function ApprovePanel({ edit, r }) {
  const [name, setName] = useState(savedName)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const blockers = approveBlockers(r)
  const current = approvalState(edit.approval, r.fingerprint) === 'current'

  async function go() {
    setBusy(true); setError('')
    try { sessionStorage.setItem(NAME, name.trim()) } catch { /* storage blocked */ }
    try { await edit.approve({ fingerprint: r.fingerprint, approved_by: name.trim(), note: note.trim() }); setNote('') } catch (e) {
      setError(e.data?.reasons ? `${e.message} ${e.data.reasons.join(' · ')}` : e.message)
    } finally { setBusy(false) }
  }

  return (
    <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }} aria-label="Approve plan">
      <h2 className="serif" style={{ fontSize: 22, margin: 0 }}>{current ? 'Approved' : 'Approve this plan'}</h2>
      {blockers.length > 0 ? (
        <div className="notice err" role="note"><Icon name="alert" />
          <span style={{ flex: '1 1 0', minWidth: 220 }}>Fix these before approving: {blockers.join(' · ')}</span>
        </div>
      ) : (
        <div className="row" style={{ gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ flex: '1 1 180px' }}><span className="lbl">Your name</span>
            <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="Dr. Advisor" />
          </label>
          <label style={{ flex: '2 1 240px' }}><span className="lbl">Note to the student (optional)</span>
            <input className="field" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Agreed in our meeting" />
          </label>
          <button type="button" className="btn" disabled={busy || !name.trim()} onClick={go}>
            <Icon name="check" />{current ? 'Approve again' : 'Approve plan'}
          </button>
        </div>
      )}
      {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}
    </section>
  )
}

/** Advisor only: plan settings, the list of changes, and saving. */
export function AdjustPanel({ edit, r }) {
  const e = edit.edits
  const s = e?.settings ?? {}
  const set = (k, v) => edit.setEdits(setSetting(e, k, v))
  const num = (v) => (v === '' ? null : Number(v))
  const max = s.max_hours ?? 18
  const changes = [
    ...(e?.pins ?? []).map((p) => ({ code: p.code, text: `${p.code} pinned to ${termName(p.term)}` })),
    ...(e?.holds ?? []).map((h) => ({ code: h.code, text: `${h.code} held until ${termName(h.not_before)}` })),
  ]
  return (
    <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }} aria-label="Adjust plan">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 8 }}>
        <h2 className="serif" style={{ fontSize: 22, margin: 0 }}>Adjust plan</h2>
        <span className="small muted">The planner re-plans around your changes; the checker re-checks every one.</span>
      </div>
      <div className="row" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label className="row" style={{ gap: 8, minHeight: 46 }}>
          <input type="checkbox" checked={!!s.include_summer} onChange={(ev) => set('include_summer', ev.target.checked || null)} />
          Use summer terms
        </label>
        <label><span className="lbl">Target hours</span>
          <input className="field" type="number" min="1" max={max} style={{ width: 90 }} value={s.target_hours ?? ''} placeholder="15"
            onChange={(ev) => set('target_hours', num(ev.target.value))} />
        </label>
        <label><span className="lbl">Max hours</span>
          <input className="field" type="number" min="12" max="21" style={{ width: 90 }} value={s.max_hours ?? ''} placeholder="18"
            onChange={(ev) => set('max_hours', num(ev.target.value))} />
        </label>
        {max > 18 && (
          <label style={{ flex: '1 1 240px' }}><span className="lbl">Overload note (required above 18)</span>
            <input className="field" value={e?.overload_note ?? ''} placeholder="Why this student may take more"
              onChange={(ev) => edit.setEdits({ ...e, overload_note: ev.target.value || null })} />
          </label>
        )}
      </div>
      <div>
        <strong className="small">Advisor changes</strong>
        {changes.length === 0
          ? <p className="small muted" style={{ margin: '4px 0 0' }}>None yet. Use “Adjust” on a course in the plan to pin it to a term or hold it back.</p>
          : (
            <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
              {changes.map((c) => (
                <li key={c.code} className="small">{c.text}{' '}
                  <button type="button" className="linkbtn small" onClick={() => edit.setEdits(clearCourse(e, c.code))}>Remove</button>
                </li>
              ))}
            </ul>
          )}
        {r.edits?.overload_note && <p className="small" style={{ margin: '6px 0 0' }}>Overload approved by advisor: {r.edits.overload_note}</p>}
      </div>
      <div className="row small" style={{ gap: 12, flexWrap: 'wrap' }}>
        {edit.canSave ? (
          edit.dirty
            ? <><span>Unsaved changes.</span><button type="button" className="btn2" onClick={edit.save}>Save changes</button></>
            : <span className="muted">{edit.updatedAt ? `Saved${edit.updatedBy ? ` by ${edit.updatedBy}` : ''} on ${fmtDate(edit.updatedAt)}.` : 'No saved changes.'}</span>
        ) : <span className="muted"><Icon name="lock" size={14} /> Not saved in the demo. Changes apply in this browser tab only.</span>}
        {edit.saveError && <span role="alert" style={{ color: 'var(--rvF)' }}>{edit.saveError}</span>}
      </div>
    </section>
  )
}

/** Advisor only: the per-course "Adjust" menu in the plan (pin to a term, or hold until one). */
export function CourseAdjust({ edit, code, startTerm, includeSummer }) {
  const terms = termsFrom(startTerm, 8, includeSummer)
  const has = (edit.edits?.pins ?? []).some((p) => p.code === code) || (edit.edits?.holds ?? []).some((h) => h.code === code)
  function onChange(ev) {
    const [kind, term] = ev.target.value.split(':')
    if (kind === 'pin') edit.setEdits(pin(edit.edits, code, term))
    if (kind === 'hold') edit.setEdits(hold(edit.edits, code, term))
    if (kind === 'clear') edit.setEdits(clearCourse(edit.edits, code))
  }
  return (
    <select className="field small" style={{ minHeight: 34, width: 'auto', maxWidth: 150 }} value="" onChange={onChange} aria-label={`Adjust ${code}`}>
      <option value="" disabled>Adjust…</option>
      <optgroup label="Pin to">{terms.map((t) => <option key={`p${t}`} value={`pin:${t}`}>{termName(t)}</option>)}</optgroup>
      <optgroup label="Hold until">{terms.slice(1).map((t) => <option key={`h${t}`} value={`hold:${t}`}>{termName(t)}</option>)}</optgroup>
      {has && <option value="clear:">Remove my change</option>}
    </select>
  )
}
