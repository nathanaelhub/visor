import { useCallback, useEffect, useRef, useState } from 'react'
import { api, cleanName, gradName, hrs, keyStore } from '../lib.js'
import Markdown from '../Markdown.jsx'
import { Icon, Logo, Pill, Spinner } from '../ui.jsx'
import { LiveRead, TranscriptReview, useTranscriptRead } from './TranscriptRead.jsx'
import { fromSaved, savedNotice } from '../chatHistory.js'

// Ask Visor: Claude, with the user's own Anthropic key, answering from Visor's planner, catalog and
// equivalency table (POST /api/chat). The key lives in sessionStorage and goes only to Visor's
// server, per request; the server never stores it.

export function useChat(student) {
  const [config, setConfig] = useState(null)
  const [key, setKey] = useState(keyStore.get())
  const [model, setModel] = useState(keyStore.model() || 'opus')
  const [status, setStatus] = useState(keyStore.get() ? 'on' : 'off') // off | checking | on | invalid
  const [statusMsg, setStatusMsg] = useState('')
  const [msgs, setMsgs] = useState([])
  const [pending, setPending] = useState(false)
  const [conversationId, setConversationId] = useState(null) // saved chats, signed in only (spec 09)
  const studentId = student?.id

  useEffect(() => {
    api('/api/chat/config').then((c) => {
      setConfig(c)
      if (c.shared_key) setStatus('on')
      if (!keyStore.model()) setModel(c.default_model)
    }).catch(() => setConfig({ shared_key: false, models: [], default_model: 'opus' }))
  }, [])

  const pendingNote = useRef(null) // shown first in the conversation that starts after a switch (US-7.6)
  useEffect(() => { // a new student is a new conversation
    setMsgs(pendingNote.current ? [{ role: 'note', text: pendingNote.current }] : [])
    setConversationId(null)
    pendingNote.current = null
  }, [studentId])

  const headers = useCallback(() => (key && !config?.shared_key ? { 'X-Anthropic-Key': key } : {}), [key, config])

  async function connect(newKey, newModel) {
    setStatus('checking'); setStatusMsg('')
    try {
      await api('/api/chat/verify', { method: 'POST', body: { model: newModel }, headers: { 'X-Anthropic-Key': newKey } })
      keyStore.set(newKey); keyStore.setModel(newModel)
      setKey(newKey); setModel(newModel); setStatus('on')
    } catch (e) {
      setStatus('invalid')
      setStatusMsg(e.code === 'invalid_key' ? 'That key was not accepted. Check it and try again.'
        : e.code === 'rate_limited' ? 'Anthropic is rate limiting this key right now. Try again shortly.'
          : e.message)
    }
  }

  function disconnect() {
    keyStore.clear(); setKey(''); setStatus('off'); setMsgs([]); setStatusMsg('')
  }

  async function send(text, history = msgs) {
    const q = text.trim()
    if (!q || pending) return
    const next = [...history.filter((m) => m.role !== 'notice'), { role: 'user', text: q }]
    setMsgs(next)
    setPending(true)
    try {
      const transcript = next.filter((m) => m.role === 'user' || m.role === 'bot')
        .map((m) => (m.role === 'user' ? { role: 'user', text: m.text } : { role: 'assistant', text: m.answer }))
      const r = await api('/api/chat', { method: 'POST', headers: headers(),
        body: { model, messages: transcript, student, conversation_id: conversationId } })
      if (r.conversation_id) setConversationId(r.conversation_id)
      setMsgs([...next, { role: 'bot', ...r }])
    } catch (e) {
      if (e.code === 'invalid_key' || e.code === 'no_key') { setStatus('invalid'); setStatusMsg(e.message) }
      const kind = e.code === 'rate_limited' ? 'rate' : e.code === 'visitor_limit' || e.code === 'site_limit' ? 'limit'
        : e.status === 503 ? 'down' : 'error'
      setMsgs([...next, { role: 'notice', kind,
        message: e.message, retryAfter: e.data?.retry_after }])
    } finally { setPending(false) }
  }

  function retry() {
    const lastUser = [...msgs].reverse().find((m) => m.role === 'user')
    if (lastUser) send(lastUser.text, msgs.slice(0, msgs.lastIndexOf(lastUser)))
  }

  const modelLabel = config?.models.find((m) => m.key === model)?.label ?? model
  return { config, key, model, setModel, status, statusMsg, msgs, pending, connect, disconnect, send, retry,
    newChat: () => { setMsgs([]); setConversationId(null) }, modelLabel, shared: !!config?.shared_key,
    conversationId,
    load: async (id) => { // reopen a saved conversation and keep going in it (spec 09)
      const c = await api(`/api/chats/${id}`)
      setMsgs(fromSaved(c.messages)); setConversationId(c.id)
    },
    announce: (text) => { pendingNote.current = text } }
}

const SUGGEST = {
  student: ['Which requirements am I still missing?', 'What should I register for next term, and why?',
    'What happens if I fail Data Structures?', 'Can you move Operating Systems to next fall?'],
  advisor: ['Why does this plan need review?', 'Which courses in this plan are offered only once a year?',
    'What does this student’s transfer credit count as?'],
  registrar: ['What does CISP 1020 at Nashville State count as?', 'Is CSCI 1020 at Columbia State confirmed?',
    'What are the prerequisites for CS 3633?'],
}

export default function AskVisor({ chat, student, role, mode, onClose, onOpenPlan, onUseRecord, account }) {
  const connected = chat.status === 'on' || chat.shared
  if (mode === 'drawer') {
    return (
      <aside className="chat chat-drawer" aria-label="Ask Visor">
        {connected ? <Chat chat={chat} student={student} role={role} onClose={onClose} onUseRecord={onUseRecord} account={account} />
          : <div style={{ overflowY: 'auto', padding: 20 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <h2 className="serif" style={{ fontSize: 22 }}>Ask Visor</h2>
                <button type="button" className="icon" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
              </div>
              <ConnectForm chat={chat} compact />
            </div>}
      </aside>
    )
  }
  if (!connected) {
    return (
      <div className="connect">
        <div className="card"><ConnectForm chat={chat} /></div>
        <CanDo />
      </div>
    )
  }
  return (
    <div className="asklayout">
      <div className="chat chat-full"><Chat chat={chat} student={student} role={role} onUseRecord={onUseRecord} account={account} /></div>
      <ContextPanel chat={chat} student={student} role={role} onOpenPlan={onOpenPlan} />
    </div>
  )
}

function ConnectForm({ chat, compact }) {
  const [k, setK] = useState('')
  const [show, setShow] = useState(false)
  const [m, setM] = useState(chat.model)
  const checking = chat.status === 'checking'
  return (
    <form className="stack" style={{ gap: 18 }} onSubmit={(e) => { e.preventDefault(); chat.connect(k.trim(), m) }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 className={compact ? 'serif' : 'h1'} style={{ fontSize: compact ? 19 : 30 }}>Connect your Anthropic API key</h2>
          <p className="muted" style={{ margin: '4px 0 0' }}>Ask Visor uses your own key to answer questions about your plan.</p>
        </div>
        <Pill status={chat.status === 'invalid' ? 'error' : 'unknown'}>{chat.status === 'invalid' ? 'Key rejected' : 'Not connected'}</Pill>
      </div>
      <div>
        <label className="lbl" htmlFor="apikey">API key</label>
        <div className="keyfield">
          <input id="apikey" className="field" type={show ? 'text' : 'password'} autoComplete="off" spellCheck={false}
            placeholder="sk-ant-…" value={k} onChange={(e) => setK(e.target.value)}
            aria-invalid={chat.status === 'invalid'} aria-describedby="keyhelp" />
          <button type="button" className="icon" onClick={() => setShow(!show)} aria-label={show ? 'Hide key' : 'Show key'}>
            <Icon name={show ? 'eyeoff' : 'eye'} />
          </button>
        </div>
        <p id="keyhelp" className="small muted" style={{ margin: '6px 0 0' }}>
          {chat.status === 'invalid' ? <span style={{ color: 'var(--erF)' }}>{chat.statusMsg}</span>
            : <>Starts with sk-ant-. <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">Where do I get a key?</a></>}
        </p>
      </div>
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="lbl">Model</legend>
        <div className="models" style={compact ? { gridTemplateColumns: '1fr' } : undefined}>
          {(chat.config?.models ?? []).map((x) => (
            <label key={x.key} className="model">
              <input type="radio" name="model" value={x.key} checked={m === x.key} onChange={() => setM(x.key)} />
              <span><strong>{x.label}</strong><br /><span className="small muted">{x.blurb}{x.key === chat.config.default_model ? ' · Default' : ''}</span></span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="secnote"><Icon name="lock" size={18} />
        <span>Your key stays in this browser session and is sent only to Visor’s server to relay your request. It is never stored or shown again.</span></div>
      <div className="row">
        <button className="btn" type="submit" disabled={!/^sk-ant-\S{10,}$/.test(k.trim()) || checking}>
          {checking && <Spinner />}{checking ? 'Checking key…' : 'Connect'}</button>
        <span className="small muted">Usage is billed to your Anthropic account.</span>
      </div>
    </form>
  )
}

function CanDo() {
  return (
    <aside className="can">
      <h2 className="serif" style={{ fontSize: 22 }}>What Ask Visor can do</h2>
      {[['plan', 'Explain why a course sits in a given term'], ['swap', 'Look up what transfer credit counts as'],
        ['fills', 'Run your degree audit and show what is left']].map(([ic, t]) => (
        <div className="item" key={t}><span className="ic"><Icon name={ic} /></span><span>{t}</span></div>
      ))}
      <div className="card" style={{ padding: 16, fontSize: 14 }} >It cannot change your plan. Only your advisor can.</div>
    </aside>
  )
}

function ContextPanel({ chat, student, role, onOpenPlan }) {
  const [r, setR] = useState(null)
  useEffect(() => {
    setR(null)
    if (student) api('/api/audit', { method: 'POST', body: student }).then(setR).catch(() => {})
  }, [student])
  const next = r?.plan?.terms?.[0]
  return (
    <aside className="stack hidem" style={{ gap: 12 }}>
      <div className="card ctxcard">
        <span className="lbl2">In context</span>
        {!student ? <p className="small muted" style={{ margin: 0 }}>{role === 'registrar'
          ? 'No student selected. Ask about transfer courses and the catalog.' : 'Open a student’s plan to ask about it.'}</p> : (
          <>
            <div>
              <div className="serif" style={{ fontSize: 19 }}>{cleanName(student.name)}’s plan</div>
              {r && <div className="small muted">{hrs(r.hours_done + r.hours_in_progress)} of {r.hours_required} hrs · Graduation {gradName(r.projected_term)}</div>}
            </div>
            {next && (
              <>
                <div className="row" style={{ justifyContent: 'space-between', borderTop: '1px solid var(--ln)', paddingTop: 12 }}>
                  <strong>{next.name}</strong><span className="pill pill-next">Register next</span>
                </div>
                {next.courses.map((c) => <div className="ctxrow" key={c.code}><span className="mono">{c.code}</span><span>{c.title}</span></div>)}
              </>
            )}
            {onOpenPlan && <button type="button" className="btn2" onClick={onOpenPlan}>Open {role === 'student' ? 'My Plan' : 'Students'}</button>}
          </>
        )}
      </div>
      <p className="small muted" style={{ margin: 0 }}>Answers use the plan, the 2026-27 catalog and the equivalency table.
        {chat.shared ? ' Ask Visor only answers planning questions, with a limit per hour and per day.' : ' Your key is held for this session only.'}</p>
    </aside>
  )
}

function Chat({ chat, student, role, onClose, onUseRecord, account }) {
  const [history, setHistory] = useState(null) // the History list, when open
  const [input, setInput] = useState('')
  const [attach, setAttach] = useState(false) // the 📎 panel: read a transcript into the chat (US-7.6)
  const bodyRef = useRef(null)
  useEffect(() => { bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' }) }, [chat.msgs, chat.pending])

  const submit = (t) => { chat.send(t); setInput('') }
  return (
    <>
      <div className="chat-head">
        <h2>Ask Visor</h2>
        {chat.shared
          ? <label className="row small" style={{ gap: 6 }}><span className="muted">Model</span>
              <select className="field" style={{ minHeight: 36, padding: '4px 8px', width: 'auto' }} value={chat.model}
                onChange={(e) => { keyStore.setModel(e.target.value); chat.setModel(e.target.value) }}>
                {(chat.config?.models ?? []).map((x) => (
                  <option key={x.key} value={x.key}>{x.label.replace('Claude ', '')} · {x.blurb}{x.units ? ` · ${x.units} unit${x.units > 1 ? 's' : ''}` : ''}</option>
                ))}
              </select></label>
          : <Pill status="ok">{`Connected · ${chat.modelLabel}`}</Pill>}
        <span className="spacer" />
        {account && (
          <button type="button" className="btn2" style={{ minHeight: 38 }} aria-expanded={!!history}
            onClick={() => (history ? setHistory(null) : api('/api/chats').then(setHistory).catch(() => setHistory([])))}>History</button>
        )}
        <button type="button" className="btn2" style={{ minHeight: 38 }} onClick={chat.newChat}>New chat</button>
        {!chat.shared && <button type="button" className="btn2" style={{ minHeight: 38 }} onClick={chat.disconnect}>Disconnect</button>}
        {onClose && <button type="button" className="icon" onClick={onClose} aria-label="Close"><Icon name="close" /></button>}
      </div>

      {history && (
        <div className="attach card" style={{ margin: '8px 16px 0' }} aria-label="Saved conversations">
          <strong>Your saved conversations</strong>
          {history.length === 0 ? <p className="small muted" style={{ margin: 0 }}>None yet.</p> : (
            <ul className="live-rows">
              {history.map((c) => (
                <li key={c.id}><button type="button" className="linkbtn" onClick={() => { chat.load(c.id); setHistory(null) }}>{c.first_question || '(empty)'}</button>
                  <span className="small muted"> · {c.student_name ? cleanName(c.student_name) : 'no student'} · {new Date(c.last_at).toLocaleDateString()}</span></li>
              ))}
            </ul>
          )}
        </div>
      )}
      <div className="chat-body" ref={bodyRef} aria-live="polite">
        {chat.msgs.length === 0 && (
          <div className="stack" style={{ margin: 'auto 0', gap: 12 }}>
            <div className="row"><Logo size={34} /><div>
              <strong>Ask about {student ? `${cleanName(student.name)}’s plan` : 'a course or transfer credit'}</strong>
              <div className="small muted">Answers come from Visor’s planner, the catalog and the equivalency table.</div></div></div>
            {SUGGEST[role].map((s) => <button key={s} type="button" className="sug" style={{ alignSelf: 'flex-start' }} onClick={() => submit(s)}>{s}</button>)}
          </div>
        )}
        {chat.msgs.map((m, i) => (
          m.role === 'note' ? <p key={i} className="chat-note small muted"><Icon name="book" size={14} /> {m.text}</p>
            : m.role === 'user' ? <div key={i} className="ubub">{m.text}</div>
            : m.role === 'bot' ? <BotMessage key={i} m={m} />
              : <Notice key={i} m={m} onRetry={chat.retry} />
        ))}
        {chat.pending && (
          <div className="bot"><span className="botmark"><Logo size={22} /></span>
            <div className="row muted small"><span className="typing"><span /><span /><span /></span>Checking your plan and the catalog…</div></div>
        )}
      </div>

      <div className="chat-foot">
        {chat.msgs.length > 0 && (
          <div className="row" style={{ gap: 8 }}>
            {SUGGEST[role].slice(0, 2).map((s) => <button key={s} type="button" className="sug" onClick={() => submit(s)} disabled={chat.pending}>{s}</button>)}
          </div>
        )}
        {attach && onUseRecord && (
          <AttachTranscript onClose={() => setAttach(false)} onUse={(rec) => {
            chat.announce(`Using ${cleanName(rec.name).replace(' (from transcript)', '')}’s transcript. Ask anything about it.`)
            onUseRecord(rec)
            setAttach(false)
          }} />
        )}
        <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(input) }}>
          {onUseRecord && (
            <button type="button" className="attachbtn" aria-label="Start from a transcript" aria-expanded={attach}
              title="Start from a transcript" onClick={() => setAttach(!attach)}>📎</button>
          )}
          <label className="sr" htmlFor="ask">Ask Visor</label>
          <textarea id="ask" rows={1} maxLength={1000} value={input} placeholder="Ask about your plan, a course or transfer credit"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(input) } }} />
          <button type="submit" className="sendbtn" disabled={!input.trim() || chat.pending} aria-label="Send"><Icon name="send" size={18} /></button>
        </form>
        <p className="legal" style={{ margin: 0 }}>Visor’s planner decides the plan; Ask Visor explains it. Check with your advisor before registering.
          {' '}<span>{savedNotice(account)}</span></p>
      </div>
    </>
  )
}

const DETAIL_FIELDS = {
  transfer_lookup: [['School', 'school'], ['Their course', (r) => `${r.external}${r.title ? ` · ${r.title}` : ''}`],
    ['Lipscomb course', (r) => r.counts_as ? `${r.counts_as}${r.counts_as_title ? ` · ${r.counts_as_title}` : ''}` : '—'],
    ['Status', 'status'], ['Note', 'note']],
  course_info: [['Course', (r) => `${r.code} · ${r.title} · ${r.credits} hrs`], ['Offered', 'offered'],
    ['Prerequisites', (r) => r.prerequisites?.map((p) => p.any_of.join(' or ') + (p.min_grade ? ` (${p.min_grade}+)` : '')).join('; ') || 'None'],
    ['Fills', (r) => r.fills?.map((f) => f.name).join(', ') || '—'], ['In this plan', (r) => r.in_this_plan?.term ?? '—']],
  run_degree_audit: [['Projected graduation', 'projected_graduation'],
    ['Hours', (r) => `${r.hours?.done} done · ${r.hours?.in_progress} in progress · ${r.hours?.required} required`],
    ['Still needed', (r) => r.requirements?.filter((g) => g.status === 'needed').map((g) => g.name).join(', ') || 'Nothing'],
    ['Warnings', (r) => r.warnings?.join('; ') || 'None']],
}

function ToolCard({ c }) {
  const [open, setOpen] = useState(false)
  const fields = DETAIL_FIELDS[c.tool] ?? []
  const val = (f) => (typeof f === 'function' ? f(c.result) : c.result?.[f]) ?? '—'
  return (
    <div className="tool">
      <button type="button" className="toolbtn" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name={c.tool === 'transfer_lookup' ? 'search' : c.tool === 'course_info' ? 'book' : 'fills'} />
        <span style={{ flex: 1 }}>{c.summary}</span>
        {['confirmed', 'proposed', 'unknown', 'review', 'error'].includes(c.status) && <Pill status={c.status} />}
        <Icon name={open ? 'up' : 'down'} />
      </button>
      {open && (
        <div className="tooldetail">
          <table className="tbl" style={{ fontSize: 13 }}>
            <tbody>
              <tr><th style={{ width: 150 }}>Tool</th><td className="mono">{c.tool}</td></tr>
              {c.result?.error ? <tr><th>Result</th><td>{c.result.error}</td></tr>
                : c.result == null ? <tr><th>Asked</th><td className="mono">{JSON.stringify(c.input ?? {})} (saved chat: summary only)</td></tr>
                  : fields.map(([label, f]) => <tr key={label}><th>{label}</th><td>{String(val(f))}</td></tr>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function BotMessage({ m }) {
  const declined = /^I can['’]t edit your plan/i.test(m.answer || '')
  const answer = declined ? m.answer.replace(/^I can['’]t edit your plan\.?\s*Ask your advisor\.?\s*/i, '') : m.answer
  return (
    <div className="bot">
      <span className="botmark"><Logo size={22} /></span>
      <div className="botbody">
        {m.tool_calls?.map((c, i) => <ToolCard key={i} c={c} />)}
        {declined && (
          <div className="locknote"><Icon name="lock" size={18} />
            <span><strong>I can’t edit your plan. Ask your advisor.</strong> Only Visor’s planner and your advisor can change where a course sits.</span></div>
        )}
        <Markdown text={answer} />
        {m.sources?.length > 0 && (
          <div className="row small" style={{ gap: 8 }}>
            <span className="muted">Sources</span>
            {m.sources.map((s) => <span className="src" key={s}><Icon name={s.startsWith('Catalog') ? 'book' : s.startsWith('Equivalency') ? 'table' : 'plan'} size={13} />{s}</span>)}
          </div>
        )}
        {m.truncated && <span className="small muted">The answer was cut short. Ask a narrower question for the rest.</span>}
      </div>
    </div>
  )
}

function Notice({ m, onRetry }) {
  const text = {
    rate: `Anthropic is rate limiting this key.${m.retryAfter ? ` Try again in about ${m.retryAfter} seconds.` : ''}`,
    limit: m.message,
    down: 'Anthropic’s API didn’t respond. Your question wasn’t lost.',
    error: m.message,
  }[m.kind]
  return (
    <div className={`notice ${m.kind === 'error' ? 'err' : 'warn'}`} role="alert">
      <Icon name="alert" size={18} />
      <span style={{ flex: '1 1 200px' }}>{text}</span>
      <button type="button" className="btn2" style={{ minHeight: 38 }} onClick={onRetry}>Try again</button>
    </div>
  )
}

// The 📎 panel (spec 07, US-7.6): same transcripts and the same check-before-use review as the
// "Start from a transcript" page. The chat switches to the record only after "Use this record".
function AttachTranscript({ onUse, onClose }) {
  const t = useTranscriptRead()
  return (
    <section className="attach card" aria-label="Start from a transcript">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
        <strong>Start from a transcript</strong>
        <button type="button" className="icon" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
      </div>
      {!t.read && !t.busy && (
        <>
          <p className="small muted" style={{ margin: 0 }}>Demo: fictional transcripts only. Claude reads it; you check it before the chat uses it.
            {t.shared ? ' Each read uses 4 units of your allowance.' : ''}</p>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            {t.demos.map((d) => (
              <button key={d.id} type="button" className="sug" onClick={() => t.readDemo(d)}>{cleanName(d.name)}</button>
            ))}
          </div>
          {t.uploadsOpen && (
            <label className="small">Or upload one (PDF, PNG or JPG):{' '}
              <input type="file" accept="application/pdf,image/png,image/jpeg" aria-label="Transcript file"
                onChange={(e) => t.readFile(e.target.files?.[0])} /></label>
          )}
        </>
      )}
      {t.error && <div className="notice err" role="alert"><Icon name="alert" />{t.error}</div>}
      <LiveRead t={t} />
      <TranscriptReview t={t} onUse={onUse} />
    </section>
  )
}
