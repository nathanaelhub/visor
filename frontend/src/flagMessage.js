// What the Transfer page says when "Flag for review" fails (#20). A public deployment keeps writes
// closed (backend/visor/auth.py answers 401 or 403), so that reads as a demo limit, not an error.
export function flagMessage(e) {
  if (e.status === 401 || e.status === 403) {
    return 'Flagging is turned off in the public demo. On a staff deployment this sends the course to a professor for review.'
  }
  if (e.status === 409) return 'Already confirmed; nothing to review.'
  return `Could not flag: ${e.message}`
}
