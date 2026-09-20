/** Layout and levels for the Learning Activity heatmap. Pure functions, so they are tested without a browser.
 *
 * The picture is a grid: one COLUMN per week and one ROW per weekday (Monday first), the last column being the
 * week that contains today. Every cell is one calendar day, coloured by how much the student did on it.
 * Dates are handled as UTC midnights of the student's own calendar date, so daylight saving never shifts a day. */

export const WEEKS = 53
export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const

/** A day with this many activities or more reaches level 1, 2, 3 and 4. Level 0 is an empty day. */
export const LEVEL_FROM = [1, 3, 6, 10] as const

export type Level = 0 | 1 | 2 | 3 | 4
export type Cell = { date: string; count: number; level: Level; today: boolean }
export type Grid = {
  /** weeks[column][row]. `null` is a day that has not happened yet. */
  weeks: (Cell | null)[][]
  /** Where each month starts, as a column index, for the labels above the grid. */
  months: { label: string; col: number }[]
}

const DAY = 86_400_000
const toMs = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}
const toIso = (ms: number) => new Date(ms).toISOString().slice(0, 10)
const weekday = (ms: number) => (new Date(ms).getUTCDay() + 6) % 7 // Monday = 0

export const levelFor = (count: number): Level => (count <= 0 ? 0 : (LEVEL_FROM.filter((t) => count >= t).length as Level))

/** The grid ending in the week that contains `today` (YYYY-MM-DD). `days` maps a date to its activity count. */
export function buildGrid(days: Record<string, number>, today: string, locale?: string): Grid {
  const end = toMs(today)
  const start = end - weekday(end) * DAY - (WEEKS - 1) * 7 * DAY // the Monday that opens the first column
  const weeks = Array.from({ length: WEEKS }, (_, w) =>
    Array.from({ length: 7 }, (_, r): Cell | null => {
      const ms = start + (w * 7 + r) * DAY
      if (ms > end) return null
      const date = toIso(ms)
      const count = days[date] ?? 0
      return { date, count, level: levelFor(count), today: ms === end }
    }),
  )
  const name = new Intl.DateTimeFormat(locale, { month: 'short', timeZone: 'UTC' })
  const months: Grid['months'] = []
  let previous = -1
  for (let w = 0; w < WEEKS; w++) {
    const month = new Date(start + w * 7 * DAY).getUTCMonth()
    if (month !== previous) months.push({ label: name.format(start + w * 7 * DAY), col: w })
    previous = month
  }
  // The first month is usually a stub of a week or two; a label squeezed against the next one is unreadable.
  if (months.length > 1 && months[1].col - months[0].col < 3) months.shift()
  return { weeks, months }
}

/** What the tooltip says: the count and the exact date. */
export function describeCell(cell: Cell, locale?: string): string {
  const when = new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(toMs(cell.date))
  const what = cell.count === 0 ? 'No activity' : cell.count === 1 ? '1 activity' : `${cell.count} activities`
  return `${what} · ${when}`
}

/** The last `n` days ending today, oldest first, for the check-in strip. */
export function recentDays(days: Record<string, number>, today: string, n = 7) {
  const end = toMs(today)
  return Array.from({ length: n }, (_, i) => {
    const ms = end - (n - 1 - i) * DAY
    const date = toIso(ms)
    return { date, count: days[date] ?? 0, label: WEEKDAYS[weekday(ms)][0], today: i === n - 1 }
  })
}
