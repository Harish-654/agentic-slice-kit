import { useCallback, useState } from 'react'
import { StartScreen } from '@/components/tutor/StartScreen'
import { TutorRuntime } from '@/components/tutor/TutorRuntime'
import { AuthGate } from '@/features/auth/AuthGate'
import { AuthProvider } from '@/features/auth/useAuth'
import { Session } from '@/features/session/Session'
import { KEY, read, write } from '@/lib/storage'

/** A signed-in student: the session they had open, or the start screen. */
function Learning({ student }: { student: string }) {
  // A session id left in the browser belongs to whoever started it. Only pick it up again for the same student.
  const [sessionId, setSessionId] = useState<string | null>(() => (read(KEY.student) === student ? read(KEY.session) : null))

  const started = useCallback(
    (id: string) => {
      write(KEY.session, id)
      write(KEY.student, student)
      setSessionId(id)
    },
    [student],
  )
  const restart = useCallback(() => {
    write(KEY.session, null)
    setSessionId(null)
  }, [])

  if (!sessionId) return <StartScreen student={student} onStarted={started} />

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

export default function App() {
  return (
    <AuthProvider>
      <AuthGate>{(student) => <Learning student={student} />}</AuthGate>
    </AuthProvider>
  )
}
