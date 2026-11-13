import { useEffect, useState } from 'react'
import { SignInButton, UserButton, useAuth } from '@clerk/react'
import { api, cleanName } from '../lib.js'
import { setTokenGetter } from '../session.js'
import { Icon, Spinner } from '../ui.jsx'

// Sign-in, the header account area and the admin page (spec 08). Only rendered when a Clerk key is
// configured. The server decides every role from the verified session; nothing here grants anything.

const ROLE_LABEL = { student: 'Student', advisor: 'Advisor', registrar: 'Registrar', admin: 'Admin' }

/** Hands Clerk's token to the API helper and loads /api/me whenever the session changes. */
export function AuthBridge({ onAccount }) {
  const { isLoaded, isSignedIn, userId, getToken } = useAuth()
  useEffect(() => {
    if (!isLoaded) return
    setTokenGetter(isSignedIn ? () => getToken() : null)
    if (!isSignedIn) { onAccount(null); return }
    api('/api/me').then(onAccount).catch(() => onAccount(null))
  }, [isLoaded, isSignedIn, userId]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

export function AccountButton({ account, onAdmin, onLog }) {
  const { isSignedIn } = useAuth()
  if (!isSignedIn) {
    return <SignInButton mode="modal"><button type="button" className="btn2" style={{ minHeight: 38 }}>Sign in</button></SignInButton>
  }
  return (
    <span className="row account" style={{ gap: 8, flexWrap: 'nowrap' }}>
      {account && account.role !== 'admin' && <span className="pill pill-ok hidem" title={account.email ?? ''}>{ROLE_LABEL[account.role] ?? account.role}</span>}
      {(account?.role === 'admin' || account?.role === 'advisor') && (
        <button type="button" className="btn2" style={{ minHeight: 38 }} onClick={onLog} aria-label="Conversations">
          <span className="admin-label">Conversations</span><span className="admin-icon" aria-hidden="true">💬</span>
        </button>
      )}
      {account?.role === 'admin' && (
        <button type="button" className="btn2" style={{ minHeight: 38 }} onClick={onAdmin} aria-label="Admin">
          <span className="admin-label">Admin</span><span className="admin-icon" aria-hidden="true">⚙</span>
        </button>
      )}
      <UserButton />
    </span>
  )
}

/** Admins set roles and advisees (spec 08, US-8.2). */
export function Admin({ onBack }) {
  const [users, setUsers] = useState(null)
  const [students, setStudents] = useState([])
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  const load = () => api('/api/admin/users').then(setUsers).catch((e) => setError(e.message))
  useEffect(() => {
    load()
    api('/api/demo/students').then(setStudents).catch(() => setStudents([]))
  }, [])

  async function setRole(u, role) {
    setError(''); setSaved('')
    try { await api(`/api/admin/users/${u.id}`, { method: 'PUT', body: { role } }); setSaved(`${u.name} is now ${ROLE_LABEL[role]}.`); load() } catch (e) { setError(e.message) }
  }
  async function toggleAdvisee(u, key) {
    const next = u.advisees.includes(key) ? u.advisees.filter((k) => k !== key) : [...u.advisees, key]
    setError(''); setSaved('')
    try { await api(`/api/admin/users/${u.id}/advisees`, { method: 'PUT', body: { advisees: next } }); load() } catch (e) { setError(e.message) }
  }

  return (
    <div className="wrap">
      <button type="button" className="linkbtn row small" onClick={onBack} style={{ alignSelf: 'flex-start', gap: 6 }}>
        <Icon name="left" /> Back
      </button>
      <div>
        <h1 className="h1">People and roles</h1>
        <p className="muted" style={{ margin: '6px 0 0' }}>Everyone who has signed in. New people start as students; advisors can edit and approve plans for their advisees only.</p>
      </div>
      {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}
      {saved && <div className="notice ok-notice" role="status"><Icon name="check" />{saved}</div>}
      {!users && !error && <p className="row muted"><Spinner /> Loading…</p>}
      {users && (
        <div className="card table-card">
          <table className="tbl">
            <thead><tr><th>Person</th><th>Role</th><th>Advisees</th><th className="hidem">Last change</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td><strong>{u.name}</strong><div className="small muted">{u.email}</div></td>
                  <td>
                    <select className="field" style={{ minHeight: 36, width: 'auto' }} value={u.role} aria-label={`Role for ${u.name}`}
                      onChange={(e) => setRole(u, e.target.value)}>
                      {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  </td>
                  <td>
                    {u.role === 'advisor' ? (
                      <details>
                        <summary className="small">{u.advisees.length} advisee{u.advisees.length === 1 ? '' : 's'}</summary>
                        <div className="stack" style={{ gap: 4, marginTop: 6 }}>
                          {students.filter((s) => s.student_number).map((s) => (
                            <label key={s.id} className="row small" style={{ gap: 6 }}>
                              <input type="checkbox" checked={u.advisees.includes(s.student_number)} onChange={() => toggleAdvisee(u, s.student_number)} />
                              {cleanName(s.name)} <span className="mono muted">{s.student_number}</span>
                            </label>
                          ))}
                        </div>
                      </details>
                    ) : <span className="small muted">—</span>}
                  </td>
                  <td className="hidem small muted">{u.role_set_by ? `${u.role_set_by}, ${new Date(u.role_set_at).toLocaleDateString()}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** Advisors and admins check what Ask Visor said (spec 09, US-9.2). Opening someone else's
 *  conversation is recorded, and the hash chain shows whether the log is intact. */
export function Conversations({ onBack }) {
  const [rows, setRows] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api('/api/admin/conversations').then(setRows).catch((e) => setError(e.message)) }, [])
  const show = (id) => api(`/api/chats/${id}`).then(setOpen).catch((e) => setError(e.message))

  return (
    <div className="wrap">
      <button type="button" className="linkbtn row small" onClick={open ? () => setOpen(null) : onBack} style={{ alignSelf: 'flex-start', gap: 6 }}>
        <Icon name="left" /> {open ? 'All conversations' : 'Back'}
      </button>
      <div>
        <h1 className="h1">{open ? `Conversation with ${open.user}` : 'Conversations'}</h1>
        <p className="muted" style={{ margin: '6px 0 0' }}>
          Saved Ask Visor conversations of signed-in people, kept one year. Advisors see their advisees only. Opening one is recorded.
        </p>
      </div>
      {error && <div className="notice err" role="alert"><Icon name="alert" />{error}</div>}
      {!rows && !error && <p className="row muted"><Spinner /> Loading…</p>}
      {rows && !open && (
        <div className="card table-card">
          <table className="tbl">
            <thead><tr><th>Person</th><th>About</th><th>First question</th><th className="hidem">Last message</th></tr></thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={4} className="muted">No saved conversations yet.</td></tr>}
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>{c.user}</td>
                  <td className="small">{c.student_name ? cleanName(c.student_name) : '—'}{c.student_key && <div className="mono muted">{c.student_key}</div>}</td>
                  <td><button type="button" className="linkbtn" onClick={() => show(c.id)}>{c.first_question || '(empty)'}</button></td>
                  <td className="hidem small muted">{new Date(c.last_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && (
        <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }} aria-label="Conversation">
          <div className={`notice ${open.verified ? 'ok-notice' : 'err'}`} role="status">
            <Icon name={open.verified ? 'check' : 'alert'} />
            {open.verified ? 'Log verified: every message is as it was saved.' : `Log broken at message ${open.broken_at}: something was changed or removed.`}
          </div>
          <p className="small muted" style={{ margin: 0 }}>
            About {open.student_name ? cleanName(open.student_name) : 'no student record'} · model {open.model} · started {new Date(open.started_at).toLocaleString()}
          </p>
          {open.messages.map((m) => (
            <div key={m.seq} className={m.role === 'user' ? 'ubub' : 'card'} style={m.role === 'user' ? {} : { padding: 12 }}>
              {m.role === 'assistant' && m.tools.length > 0 && (
                <ul className="small muted" style={{ margin: '0 0 6px', paddingLeft: 18 }}>
                  {m.tools.map((t, i) => <li key={i}><span className="mono">{t.tool}</span> · {t.summary}</li>)}
                </ul>
              )}
              <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
              <div className="small muted" style={{ marginTop: 4 }}>{new Date(m.created_at).toLocaleString()}</div>
            </div>
          ))}
          <p className="small muted" style={{ margin: 0 }}>
            Read by: {open.read_by.length ? open.read_by.map((r) => `${r.reader} (${new Date(r.at).toLocaleString()})`).join(', ') : 'nobody else yet'}
          </p>
        </section>
      )}
    </div>
  )
}
