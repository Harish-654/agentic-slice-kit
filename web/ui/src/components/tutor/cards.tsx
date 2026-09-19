import { useEffect, useId, useRef, useState } from 'react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { BookOpenIcon, CheckCircle2Icon, FileTextIcon, HelpCircleIcon, InfoIcon, LightbulbIcon, SparklesIcon, TriangleAlertIcon, XCircleIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { humanize, STYLE_LABEL } from '@/lib/format'
import type { Answered, Confidence, Gap, OpenQ, Quiz } from '@/lib/api'
import { useTutor } from './context'

/** Concept, how it is being taught, and where the facts came from. The source is always
 * shown: a lesson written from general knowledge is not checked against anything. */
export const LessonHeader: ToolCallMessagePartComponent = ({ args, toolCallId }) => {
  const { concept, style, source, citations } = args as {
    concept: string
    style: string
    source: 'general' | 'docs'
    citations: string[]
  }
  return (
    // The id is what the thread scrolls to when a new lesson arrives.
    <div id={toolCallId} className="mb-3 flex scroll-mt-4 flex-wrap items-center gap-2">
      <h2 className="text-lg font-semibold tracking-tight">{humanize(concept)}</h2>
      <Badge variant="secondary">{STYLE_LABEL[style] ?? humanize(style)}</Badge>
      {source === 'docs' ? (
        <Badge variant="outline" className="gap-1 font-normal">
          <FileTextIcon className="size-3" />
          From your documents
        </Badge>
      ) : (
        <Badge
          variant="outline"
          className="gap-1 font-normal text-muted-foreground"
          title="Written by the AI from what it knows. It has not been checked against your documents."
        >
          <SparklesIcon className="size-3" />
          General knowledge
        </Badge>
      )}
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

const LEVELS: { value: Confidence; label: string }[] = [
  { value: 'low', label: 'Just guessing' },
  { value: 'medium', label: 'Fairly sure' },
  { value: 'high', label: 'Certain' },
]

/** How sure the student is. Asked every time and never defaulted: a default would be an answer
 * they did not give. Together with "I don't know", it sits inside the question it belongs to. */
function AnswerActions({ withSubmit }: { withSubmit: boolean }) {
  const { picked, confidence, setConfidence, submitChoice, dontKnow } = useTutor()
  return (
    <div className="mt-4 flex flex-col gap-3 border-t pt-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2" role="radiogroup" aria-label="How sure are you?">
        <span className="text-sm text-muted-foreground">How sure are you?</span>
        <div className="inline-flex rounded-lg border p-0.5">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              role="radio"
              aria-checked={confidence === l.value}
              onClick={() => setConfidence(l.value)}
              className={cn(
                'rounded-md px-3 py-1 text-sm transition-colors',
                confidence === l.value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between gap-3">
        <Button type="button" variant="outline" size="sm" onClick={dontKnow}>
          I don’t know
        </Button>
        {withSubmit ? (
          <Button type="button" disabled={picked === null || confidence === null} onClick={submitChoice}>
            Submit answer
          </Button>
        ) : null}
      </div>
      {withSubmit ? (
        <p className="text-xs text-muted-foreground">Pick an option, say how sure you are, then submit.</p>
      ) : null}
    </div>
  )
}

/** The check. Multiple choice by default; in text mode the answer goes in the box
 * below, so the card only shows the question. */
export const QuizCard: ToolCallMessagePartComponent = ({ args }) => {
  const { quiz } = args as { quiz: Quiz }
  const { canAnswer, picked, setPicked } = useTutor()
  const answered: Answered | null = quiz.answered
  const open = !answered && canAnswer

  return (
    <Card className="mt-4 gap-3 py-4">
      <CardContent className="px-4">
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Check yourself</p>
        <p className="font-medium leading-snug">{quiz.question}</p>
        {quiz.code ? <Code>{quiz.code}</Code> : null}

        {/* A multiple-choice card stays multiple choice whatever the toggle says: the
            toggle only decides what the NEXT question is. */}
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
                  onClick={() => setPicked(i)}
                  aria-pressed={open && picked === i}
                  className={cn(
                    'h-auto w-full justify-start gap-3 whitespace-normal px-3 py-2.5 text-left font-normal',
                    answered && isRight && 'border-emerald-500 bg-emerald-500/10 disabled:opacity-100',
                    answered && isChosen && !isRight && 'border-destructive bg-destructive/10 disabled:opacity-100',
                    answered && !isRight && !isChosen && 'disabled:opacity-45',
                    open && picked === i && 'border-foreground bg-muted ring-2 ring-foreground/20',
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
        {open ? <AnswerActions withSubmit /> : null}
      </CardContent>
    </Card>
  )
}

/** A question the student answers by typing. The answer box lives in the thread's footer. */
export const OpenQuestionCard: ToolCallMessagePartComponent = ({ args }) => {
  const { open } = args as { open: OpenQ }
  const { canAnswer } = useTutor()
  return (
    <Card className="mt-4 gap-3 py-4">
      <CardContent className="px-4">
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Explain in your own words
        </p>
        <p className="font-medium leading-snug">{open.question}</p>
        {open.code ? <Code>{open.code}</Code> : null}
        <p className="mt-3 text-sm text-muted-foreground">
          {open.answered?.dont_know
            ? 'You said you did not know.'
            : open.answered
              ? 'You answered in your own words.'
              : 'Write your answer in the box below.'}
        </p>
        {!open.answered && canAnswer ? <AnswerActions withSubmit={false} /> : null}
      </CardContent>
    </Card>
  )
}

const SURE: Record<Confidence, string> = { low: 'just guessing', medium: 'fairly sure', high: 'certain' }

/** Right or wrong, why, and what how sure they were says about it. Being certain and wrong is
 * the most useful thing to learn from; a right answer that was a guess has not been learnt yet. */
export const FeedbackCard: ToolCallMessagePartComponent = ({ args }) => {
  const { correct, text, misconception, via, confidence, dont_know } = args as {
    correct: boolean
    text: string
    misconception: string | null
    via: 'mcq' | 'text'
    confidence: Confidence | null
    dont_know: boolean
  }
  const note = dont_know
    ? null
    : !correct && confidence === 'high'
      ? 'You were certain, so this is the idea most worth fixing.'
      : correct && confidence === 'low'
        ? 'Right, though you were only guessing, so it will come back for more practice.'
        : null
  return (
    <div
      className={cn(
        'flex gap-3 rounded-lg border p-4',
        dont_know ? 'bg-muted/40' : correct ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-amber-500/40 bg-amber-500/5',
      )}
    >
      {dont_know ? (
        <HelpCircleIcon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
      ) : correct ? (
        <CheckCircle2Icon className="mt-0.5 size-5 shrink-0 text-emerald-600" />
      ) : (
        <LightbulbIcon className="mt-0.5 size-5 shrink-0 text-amber-600" />
      )}
      <div className="text-sm leading-relaxed">
        <p className="font-semibold">{dont_know ? 'No problem' : correct ? 'Correct' : 'Not quite'}</p>
        <p className="mt-0.5">{text}</p>
        {!correct && !dont_know && misconception ? (
          <p className="mt-2 text-muted-foreground">
            {via === 'text' ? 'Your answer points to the idea:' : 'That option rests on the idea:'}{' '}
            <span className="font-medium text-foreground">{humanize(misconception)}</span>
          </p>
        ) : null}
        {confidence && !dont_know ? (
          <p className="mt-2 text-xs text-muted-foreground">
            You said you were {SURE[confidence]}.{note ? ` ${note}` : ''}
          </p>
        ) : null}
      </div>
    </div>
  )
}

const END_TEXT: Record<string, string> = {
  mastery: 'You have got the hang of all of these. Nicely done.',
  skipped: 'You skipped the topics your documents do not cover. Your progress is saved.',
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

const GAP_CHOICE: Record<string, string> = { general: 'taught from general knowledge', skip: 'skipped' }

/** What to do when a topic is not in the documents. Never decided silently. */
function GapChoice({ gap }: { gap: Gap }) {
  const { snap, fallback } = useTutor()
  if (gap.answer) {
    return <p className="mt-2 text-muted-foreground">You chose: {GAP_CHOICE[gap.answer]}.</p>
  }
  const ready = snap.status === 'waiting_choice'
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <Button size="sm" disabled={!ready} onClick={() => fallback('general')}>
        Teach it from general knowledge
      </Button>
      <Button size="sm" variant="outline" disabled={!ready} onClick={() => fallback('skip')}>
        Skip this topic
      </Button>
    </div>
  )
}

export const NoticeCard: ToolCallMessagePartComponent = ({ args }) => {
  const { text, problem, gap } = args as { text: string; problem: boolean; gap: Gap | null }
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
        {gap ? <GapChoice gap={gap} /> : null}
        {problem ? (
          <Button variant="outline" size="sm" className="mt-3" onClick={restart}>
            Start a new session
          </Button>
        ) : null}
      </div>
    </div>
  )
}
