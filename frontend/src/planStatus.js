// How a requirement group and the load check read on the plan page (user-case findings F10, F11).

/** 'met' | 'in_progress' | 'partial' | 'needed': a group with hours counted but not met is partly done. */
export function groupStatus(g) {
  if (g.status === 'needed' && (g.counted_hours ?? 0) > 0) return 'partial'
  return g.status
}

/** { ok, text } for the load line in Plan checks. */
export function loadCheck(checks) {
  const ok = checks.max_load <= checks.load_limit
  return ok
    ? { ok, text: `Every term at or under ${checks.load_limit} hrs (heaviest ${checks.max_load})` }
    : { ok, text: `A term has ${checks.max_load} hrs, over the ${checks.load_limit}-hour limit` }
}
