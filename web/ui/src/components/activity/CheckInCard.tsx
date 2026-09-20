import type { FC } from 'react'
import { CheckIcon } from 'lucide-react'
import { recentDays } from '@/lib/heatmap'
import { useActivity } from '@/lib/useActivity'
import { cn } from '@/lib/utils'
import { streakSentence } from './StreakChip'

/** Today's check-in. There is no button to press: answering a question or running some code IS the
 * check-in, so the streak can only be earned by learning something. This card says where things stand. */
export const CheckInCard: FC<{ className?: string }> = ({ className }) => {
  const { activity } = useActivity()
  if (!activity) return null
  const done = activity.checked_in_today
  const week = recentDays(activity.days, activity.today)
  return (
    <section aria-labelledby="checkin-title" className={cn('bg-card rounded-2xl border p-5 shadow-[var(--shadow-page)]', className)}>
      <h2 id="checkin-title" className="eyebrow">
        Today’s check-in
      </h2>
      <div className="mt-3 flex items-center gap-3">
        <span
          aria-hidden
          className={cn('flex size-10 shrink-0 items-center justify-center rounded-full border', done ? 'border-transparent bg-[var(--heat-3)] text-white' : 'border-dashed text-muted-foreground')}
        >
          {done ? <CheckIcon className="size-5" /> : '🔥'}
        </span>
        <div>
          <p className="font-heading text-lg leading-tight font-semibold">{done ? 'You have checked in' : 'Not checked in yet'}</p>
          <p className="text-muted-foreground text-sm">
            {done
              ? `${activity.today_count} ${activity.today_count === 1 ? 'thing' : 'things'} done today.`
              : 'Answer one question, or run some code, to check in.'}
          </p>
        </div>
      </div>

      <p className="mt-4 text-sm">
        <span aria-hidden>🔥</span> <span className="font-semibold tabular-nums">{activity.current_streak}</span>
        <span className="text-muted-foreground"> day streak · longest </span>
        <span className="font-semibold tabular-nums">{activity.longest_streak}</span>
      </p>
      <p className="text-muted-foreground mt-0.5 text-xs">{streakSentence(activity.current_streak, activity.at_risk)}</p>

      <ol className="mt-4 flex items-end justify-between gap-1" aria-label="The last seven days">
        {week.map((d) => (
          <li key={d.date} className="flex flex-col items-center gap-1" title={`${d.date}: ${d.count} ${d.count === 1 ? 'activity' : 'activities'}`}>
            <span
              aria-hidden
              className={cn('size-6 rounded-md', d.today && 'ring-2 ring-route ring-offset-2 ring-offset-card')}
              style={{ background: d.count > 0 ? 'var(--heat-3)' : 'var(--heat-0)' }}
            />
            <span className="text-muted-foreground text-[0.65rem]">{d.label}</span>
            <span className="sr-only">
              {d.date}: {d.count > 0 ? 'active' : 'nothing'}
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
