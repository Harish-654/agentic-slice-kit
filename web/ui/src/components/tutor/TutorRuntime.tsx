import { useCallback, useMemo, useState, type ReactNode } from 'react'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { Button } from '@/components/ui/button'
import type { CodeTaskQ, Confidence, Msg, OpenQ, Quiz } from '@/lib/api'
import { api, ApiError } from '@/lib/api'
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
  /** The check on a lesson or a revealed card. Empty while a guided explanation holds its check back. */
  const checkParts = (c: { quiz: Quiz | null; open: OpenQ | null; code_task: CodeTaskQ | null }) =>
    c.quiz
      ? [call('quiz', { quiz: c.quiz }, c.quiz.answered ?? undefined)]
      : c.code_task
        ? [call('code_task', { task: c.code_task }, c.code_task.answered ?? undefined)]
        : c.open
          ? [call('open_question', { open: c.open }, c.open.answered ?? undefined)]
          : []
  switch (m.kind) {
    case 'lesson':
      return {
        id: m.id,
        role: 'assistant',
        status: done,
        content: [
          call('lesson_header', { concept: m.concept, style: m.style, source: m.source, citations: m.citations }, true),
          { type: 'text', text: m.explanation },
          ...(m.diagram ? [call('diagram', { source: m.diagram }, true)] : []),
          ...checkParts(m), // none while a guided explanation is waiting to be followed by a quiz
        ],
      }
    case 'card':
      return { id: m.id, role: 'assistant', status: done, content: checkParts(m) }
    case 'choices':
      return {
        id: m.id,
        role: 'assistant',
        status: done,
        content: [call('choices', { options: m.options, chosen: m.chosen }, m.chosen ?? undefined)],
      }
    case 'answer':
      return { id: m.id, role: 'user', content: [{ type: 'text', text: m.text }] }
    case 'feedback':
      return {
        id: m.id,
        role: 'assistant',
        status: done,
        content: [
          call(
            'feedback',
            {
              correct: m.correct,
              text: m.text,
              misconception: m.misconception,
              via: m.via,
              confidence: m.confidence,
              dont_know: m.dont_know,
            },
            true,
          ),
        ],
      }
    case 'end':
      return { id: m.id, role: 'assistant', status: done, content: [call('end', { reason: m.reason }, true)] }
    case 'notice':
      return {
        id: m.id,
        role: 'assistant',
        status: done,
        content: [call('notice', { text: m.text, problem: m.problem, gap: m.gap }, true)],
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
  const { snap, error, answerChoice, answerText, answerCode, dontKnow, setMode, setSource, fallback, choose, refresh } =
    useSession(sessionId)
  const status = snap?.status
  const canAnswer = status === 'waiting_student'

  // What the student has picked and how sure they are belongs to ONE lesson. Keying it by the
  // lesson's id means a new lesson starts clean, with no effect needed to reset it.
  const lessonId = snap?.messages.findLast((m) => m.kind === 'lesson')?.id ?? null
  const [sel, setSel] = useState<{ id: string | null; picked: number | null; confidence: Confidence | null }>({
    id: null,
    picked: null,
    confidence: null,
  })
  const cur = sel.id === lessonId ? sel : { id: lessonId, picked: null, confidence: null }

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (!canAnswer || !cur.confidence || part?.type !== 'text' || !part.text.trim()) return
      await answerText(part.text.trim(), cur.confidence)
    },
    [canAnswer, cur.confidence, answerText],
  )

  const runtime = useExternalStoreRuntime<Msg>({
    messages: snap?.messages ?? [],
    isRunning: status === 'working',
    convertMessage,
    onNew,
  })

  const student = snap?.student ?? ''
  // A document change re-reads the session, so the panel shows what the server now holds.
  const docs = useCallback(
    (action: () => Promise<unknown>) =>
      action().then(refresh, (e) => {
        throw new Error(e instanceof ApiError ? e.message : 'Could not reach the tutor.')
      }),
    [refresh],
  )

  const tutor = useMemo<TutorApi | null>(
    () =>
      snap
        ? {
            snap,
            canAnswer,
            picked: cur.picked,
            setPicked: (choice) => setSel({ ...cur, picked: choice }),
            confidence: cur.confidence,
            setConfidence: (c) => setSel({ ...cur, confidence: c }),
            submitChoice: () => {
              if (cur.picked !== null && cur.confidence) void answerChoice(cur.picked, cur.confidence)
            },
            dontKnow: () => void dontKnow(),
            submitCode: (code, assisted) => {
              if (cur.confidence) void answerCode(code, cur.confidence, assisted)
            },
            setMode,
            setSource,
            fallback,
            choose,
            addDocs: (files) => docs(() => api.upload(student, files)),
            addSample: () => docs(() => api.sample(student)),
            removeDoc: (name) => docs(() => api.removeDoc(student, name)),
            restart: onRestart,
            refresh,
          }
        : null,
    // The actions close over the session id only; the snapshot is what changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [snap, canAnswer, onRestart, docs, student, lessonId, cur.picked, cur.confidence],
  )

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <TutorContext.Provider value={tutor}>
        {error && !snap ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" onClick={onRestart}>
              Start over
            </Button>
          </div>
        ) : null}
        {children(tutor !== null)}
      </TutorContext.Provider>
    </AssistantRuntimeProvider>
  )
}
