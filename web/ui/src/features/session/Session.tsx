import { useCallback, useState, type FC } from 'react'
import { m } from 'motion/react'
import { ChevronDownIcon } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { MarginRail } from '@/components/shell/MarginRail'
import { TopBar } from '@/components/shell/TopBar'
import type { View } from '@/components/shell/ViewTabs'
import { Thread } from '@/components/tutor/Thread'
import { useTutor } from '@/components/tutor/context'
import { TwinView } from '@/components/twin/TwinView'
import { MissionRoute } from '@/components/missions/MissionRoute'
import { rise } from '@/design/motion'

const VIEW_IDS: View[] = ['study', 'twin', 'route']
const fromHash = (): View => {
  const h = window.location.hash.slice(1)
  return (VIEW_IDS as string[]).includes(h) ? (h as View) : 'study'
}

/** One session, three views. Study stays mounted while another view is open, so a half-written
 * answer or program is still there when the student comes back. */
export const Session: FC<{ onRestart: () => void }> = ({ onRestart }) => {
  const { snap } = useTutor()
  const [view, setView] = useState<View>(fromHash)
  const go = useCallback((v: View) => {
    setView(v)
    try {
      window.history.replaceState(null, '', v === 'study' ? window.location.pathname : `#${v}`)
    } catch {
      /* fine */
    }
  }, [])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <TopBar student={snap.student} view={view} onView={go} onRestart={onRestart} />

      <div id="panel-study" role="tabpanel" aria-labelledby="tab-study" hidden={view !== 'study'} className="flex min-h-0 flex-1 flex-col data-[hidden]:hidden">
        {/* On a phone the margin folds away above the thread. */}
        <Collapsible className="border-b lg:hidden">
          <CollapsibleTrigger className="flex w-full items-center justify-between px-4 py-2 text-sm font-medium">
            Route, ideas and sources
            <ChevronDownIcon className="size-4" />
          </CollapsibleTrigger>
          <CollapsibleContent className="max-h-[60vh] overflow-y-auto">
            <MarginRail onView={go} />
          </CollapsibleContent>
        </Collapsible>
        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1">
            <Thread />
          </main>
          <aside className="bg-card/50 hidden w-80 shrink-0 overflow-y-auto border-l lg:block">
            <MarginRail onView={go} />
          </aside>
        </div>
      </div>

      {view === 'twin' ? (
        <m.div key="twin" id="panel-twin" role="tabpanel" aria-labelledby="tab-twin" className="min-h-0 flex-1 overflow-y-auto" {...rise}>
          <TwinView />
        </m.div>
      ) : null}
      {view === 'route' ? (
        <m.div key="route" id="panel-route" role="tabpanel" aria-labelledby="tab-route" className="min-h-0 flex-1 overflow-y-auto" {...rise}>
          <MissionRoute onStudy={() => go('study')} />
        </m.div>
      ) : null}
    </div>
  )
}
