import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupStatus, loadCheck } from './planStatus.js'

test('a started but unmet group is partly done (F10)', () => {
  assert.equal(groupStatus({ status: 'needed', counted_hours: 38 }), 'partial')
  assert.equal(groupStatus({ status: 'needed', counted_hours: 0 }), 'needed')
  assert.equal(groupStatus({ status: 'met', counted_hours: 9 }), 'met')
  assert.equal(groupStatus({ status: 'in_progress', counted_hours: 3 }), 'in_progress')
})

test('the load line compares the heaviest term with the limit (F11)', () => {
  assert.deepEqual(loadCheck({ max_load: 18, load_limit: 18 }), { ok: true, text: 'Every term at or under 18 hrs (heaviest 18)' })
  assert.equal(loadCheck({ max_load: 21, load_limit: 18 }).ok, false)
})
