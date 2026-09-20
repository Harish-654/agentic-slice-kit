/** "default-is-copied" -> "Default is copied" */
export function humanize(tag: string): string {
  const s = tag.replace(/[-_]+/g, ' ').trim()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** Explanation styles, as the student should read them. */
export const STYLE_LABEL: Record<string, string> = {
  plain: 'Straight explanation',
  analogy: 'By analogy',
  worked_example: 'Worked example',
  diagram: 'With a diagram',
  probe: 'Quick check',
  final: 'Final check',
}

/** "today", "yesterday", "5 days ago", "2 months ago": how long since a moment given in epoch seconds. */
export function timeAgo(seconds: number, now: number = Date.now() / 1000): string {
  const days = Math.floor((now - seconds) / 86400)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  const months = Math.floor(days / 30)
  return months === 1 ? '1 month ago' : `${months} months ago`
}

/** What the page says while a lesson is being written, one line after another. They are status lines, not a log:
 * the work underneath is the model writing the lesson. */
export const THINKING = [
  'Analyzing your learning patterns…',
  'Identifying knowledge gaps…',
  'Connecting related concepts…',
  'Tailoring your learning path…',
  'Preparing your next challenge…',
] as const
export const THINKING_MS = 2400

/** The line to show after `elapsedMs` of waiting: each for THINKING_MS, then round again. */
export function thinkingAt(elapsedMs: number): string {
  return THINKING[Math.floor(Math.max(0, elapsedMs) / THINKING_MS) % THINKING.length]
}
