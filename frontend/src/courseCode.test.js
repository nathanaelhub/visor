import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseCourseCode } from './courseCode.js'

test('reads the usual forms', () => {
  for (const s of ['CISP 1020', 'cisp1020', '  CISP   1020 ', 'CISP-1020', 'cisp - 1020']) {
    assert.deepEqual(parseCourseCode(s), { subject: 'CISP', number: '1020' }, s)
  }
})

test('keeps a letter suffix on the number', () => {
  assert.deepEqual(parseCourseCode('BIOL 1110L'), { subject: 'BIOL', number: '1110L' })
})

test('rejects a subject with no number instead of splitting it', () => {
  for (const s of ['HIST', 'HIS T', 'CS', '', '1020', 'CISP 10-20', 'CISP -']) {
    assert.equal(parseCourseCode(s), null, s)
  }
})
