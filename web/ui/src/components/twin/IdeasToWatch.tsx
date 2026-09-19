import type { FC } from 'react'
import { m } from 'motion/react'
import { item, stagger } from '@/design/motion'
import { humanize } from '@/lib/format'
import type { Mark } from '@/lib/derive'

/** A tally: one stroke per time an answer pointed at the idea. */
const Tally: FC<{ n: number }> = ({ n }) => (
  <span className="text-destructive/80 font-mono text-sm tracking-tighter select-none" aria-label={`${n} time${n > 1 ? 's' : ''}`}>
    {'|'.repeat(Math.min(n, 5))}
    {n > 5 ? ` ×${n}` : ''}
  </span>
)

/** The wrong ideas the answers have pointed to, written like notes in a margin. The tutor aims
 * its next lessons at these. */
export const IdeasToWatch: FC<{ marks: Mark[]; limit?: number }> = ({ marks, limit }) => {
  const shown = limit ? marks.slice(0, limit) : marks
  if (marks.length === 0)
    return <p className="text-muted-foreground text-sm">None yet. When an answer points to a wrong idea, the tutor writes it down here and teaches at it.</p>
  return (
    <m.ul variants={stagger(0.05)} initial="initial" animate="animate" className="flex flex-col gap-2">
      {shown.map((k) => (
        <m.li key={k.tag} variants={item} className="flex items-baseline justify-between gap-3 border-b border-dashed pb-1.5 last:border-0">
          <span className="font-heading text-[0.95rem] italic">{humanize(k.tag)}</span>
          <Tally n={k.count} />
        </m.li>
      ))}
      {limit && marks.length > limit ? <li className="text-muted-foreground text-xs">and {marks.length - limit} more in your Twin</li> : null}
    </m.ul>
  )
}
