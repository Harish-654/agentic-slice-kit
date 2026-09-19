import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { MermaidView } from '../MermaidView'

/** A diagram the model drew in a lesson (a flowchart, class, sequence or state diagram), set on the
 * page as a figure. The drawing, and dropping one that does not parse, is MermaidView's job. */
export const DiagramView: ToolCallMessagePartComponent = ({ args }) => {
  const { source } = args as { source: string }
  return (
    <figure className="my-5">
      <MermaidView source={source} className="bg-card flex justify-center overflow-x-auto rounded-xl border p-4" />
      <figcaption className="eyebrow mt-2 text-center">Figure</figcaption>
    </figure>
  )
}
