// Parse a course code typed on the Transfer page into { subject, number }, or null.
// Subject: letters. Number: starts with a digit, may end in letters (1110L). A space or hyphen
// between them is optional, so 'CISP 1020', 'cisp1020' and 'CISP-1020' all read the same.
export function parseCourseCode(text) {
  const m = String(text).trim().toUpperCase().match(/^([A-Z]+)\s*-?\s*(\d+[A-Z]*)$/)
  return m ? { subject: m[1], number: m[2] } : null
}
