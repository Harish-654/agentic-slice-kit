import type { FC } from 'react'
import { cn } from '@/lib/utils'
import { useActivity } from '@/lib/useActivity'

/** What the streak means, in words, for the tooltip and for screen readers. */
export function streakSentence(streak: number, atRisk: boolean): string {
  if (streak === 0) return 'No streak yet. Answer a question today to start one.'
  const days = `${streak}-day streak.`
  return atRisk ? `${days} Answer a question today to keep it.` : `${days} You have checked in today.`
}

/** The 🔥 streak: how many days in a row the student has done something real. Dimmed at zero, lit once
 * there is a streak, and pulsing gently (unless the student prefers no motion) when it is alive but today has
 * not been checked in yet. */
export const StreakChip: FC<{ className?: string }> = ({ className }) => {
  const { activity } = useActivity()
  if (!activity) return null
  const n = activity.current_streak
  const say = streakSentence(n, activity.at_risk)
  return (
    <span
      title={say}
      aria-label={say}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm font-medium tabular-nums',
        n > 0 ? 'border-route/40 bg-route/10' : 'text-muted-foreground',
        className,
      )}
    >
      <span aria-hidden className={cn(n === 0 && 'opacity-50 grayscale')}>
        🔥
      </span>
      <span aria-hidden>{n}</span>
      {activity.at_risk ? <span aria-hidden className="bg-route size-1.5 rounded-full motion-safe:animate-pulse" /> : null}
    </span>
  )
}
