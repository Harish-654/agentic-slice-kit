import type { FC } from 'react'
import { cn } from '@/lib/utils'

/** The atlas mark: a compass rose inside a ring. Drawn, not an icon-library glyph, so the brand is ours. */
export const Mark: FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 32 32" className={cn('size-7', className)} aria-hidden>
    <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M16 4 L19 16 L16 28 L13 16 Z" fill="currentColor" opacity="0.9" />
    <path d="M4 16 L16 13 L28 16 L16 19 Z" fill="currentColor" opacity="0.35" />
    <circle cx="16" cy="16" r="2" className="fill-background" />
  </svg>
)
