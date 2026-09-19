import { m } from 'motion/react'
import { CheckCircle2Icon, HelpCircleIcon, LightbulbIcon } from 'lucide-react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { stamp } from '@/design/motion'
import type { Confidence } from '@/lib/api'
import { humanize } from '@/lib/format'
import { cn } from '@/lib/utils'

const SURE: Record<Confidence, string> = { low: 'just guessing', medium: 'fairly sure', high: 'certain' }

/** Right or wrong, why, and what how sure they were says about it. Being certain and wrong is
 * the most useful thing to learn from; a right answer that was a guess has not been learnt yet.
 * It lands like a stamp on the page. */
export const FeedbackCard: ToolCallMessagePartComponent = ({ args }) => {
  const { correct, text, misconception, via, confidence, dont_know } = args as {
    correct: boolean
    text: string
    misconception: string | null
    via: 'mcq' | 'text' | 'code'
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
    <m.div
      {...stamp}
      className={cn(
        'flex gap-4 rounded-2xl border-2 p-4 shadow-[var(--shadow-page)]',
        dont_know ? 'bg-muted/50 border-border border-dashed' : correct ? 'border-correct/50 bg-correct/8' : 'border-caution/55 bg-caution/8',
      )}
    >
      <span
        className={cn(
          'mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-full border-2',
          dont_know ? 'text-muted-foreground border-border' : correct ? 'border-correct text-correct' : 'border-caution text-caution',
        )}
      >
        {dont_know ? <HelpCircleIcon className="size-5" /> : correct ? <CheckCircle2Icon className="size-5" /> : <LightbulbIcon className="size-5" />}
      </span>
      <div className="text-sm leading-relaxed">
        <p className="font-heading text-lg font-semibold">{dont_know ? 'No problem' : correct ? 'Correct' : 'Not quite'}</p>
        <p className="mt-0.5">{text}</p>
        {!correct && !dont_know && misconception ? (
          <p className="text-muted-foreground mt-2">
            {via === 'text' ? 'Your answer points to the idea:' : via === 'code' ? 'Your program points to the idea:' : 'That option rests on the idea:'}{' '}
            <span className="font-heading text-foreground font-medium italic">{humanize(misconception)}</span>
          </p>
        ) : null}
        {confidence && !dont_know ? (
          <p className="text-muted-foreground mt-2 text-xs">
            You said you were {SURE[confidence]}.{note ? ` ${note}` : ''}
          </p>
        ) : null}
      </div>
    </m.div>
  )
}
