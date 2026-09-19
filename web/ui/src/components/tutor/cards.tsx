import { useEffect, useId, useRef, useState } from 'react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { BookOpenIcon, CheckCircle2Icon, InfoIcon, LightbulbIcon, TriangleAlertIcon, XCircleIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { humanize, STYLE_LABEL } from '@/lib/format'
import type { Answered, Quiz } from '@/lib/api'
import { useTutor } from './context'

/** Concept, how it is being taught, and which of the teacher's notes it came from. */
export const LessonHeader: ToolCallMessagePartComponent = ({ args, toolCallId }) => {
  const { concept, style, citations } = args as { concept: string; style: string; citations: string[] }
  return (
    // The id is what the thread scrolls to when a new lesson arrives.
    <div id={toolCallId} className="mb-3 flex scroll-mt-4 flex-wrap items-center gap-2">
      <h2 className="text-lg font-semibold tracking-tight">{humanize(concept)}</h2>
      <Badge variant="secondary">{STYLE_LABEL[style] ?? humanize(style)}</Badge>
      {citations.map((c) => (
        <Badge key={c} variant="outline" className="gap-1 font-normal text-muted-foreground">
          <BookOpenIcon className="size-3" />
          {c}
        </Badge>
      ))}
    </div>
  )
}

const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'

/** A diagram the model drew. Mermaid is loaded only when a lesson has one, and a
 * diagram that does not parse is dropped: a missing picture beats an error graphic. */
export const DiagramView: ToolCallMessagePartComponent = ({ args }) => {
  const { source } = args as { source: string }
  const host = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'hidden'>('loading')
  const id = useId().replace(/:/g, '')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const { default: mermaid } = await import(/* @vite-ignore */ MERMAID)
        const dark = document.documentElement.classList.contains('dark')
        mermaid.initialize({ startOnLoad: false, suppressErrorRendering: true, theme: dark ? 'dark' : 'default' })
        await mermaid.parse(source)
        const { svg } = await mermaid.render(`d${id}`, source)
        if (cancelled || !host.current) return
        host.current.innerHTML = svg
        setState('ok')
      } catch {
        if (!cancelled) setState('hidden')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [source, id])

  if (state === 'hidden') return null
  return (
    <div
      ref={host}
      className={cn(
        'my-3 flex justify-center overflow-x-auto rounded-lg border bg-card p-3',
        state === 'loading' && 'h-24 animate-pulse',
      )}
    />
  )
}

function Code({ children }: { children: string }) {
  return (
    <pre className="my-3 overflow-x-auto rounded-lg bg-muted px-4 py-3 font-mono text-sm leading-relaxed">
      <code>{children.trim()}</code>
    </pre>
  )
}

const LETTERS = 'ABCDE'

/** The check. Multiple choice by default; in text mode the answer goes in the box
 * below, so the card only shows the question. */
export const QuizCard: ToolCallMessagePartComponent = ({ args }) => {
  const { quiz } = args as { quiz: Quiz }
  const { snap, canAnswer, answerChoice } = useTutor()
  const answered: Answered | null = quiz.answered
  const mcq = snap.progress.answer_mode === 'mcq'
  const open = !answered && canAnswer
  // Options show for a multiple-choice quiz, and for any quiz that was answered by choosing one.
  const showOptions = answered ? answered.chosen !== null : mcq

  return (
    <Card className="mt-4 gap-3 py-4">
      <CardContent className="px-4">
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Check yourself</p>
        <p className="font-medium leading-snug">{quiz.question}</p>
        {quiz.code ? <Code>{quiz.code}</Code> : null}

        {showOptions ? (
          <ul className="mt-3 flex flex-col gap-2">
            {quiz.options.map((o, i) => {
              const isChosen = answered?.chosen === i
              const isRight = answered?.correct_index === i
              return (
                <li key={i}>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!open}
                    onClick={() => answerChoice(i)}
                    className={cn(
                      'h-auto w-full justify-start gap-3 whitespace-normal px-3 py-2.5 text-left font-normal',
                      answered && isRight && 'border-emerald-500 bg-emerald-500/10 disabled:opacity-100',
                      answered && isChosen && !isRight && 'border-destructive bg-destructive/10 disabled:opacity-100',
                      answered && !isRight && !isChosen && 'disabled:opacity-45',
                    )}
                  >
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium">
                      {answered && isRight ? (
                        <CheckCircle2Icon className="size-4 text-emerald-600" />
                      ) : answered && isChosen ? (
                        <XCircleIcon className="size-4 text-destructive" />
                      ) : (
                        LETTERS[i]
                      )}
                    </span>
                    <span>{o.text}</span>
                  </Button>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            {answered ? 'You answered in your own words.' : 'Write your answer in the box below.'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

/** Right or wrong, why, and, when wrong, the belief the chosen option stood for. */
export const FeedbackCard: ToolCallMessagePartComponent = ({ args }) => {
  const { correct, text, misconception, via } = args as {
    correct: boolean
    text: string
    misconception: string | null
    via: 'mcq' | 'text'
  }
  return (
    <div
      className={cn(
        'flex gap-3 rounded-lg border p-4',
        correct ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-amber-500/40 bg-amber-500/5',
      )}
    >
      {correct ? (
        <CheckCircle2Icon className="mt-0.5 size-5 shrink-0 text-emerald-600" />
      ) : (
        <LightbulbIcon className="mt-0.5 size-5 shrink-0 text-amber-600" />
      )}
      <div className="text-sm leading-relaxed">
        <p className="font-semibold">{correct ? 'Correct' : 'Not quite'}</p>
        <p className="mt-0.5">{text}</p>
        {!correct && misconception ? (
          <p className="mt-2 text-muted-foreground">
            {via === 'text' ? 'Your answer points to the idea:' : 'That option rests on the idea:'}{' '}
            <span className="font-medium text-foreground">{humanize(misconception)}</span>
          </p>
        ) : null}
      </div>
    </div>
  )
}

const END_TEXT: Record<string, string> = {
  mastery: 'You have got the hang of all of these. Nicely done.',
  session_limit: 'That is enough for one sitting. Your progress is saved, so pick up again whenever you like.',
  student_left: 'The session timed out while waiting for your answer. Your progress is saved.',
}

export const EndCard: ToolCallMessagePartComponent = ({ args }) => {
  const { reason } = args as { reason: string }
  const { restart } = useTutor()
  return (
    <Card className="gap-3 py-4">
      <CardContent className="flex flex-col items-start gap-3 px-4">
        <p className="font-semibold">Session complete</p>
        <p className="text-sm text-muted-foreground">{END_TEXT[reason] ?? 'The session has finished.'}</p>
        <Button onClick={restart}>Start another session</Button>
      </CardContent>
    </Card>
  )
}

export const NoticeCard: ToolCallMessagePartComponent = ({ args }) => {
  const { text, problem } = args as { text: string; problem: boolean }
  const { restart } = useTutor()
  return (
    <div className={cn('flex gap-3 rounded-lg border p-4', problem ? 'border-destructive/40 bg-destructive/5' : 'bg-muted/40')}>
      {problem ? (
        <TriangleAlertIcon className="mt-0.5 size-5 shrink-0 text-destructive" />
      ) : (
        <InfoIcon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
      )}
      <div className="text-sm leading-relaxed">
        <p>{text}</p>
        {problem ? (
          <Button variant="outline" size="sm" className="mt-3" onClick={restart}>
            Start a new session
          </Button>
        ) : null}
      </div>
    </div>
  )
}
