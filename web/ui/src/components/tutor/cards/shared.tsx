import type { FC, ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import type { Confidence } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useTutor } from '../context'

/** A question slip: the paper card every check sits on. */
export const Slip: FC<{ eyebrow: string; children: ReactNode; className?: string }> = ({ eyebrow, children, className }) => (
  <div className={cn('relative mt-5 rounded-2xl border bg-card p-5 shadow-[var(--shadow-page)]', className)}>
    <span className="bg-route/70 absolute inset-y-4 left-0 w-0.5 rounded-full" aria-hidden />
    <p className="eyebrow mb-1.5">{eyebrow}</p>
    {children}
  </div>
)

export const Code: FC<{ children: string }> = ({ children }) => (
  <pre className="bg-muted my-3 overflow-x-auto rounded-lg border px-4 py-3 font-mono text-sm leading-relaxed">
    <code>{children.trim()}</code>
  </pre>
)

const LEVELS: { value: Confidence; label: string }[] = [
  { value: 'low', label: 'Just guessing' },
  { value: 'medium', label: 'Fairly sure' },
  { value: 'high', label: 'Certain' },
]

/** How sure the student is. Asked every time and never defaulted: a default would be an answer
 * they did not give. Together with "I don't know", it sits inside the question it belongs to. */
export const AnswerActions: FC<{ withSubmit: boolean }> = ({ withSubmit }) => {
  const { picked, confidence, setConfidence, submitChoice, dontKnow } = useTutor()
  return (
    <div className="mt-5 flex flex-col gap-3 border-t border-dashed pt-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2" role="radiogroup" aria-label="How sure are you?">
        <span className="text-muted-foreground text-sm">How sure are you?</span>
        <div className="bg-muted/60 inline-flex rounded-lg border p-0.5">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              role="radio"
              aria-checked={confidence === l.value}
              onClick={() => setConfidence(l.value)}
              className={cn(
                'focus-visible:ring-ring/50 rounded-md px-3 py-1 text-sm transition-colors outline-none focus-visible:ring-3',
                confidence === l.value ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
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
      {withSubmit ? <p className="text-muted-foreground text-xs">Pick an option, say how sure you are, then submit.</p> : null}
    </div>
  )
}
