// One map from "what state is this in" to "how does it look". Every place that colours a
// mastery band, a right/wrong answer or a source reads from here, so the app cannot drift.
import type { ConceptProgress } from '@/lib/api'

export type Band = 'new' | 'learning' | 'review' | 'got-it'

export const BAND: Record<Band, { label: string; chip: string; text: string; stroke: string; fill: string }> = {
  new: { label: 'New', chip: 'bg-muted text-muted-foreground', text: 'text-muted-foreground', stroke: 'stroke-border', fill: 'fill-muted-foreground' },
  learning: { label: 'Learning', chip: 'bg-twin/12 text-twin', text: 'text-twin', stroke: 'stroke-twin', fill: 'fill-twin' },
  review: { label: 'Review due', chip: 'bg-caution/15 text-caution', text: 'text-caution', stroke: 'stroke-caution', fill: 'fill-caution' },
  'got-it': { label: 'Got it', chip: 'bg-correct/14 text-correct', text: 'text-correct', stroke: 'stroke-correct', fill: 'fill-correct' },
}

export function band(c: ConceptProgress): Band {
  if (c.review_due) return 'review'
  if (c.mastered) return 'got-it'
  if (c.seen) return 'learning'
  return 'new'
}

/** Untouched topics read 0%: the model's starting guess is not something the student earned. */
export const pct = (c: ConceptProgress) => (c.seen ? Math.round(c.mastery * 100) : 0)
