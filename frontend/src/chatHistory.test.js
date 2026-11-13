import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fromSaved, savedNotice } from './chatHistory.js'

test('saved messages come back in the chat shape, tool summaries only', () => {
  const msgs = fromSaved([
    { role: 'user', text: 'What does CS 2623 need?' },
    { role: 'assistant', text: 'CS 2233.', model: 'claude-haiku-5-5', tools: [{ tool: 'course_info', input: { code: 'CS 2623' }, summary: 'Checked CS 2623', status: 'ok' }] },
  ])
  assert.deepEqual(msgs[0], { role: 'user', text: 'What does CS 2623 need?' })
  assert.equal(msgs[1].role, 'bot')
  assert.equal(msgs[1].answer, 'CS 2233.')
  assert.equal(msgs[1].tool_calls[0].summary, 'Checked CS 2623')
  assert.equal(msgs[1].tool_calls[0].result, null)
})

test('the notice says whether the chat is saved', () => {
  assert.equal(savedNotice(null), 'Not saved.')
  assert.match(savedNotice({ role: 'student' }), /Saved for one year/)
})
