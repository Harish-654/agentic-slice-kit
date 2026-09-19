import { useEffect, useId, useRef, useState } from 'react'
import type { ToolCallMessagePartComponent } from '@assistant-ui/react'
import { useIsDark } from '@/lib/theme'
import { cn } from '@/lib/utils'

const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'

/** Mermaid draws with its own palette; give it ours so a diagram looks like part of the page. */
const themeVariables = (dark: boolean) => {
  const css = getComputedStyle(document.documentElement)
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback
  return {
    fontFamily: "'Geist Variable', sans-serif",
    primaryColor: v('--card', dark ? '#2a2b3a' : '#fbf7ee'),
    primaryTextColor: v('--foreground', dark ? '#eee' : '#2a221a'),
    primaryBorderColor: v('--route', '#b5562d'),
    lineColor: v('--muted-foreground', '#777'),
    secondaryColor: v('--muted', '#eee'),
    tertiaryColor: v('--background', '#fff'),
  }
}

/** A diagram the model drew, set on the page as a numbered figure. Mermaid is loaded only when a
 * lesson has one, and a diagram that does not parse is dropped: a missing picture beats an error graphic. */
export const DiagramView: ToolCallMessagePartComponent = ({ args }) => {
  const { source } = args as { source: string }
  const host = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'hidden'>('loading')
  const id = useId().replace(/:/g, '')
  const dark = useIsDark()

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const { default: mermaid } = await import(/* @vite-ignore */ MERMAID)
        mermaid.initialize({ startOnLoad: false, suppressErrorRendering: true, theme: 'base', themeVariables: themeVariables(dark) })
        await mermaid.parse(source)
        const { svg } = await mermaid.render(`d${id}${dark ? 'd' : 'l'}`, source)
        if (cancelled || !host.current) return
        host.current.innerHTML = svg
        setState('ok')
      } catch {
        if (!cancelled) setState('hidden')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [source, id, dark])

  if (state === 'hidden') return null
  return (
    <figure className="my-5">
      <div ref={host} className={cn('bg-card flex justify-center overflow-x-auto rounded-xl border p-4', state === 'loading' && 'h-24 animate-pulse')} />
      <figcaption className="eyebrow mt-2 text-center">Figure</figcaption>
    </figure>
  )
}
