// Light, dark, or follow the system. shadcn switches on a `dark` class on <html>.
import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark' | 'system'
const KEY = 'tutor.theme'

// Storage can be unavailable (private windows); the app must work without it.
function stored(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

const media = () => window.matchMedia('(prefers-color-scheme: dark)')

export function applyTheme(theme: Theme = stored()) {
  const dark = theme === 'system' ? media().matches : theme === 'dark'
  document.documentElement.classList.toggle('dark', dark)
}

/** Sets the class now and keeps following the system while the choice is "system". */
export function initTheme() {
  applyTheme()
  media().addEventListener('change', () => applyTheme())
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(stored)
  const setTheme = useCallback((t: Theme) => {
    try {
      if (t === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, t)
    } catch {
      /* fine */
    }
    setThemeState(t)
    applyTheme(t)
  }, [])
  return { theme, setTheme }
}

/** True while the page is dark; re-renders when the theme changes (for things drawn once, like diagrams). */
export function useIsDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const el = document.documentElement
    const obs = new MutationObserver(() => setDark(el.classList.contains('dark')))
    obs.observe(el, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return dark
}
