import { test } from 'node:test'
import assert from 'node:assert/strict'
import { approvalState, approveBlockers, clearCourse, emptyEdits, hold, isEmpty, pin, setSetting, termsFrom } from './planEdits.js'

test('one change per course: a pin replaces a hold and the other way round', () => {
  let e = pin(null, 'CS 2623', '2027FA')
  e = hold(e, 'CS 2623', '2028SP')
  assert.deepEqual(e.pins, [])
  assert.deepEqual(e.holds, [{ code: 'CS 2623', not_before: '2028SP' }])
  e = pin(e, 'CS 2623', '2027FA')
  assert.deepEqual(e.holds, [])
  assert.ok(isEmpty(clearCourse(e, 'CS 2623')))
})

test('settings can be set and cleared', () => {
  let e = setSetting(emptyEdits(), 'include_summer', true)
  assert.equal(e.settings.include_summer, true)
  e = setSetting(e, 'include_summer', null)
  assert.ok(isEmpty(e))
})

test('an approval is current only for the exact plan it approved', () => {
  assert.equal(approvalState(null, 'abc'), 'none')
  assert.equal(approvalState({ fingerprint: 'abc' }, 'abc'), 'current')
  assert.equal(approvalState({ fingerprint: 'abc' }, 'def'), 'stale')
})

test('term options walk forward, with summers only when asked', () => {
  assert.deepEqual(termsFrom('2027SP', 4), ['2027SP', '2027FA', '2028SP', '2028FA'])
  assert.deepEqual(termsFrom('2027FA', 3, true), ['2027FA', '2028SP', '2028SU'])
})

test('approve is blocked by checker violations and unplaced courses', () => {
  assert.deepEqual(approveBlockers({ plan: {}, checks: { violations: [] }, warnings: [{ kind: 'pin_ignored', message: 'x' }] }), [])
  assert.deepEqual(approveBlockers({ plan: {}, checks: { violations: [{ message: 'CS 3123 is not offered' }] },
    warnings: [{ kind: 'unplaceable', message: 'CS 4999 could not be placed' }] }),
  ['CS 3123 is not offered', 'CS 4999 could not be placed'])
})
