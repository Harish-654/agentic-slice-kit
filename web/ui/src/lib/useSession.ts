import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Snapshot } from './api'

const POLL_MS = 1000
// A stalled run is resumed rather than watched; waiting on the student needs no polling.
const LIVE = new Set(['working', 'stalled'])

/**
 * One session, kept fresh. While the tutor is writing a lesson the page polls;
 * once it is the student's turn the polling stops, so an idle tab costs nothing.
 */
export function useSession(id: string | null) {
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const last = useRef('')

  const accept = useCallback((next: Snapshot) => {
    // Polls return a fresh object each time; only re-render when something changed.
    const key = JSON.stringify(next)
    if (key !== last.current) {
      last.current = key
      setSnap(next)
    }
    setError(null)
  }, [])

  const refresh = useCallback(async () => {
    if (!id) return
    try {
      accept(await api.get(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the tutor.')
    }
  }, [id, accept])

  // One mount per session (App keys the runtime by id), so state starts fresh.
  useEffect(() => {
    if (id) void refresh()
  }, [id, refresh])

  const status = snap?.status
  useEffect(() => {
    if (!id || !status) return
    if (status === 'stalled') {
      api.resume(id).then(accept, () => undefined)
    }
    if (!LIVE.has(status)) return
    const t = setInterval(() => void refresh(), POLL_MS)
    return () => clearInterval(t)
  }, [id, status, refresh, accept])

  const run = useCallback(
    async (action: Promise<Snapshot>) => {
      try {
        accept(await action)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Something went wrong.')
        void refresh()
      }
    },
    [accept, refresh],
  )

  return {
    snap,
    error,
    answerChoice: (choice: number) => (id ? run(api.answerChoice(id, choice)) : undefined),
    answerText: (text: string) => (id ? run(api.answerText(id, text)) : undefined),
    setMode: (mode: 'mcq' | 'text') => (id ? run(api.setMode(id, mode)) : undefined),
    setSource: (on: boolean) => (id ? run(api.setSource(id, on)) : undefined),
    fallback: (choice: 'general' | 'skip') => (id ? run(api.fallback(id, choice)) : undefined),
    refresh,
  }
}
