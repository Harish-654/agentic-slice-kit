/** What the browser remembers between visits. Storage can be unavailable (private windows), so every read
 * and write is guarded and the app works without it. */
export const KEY = { session: 'tutor.session', student: 'tutor.student' }

export const read = (k: string) => {
  try {
    return localStorage.getItem(k)
  } catch {
    return null
  }
}

export const write = (k: string, v: string | null) => {
  try {
    if (v === null) localStorage.removeItem(k)
    else localStorage.setItem(k, v)
  } catch {
    /* fine */
  }
}
