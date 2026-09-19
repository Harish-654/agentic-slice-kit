import { useEffect, useId, useRef, useState, type FC } from 'react'
import { useIsDark } from '@/lib/theme'
import { cn } from '@/lib/utils'

const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'
let renders = 0 // Mermaid wants a fresh element id for every render, including a re-render of the same view

/** Mermaid's colour maths cannot read oklch(), which is what our tokens are written in, so each
 * colour is painted onto a one-pixel canvas and read back as plain RGB. */
let pixel: CanvasRenderingContext2D | null | undefined
const toRgb = (css: string, fallback: string) => {
  if (pixel === undefined) pixel = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
  if (!pixel || !css) return fallback
  pixel.clearRect(0, 0, 1, 1)
  pixel.fillStyle = '#000'
  pixel.fillStyle = css
  pixel.fillRect(0, 0, 1, 1)
  const [r, g, b] = pixel.getImageData(0, 0, 1, 1).data
  return `rgb(${r}, ${g}, ${b})`
}

/** Mermaid draws with its own palette; give it ours so a diagram looks like part of the page. */
const themeVariables = (dark: boolean) => {
  const css = getComputedStyle(document.documentElement)
  const v = (name: string, fallback: string) => toRgb(css.getPropertyValue(name).trim(), fallback)
  return {
    fontFamily: "'Geist Variable', sans-serif",
    primaryColor: v('--card', dark ? '#2a2b3a' : '#fbf7ee'),
    primaryTextColor: v('--foreground', dark ? '#eeeeee' : '#2a221a'),
    primaryBorderColor: v('--route', '#b5562d'),
    lineColor: v('--muted-foreground', '#777777'),
    secondaryColor: v('--muted', '#eeeeee'),
    tertiaryColor: v('--background', '#ffffff'),
  }
}

/** Draws Mermaid source. The library is fetched only when something needs drawing, the source is
 * parse-checked first, and one that does not parse is dropped: a missing picture beats an error
 * graphic. The server has already refused any kind of diagram it does not allow. It redraws when
 * the theme changes, so a diagram never stays in the wrong palette. */
export const MermaidView: FC<{ source: string; className?: string }> = ({ source, className }) => {
  const host = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'hidden'>('loading')
  const id = useId().replace(/:/g, '')
  const dark = useIsDark()

  useEffect(() => {
    let cancelled = false
    setState('loading')
    ;(async () => {
      try {
        const { default: mermaid } = await import(/* @vite-ignore */ MERMAID)
        mermaid.initialize({ startOnLoad: false, suppressErrorRendering: true, theme: 'base', themeVariables: themeVariables(dark) })
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
  }, [source, id, dark])

  if (state === 'hidden') return null
  return <div ref={host} className={cn(className, state === 'loading' && 'h-24 animate-pulse')} />
}
