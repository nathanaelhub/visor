import { useEffect, useState } from 'react'
import { api, cleanName, gradName, hrs } from '../lib.js'
import { Bar, Chip, Icon, Logo, Pill } from '../ui.jsx'

// Landing page. The example student, plan term and transfer result are live output from the API
// (a fictional demo student), so the page never shows numbers the planner didn't produce.
const EXAMPLE = 'demo-02'

export default function Landing({ onStart, dark, setDark }) {
  const [ex, setEx] = useState(null)
  const [xfer, setXfer] = useState(null)

  useEffect(() => {
    api('/api/demo/students').then((all) => {
      const s = all.find((x) => x.id === EXAMPLE)
      if (s) api('/api/audit', { method: 'POST', body: s }).then((r) => setEx({ s, r }))
    }).catch(() => {})
    api('/api/schools').then((schools) => {
      const ns = schools.find((x) => x.name.startsWith('Nashville State'))
      if (ns) api('/api/equivalencies/lookup', { method: 'POST', body: { school_id: ns.id, subject: 'CISP', number: '1020' } }).then(setXfer)
    }).catch(() => {})
  }, [])

  const r = ex?.r
  const next = r?.plan?.terms?.[0]

  return (
    <div>
      <header className="landnav">
        <div className="in">
          <span className="row" style={{ gap: 10 }}><Logo />
            <span><span className="brand-name">Visor</span><span className="brand-sub">Lipscomb University</span></span></span>
          <span className="spacer" />
          <a className="navlink hidem" href="#how">How it works</a>
          <a className="navlink hidem" href="#see">See a plan</a>
          <a className="navlink hidem" href="#trust">Ask Visor</a>
          <button type="button" className="icon" onClick={() => setDark(!dark)} aria-label={dark ? 'Light mode' : 'Dark mode'}>
            <Icon name={dark ? 'sun' : 'moon'} size={18} /></button>
          <button type="button" className="btn2" onClick={() => onStart('student')}>Open demo</button>
        </div>
      </header>

      <section className="land-hero">
        <div className="in">
          <div>
            <span className="eyebrow">Course planning and transfer advising</span>
            <h1 className="hero">Know your path to graduation, and why every course is on it.</h1>
            <p className="lead">Visor checks your record against Lipscomb’s published catalog and lays out a plan term by term,
              with a plain reason beside every course. Your advisor reviews it before you register.</p>
            <p className="small" style={{ fontWeight: 600, color: 'var(--ink2)', margin: '26px 0 10px' }}>Start as</p>
            <div className="startas">
              <button type="button" className="btn" onClick={() => onStart('student')}><Icon name="cap" />I’m a student</button>
              <button type="button" className="btn2" onClick={() => onStart('advisor')}><Icon name="advisor" />I’m an advisor</button>
              <button type="button" className="btn2" onClick={() => onStart('registrar')}><Icon name="swap" />Registrar’s office</button>
            </div>
          </div>
          <div className="card herocard" aria-label="Example plan summary">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span className="small muted">Example student · fictional</span>
                <div className="serif" style={{ fontSize: 24 }}>{ex ? cleanName(ex.s.name) : '…'}</div>
                <span className="small muted">{r ? `${r.program_name} · Catalog ${r.catalog_year}` : ''}</span>
              </div>
              {r && (r.needs_review ? <Pill status="review" /> : <Pill status="ok">Plan checks pass</Pill>)}
            </div>
            {r && (
              <>
                <div className="row" style={{ alignItems: 'baseline' }}>
                  <span className="serif" style={{ fontSize: 40, lineHeight: 1 }}>{hrs(r.hours_done + r.hours_in_progress)}</span>
                  <span className="muted">of {r.hours_required} hours</span>
                </div>
                <Bar done={r.hours_done} prog={r.hours_in_progress} total={r.hours_required} label="Progress toward the degree" />
                <div className="row small muted" style={{ gap: 6 }}>
                  <span className="key"><span className="sw" style={{ background: 'var(--pu)' }} />{hrs(r.hours_done)} done</span>
                  <span className="key"><span className="sw" style={{ background: '#F4AA00' }} />{hrs(r.hours_in_progress)} in progress</span>
                  <span className="key"><span className="sw" style={{ background: 'var(--ndB)', border: '1px solid var(--ln)' }} />
                    {hrs(r.hours_required - r.hours_done - r.hours_in_progress)} to go</span>
                </div>
                <div className="row" style={{ gap: 12, flexWrap: 'nowrap' }}>
                  <div className="minibox" style={{ flex: 1 }}><span className="small muted">Projected graduation</span><div><strong>{gradName(r.projected_term)}</strong></div></div>
                  {next && <div className="minibox" style={{ flex: 1 }}><span className="small muted">Next term</span><div><strong>{next.name} · {hrs(next.hours)} hrs</strong></div></div>}
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="section" id="how">
        <h2>How it works</h2>
        <p className="muted" style={{ maxWidth: 620 }}>The plan comes from a rules engine reading the real catalog. Same record in, same plan out, every time.</p>
        <div className="steps">
          {[['Your courses and transfer credit', 'Completed and in progress courses from your record, plus credit from other schools matched through Lipscomb’s equivalency table.'],
            ['Degree audit against the catalog', 'Every requirement group in your catalog year is checked and marked Met, In progress or Needed.'],
            ['A term by term plan with reasons', 'Courses are placed by prerequisites, when they are offered and your load, each with the reason it sits where it does.']]
            .map(([t, d], i) => (
              <div className="step" key={t}><div className="num">{i + 1}</div><h3 style={{ fontSize: 18, margin: '8px 0' }}>{t}</h3><p className="muted" style={{ margin: 0 }}>{d}</p></div>
            ))}
        </div>
      </section>

      <section style={{ background: 'var(--bg)', borderTop: '1px solid var(--ln)' }}>
        <div className="section" id="see">
          <h2>What you will see</h2>
          <p className="muted">A plan you can read in ten seconds, and transfer answers with a clear status.</p>
          <div className="see">
            {next && (
              <div className="card term" style={{ overflow: 'hidden' }}>
                <div className="termhead"><div><h3>{next.name}</h3><span className="small muted">{hrs(next.hours)} hours · {next.courses.length} courses</span></div>
                  <span className="spacer" /><span className="pill pill-next">Register next</span></div>
                {next.courses.map((c) => (
                  <div className="courserow" key={c.code}>
                    <span className="mono">{c.code}</span>
                    <div><span className="title">{c.title}</span><div className="chips" style={{ marginTop: 6 }}>
                      {c.reasons.filter((x) => x.kind !== 'requirement').slice(0, 2).concat(c.reasons.filter((x) => x.kind === 'requirement').slice(0, 1))
                        .map((x, k) => <Chip key={k} kind={x.kind}>{x.text}</Chip>)}</div></div>
                    <span className="small muted">{hrs(c.credits)} hrs</span>
                  </div>
                ))}
              </div>
            )}
            <div className="stack">
              {xfer && (
                <div className="card" style={{ padding: 22 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}><span className="small muted" style={{ fontWeight: 600 }}>Transfer lookup</span><Pill status={xfer.status} /></div>
                  <div className="row" style={{ marginTop: 14, alignItems: 'flex-start', gap: 20, flexWrap: 'nowrap' }}>
                    <div style={{ flex: 1 }}><span className="small muted">{xfer.external_course.school.replace(' Community College', ' CC')}</span>
                      <div className="mono" style={{ fontSize: 17 }}>{xfer.external_course.subject} {xfer.external_course.number}</div>
                      <span className="small muted">{xfer.external_course.title}</span></div>
                    <Icon name="right" size={22} style={{ color: '#F4AA00', marginTop: 20 }} />
                    <div style={{ flex: 1 }}><span className="small muted">Lipscomb</span>
                      <div className="mono" style={{ fontSize: 17 }}>{xfer.equivalency?.course?.code}</div>
                      <span className="small muted">{xfer.equivalency?.course?.title}</span></div>
                  </div>
                </div>
              )}
              <div className="legend3">
                {[['confirmed', 'On file. Counts now.'], ['proposed', 'A person must confirm.'], ['unknown', 'Flagged for a professor.']].map(([s, t]) => (
                  <div className="card" style={{ padding: 14 }} key={s}><Pill status={s} /><div className="small muted" style={{ marginTop: 6 }}>{t}</div></div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="trust" id="trust">
        <div className="section">
          <h2>A planner you can check</h2>
          <div className="grid">
            {[['book', 'Built on Lipscomb’s published 2026-27 catalog', 'Every rule traces back to a catalog page, and every judgment call is written down.'],
              ['advisor', 'Advisors approve every plan', 'AI never decides a plan. Ask Visor only explains it, using read-only access to the plan and catalog.'],
              ['lock', 'Demo uses fictional students only', 'No real student records appear in demo mode.']].map(([ic, t, d]) => (
              <div className="item" key={t}><span className="ic"><Icon name={ic} size={18} /></span><div><strong>{t}</strong><p className="muted" style={{ margin: '4px 0 0' }}>{d}</p></div></div>
            ))}
          </div>
        </div>
      </section>

      <footer className="foot">
        <div className="in">
          <div><span className="row" style={{ gap: 10 }}><Logo /><strong style={{ margin: 0, fontSize: 20 }}>Visor</strong></span>
            <p>Course planning and transfer advising for Lipscomb University, Nashville, TN.</p></div>
          <div><strong>Catalog source</strong>Lipscomb University Undergraduate Catalog 2026-27.<br />
            <a href="https://catalog.lipscomb.edu/" target="_blank" rel="noreferrer">View the catalog</a></div>
          <div><strong>Privacy</strong>Student records follow FERPA. A record is shown only to the student, their advisor and the registrar’s office.</div>
          <div><strong>Built on</strong>The Lunatic Labs Visor project (Software Studio), extended as a showcase.</div>
        </div>
      </footer>
    </div>
  )
}
