import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, type AnswerMode, type Choice, type Confidence, type Snapshot } from './api'

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
  // The type of the NEXT question, asked for while a lesson was being written. The server refuses that (the run is about
  // to write the learner model itself), so it waits here and is sent the moment the lesson lands.
  const [pendingMode, setPendingMode] = useState<AnswerMode | null>(null)

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

  const serverMode = snap?.progress.answer_mode
  useEffect(() => {
    if (!id || !pendingMode || !status || status === 'working' || status === 'stalled') return
    const mode = pendingMode
    setPendingMode(null)
    if (serverMode === mode) return
    api.setMode(id, mode).then(accept, async (e) => {
      await refresh() // learn what the run is doing now before deciding anything
      if (e instanceof ApiError && e.status === 409) setPendingMode(mode) // it started again: wait for it to land
      else setError(e instanceof Error ? e.message : 'Could not change that.')
    })
  }, [id, pendingMode, status, serverMode, accept, refresh])

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
    answerChoice: (choice: number, c: Confidence) => (id ? run(api.answerChoice(id, choice, c)) : undefined),
    answerText: (text: string, c: Confidence) => (id ? run(api.answerText(id, text, c)) : undefined),
    answerCode: (code: string, c: Confidence, assisted: boolean) =>
      id ? run(api.answerCode(id, code, c, assisted)) : undefined,
    dontKnow: () => (id ? run(api.dontKnow(id)) : undefined),
    /** What the next question will be, counting a change that is still waiting to be sent. */
    nextMode: (pendingMode ?? serverMode ?? 'mcq') as AnswerMode,
    setMode: (mode: AnswerMode) => {
      if (!id) return undefined
      if (status === 'working') {
        setPendingMode(mode)
        return undefined
      }
      setPendingMode(null)
      return run(api.setMode(id, mode))
    },
    setSource: (on: boolean) => (id ? run(api.setSource(id, on)) : undefined),
    fallback: (choice: 'general' | 'skip') => (id ? run(api.fallback(id, choice)) : undefined),
    choose: (choice: Choice) => (id ? run(api.choose(id, choice)) : undefined),
    refresh,
  }
}
