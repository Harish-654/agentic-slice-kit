import { useCallback, useState, type FC } from 'react'
import { ChevronDownIcon, GraduationCapIcon, PlusIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { CodeCoach } from '@/components/tutor/CodeCoach'
import { ProgressPanel } from '@/components/tutor/ProgressPanel'
import { StartScreen } from '@/components/tutor/StartScreen'
import { Thread } from '@/components/tutor/Thread'
import { TutorRuntime } from '@/components/tutor/TutorRuntime'
import { useTutor } from '@/components/tutor/context'

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

const Session: FC<{ onRestart: () => void }> = ({ onRestart }) => {
  const { snap } = useTutor()
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center justify-between border-b px-4 py-2.5">
        <div className="flex items-center gap-2 font-semibold">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <GraduationCapIcon className="size-4" />
          </span>
          Tutor
        </div>
        <Button variant="ghost" size="sm" onClick={onRestart}>
          <PlusIcon className="size-4" />
          New session
        </Button>
      </header>

      {/* On a phone the progress panel folds away above the thread. */}
      <Collapsible className="border-b lg:hidden">
        <CollapsibleTrigger className="flex w-full items-center justify-between px-4 py-2 text-sm font-medium">
          Your progress
          <ChevronDownIcon className="size-4" />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <ProgressPanel progress={snap.progress} student={snap.student} />
          <CodeCoach />
        </CollapsibleContent>
      </Collapsible>

      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1">
          <Thread />
        </main>
        <aside className="hidden w-80 shrink-0 overflow-y-auto border-l bg-muted/20 lg:block">
          <ProgressPanel progress={snap.progress} student={snap.student} />
          <CodeCoach />
        </aside>
      </div>
    </div>
  )
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
