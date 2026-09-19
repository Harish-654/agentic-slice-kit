import type { FC } from 'react'
import { BAND } from '@/design/status'
import { humanize } from '@/lib/format'
import type { RouteStep } from '@/lib/derive'
import { cn } from '@/lib/utils'

/** The route in the margin: a thin vertical trail, one dot per stop, the current one named in ink. */
export const RouteMini: FC<{ steps: RouteStep[] }> = ({ steps }) => (
  <ol className="relative flex flex-col gap-2.5 border-l border-dashed border-route/50 pl-4">
    {steps.map((s) => (
      <li key={s.concept} aria-current={s.current ? 'step' : undefined} className="relative flex items-baseline justify-between gap-2 text-sm">
        <span
          className={cn(
            'absolute top-1.5 -left-[21px] size-2.5 rounded-full border-2 border-background',
            s.band === 'got-it' ? 'bg-correct' : s.band === 'review' ? 'bg-caution' : s.band === 'learning' ? 'bg-twin' : 'bg-border',
            s.current && 'ring-2 ring-route/60',
          )}
          aria-hidden
        />
        <span className={cn('min-w-0 truncate', s.current ? 'font-semibold' : 'text-muted-foreground')}>{humanize(s.concept)}</span>
        <span className={cn('shrink-0 text-xs tabular-nums', BAND[s.band].text)}>{s.pct}%</span>
      </li>
    ))}
  </ol>
)
