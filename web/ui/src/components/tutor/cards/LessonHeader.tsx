import { BookOpenIcon, FileTextIcon, SparklesIcon } from 'lucide-react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { STYLE_LABEL, humanize } from '@/lib/format'
import { cn } from '@/lib/utils'

/** The chapter opener: what is being taught, how, and where the facts came from. The source is
 * always shown: a lesson written from general knowledge is not checked against anything. */
export const LessonHeader: ToolCallMessagePartComponent = ({ args, toolCallId }) => {
  const { concept, style, source, citations } = args as {
    concept: string
    style: string
    source: 'general' | 'docs'
    citations: string[]
  }
  const docs = source === 'docs'
  return (
    // The id is what the thread scrolls to when a new lesson arrives.
    <div id={toolCallId} className="mb-4 scroll-mt-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="eyebrow">{STYLE_LABEL[style] ?? humanize(style)}</span>
        <span
          className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', docs ? 'bg-correct/14 text-correct' : 'bg-caution/15 text-caution')}
          title={docs ? undefined : 'Written by the AI from what it knows. It has not been checked against your documents.'}
        >
          {docs ? <FileTextIcon className="size-3" /> : <SparklesIcon className="size-3" />}
          {docs ? 'From your documents' : 'General knowledge'}
        </span>
      </div>
      <h2 className="mt-2 text-3xl leading-tight font-semibold">{humanize(concept)}</h2>
      {citations.length > 0 ? (
        <p className="text-muted-foreground mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <BookOpenIcon className="size-3" aria-hidden />
          {citations.map((c, i) => (
            <span key={c} className="font-mono">
              <sup className="mr-0.5">{i + 1}</sup>
              {c}
            </span>
          ))}
        </p>
      ) : null}
    </div>
  )
}
