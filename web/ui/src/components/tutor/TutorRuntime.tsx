import { useCallback, useMemo, type ReactNode } from 'react'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { Button } from '@/components/ui/button'
import type { Msg } from '@/lib/api'
import { useSession } from '@/lib/useSession'
import { TutorContext, type TutorApi } from './context'

const done = { type: 'complete', reason: 'stop' } as const

/** One tutor message becomes one chat message. Everything that is not plain text
 * is a tool-call part, which the thread renders with our own components. */
function convertMessage(m: Msg): ThreadMessageLike {
  const call = (name: string, args: Record<string, unknown>, result?: unknown) => ({
    type: 'tool-call' as const,
    toolCallId: `${m.id}-${name}`,
    toolName: name,
    args: args as never,
    result: result as never,
  })
  switch (m.kind) {
    case 'lesson':
      return {
        id: m.id,
        role: 'assistant',
        status: done,
        content: [
          call('lesson_header', { concept: m.concept, style: m.style, citations: m.citations }, true),
          { type: 'text', text: m.explanation },
          ...(m.diagram ? [call('diagram', { source: m.diagram }, true)] : []),
          call('quiz', { quiz: m.quiz }, m.quiz.answered ?? undefined),
        ],
      }
    case 'answer':
      return { id: m.id, role: 'user', content: [{ type: 'text', text: m.text }] }
    case 'feedback':
      return {
        id: m.id,
        role: 'assistant',
        status: done,
        content: [
          call('feedback', { correct: m.correct, text: m.text, misconception: m.misconception, via: m.via }, true),
        ],
      }
    case 'end':
      return { id: m.id, role: 'assistant', status: done, content: [call('end', { reason: m.reason }, true)] }
    case 'notice':
      return {
        id: m.id,
        role: 'assistant',
        status: done,
        content: [call('notice', { text: m.text, problem: m.problem }, true)],
      }
  }
}

/** Puts one tutoring session behind assistant-ui's runtime. The session lives on the
 * server; this only maps it onto chat messages and sends the student's answers back. */
export function TutorRuntime({
  sessionId,
  onRestart,
  children,
}: {
  sessionId: string
  onRestart: () => void
  children: (ready: boolean) => ReactNode
}) {
  const { snap, error, answerChoice, answerText, setMode } = useSession(sessionId)
  const status = snap?.status
  const canAnswer = status === 'waiting_student'

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (!canAnswer || part?.type !== 'text' || !part.text.trim()) return
      await answerText(part.text.trim())
    },
    [canAnswer, answerText],
  )

  const runtime = useExternalStoreRuntime<Msg>({
    messages: snap?.messages ?? [],
    isRunning: status === 'working',
    convertMessage,
    onNew,
  })

  const api = useMemo<TutorApi | null>(
    () =>
      snap
        ? { snap, canAnswer, answerChoice, answerText, setMode, restart: onRestart }
        : null,
    // The actions close over the session id only; the snapshot is what changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [snap, canAnswer, onRestart],
  )

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <TutorContext.Provider value={api}>
        {error && !snap ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" onClick={onRestart}>
              Start over
            </Button>
          </div>
        ) : null}
        {children(api !== null)}
      </TutorContext.Provider>
    </AssistantRuntimeProvider>
  )
}
