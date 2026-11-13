// Who stands behind an equivalency, in words for the Transfer page (spec 03; spec 07, US-7.2).
// Claude's suggestions are never confirmed on their own, so they always say a person must check them.
export function sourceLabel(eq) {
  if (!eq) return { text: 'No row on file', reason: null }
  const why = (eq.notes || '').replace(/^Proposed by Claude:\s*/, '') || null
  if (eq.source === 'ai_proposed' && eq.decided_by && (eq.status === 'confirmed' || eq.status === 'rejected')) {
    const verb = eq.status === 'confirmed' ? 'Confirmed' : 'Rejected'
    return { text: `${verb} by ${eq.decided_by}${eq.decided_at ? `, ${eq.decided_at}` : ''} (proposed by Claude)`, reason: why }
  }
  if (eq.source === 'ai_proposed') {
    return { text: 'Proposed by Claude · needs a person to confirm', reason: (eq.notes || '').replace(/^Proposed by Claude:\s*/, '') || null }
  }
  if (eq.decided_by) return { text: `${eq.decided_by}${eq.decided_at ? `, ${eq.decided_at}` : ''}`, reason: null }
  return { text: eq.source ? `Equivalency table (${eq.source})` : 'No row on file', reason: null }
}
