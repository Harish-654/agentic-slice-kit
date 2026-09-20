import type { FC, KeyboardEvent } from 'react'
import { m } from 'motion/react'
import { GraduationCapIcon, LayoutDashboardIcon } from 'lucide-react'
import { spring } from '@/design/motion'
import { cn } from '@/lib/utils'

export type Home = 'learn' | 'dashboard'
const TABS: { id: Home; label: string; hint: string; Icon: typeof GraduationCapIcon }[] = [
  { id: 'learn', label: 'Learn', hint: 'Start something new', Icon: GraduationCapIcon },
  { id: 'dashboard', label: 'Dashboard', hint: 'What you have learnt so far', Icon: LayoutDashboardIcon },
]

/** The start screen's two tabs, styled like the session's view tabs. Arrow keys move between them, and only the
 * selected tab is in the tab order, as a tab list should be. */
export const HomeTabs: FC<{ tab: Home; onChange: (t: Home) => void }> = ({ tab, onChange }) => {
  const move = (e: KeyboardEvent) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return
    e.preventDefault()
    const focused = TABS.findIndex((t) => `home-tab-${t.id}` === document.activeElement?.id)
    const i = focused >= 0 ? focused : TABS.findIndex((t) => t.id === tab)      // from the tab that has focus
    const next = e.key === 'Home' ? 0 : e.key === 'End' ? TABS.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + TABS.length) % TABS.length
    onChange(TABS[next].id)
    document.getElementById(`home-tab-${TABS[next].id}`)?.focus()
  }
  return (
    <div role="tablist" aria-label="Start" onKeyDown={move} className="mt-2 flex items-center gap-1 border-b">
      {TABS.map(({ id, label, hint, Icon }) => {
        const on = tab === id
        return (
          <button
            key={id}
            type="button"
            role="tab"
            id={`home-tab-${id}`}
            aria-selected={on}
            aria-controls={`panel-${id}`}
            tabIndex={on ? 0 : -1}
            title={hint}
            onClick={() => onChange(id)}
            className={cn(
              'relative flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
              on ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon className="size-4" />
            {label}
            {on ? <m.span layoutId="home-underline" transition={spring} className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-route" /> : null}
          </button>
        )
      })}
    </div>
  )
}
