import { cleanName } from '../lib.js'
import { Icon, Spinner } from '../ui.jsx'
import { LiveRead, TranscriptReview, useTranscriptRead } from './TranscriptRead.jsx'

// Start from a transcript (spec 05, US-5.7). Claude reads one of the fictional transcripts into a
// course list; the person checks and edits it, and nothing runs until they press "Use this record".
// The public demo only offers the bundled fictional transcripts (no file picker).
export default function Transcript({ onUse, onCancel }) {
  const t = useTranscriptRead()
  const { demos, shared, busy, error, uploadsOpen, readDemo, readFile } = t
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
                <button type="button" className="btn" disabled={!!busy} onClick={() => readDemo(d)}>
                  {busy === d.id ? <><Spinner /> Reading…</> : 'Read it'}
                </button>
                <a className="small" href={`/api/transcript/demos/${d.id}/file`} target="_blank" rel="noreferrer">{d.kind === 'image' ? 'View scan' : 'View PDF'}</a>
              </div>
            </div>
          ))}
        </div>
      </section>

      {uploadsOpen && (
        <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 8 }} aria-label="Upload a transcript">
          <h2 style={{ margin: 0, fontSize: 18 }}>Or upload one (local and staff deployments only)</h2>
          <p className="small muted" style={{ margin: 0 }}>PDF, PNG or JPG, up to 5 MB and 6 pages. Use fictional transcripts unless IT has signed off.</p>
          <input type="file" accept="application/pdf,image/png,image/jpeg" disabled={!!busy}
            aria-label="Transcript file" onChange={(e) => readFile(e.target.files?.[0])} />
        </section>
      )}

      {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}

      <LiveRead t={t} />

      <TranscriptReview t={t} onUse={onUse} />
    </div>
  )
}
