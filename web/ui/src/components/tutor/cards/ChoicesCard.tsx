import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { Button } from '@/components/ui/button'
import type { Choice } from '@/lib/api'
import { useTutor } from '../context'

const CHOICE_LABEL: Record<Choice, string> = {
  quiz: 'Quiz me',
  example: 'Show me an example',
  more_detail: 'More detail',
  deeper: 'Go deeper',
  skip: 'Skip this part',
  stop: 'Stop for now',
}

/** Guided sessions: after an explanation the student decides what happens next. The tutor has
 * already written the check, so "Quiz me" is instant. Once they have picked, it reads as a
 * plain line instead of buttons. */
export const ChoicesCard: ToolCallMessagePartComponent = ({ args }) => {
  const { options, chosen } = args as { options: Choice[]; chosen: Choice | null }
  const { snap, choose } = useTutor()
  if (chosen) return <p className="text-muted-foreground font-heading text-sm italic">You chose: {CHOICE_LABEL[chosen]}.</p>
  const ready = snap.status === 'waiting_choice'
  return (
    <div className="mt-2 flex flex-col gap-2">
      <p className="eyebrow">What next?</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label="What next?">
        {options.map((o) => (
          <Button key={o} type="button" size="lg" variant={o === 'quiz' ? 'default' : 'outline'} disabled={!ready} onClick={() => choose(o)}>
            {CHOICE_LABEL[o]}
          </Button>
        ))}
      </div>
    </div>
  )
}
