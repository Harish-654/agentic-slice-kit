import type { FC, ReactNode } from 'react'
import { m } from 'motion/react'
import { BAND, type Band } from '@/design/status'
import { dur, ease } from '@/design/motion'
import { cn } from '@/lib/utils'

const R = 20

/** Mastery drawn as ink filling a ring. The small tick marks the “got it” line, so the ring shows
 * not only how far the student is but how far there is to go. */
export const MasteryRing: FC<{
  value: number
  band: Band
  threshold?: number
  size?: number
  stroke?: number
  className?: string
  children?: ReactNode
}> = ({ value, band, threshold, size = 56, stroke = 3.5, className, children }) => {
  const v = Math.min(1, Math.max(0, value))
  const angle = threshold === undefined ? null : threshold * 2 * Math.PI - Math.PI / 2
  return (
    <span className={cn('relative inline-flex shrink-0 items-center justify-center', className)} style={{ width: size, height: size }}>
      <svg viewBox="0 0 48 48" width={size} height={size} className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx="24" cy="24" r={R} fill="none" strokeWidth={stroke} className="stroke-border" />
        <m.circle
          cx="24"
          cy="24"
          r={R}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className={BAND[band].stroke}
          initial={{ pathLength: 0 }}
          animate={{ pathLength: v }}
          transition={{ duration: dur.slow, ease }}
        />
      </svg>
      {angle !== null ? (
        <svg viewBox="-24 -24 48 48" width={size} height={size} className="absolute inset-0" aria-hidden>
          <line
            x1={(R - 4) * Math.cos(angle)}
            y1={(R - 4) * Math.sin(angle)}
            x2={(R + 4) * Math.cos(angle)}
            y2={(R + 4) * Math.sin(angle)}
            className="stroke-foreground/50"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      ) : null}
      <span className="relative flex items-center justify-center">{children}</span>
    </span>
  )
}
