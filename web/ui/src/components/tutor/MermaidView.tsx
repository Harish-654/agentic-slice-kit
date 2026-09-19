import { useEffect, useId, useRef, useState, type FC } from 'react'
import { cn } from '@/lib/utils'

const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'
let renders = 0 // Mermaid wants a fresh element id for every render, including a re-render of the same view

/** Draws Mermaid source. The library is fetched only when something needs drawing, the source is
 * parse-checked first, and one that does not parse is dropped: a missing picture beats an error
 * graphic. The server has already refused any kind of diagram it does not allow. */
export const MermaidView: FC<{ source: string; className?: string }> = ({ source, className }) => {
  const host = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'hidden'>('loading')
  const id = useId().replace(/:/g, '')

  useEffect(() => {
    let cancelled = false
    setState('loading')
    ;(async () => {
      try {
        const { default: mermaid } = await import(/* @vite-ignore */ MERMAID)
        const dark = document.documentElement.classList.contains('dark')
        mermaid.initialize({ startOnLoad: false, suppressErrorRendering: true, theme: dark ? 'dark' : 'default' })
        await mermaid.parse(source)
        const { svg } = await mermaid.render(`d${id}-${++renders}`, source)
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
  }, [source, id])

  if (state === 'hidden') return null
  return <div ref={host} className={cn(className, state === 'loading' && 'h-24 animate-pulse')} />
}
