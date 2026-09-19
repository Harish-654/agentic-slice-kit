import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import type { OpenQ } from '@/lib/api'
import { useTutor } from '../context'
import { AnswerActions, Code, Slip } from './shared'

/** A question the student answers by typing. The answer box lives in the thread's footer. */
export const OpenQuestionCard: ToolCallMessagePartComponent = ({ args }) => {
  const { open } = args as { open: OpenQ }
  const { canAnswer } = useTutor()
  return (
    <Slip eyebrow="Explain in your own words">
      <p className="font-heading text-lg leading-snug font-medium">{open.question}</p>
      {open.code ? <Code>{open.code}</Code> : null}
      <p className="text-muted-foreground mt-3 text-sm">
        {open.answered?.dont_know ? 'You said you did not know.' : open.answered ? 'You answered in your own words.' : 'Write your answer in the box below.'}
      </p>
      {!open.answered && canAnswer ? <AnswerActions withSubmit={false} /> : null}
    </Slip>
  )
}
