import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { AwardIcon } from 'lucide-react'
import { Mark } from '@/components/shell/Mark'
import { Button } from '@/components/ui/button'
import { milestones, missionRoute } from '@/lib/derive'
import { useTutor } from '../context'

const END_TEXT: Record<string, string> = {
  revision_limit:
    'You tried the final check three times. The parts that tripped you up are marked in your progress, so come back to them whenever you like.',
  student_stopped: 'You stopped here. Your progress is saved, so pick up again whenever you like.',
  mastery: 'You have got the hang of all of these. Nicely done.',
  skipped: 'You skipped the topics your documents do not cover. Your progress is saved.',
  session_limit: 'That is enough for one sitting. Your progress is saved, so pick up again whenever you like.',
  student_left: 'The session timed out while waiting for your answer. Your progress is saved.',
}

/** The end of the session: what was said, and a plain tally worked out from what happened. */
export const EndCard: ToolCallMessagePartComponent = ({ args }) => {
  const { reason } = args as { reason: string }
  const { restart, snap } = useTutor()
  const steps = missionRoute(snap.progress)
  const done = steps.filter((s) => s.band === 'got-it').length
  const earned = milestones(snap).filter((k) => k.earned).length
  return (
    <div className="bg-card relative overflow-hidden rounded-2xl border p-6 shadow-[var(--shadow-page)]">
      <Mark className="text-route/15 absolute -top-6 -right-6 size-40" />
      <div className="relative flex flex-col items-start gap-3">
        <p className="eyebrow">Session complete</p>
        <p className="font-heading text-2xl font-semibold">{reason === 'mastery' ? 'Route complete' : 'Until next time'}</p>
        <p className="text-muted-foreground max-w-prose text-sm">{END_TEXT[reason] ?? 'The session has finished.'}</p>
        <p className="flex items-center gap-4 text-sm">
          <span>
            <span className="font-heading text-xl font-semibold tabular-nums">{done}</span>
            <span className="text-muted-foreground"> of {steps.length} stops at “got it”</span>
          </span>
          <span className="flex items-center gap-1.5">
            <AwardIcon className="text-highlight size-4" />
            <span className="tabular-nums">{earned}</span>
            <span className="text-muted-foreground">markers</span>
          </span>
        </p>
        <Button onClick={restart} size="lg">
          Start another session
        </Button>
      </div>
    </div>
  )
}
