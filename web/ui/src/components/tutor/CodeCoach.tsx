import { useState, type FC } from 'react'
import { useCodeStatus } from '@/lib/useCodeStatus'
import { CodeEditor } from './CodeEditor'

/** Free play: run your own Python beside the lesson. The sandbox is on the server and fails
 * closed: if it cannot prove it is isolated, this says so and offers nothing to run. A failure
 * teaches the tutor which idea you are missing; a run that only works counts for nothing unless
 * you say what it should print. */
export const CodeCoach: FC = () => {
  const status = useCodeStatus()
  const [code, setCode] = useState('')
  const [assisted, setAssisted] = useState(false)

  if (!status) return null
  if (!status.available)
    return (
      <section className="border-t border-dashed p-5 text-xs text-muted-foreground">
        <h3 className="eyebrow mb-2">Code coach</h3>
        Running code is switched off on this server. {status.reason}
      </section>
    )
  return (
    <section className="space-y-3 p-5">
      <h3 className="eyebrow">Code coach</h3>
      <CodeEditor
        code={code}
        setCode={(c) => {
          setCode(c)
          if (!c.trim()) setAssisted(false)
        }}
        assisted={assisted}
        setAssisted={setAssisted}
        allowExpected
      />
    </section>
  )
}
