import type { FC } from 'react'
import { m } from 'motion/react'
import { BookOpenIcon, BrainCircuitIcon, RouteIcon } from 'lucide-react'
import { spring } from '@/design/motion'
import { cn } from '@/lib/utils'

export type View = 'study' | 'twin' | 'route'
export const VIEWS: { id: View; label: string; hint: string; Icon: typeof BookOpenIcon }[] = [
  { id: 'study', label: 'Study', hint: 'The lesson in front of you', Icon: BookOpenIcon },
  { id: 'twin', label: 'Twin', hint: 'What the tutor believes about you', Icon: BrainCircuitIcon },
  { id: 'route', label: 'Route', hint: 'Where you are going', Icon: RouteIcon },
]

/** Three views of one session. The underline glides between tabs (a shared layout animation). */
export const ViewTabs: FC<{ view: View; onChange: (v: View) => void }> = ({ view, onChange }) => (
  <div role="tablist" aria-label="Views" className="flex items-center gap-1">
    {VIEWS.map(({ id, label, hint, Icon }) => {
      const on = view === id
      return (
        <button
          key={id}
          type="button"
          role="tab"
          id={`tab-${id}`}
          aria-selected={on}
          aria-controls={`panel-${id}`}
          title={hint}
          onClick={() => onChange(id)}
          className={cn(
            'relative flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
            on ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Icon className="size-4" />
          {label}
          {on ? <m.span layoutId="view-underline" transition={spring} className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-route" /> : null}
        </button>
      )
    })}
  </div>
)
