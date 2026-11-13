// The signed-in person's Clerk session token, for API calls (spec 08). The server checks the token
// and decides the role; the browser never claims one.
const env = import.meta.env ?? {} // undefined outside Vite (node --test)
export const CLERK_KEY = env.VITE_CLERK_PUBLISHABLE_KEY || env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || ''

let getToken = async () => null
export function setTokenGetter(fn) { getToken = fn || (async () => null) }

/** Headers that carry the session, if any: { Authorization: 'Bearer …' } or {}. */
export async function authHeaders() {
  try {
    const t = await getToken()
    return t ? { Authorization: `Bearer ${t}` } : {}
  } catch { return {} }
}
