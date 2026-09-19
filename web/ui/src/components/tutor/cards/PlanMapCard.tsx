import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { MermaidView } from '../MermaidView'
import { Slip } from './shared'

/** The plan as a picture, shown once when a guided session starts: what the topic builds on, the
 * parts it will be taught in, and how much of it you already know. The margin keeps a live copy. */
export const PlanMapCard: ToolCallMessagePartComponent = ({ args }) => {
  const { flowchart } = args as { flowchart: string; mindmap: string }
  return (
    <Slip eyebrow="Your plan">
      <p className="text-muted-foreground mb-3 text-sm">
        What this topic builds on, and the parts we will cover. Green is what you know, amber is shaky, grey is new.
      </p>
      <MermaidView source={flowchart} className="flex justify-center overflow-x-auto" />
    </Slip>
  )
}
