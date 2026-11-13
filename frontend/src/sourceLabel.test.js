import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sourceLabel } from './sourceLabel.js'

test("Claude's proposals say a person must confirm them, with the reason", () => {
  const l = sourceLabel({ source: 'ai_proposed', status: 'proposed', notes: 'Proposed by Claude: Same first programming course.' })
  assert.equal(l.text, 'Proposed by Claude · needs a person to confirm')
  assert.equal(l.reason, 'Same first programming course.')
})

test('people and the table keep their labels', () => {
  assert.equal(sourceLabel({ source: 'sis_import', decided_by: 'Registrar', decided_at: '2026-08-15' }).text, 'Registrar, 2026-08-15')
  assert.equal(sourceLabel({ source: 'manual' }).text, 'Equivalency table (manual)')
  assert.equal(sourceLabel(null).text, 'No row on file')
})

test("once a person decides Claude's proposal, the person is named", () => {
  const l = sourceLabel({ source: 'ai_proposed', status: 'confirmed', decided_by: 'Ms. Registrar', decided_at: '2026-11-13', notes: 'Proposed by Claude: Same course.' })
  assert.equal(l.text, 'Confirmed by Ms. Registrar, 2026-11-13 (proposed by Claude)')
  assert.equal(l.reason, 'Same course.')
})
