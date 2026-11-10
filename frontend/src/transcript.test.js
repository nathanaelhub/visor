import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toStudent } from './transcript.js'

const record = { id: 'transcript-retake', name: 'Casey Lin (from transcript)', program_id: 'cs-bs-2026-27', start_term: '2027SP' }

test('edited rows become a student record', () => {
  const { student, problems } = toStudent(record,
    [{ code: 'cs2233', title: 'Data Structures', credits: '3', grade: 'c', term: '2026SP' },
      { code: 'CS 2243', title: 'Algorithms', credits: 3, grade: 'IP', term: '2026FA' }],
    [{ school: 'Nashville State Community College', school_id: 1, subject: 'cisp', number: '1010', grade: 'A' }])
  assert.deepEqual(problems, [])
  assert.equal(student.program_id, 'cs-bs-2026-27')
  assert.deepEqual(student.taken[0], { code: 'CS 2233', title: 'Data Structures', credits: 3, grade: 'C', term: '2026SP' })
  assert.equal(student.taken[1].grade, null) // in progress
  assert.equal(student.transfer[0].subject, 'CISP')
})

test('emptied rows are dropped, bad ones are reported', () => {
  const { student, problems } = toStudent(record,
    [{ code: '', title: '', grade: '' }, { code: 'Data Structures', grade: 'A' }, { code: 'CS 1213', credits: 'three' }],
    [{ school: '', subject: 'CISP', number: '1010' }])
  assert.equal(student.taken.length, 1)
  assert.equal(problems.length, 3)
})
