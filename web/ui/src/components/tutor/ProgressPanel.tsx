import type { FC } from 'react'
import { RefreshCwIcon, SparklesIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { humanize } from '@/lib/format'
import type { ConceptProgress, Progress as ProgressData } from '@/lib/api'

function state(c: ConceptProgress): { label: string; tone: string } {
  if (c.review_due) return { label: 'Review due', tone: 'bg-amber-500/15 text-amber-700 dark:text-amber-300' }
  if (c.mastered) return { label: 'Got it', tone: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' }
  if (c.seen) return { label: 'Learning', tone: 'bg-sky-500/15 text-sky-700 dark:text-sky-300' }
  return { label: 'New', tone: 'bg-muted text-muted-foreground' }
}

/** The learner model, made visible: how well the student knows each concept and
 * which wrong beliefs they keep coming back to. */
export const ProgressPanel: FC<{ progress: ProgressData; student: string }> = ({ progress, student }) => {
  const beliefs = progress.concepts.flatMap((c) => c.beliefs.map(([tag, n]) => ({ tag, n, concept: c.concept })))
  return (
    <div className="flex flex-col gap-5 p-5">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Learning as</p>
        <p className="mt-0.5 font-semibold">{student}</p>
        {progress.interests.length > 0 ? (
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
            <SparklesIcon className="size-3.5" />
            Analogies from {progress.interests.join(', ')}
          </p>
        ) : null}
      </div>

      <Separator />

      <div className="flex flex-col gap-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">What you know</p>
        {progress.concepts.map((c) => {
          const s = state(c)
          return (
            <div key={c.concept} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{humanize(c.concept)}</span>
                <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', s.tone)}>
                  {c.review_due ? <RefreshCwIcon className="size-3" /> : null}
                  {s.label}
                </span>
              </div>
              <div className="relative">
                <Progress value={c.seen ? Math.round(c.mastery * 100) : 0} aria-label={`${humanize(c.concept)} mastery`} />
                {/* where "got it" starts */}
                <span
                  className="absolute -top-0.5 h-2.5 w-px bg-foreground/40"
                  style={{ left: `${progress.threshold * 100}%` }}
                  aria-hidden
                />
              </div>
            </div>
          )
        })}
      </div>

      {beliefs.length > 0 ? (
        <>
          <Separator />
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Ideas to watch</p>
            <p className="text-xs text-muted-foreground">Wrong ideas your answers have pointed to. The tutor aims lessons at these.</p>
            <div className="flex flex-wrap gap-1.5">
              {beliefs.map((b) => (
                <Badge key={`${b.concept}-${b.tag}`} variant="outline" className="font-normal">
                  {humanize(b.tag)}
                  {b.n > 1 ? <span className="ml-1 text-muted-foreground">×{b.n}</span> : null}
                </Badge>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
