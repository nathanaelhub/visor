import { test } from 'node:test'
import assert from 'node:assert/strict'
import { restorePlace, savePlace } from './tabState.js'

const ROLE_TABS = { student: ['myplan', 'ask'], advisor: ['students', 'transfer', 'ask'], registrar: ['transfer', 'ask'] }
const mem = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) } }

test('the place survives a reload (R3-F8)', () => {
  const s = mem()
  savePlace(s, { view: 'app', role: 'advisor', tab: 'students' })
  assert.deepEqual(restorePlace(s, ROLE_TABS), { view: 'app', role: 'advisor', tab: 'students' })
})

test('nothing saved, bad JSON, blocked storage or a tab the role lacks: the landing page', () => {
  const landing = { view: 'landing', role: 'student', tab: 'myplan' }
  assert.deepEqual(restorePlace(mem(), ROLE_TABS), landing)
  assert.deepEqual(restorePlace({ getItem: () => '{nope' }, ROLE_TABS), landing)
  assert.deepEqual(restorePlace({ getItem: () => { throw new Error('blocked') } }, ROLE_TABS), landing)
  assert.deepEqual(restorePlace(null, ROLE_TABS), landing)
  const s = mem(); savePlace(s, { view: 'app', role: 'registrar', tab: 'students' })
  assert.deepEqual(restorePlace(s, ROLE_TABS), landing)
  assert.doesNotThrow(() => savePlace({ setItem: () => { throw new Error('blocked') } }, landing))
})
