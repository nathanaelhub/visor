import { useEffect, useState } from 'react'
import { api, cleanName, gradName, hrs, termName, termsAfter } from '../lib.js'
import { Bar, Chip, Icon, Pill, Spinner } from '../ui.jsx'
import { transferStatus } from '../transferStatus.js'
import { AdjustPanel, ApprovalBanner, ApprovePanel, CourseAdjust } from './AdvisorEdits.jsx'

// My Plan (student) and an advisee's plan (advisor). Everything on this page comes from
// POST /api/audit — the planner's own output; nothing here is computed in the browser.
export default function MyPlan({ student, mode, onAsk, onBack, onTranscript, edit }) {
  const [r, setR] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let live = true
    setR(null)
    setError('')
    api('/api/audit', { method: 'POST', body: student })
      .then((d) => { if (live) setR(d) })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [student])

  const name = cleanName(student.name)
  return (
    <div className="wrap">
      {mode === 'advisor' && (
        <button type="button" className="linkbtn row small" onClick={onBack} style={{ alignSelf: 'flex-start', gap: 6 }}>
          <Icon name="left" /> All advisees
        </button>
      )}
      <div className="pagehead">
        <div style={{ flex: '1 1 420px' }}>
          <h1 className="h1">{mode === 'advisor' ? `${name}’s plan` : 'My Plan'}</h1>
          <p className="muted" style={{ margin: '6px 0 0' }}>
            {name} · {r?.program_name ?? 'B.S. Computer Science'} · Catalog {r?.catalog_year ?? '2026-27'}
            {student.student_number && <> · <span className="mono">{student.student_number}</span></>}
          </p>
        </div>
        {r && (r.needs_review ? <Pill status="review">Needs advisor review</Pill> : <Pill status="ok">Plan checks pass</Pill>)}
        {onTranscript && <button type="button" className="btn2" onClick={onTranscript}><Icon name="book" />Start from a transcript</button>}
        <button type="button" className="btn2" onClick={onAsk}><Icon name="chat" />Ask about this plan</button>
      </div>

      {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}
      {!r && !error && <p className="row muted"><Spinner /> Running the degree audit…</p>}
      {r && <Plan r={r} story={student.story} mode={mode} edit={edit} />}
    </div>
  )
}

function Plan({ r, story, mode, edit }) {
  const plan = r.plan
  const counted = r.hours_done + r.hours_in_progress
  const after = termsAfter(r.in_progress.term, r.projected_term)
  const next = plan?.terms[0]
  const retakes = r.checks?.retakes ?? []

  return (
    <>
      {story && <p className="small muted" style={{ margin: '-8px 0 0' }}><em>Demo: {story}</em></p>}
      {edit && <ApprovalBanner edit={edit} r={r} mode={mode} />}

      {r.needs_review && (
        <div className="review" role="alert">
          <strong><Icon name="alert" />Needs advisor review</strong>
          <span style={{ flex: '1 1 280px' }}>{r.warnings.map((w) => w.message).join(' · ')}</span>
        </div>
      )}

      <section className="summary" aria-label="Progress summary">
        <div className="card hours">
          <div className="row" style={{ alignItems: 'baseline', justifyContent: 'space-between' }}>
            <div className="row" style={{ alignItems: 'baseline' }}>
              <span className="serif" style={{ fontSize: 40, lineHeight: 1 }}>{hrs(counted)}</span>
              <span className="muted">of {r.hours_required} hours counted</span>
            </div>
            {r.transfer_hours > 0 && <span className="small muted">Includes {hrs(r.transfer_hours)} transfer hours</span>}
          </div>
          <Bar done={r.hours_done} prog={r.hours_in_progress} total={r.hours_required}
            label={`${r.hours_done} hours done, ${r.hours_in_progress} in progress, of ${r.hours_required}`} />
          <div className="row small muted" style={{ gap: '8px 24px' }}>
            <span className="key"><span className="sw" style={{ background: 'var(--pu)' }} />Done <strong style={{ color: 'var(--ink)' }}>{hrs(r.hours_done)} hrs</strong></span>
            <span className="key"><span className="sw" style={{ background: '#F4AA00' }} />In progress <strong style={{ color: 'var(--ink)' }}>{hrs(r.hours_in_progress)} hrs</strong></span>
            <span className="key"><span className="sw" style={{ background: 'var(--ndB)', border: '1px solid var(--ln)' }} />Required <strong style={{ color: 'var(--ink)' }}>{r.hours_required} hrs</strong></span>
          </div>
        </div>
        <div className="gradcard">
          <span className="small" style={{ color: 'var(--heroI2)' }}>Projected graduation</span>
          <span className="serif" style={{ fontSize: 34, lineHeight: 1 }}>
            {plan?.complete ? 'Requirements met' : r.projected_term ? gradName(r.projected_term) : 'Not yet known'}
          </span>
          <span className="sub"><span className="dot" />
            {plan?.complete ? 'Complete pending final grades'
              : !r.projected_term ? 'Some courses could not be placed · Needs review'
              : `${after ?? '?'} term${after === 1 ? '' : 's'} after this one · ${r.needs_review ? 'Needs review' : 'On track'}`}
          </span>
        </div>
      </section>

      {r.checks && (
        <section className="card checks" aria-label="Plan checks">
          <strong>Plan checks</strong>
          <Check ok={r.checks.prerequisites_ok} good="Prerequisites satisfied" bad="Prerequisite problem — see warnings" />
          <Check ok={r.checks.offerings_ok} good="Every course placed in a term it is offered" bad="Offering problem" />
          {retakes.length > 0
            ? <Check ok={false} bad={`${retakes.length} retake${retakes.length > 1 ? 's' : ''} required: ${retakes.join(', ')}`} />
            : <Check ok good="No retakes needed" />}
          <span className="muted">Load per term stays at or under {r.checks.load_limit} hrs</span>
        </section>
      )}

      {mode === 'advisor' && edit && <AdjustPanel edit={edit} r={r} />}
      {mode === 'advisor' && edit && <ApprovePanel edit={edit} r={r} />}

      {r.transfer.length > 0 && <TransferCredit rows={r.transfer} hours={r.transfer_hours} />}

      <div className="planlayout">
        <Requirements groups={r.groups} />
        <section aria-label="Semester plan" className="stack">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
            <h2 className="serif" style={{ fontSize: 24 }}>Semester plan</h2>
            <span className="small muted">Built by Visor’s planner from the {r.catalog_year} catalog</span>
          </div>
          <div className="terms">
            {r.in_progress.courses.length > 0 && <InProgress term={r.in_progress} />}
            {plan?.complete && <div className="card" style={{ padding: 20 }}>Every requirement is met or in progress. Nothing left to plan.</div>}
            {plan?.terms.map((t, i) => (
              <Term key={t.term} t={t} next={t === next} last={!!r.projected_term && i === plan.terms.length - 1}
                adjust={mode === 'advisor' && edit ? (code) => (
                  <CourseAdjust edit={edit} code={code} startTerm={plan.start_term}
                    includeSummer={!!r.edits?.settings?.include_summer} />) : null} />
            ))}
          </div>
          {plan?.free_elective_hours > 0 && (
            <p className="small muted" style={{ margin: 0 }}>
              Plus <strong>{hrs(plan.free_elective_hours)} hours of free electives</strong> of your choice to reach {r.hours_required} hours.
            </p>
          )}
          <p className="chipkey" style={{ margin: 0 }}>
            Chip key: <strong>Unlocks</strong> later courses depend on it · <strong>Offered</strong> only taught that term ·{' '}
            <strong>Retake</strong> grade below the minimum · <strong>Needs</strong> prerequisite placed earlier ·{' '}
            <strong>Fills</strong> the requirement it counts toward
          </p>
        </section>
      </div>
    </>
  )
}

function TransferCredit({ rows, hours }) {
  const counted = rows.filter((t) => t.counted).length
  return (
    <section className="card table-card" aria-label="Transfer credit">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', padding: '16px 16px 4px', flexWrap: 'wrap', gap: 8 }}>
        <h2 className="serif" style={{ fontSize: 24 }}>Transfer credit</h2>
        <span className="small muted">{counted} of {rows.length} course{rows.length === 1 ? '' : 's'} count · {hrs(hours)} hrs</span>
      </div>
      <table className="tbl">
        <thead><tr><th>Course</th><th className="hidem">School</th><th>Status</th><th>Why</th></tr></thead>
        <tbody>
          {rows.map((t) => {
            const st = transferStatus(t)
            return (
              <tr key={`${t.school}|${t.external}`}>
                <td><span className="mono">{t.external}</span>{t.title && <div className="small muted">{t.title}</div>}</td>
                <td className="hidem small">{(t.school ?? 'Unknown school').replace(' Community College', '')}</td>
                <td><Pill status={st.pill}>{st.label}</Pill></td>
                <td className="small">{st.why}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

function Check({ ok, good, bad }) {
  return (
    <span className="row" style={{ gap: 6 }}>
      <Icon name={ok ? 'check' : 'alert'} size={15} className={ok ? 'ok' : 'warn'} />{ok ? good : bad}
    </span>
  )
}

function Requirements({ groups }) {
  const n = (s) => groups.filter((g) => g.status === s).length
  return (
    <section className="card reqs" aria-label="Requirements">
      <header>
        <h2 className="serif" style={{ fontSize: 24 }}>Requirements</h2>
        <span className="small muted">{n('met')} met · {n('in_progress')} in progress · {n('needed')} needed</span>
      </header>
      {groups.map((g) => (
        <div className="req" key={g.id}>
          <div className="top"><span className="name">{g.name.replace(/^Core: /, '')}</span><Pill status={g.status} /></div>
          <div className="meter">
            <Bar thin status={g.status} done={g.done_hours} prog={g.counted_hours} total={g.required_hours}
              label={`${g.counted_hours} of ${g.required_hours} hours`} />
            <span>{hrs(g.counted_hours)} of {hrs(g.required_hours)} hrs</span>
          </div>
          {g.used.length > 0 ? (
            <details>
              <summary>{g.status === 'needed' ? `Still needed: ${g.remaining}` : `${g.used.length} course${g.used.length > 1 ? 's' : ''} counted`} · show</summary>
              <ul>{g.used.map((u) => (
                <li key={u.code}><span className="mono">{u.code}</span> {u.via === 'completed' ? '' : `(${u.via.replace('_', ' ')}${u.detail ? `: ${u.detail}` : ''})`}</li>
              ))}</ul>
            </details>
          ) : <span className="small muted">{g.status === 'needed' ? `Needed: ${g.remaining}` : g.remaining}</span>}
        </div>
      ))}
    </section>
  )
}

function InProgress({ term }) {
  const [open, setOpen] = useState(false)
  const total = term.courses.reduce((a, c) => a + c.credits, 0)
  return (
    <article className="card term">
      <div className="termhead">
        <h3>{termName(term.term)}</h3>
        <Pill status="in_progress" />
        <span className="small muted">{term.courses.length} courses · {hrs(total)} hrs</span>
        <span className="spacer" />
        <button type="button" className="btn2" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? 'Hide courses' : 'Show courses'}
        </button>
      </div>
      {open && term.courses.map((c) => (
        <div className="courserow" key={c.code}>
          <span className="mono">{c.code}</span><span className="title">{c.title}</span><span className="small muted">{hrs(c.credits)} hrs</span>
        </div>
      ))}
    </article>
  )
}

function reasonChips(c) {
  const order = { pinned: -2, held: -1, unlocks: 0, retake: 1, offering: 2, needs: 3, standing: 4, prerequisite: 5, requirement: 6 }
  const chips = [...c.reasons].sort((a, b) => (order[a.kind] ?? 9) - (order[b.kind] ?? 9))
  if (c.deferred_from && !c.reasons.some((x) => x.kind === 'offering')) {
    chips.push({ kind: 'deferred', text: `Not offered ${termName(c.deferred_from)}` })
  }
  return chips
}

function Term({ t, next, last, adjust }) {
  return (
    <article className={`card term${next ? ' next' : ''}`}>
      <div className="termhead">
        <h3>{t.name}</h3>
        <span className="small muted">{hrs(t.hours)} hrs · {t.courses.length} course{t.courses.length > 1 ? 's' : ''}
          {last ? ' · Graduation term' : ''}{t.light ? ' · Light term' : ''}</span>
        <span className="spacer" />
        {next && <span className="pill pill-next">Register next</span>}
      </div>
      {t.courses.map((c) => (
        <div className="courserow" key={c.code}>
          <span className="mono">{c.code}</span>
          <div>
            <span className="title">{c.title}</span>
            <span className="chips" style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 6, verticalAlign: 'middle' }}>
              {reasonChips(c).map((x, k) => <Chip key={k} kind={x.kind}>{x.text}</Chip>)}
            </span>
          </div>
          <span className="small muted" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            {hrs(c.credits)} hrs{adjust && adjust(c.code)}
          </span>
        </div>
      ))}
    </article>
  )
}
