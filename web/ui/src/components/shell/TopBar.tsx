import type { FC } from 'react'
import { PlusIcon } from 'lucide-react'
import { StreakChip } from '@/components/activity/StreakChip'
import { Button } from '@/components/ui/button'
import { Mark } from './Mark'
import { SignOutButton } from './SignOutButton'
import { ThemeToggle } from './ThemeToggle'
import { ViewTabs, type View } from './ViewTabs'

export const TopBar: FC<{ student: string; view: View; onView: (v: View) => void; onRestart: () => void }> = ({ student, view, onView, onRestart }) => (
  <header className="bg-background/85 sticky top-0 z-20 border-b backdrop-blur">
    <div className="flex items-center justify-between gap-3 px-4 py-2 sm:px-6">
      <div className="flex items-center gap-2.5">
        <Mark className="text-route" />
        <div className="leading-none">
          <p className="font-heading text-lg font-semibold">Strata</p>
          <p className="eyebrow mt-1 hidden text-[0.625rem] sm:block">Learning as {student}</p>
        </div>
      </div>
      <div className="hidden md:block">
        <ViewTabs view={view} onChange={onView} />
      </div>
      <div className="flex items-center gap-1">
        <StreakChip className="mr-1" />
        <ThemeToggle />
        <Button variant="ghost" size="sm" onClick={onRestart}>
          <PlusIcon />
          <span className="hidden sm:inline">New session</span>
          <span className="sr-only sm:hidden">New session</span>
        </Button>
        <SignOutButton />
      </div>
    </div>
    <div className="border-t px-2 md:hidden">
      <ViewTabs view={view} onChange={onView} />
    </div>
  </header>
)
