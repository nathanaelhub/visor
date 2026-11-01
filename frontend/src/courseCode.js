// Parse a course code typed on the Transfer page into { subject, number }, or null.
export function parseCourseCode(text) {
  const m = String(text).trim().toUpperCase().match(/^([A-Z]+)\s*([\w-]+)$/)
  return m ? { subject: m[1], number: m[2] } : null
}
