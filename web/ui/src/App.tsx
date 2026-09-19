import { useCallback, useState } from 'react'
import { StartScreen } from '@/components/tutor/StartScreen'
import { TutorRuntime } from '@/components/tutor/TutorRuntime'
import { Session } from '@/features/session/Session'

const KEY = { session: 'tutor.session', student: 'tutor.student' }

// Storage can be unavailable (private windows); the app must work without it.
const read = (k: string) => {
  try {
    return localStorage.getItem(k)
  } catch {
    return null
  }
}
const write = (k: string, v: string | null) => {
  try {
    if (v === null) localStorage.removeItem(k)
    else localStorage.setItem(k, v)
  } catch {
    /* fine */
  }
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(() => read(KEY.session))
  const [student, setStudent] = useState(() => read(KEY.student) ?? '')

  const started = useCallback((id: string, name: string) => {
    write(KEY.session, id)
    write(KEY.student, name)
    setStudent(name)
    setSessionId(id)
  }, [])
  const restart = useCallback(() => {
    write(KEY.session, null)
    setSessionId(null)
  }, [])

  if (!sessionId) return <StartScreen initialName={student} onStarted={started} />

  return (
    <TutorRuntime key={sessionId} sessionId={sessionId} onRestart={restart}>
      {(ready) =>
        ready ? (
          <Session onRestart={restart} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Opening your session…</div>
        )
      }
    </TutorRuntime>
  )
}
