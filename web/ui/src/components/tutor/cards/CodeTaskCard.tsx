import { useState } from 'react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { Button } from '@/components/ui/button'
import type { CodeTaskQ } from '@/lib/api'
import { CodeEditor } from '../CodeEditor'
import { useTutor } from '../context'
import { AnswerActions, Slip } from './shared'

/** A question answered by writing a program. Run is free and ungraded; Submit runs it against
 * hidden tests and tells the tutor which idea a failing test points at. */
export const CodeTaskCard: ToolCallMessagePartComponent = ({ args }) => {
  const { task } = args as { task: CodeTaskQ }
  const { canAnswer, confidence, submitCode } = useTutor()
  const [code, setCode] = useState(task.starter)
  const [assisted, setAssisted] = useState(false)
  const open = !task.answered && canAnswer
  return (
    <Slip eyebrow="Write a program">
      <p className="font-heading text-lg leading-snug font-medium">{task.question}</p>
      {open ? (
        <div className="mt-3">
          <CodeEditor code={code} setCode={setCode} assisted={assisted} setAssisted={setAssisted}>
            <Button type="button" size="sm" disabled={!confidence || !code.trim()} onClick={() => submitCode(code, assisted)}>
              Submit program
            </Button>
          </CodeEditor>
          <p className="text-muted-foreground mt-2 text-xs">Run as often as you like. Say how sure you are to unlock Submit.</p>
          <AnswerActions withSubmit={false} />
        </div>
      ) : (
        <p className="text-muted-foreground mt-3 text-sm">
          {task.answered?.dont_know ? 'You said you did not know.' : task.answered ? 'You submitted a program.' : null}
        </p>
      )}
    </Slip>
  )
}
