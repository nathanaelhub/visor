// Turn the edited transcript table back into a student record for POST /api/audit (spec 05, US-5.7).
// Pure, so it can be tested without a browser. Returns { student, problems }: problems are rows the
// person must fix before "Use this record" is allowed.
import { parseCourseCode } from './courseCode.js'

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
