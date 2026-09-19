import { CheckCircle2Icon, XCircleIcon } from 'lucide-react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import type { Answered, Quiz } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useTutor } from '../context'
import { AnswerActions, Code, Slip } from './shared'

const LETTERS = 'ABCDE'

/** The check. Multiple choice by default; in text mode the answer goes in the box
 * below, so the card only shows the question. */
export const QuizCard: ToolCallMessagePartComponent = ({ args }) => {
  const { quiz } = args as { quiz: Quiz }
  const { canAnswer, picked, setPicked } = useTutor()
  const answered: Answered | null = quiz.answered
  const open = !answered && canAnswer

  return (
    <Slip eyebrow="Check yourself">
      <p className="font-heading text-lg leading-snug font-medium">{quiz.question}</p>
      {quiz.code ? <Code>{quiz.code}</Code> : null}

      {/* A multiple-choice card stays multiple choice whatever the toggle says: the
          toggle only decides what the NEXT question is. */}
      <ul className="mt-4 flex flex-col gap-2">
        {quiz.options.map((o, i) => {
          const isChosen = answered?.chosen === i
          const isRight = answered?.correct_index === i
          const on = open && picked === i
          return (
            <li key={i}>
              <button
                type="button"
                disabled={!open}
                onClick={() => setPicked(i)}
                aria-pressed={on}
                className={cn(
                  'focus-visible:ring-ring/50 flex w-full items-start gap-3 rounded-xl border bg-background/60 px-3.5 py-3 text-left text-[0.95rem] transition-all outline-none focus-visible:ring-3',
                  open && 'hover:border-route/60 hover:bg-route/5 active:translate-y-px',
                  on && 'border-route bg-route/8 ring-route/25 ring-2',
                  answered && isRight && 'border-correct bg-correct/10',
                  answered && isChosen && !isRight && 'border-destructive bg-destructive/8',
                  answered && !isRight && !isChosen && 'opacity-50',
                )}
              >
                <span
                  className={cn(
                    'mt-px flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs font-medium',
                    on && 'border-route bg-route text-background',
                  )}
                >
                  {answered && isRight ? (
                    <CheckCircle2Icon className="text-correct size-4" />
                  ) : answered && isChosen ? (
                    <XCircleIcon className="text-destructive size-4" />
                  ) : (
                    LETTERS[i]
                  )}
                </span>
                <span className="pt-px">{o.text}</span>
              </button>
            </li>
          )
        })}
      </ul>
      {open ? <AnswerActions withSubmit /> : null}
    </Slip>
  )
}
