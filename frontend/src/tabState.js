// Where the person is in the app (landing or app, role, tab), kept for this browser tab only so that
// Clerk's reload after sign-in returns them to the same place (R3-F8). Anything unexpected in storage
// falls back to the landing page.
const KEY = 'visor.place'

export function restorePlace(storage, roleTabs) {
  const fallback = { view: 'landing', role: 'student', tab: 'myplan' }
  let saved
  try { saved = JSON.parse(storage?.getItem(KEY) ?? 'null') } catch { return fallback }
  if (!saved || typeof saved !== 'object') return fallback
  const { view, role, tab } = saved
  if (!['landing', 'app'].includes(view) || !roleTabs[role] || !roleTabs[role].includes(tab)) return fallback
  return { view, role, tab }
}

export function savePlace(storage, place) {
  try { storage?.setItem(KEY, JSON.stringify(place)) } catch { /* storage blocked: nothing to keep */ }
}
