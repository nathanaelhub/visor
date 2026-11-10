// Advisor edits to a plan (spec 06): pure helpers, so they can be tested without a browser.
// Edits are planner inputs { settings, pins, holds, overload_note }; the server re-plans with them.

export const emptyEdits = () => ({ settings: {}, pins: [], holds: [], overload_note: null })

export function isEmpty(e) {
  return !e || (!Object.keys(e.settings ?? {}).length && !e.pins?.length && !e.holds?.length && !e.overload_note)
}

const without = (list = [], code) => list.filter((x) => x.code !== code)

/** One change per course: pinning replaces a hold on the same course, and the other way round. */
export function pin(e, code, term) {
  const b = e ?? emptyEdits()
  return { ...b, pins: [...without(b.pins, code), { code, term }], holds: without(b.holds, code) }
}

export function hold(e, code, notBefore) {
  const b = e ?? emptyEdits()
  return { ...b, holds: [...without(b.holds, code), { code, not_before: notBefore }], pins: without(b.pins, code) }
}

export function clearCourse(e, code) {
  const b = e ?? emptyEdits()
  return { ...b, pins: without(b.pins, code), holds: without(b.holds, code) }
}

export function setSetting(e, key, value) {
  const b = e ?? emptyEdits()
  const settings = { ...b.settings }
  if (value === null || value === undefined || value === '') delete settings[key]
  else settings[key] = value
  return { ...b, settings }
}

/** 'none' (never approved), 'current' (approved this exact plan) or 'stale' (plan changed since). */
export function approvalState(approval, fingerprint) {
  if (!approval) return 'none'
  return approval.fingerprint === fingerprint ? 'current' : 'stale'
}

const SEASONS = ['SP', 'SU', 'FA']

/** The next `count` term codes from `start` ("2027SP"), with or without summers. */
export function termsFrom(start, count, includeSummer = false) {
  const out = []
  let y = Number(start.slice(0, 4))
  let i = SEASONS.indexOf(start.slice(4))
  while (out.length < count) {
    const s = SEASONS[i]
    if (includeSummer || s !== 'SU') out.push(`${y}${s}`)
    i += 1
    if (i === SEASONS.length) { i = 0; y += 1 }
  }
  return out
}

/** Why approve is not allowed yet (spec 06, US-6.4): checker violations and courses with no term. */
export function approveBlockers(r) {
  if (!r?.plan) return ['There is no plan to approve.']
  return [...(r.checks?.violations ?? []).map((v) => v.message),
    ...r.warnings.filter((w) => w.kind === 'unplaceable').map((w) => w.message)]
}
