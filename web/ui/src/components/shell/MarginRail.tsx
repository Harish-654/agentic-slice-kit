import type { FC } from 'react'
import { ArrowRightIcon } from 'lucide-react'
import { RouteMini } from '@/components/atlas/RouteMini'
import { CodeCoach } from '@/components/tutor/CodeCoach'
import { Documents } from '@/components/tutor/Documents'
import { useTutor } from '@/components/tutor/context'
import { IdeasToWatch } from '@/components/twin/IdeasToWatch'
import { misconceptionMarks, missionRoute } from '@/lib/derive'
import type { View } from './ViewTabs'

const Section: FC<{ title: string; to?: { view: View; label: string }; onView?: (v: View) => void; children: React.ReactNode }> = ({ title, to, onView, children }) => (
  <section className="flex flex-col gap-3 border-b border-dashed p-5 last:border-0">
    <div className="flex items-baseline justify-between">
      <h3 className="eyebrow">{title}</h3>
      {to && onView ? (
        <button type="button" onClick={() => onView(to.view)} className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-xs">
          {to.label}
          <ArrowRightIcon className="size-3" />
        </button>
      ) : null}
    </div>
    {children}
  </section>
)

/** The margin of the study page: a glance at the route and the twin, plus the tools (documents, code).
 * The full versions are one tab away. */
export const MarginRail: FC<{ onView: (v: View) => void }> = ({ onView }) => {
  const { snap } = useTutor()
  const { progress } = snap
  return (
    <div className="flex flex-col">
      <Section title="Route" to={{ view: 'route', label: 'Open' }} onView={onView}>
        <RouteMini steps={missionRoute(progress)} />
      </Section>
      <Section title="Ideas to watch" to={{ view: 'twin', label: 'Your twin' }} onView={onView}>
        <IdeasToWatch marks={misconceptionMarks(progress)} limit={3} />
      </Section>
      <Section title="Sources">
        <Documents docs={progress.docs} useDocs={progress.use_docs} />
      </Section>
      <CodeCoach />
    </div>
  )
}
