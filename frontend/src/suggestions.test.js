import { test } from 'node:test'
import assert from 'node:assert/strict'
import { suggestionsFor } from './suggestions.js'

test('students get questions about their own major (R3-F3)', () => {
  const cs = suggestionsFor('student', 'cs-bs-2026-27').join(' ')
  assert.match(cs, /Data Structures/)
  for (const p of ['bio-bs-2026-27', 'psych-bs-2026-27', 'nursing-bsn-2026-27', 'mgmt-bba-2026-27']) {
    const qs = suggestionsFor('student', p)
    assert.equal(qs.length, 4, p)
    assert.doesNotMatch(qs.join(' '), /Data Structures|Operating Systems/, p)
  }
})

test('an unknown major or no student gets the general questions only', () => {
  assert.deepEqual(suggestionsFor('student', undefined), suggestionsFor('student', 'nope'))
  assert.equal(suggestionsFor('student', undefined).length, 2)
})

test('advisor and registrar questions do not depend on the major', () => {
  assert.deepEqual(suggestionsFor('registrar', 'psych-bs-2026-27'), suggestionsFor('registrar', 'cs-bs-2026-27'))
  assert.ok(suggestionsFor('advisor').length >= 3)
})
