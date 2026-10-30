// API client and formatting helpers shared by every view.

export async function api(path, { method = 'GET', body, headers = {} } = {}) {
  const r = await fetch(path, {
    method,
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...headers },
    body: body ? JSON.stringify(body) : undefined,
  })
  let data = null
  try { data = await r.json() } catch { /* empty body */ }
  if (!r.ok) {
    const err = new Error(data?.message || data?.error || `HTTP ${r.status}`)
    err.status = r.status
    err.code = data?.error
    err.data = data
    throw err
  }
  return data
}

const SEASON = { SP: 'Spring', SU: 'Summer', FA: 'Fall' }
const GRAD_MONTH = { SP: 'May', SU: 'Aug', FA: 'Dec' }

/** "2027SP" -> "Spring 2027" */
export function termName(code) {
  if (!code) return ''
  return `${SEASON[code.slice(4)] ?? code.slice(4)} ${code.slice(0, 4)}`
}

/** "2028SP" -> "May 2028" (commencement month) */
export function gradName(code) {
  if (!code) return '—'
  return `${GRAD_MONTH[code.slice(4)] ?? ''} ${code.slice(0, 4)}`.trim()
}

/** Number of terms between the current term and the projected one, Fall/Spring only. */
export function termsAfter(current, last) {
  if (!current || !last) return null
  const idx = (c) => Number(c.slice(0, 4)) * 2 + (c.endsWith('FA') ? 1 : 0)
  return Math.max(0, idx(last) - idx(current))
}

export function initials(name = '') {
  return name.replace(/\(.*?\)/g, '').trim().split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase()
}

export function cleanName(name = '') {
  return name.replace(/\s*\(fictional\)\s*/i, '')
}

export const hrs = (n) => `${Number(n || 0) % 1 ? Number(n).toFixed(1) : Number(n || 0)}`

// Session-only key storage for Ask Visor (the design: "stays in this browser session").
const KEY = 'visor.anthropicKey'
const MODEL = 'visor.model'
export const keyStore = {
  get: () => { try { return sessionStorage.getItem(KEY) || '' } catch { return '' } },
  set: (k) => { try { sessionStorage.setItem(KEY, k) } catch { /* private mode */ } },
  clear: () => { try { sessionStorage.removeItem(KEY) } catch { /* private mode */ } },
  model: () => { try { return sessionStorage.getItem(MODEL) || '' } catch { return '' } },
  setModel: (m) => { try { sessionStorage.setItem(MODEL, m) } catch { /* private mode */ } },
}
