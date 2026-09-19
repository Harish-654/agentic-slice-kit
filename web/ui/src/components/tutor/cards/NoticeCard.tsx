import { InfoIcon, TriangleAlertIcon } from 'lucide-react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { Button } from '@/components/ui/button'
import type { Gap } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useTutor } from '../context'

const GAP_CHOICE: Record<string, string> = { general: 'taught from general knowledge', skip: 'skipped' }

/** What to do when a topic is not in the documents. Never decided silently. */
function GapChoice({ gap }: { gap: Gap }) {
  const { snap, fallback } = useTutor()
  if (gap.answer) {
    return <p className="text-muted-foreground mt-2">You chose: {GAP_CHOICE[gap.answer]}.</p>
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
    <div className={cn('flex gap-3 rounded-2xl border p-4', problem ? 'border-destructive/40 bg-destructive/6' : 'bg-card border-dashed')}>
      {problem ? <TriangleAlertIcon className="text-destructive mt-0.5 size-5 shrink-0" /> : <InfoIcon className="text-twin mt-0.5 size-5 shrink-0" />}
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
