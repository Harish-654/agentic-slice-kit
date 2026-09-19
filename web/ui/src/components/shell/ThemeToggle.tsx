import type { FC } from 'react'
import { MonitorIcon, MoonIcon, SunIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTheme, type Theme } from '@/lib/theme'

const NEXT: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' }
const LABEL: Record<Theme, string> = { system: 'Following your system', light: 'Day paper', dark: 'Night study' }
const ICON = { system: MonitorIcon, light: SunIcon, dark: MoonIcon }

export const ThemeToggle: FC = () => {
  const { theme, setTheme } = useTheme()
  const Icon = ICON[theme]
  return (
    <Button variant="ghost" size="icon" onClick={() => setTheme(NEXT[theme])} aria-label={`Theme: ${LABEL[theme]}. Click to change.`} title={LABEL[theme]}>
      <Icon />
    </Button>
  )
}
