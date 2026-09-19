import { useLayoutEffect, useRef, useState, type FC } from 'react'
import { m } from 'motion/react'
import { CheckIcon, FlagIcon, RefreshCwIcon } from 'lucide-react'
import { BAND } from '@/design/status'
import { dur, ease } from '@/design/motion'
import { humanize } from '@/lib/format'
import type { RouteStep, StepRole } from '@/lib/derive'
import { cn } from '@/lib/utils'
import { MasteryRing } from './MasteryRing'

const ROW = 116 // px between stops
const PAD = 48
const LEFT = 24 // percent across the map
const RIGHT = 76

const ROLE: Record<StepRole, string> = { prerequisite: 'Builds on', part: 'Part', final: 'Final check', topic: 'Topic' }

const pctX = (i: number) => (i % 2 === 0 ? LEFT : RIGHT)
const y = (i: number) => PAD + i * ROW

/** The route drawn as a trail winding down a sheet: one landmark per stop, ink laid along the
 * part already walked, dashes for the part still ahead. The stops are a real ordered list, so it
 * reads the same to a screen reader as it does to the eye. */
export const SkillMap: FC<{ steps: RouteStep[]; threshold: number }> = ({ steps, threshold }) => {
  const n = steps.length
  const height = PAD * 2 + Math.max(0, n - 1) * ROW
  // The trail is drawn in real pixels, so strokes are never stretched and the dash pattern is even.
  const box = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(0)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => setW(el.clientWidth))
    ro.observe(el)
    setW(el.clientWidth)
    return () => ro.disconnect()
  }, [])
  const px = (i: number) => (pctX(i) / 100) * w
  let d = ''
  steps.forEach((_, i) => {
    if (i === 0) d = `M ${px(0)} ${y(0)}`
    else d += ` C ${px(i - 1)} ${y(i - 1) + ROW * 0.55}, ${px(i)} ${y(i) - ROW * 0.55}, ${px(i)} ${y(i)}`
  })
  const now = steps.findIndex((s) => s.current)
  const walked = n < 2 ? 0 : (now === -1 ? n - 1 : now) / (n - 1)

  return (
    <div ref={box} className="relative mx-auto w-full max-w-2xl" style={{ height }}>
      <svg width={w} height={height} className="absolute inset-0 overflow-visible" aria-hidden>
        <path d={d} fill="none" strokeWidth="2" strokeDasharray="0.1 8" strokeLinecap="round" className="stroke-route/45" />
        <m.path
          d={d}
          fill="none"
          strokeWidth="2.5"
          strokeLinecap="round"
          className="stroke-route"
         
          initial={{ pathLength: 0 }}
          animate={{ pathLength: walked }}
          transition={{ duration: 1.1, ease }}
        />
      </svg>
      <ol className="absolute inset-0 m-0 list-none p-0">
        {steps.map((s, i) => {
          const left = pctX(i) < 50
          const Icon = s.band === 'got-it' ? CheckIcon : s.band === 'review' ? RefreshCwIcon : s.role === 'final' ? FlagIcon : null
          return (
            <m.li
              key={s.concept}
              className={cn('absolute flex h-16 w-[58%] items-center gap-3', left ? 'flex-row' : 'flex-row-reverse text-right')}
              // Margins, not a transform: Motion owns `transform` on this element.
              style={{ top: y(i), marginTop: -32, ...(left ? { left: `${pctX(i)}%`, marginLeft: -32 } : { right: `${100 - pctX(i)}%`, marginRight: -32 }) }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: dur.base, ease, delay: i * 0.07 }}
              aria-current={s.current ? 'step' : undefined}
            >
              <span className="relative shrink-0 rounded-full bg-background">
                {s.current ? (
                  <m.span
                    className="absolute -inset-1.5 rounded-full border border-route"
                    animate={{ scale: [1, 1.18, 1], opacity: [0.9, 0.2, 0.9] }}
                    transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                    aria-hidden
                  />
                ) : null}
                <MasteryRing value={s.pct / 100} band={s.band} threshold={threshold} size={64}>
                  {Icon ? <Icon className={cn('size-5', BAND[s.band].text)} /> : <span className="text-xs font-semibold tabular-nums">{s.pct}%</span>}
                </MasteryRing>
              </span>
              <span className="min-w-0">
                <span className="eyebrow block">{ROLE[s.role]}</span>
                <span className="font-heading block text-base leading-snug font-semibold">{humanize(s.concept)}</span>
                <span className={cn('mt-0.5 block text-xs', BAND[s.band].text)}>
                  {s.current ? 'You are here · ' : ''}
                  {BAND[s.band].label}
                  {s.beliefs > 0 ? ` · ${s.beliefs} slip${s.beliefs > 1 ? 's' : ''}` : ''}
                </span>
              </span>
            </m.li>
          )
        })}
      </ol>
    </div>
  )
}
