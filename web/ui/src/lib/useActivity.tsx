import { createContext, useCallback, useContext, useEffect, useMemo, useState, type FC, type ReactNode } from 'react'
import { api, type Activity } from './api'

type Ctx = {
  /** null until the first answer from the server. */
  activity: Activity | null
  /** The last fetch failed; the old numbers, if any, are still shown. */
  failed: boolean
  /** Ask again, e.g. after the student answers a question or runs code. */
  refresh: () => void
}
const ActivityContext = createContext<Ctx | null>(null)

/** One copy of the student's activity for the whole signed-in app, so the streak in the top bar, the
 * check-in card and the heatmap always agree and cost a single request. */
export const ActivityProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [activity, setActivity] = useState<Activity | null>(null)
  const [failed, setFailed] = useState(false)
  const refresh = useCallback(() => {
    api.activity().then(
      (a) => {
        setActivity(a)
        setFailed(false)
      },
      () => setFailed(true),
    )
  }, [])
  useEffect(() => {
    refresh()
  }, [refresh])
  const value = useMemo(() => ({ activity, failed, refresh }), [activity, failed, refresh])
  return <ActivityContext.Provider value={value}>{children}</ActivityContext.Provider>
}

export function useActivity(): Ctx {
  const ctx = useContext(ActivityContext)
  if (!ctx) throw new Error('useActivity must be used inside <ActivityProvider>')
  return ctx
}
