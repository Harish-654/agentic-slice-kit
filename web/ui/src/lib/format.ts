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
