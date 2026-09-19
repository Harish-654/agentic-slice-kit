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
}
