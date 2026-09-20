import { describe, expect, it } from 'vitest'
import { WEEKS, buildGrid, describeCell, levelFor, recentDays } from './heatmap'

const dow = (iso: string) => (new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7 // Monday = 0
const cells = (g: ReturnType<typeof buildGrid>) => g.weeks.flat().filter((c): c is NonNullable<typeof c> => c !== null)

describe('levelFor', () => {
  it('maps counts to five levels, an empty day being 0', () => {
    expect([0, 1, 2, 3, 5, 6, 9, 10, 400].map(levelFor)).toEqual([0, 1, 1, 2, 2, 3, 3, 4, 4])
    expect(levelFor(-3)).toBe(0)
  })
})

describe('buildGrid', () => {
  const today = '2026-09-21' // a Monday
  const g = buildGrid({}, today, 'en-US')

  it('is 53 weekly columns of 7 weekday rows, Monday first', () => {
    expect(g.weeks).toHaveLength(WEEKS)
    expect(g.weeks.every((w) => w.length === 7)).toBe(true)
    expect(dow(g.weeks[0][0]!.date)).toBe(0) // the first cell is a Monday
    expect(g.weeks.every((w) => w[0] === null || dow(w[0].date) === 0)).toBe(true)
  })

  it('ends in the week that holds today, with the days after it blank', () => {
    const last = g.weeks[WEEKS - 1]
    expect(last[0]?.date).toBe('2026-09-21') // today is a Monday: the last column has just one day
    expect(last.slice(1).every((c) => c === null)).toBe(true)
    expect(cells(g).filter((c) => c.today).map((c) => c.date)).toEqual(['2026-09-21'])
  })

  it('fills the whole last column when today is a Sunday', () => {
    const sunday = buildGrid({}, '2026-09-27')
    expect(sunday.weeks[WEEKS - 1].every((c) => c !== null)).toBe(true)
    expect(sunday.weeks[WEEKS - 1][6]?.today).toBe(true)
  })

  it('has one cell per day with no gaps or repeats, the oldest a full 52 weeks back', () => {
    const all = cells(g).map((c) => c.date)
    expect(new Set(all).size).toBe(all.length)
    expect(all).toEqual([...all].sort())
    expect(all[0]).toBe('2025-09-22') // 52 weeks before this week's Monday
    expect(all.length).toBe(52 * 7 + 1)
  })

  it('puts each count in its own day, with the right level', () => {
    const busy = buildGrid({ '2026-09-21': 12, '2026-09-19': 3, '2026-01-01': 1, '2020-01-01': 99 }, today)
    const by = Object.fromEntries(cells(busy).map((c) => [c.date, c]))
    expect(by['2026-09-21']).toMatchObject({ count: 12, level: 4, today: true })
    expect(by['2026-09-19']).toMatchObject({ count: 3, level: 2 })
    expect(by['2026-01-01']).toMatchObject({ count: 1, level: 1 })
    expect(by['2026-09-20']).toMatchObject({ count: 0, level: 0 })
    expect(by['2020-01-01']).toBeUndefined() // older than the window: not drawn
  })

  it('labels each month once, in order, never crowding two labels together', () => {
    const cols = g.months.map((m) => m.col)
    expect(cols).toEqual([...cols].sort((a, b) => a - b))
    expect(cols.every((c, i) => i === 0 || c - cols[i - 1] >= 3)).toBe(true)
    expect(g.months.map((m) => m.label)).toEqual(['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'])
  })

  it('keeps a leap day and is not thrown by month ends', () => {
    expect(cells(buildGrid({}, '2028-03-05')).some((c) => c.date === '2028-02-29')).toBe(true)
    const y = cells(buildGrid({}, '2026-01-01')).map((c) => c.date)
    expect(y).toContain('2025-12-31')
  })
})

describe('describeCell', () => {
  it('says the exact date and the count', () => {
    expect(describeCell({ date: '2026-09-21', count: 3, level: 2, today: false }, 'en-US')).toBe('3 activities · Mon, Sep 21, 2026')
    expect(describeCell({ date: '2026-09-21', count: 1, level: 1, today: false }, 'en-US')).toBe('1 activity · Mon, Sep 21, 2026')
    expect(describeCell({ date: '2026-02-01', count: 0, level: 0, today: false }, 'en-US')).toBe('No activity · Sun, Feb 1, 2026')
  })
})

describe('recentDays', () => {
  it('is the last seven days ending today, oldest first', () => {
    const r = recentDays({ '2026-09-21': 2, '2026-09-19': 5 }, '2026-09-21')
    expect(r.map((d) => d.date)).toEqual(['2026-09-15', '2026-09-16', '2026-09-17', '2026-09-18', '2026-09-19', '2026-09-20', '2026-09-21'])
    expect(r.map((d) => d.label).join('')).toBe('TWTFSSM')
    expect(r.filter((d) => d.count > 0).map((d) => d.date)).toEqual(['2026-09-19', '2026-09-21'])
    expect(r.filter((d) => d.today)).toHaveLength(1)
  })
})
