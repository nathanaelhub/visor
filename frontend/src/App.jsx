import { useEffect, useState } from 'react'
import { api, cleanName, initials } from './lib.js'
import { Icon, Logo } from './ui.jsx'
import Landing from './views/Landing.jsx'
import MyPlan from './views/MyPlan.jsx'
import Students from './views/Students.jsx'
import Transfer from './views/Transfer.jsx'
import AskVisor, { useChat } from './views/AskVisor.jsx'

// Only the tabs each role needs (design brief): schedule and prerequisite checks live inside My Plan.
const ROLE_TABS = { student: ['myplan', 'ask'], advisor: ['students', 'transfer', 'ask'], registrar: ['transfer', 'ask'] }
const TAB = {
  myplan: { label: 'My Plan', icon: 'plan' },
  students: { label: 'Students', icon: 'users' },
  transfer: { label: 'Transfer', icon: 'swap' },
  ask: { label: 'Ask Visor', icon: 'chat' },
}
const ROLE_LABEL = { student: 'Student', advisor: 'Advisor', registrar: 'Registrar' }
const DEFAULT_STUDENT = 'demo-02'

function useTheme() {
  const [dark, setDark] = useState(() => {
    try {
      const saved = localStorage.getItem('visor.theme')
      if (saved) return saved === 'dark'
    } catch { /* storage blocked */ }
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  })
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    try { localStorage.setItem('visor.theme', dark ? 'dark' : 'light') } catch { /* storage blocked */ }
  }, [dark])
  return [dark, setDark]
}

export default function App() {
  const [view, setView] = useState('landing')
  const [role, setRole] = useState('student')
  const [tab, setTab] = useState('myplan')
  const [dark, setDark] = useTheme()
  const [students, setStudents] = useState([])
  const [loadError, setLoadError] = useState('')
  const [me, setMe] = useState(DEFAULT_STUDENT)
  const [opened, setOpened] = useState(null) // advisor: student id whose plan is open
  const [drawer, setDrawer] = useState(false)

  useEffect(() => {
    api('/api/demo/students').then(setStudents)
      .catch(() => setLoadError('Could not reach the Visor API. Start the backend and seed the demo data.'))
  }, [])

  const contextStudent = students.find((s) => s.id === (role === 'student' ? me : opened)) || null
  const chat = useChat(contextStudent)

  function go(r, t) {
    setRole(r)
    setTab(t ?? ROLE_TABS[r][0])
    setOpened(null)
    setDrawer(false)
    setView('app')
    window.scrollTo(0, 0)
  }

  if (view === 'landing') {
    return <Landing onStart={go} dark={dark} setDark={setDark} />
  }

  const tabs = ROLE_TABS[role]
  const who = role === 'student' ? students.find((s) => s.id === me) : null
  const avatar = role === 'student' ? initials(who?.name) : role === 'advisor' ? 'RA' : 'RO'

  let body
  if (tab === 'ask') {
    body = <AskVisor chat={chat} student={contextStudent} role={role} mode="full" onOpenPlan={() => setTab(role === 'student' ? 'myplan' : 'students')} />
  } else if (tab === 'myplan' && who) {
    body = <MyPlan student={who} mode="student" onAsk={() => setDrawer(true)} />
  } else if (tab === 'students') {
    const s = students.find((x) => x.id === opened)
    body = s
      ? <MyPlan student={s} mode="advisor" onBack={() => setOpened(null)} onAsk={() => setDrawer(true)} />
      : <Students onOpen={setOpened} />
  } else if (tab === 'transfer') {
    body = <Transfer />
  } else {
    body = <div className="wrap"><p className="muted">{loadError || 'Loading…'}</p></div>
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-in">
          <button type="button" className="brand" onClick={() => setView('landing')} aria-label="Visor home">
            <Logo /><span className="brand-name">Visor</span>
          </button>
          <nav className="tabs" aria-label="Main">
            {tabs.map((t) => (
              <button key={t} type="button" className="tab" aria-current={tab === t ? 'page' : undefined}
                onClick={() => { setTab(t); setOpened(null) }}>
                <Icon name={TAB[t].icon} />{TAB[t].label}
              </button>
            ))}
          </nav>
          <span className="spacer" />
          <span className="pill pill-demo hidem">DEMO</span>
          <span className="seglabel small muted">Viewing as</span>
          <div className="seg" role="group" aria-label="Viewing as">
            {Object.keys(ROLE_TABS).map((r) => (
              <button key={r} type="button" aria-pressed={role === r} onClick={() => go(r)}>{ROLE_LABEL[r]}</button>
            ))}
          </div>
          <label className="rolesel">
            <span className="sr">Viewing as</span>
            <select className="field" style={{ minHeight: 38 }} value={role} onChange={(e) => go(e.target.value)}>
              {Object.keys(ROLE_TABS).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </select>
          </label>
          <button type="button" className="icon" onClick={() => setDark(!dark)} aria-label={dark ? 'Light mode' : 'Dark mode'}>
            <Icon name={dark ? 'sun' : 'moon'} size={18} />
          </button>
          {role === 'student' ? (
            <label title="Which fictional student you are" style={{ position: 'relative' }}>
              <span className="sr">Demo student</span>
              <span className="avatar" aria-hidden="true">{avatar}</span>
              <select value={me} onChange={(e) => setMe(e.target.value)} aria-label="Demo student"
                style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer' }}>
                {students.map((s) => <option key={s.id} value={s.id}>{cleanName(s.name)}</option>)}
              </select>
            </label>
          ) : <span className="avatar" aria-hidden="true">{avatar}</span>}
        </div>
      </header>

      <main>{body}</main>

      <nav className="botnav" aria-label="Main">
        {tabs.map((t) => (
          <button key={t} type="button" className="bn" aria-current={tab === t ? 'page' : undefined}
            onClick={() => { setTab(t); setOpened(null) }}>
            <span className="bni"><Icon name={TAB[t].icon} size={20} /></span>{TAB[t].label}
          </button>
        ))}
      </nav>

      {drawer && (
        <>
          <button type="button" className="scrim" aria-label="Close Ask Visor" onClick={() => setDrawer(false)} />
          <AskVisor chat={chat} student={contextStudent} role={role} mode="drawer" onClose={() => setDrawer(false)} />
        </>
      )}
    </div>
  )
}
