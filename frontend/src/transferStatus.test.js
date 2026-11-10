import { test } from 'node:test'
import assert from 'node:assert/strict'
import { transferStatus } from './transferStatus.js'

const row = (o) => ({ school: 'Nashville State Community College', external: 'X 1', status: 'unknown', counts_as: null, counted: false, note: '', ...o })

test('every transfer outcome gets a status and a reason (#2)', () => {
  assert.deepEqual(transferStatus(row({ status: 'confirmed', counted: true, counts_as: 'CS 1213' })),
    { pill: 'confirmed', label: 'Counts', why: 'Counts as CS 1213.' })
  assert.deepEqual(transferStatus(row({ status: 'confirmed', counted: true, counts_as: '3 hours elective credit' })),
    { pill: 'confirmed', label: 'Counts', why: 'Counts as 3 hours elective credit.' })
  assert.deepEqual(transferStatus(row({ status: 'proposed', counts_as: 'CS 2233', note: 'Pending: a person has to confirm this before it counts.' })),
    { pill: 'proposed', label: 'Pending', why: 'Proposed as CS 2233. Pending: a person has to confirm this before it counts.' })
  assert.deepEqual(transferStatus(row({ status: 'confirmed', note: 'Confirmed as not transferring.' })),
    { pill: 'needed', label: 'Does not transfer', why: 'Confirmed as not transferring.' })
  assert.deepEqual(transferStatus(row({ note: 'No equivalency yet; flag it for review from the lookup page.' })),
    { pill: 'unknown', label: 'Unknown', why: 'No equivalency yet; flag it for review from the lookup page.' })
})
