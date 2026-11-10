// One status and one plain reason for each transfer course on the plan page (#2). The planner's
// transfer report (POST /api/audit → transfer) has the facts; this only words them.
export function transferStatus(t) {
  if (t.counted) return { pill: 'confirmed', label: 'Counts', why: `Counts as ${t.counts_as}.` }
  if (t.status === 'proposed') {
    return { pill: 'proposed', label: 'Pending', why: [t.counts_as && `Proposed as ${t.counts_as}.`, t.note].filter(Boolean).join(' ') }
  }
  if (t.status === 'confirmed') return { pill: 'needed', label: 'Does not transfer', why: t.note || 'Confirmed as not transferring.' }
  return { pill: 'unknown', label: 'Unknown', why: t.note || 'No equivalency on file yet.' }
}
