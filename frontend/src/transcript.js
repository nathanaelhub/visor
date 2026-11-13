// Turn the edited transcript table back into a student record for POST /api/audit (spec 05, US-5.7).
// Pure, so it can be tested without a browser. Returns { student, problems }: problems are rows the
// person must fix before "Use this record" is allowed.
import { parseCourseCode } from './courseCode.js'
import { authHeaders } from './session.js'

const blank = (s) => String(s ?? '').trim() === ''

export function toStudent(record, taken, transfer) {
  const problems = []
  const outTaken = []
  taken.forEach((row, i) => {
    if (blank(row.code) && blank(row.title) && blank(row.grade)) return // an emptied row is removed
    const code = parseCourseCode(row.code ?? '')
    if (!code) { problems.push(`Course row ${i + 1}: "${row.code}" is not a course code like CS 2233.`); return }
    const credits = blank(row.credits) ? null : Number(row.credits)
    if (credits !== null && !(credits >= 0)) problems.push(`${code.subject} ${code.number}: hours must be a number.`)
    outTaken.push({ code: `${code.subject} ${code.number}`, title: row.title ?? '', credits,
      grade: blank(row.grade) || String(row.grade).trim().toUpperCase() === 'IP' ? null : String(row.grade).trim().toUpperCase(),
      term: row.term || null })
  })
  const outTransfer = []
  transfer.forEach((row, i) => {
    if (blank(row.subject) && blank(row.number)) return
    if (blank(row.school) || blank(row.subject) || blank(row.number)) {
      problems.push(`Transfer row ${i + 1}: needs a school, subject and number.`); return
    }
    outTransfer.push({ ...row, subject: String(row.subject).trim().toUpperCase(), number: String(row.number).trim(),
      grade: blank(row.grade) ? null : String(row.grade).trim().toUpperCase() })
  })
  return { student: { ...record, taken: outTaken, transfer: outTransfer }, problems }
}

/** Split streamed NDJSON text into complete lines and the unfinished rest (spec 07, US-7.4). */
export function ndjsonLines(buffer) {
  const parts = buffer.split('\n')
  const rest = parts.pop()
  return [parts.filter((l) => l.trim()).map((l) => JSON.parse(l)), rest]
}

/** POST a transcript read with ?stream=1 and call onRow for each row as Claude reads it.
 *  Resolves to the final result; rejects with { message, code, status } like api(). */
export async function streamRead(body, headers, onRow) {
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData
  const auth = await authHeaders()
  const r = await fetch('/api/transcript?stream=1', {
    method: 'POST', body: isForm ? body : JSON.stringify(body),
    headers: isForm ? { ...auth, ...headers } : { 'Content-Type': 'application/json', ...auth, ...headers },
  })
  if (!r.ok) {
    let data = null
    try { data = await r.json() } catch { /* empty */ }
    throw Object.assign(new Error(data?.message || `HTTP ${r.status}`), { status: r.status, code: data?.error, data })
  }
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (value) buf += dec.decode(value, { stream: true })
    const [events, rest] = ndjsonLines(done ? `${buf}\n` : buf)
    buf = rest
    for (const e of events) {
      if (e.type === 'row') onRow(e)
      if (e.type === 'done') return e.result
      if (e.type === 'error') throw Object.assign(new Error(e.message || 'Could not read that transcript'), { status: e.status, code: e.error })
    }
    if (done) throw new Error('The read ended before Claude finished.')
  }
}
