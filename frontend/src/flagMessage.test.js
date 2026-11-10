import { test } from 'node:test'
import assert from 'node:assert/strict'
import { flagMessage } from './flagMessage.js'

const err = (status, message = 'x') => Object.assign(new Error(message), { status })

test('closed writes on a public deployment read as a demo limit, not a bug (#20)', () => {
  for (const status of [401, 403]) {
    const m = flagMessage(err(status, 'missing or wrong X-Visor-Token header'))
    assert.match(m, /turned off in the public demo/)
    assert.doesNotMatch(m, /token/i)
  }
})

test('already confirmed and other errors keep their meaning', () => {
  assert.equal(flagMessage(err(409)), 'Already confirmed; nothing to review.')
  assert.equal(flagMessage(err(500, 'boom')), 'Could not flag: boom')
})
