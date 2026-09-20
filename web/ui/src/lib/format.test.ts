import { describe, expect, it } from 'vitest'
import { THINKING, THINKING_MS, humanize, thinkingAt, timeAgo } from './format'

const NOW = 1_800_000_000
const DAY = 86400

describe('timeAgo', () => {
  it('reads in days, then months', () => {
    expect(timeAgo(NOW - 3600, NOW)).toBe('today')
    expect(timeAgo(NOW - DAY - 60, NOW)).toBe('yesterday')
    expect(timeAgo(NOW - 5 * DAY, NOW)).toBe('5 days ago')
    expect(timeAgo(NOW - 29 * DAY, NOW)).toBe('29 days ago')
    expect(timeAgo(NOW - 30 * DAY, NOW)).toBe('1 month ago')
    expect(timeAgo(NOW - 75 * DAY, NOW)).toBe('2 months ago')
  })
  it('never says something is in the future', () => {
    expect(timeAgo(NOW + 5 * DAY, NOW)).toBe('today')
  })
})

describe('humanize', () => {
  it('turns ids and typed topics into readable names', () => {
    expect(humanize('virtual-functions')).toBe('Virtual functions')
    expect(humanize('inheritance in C++')).toBe('Inheritance in C++')
  })
})

describe('thinkingAt', () => {
  it('goes through the five lines in order, each for its time, then starts again', () => {
    const seen = [0, 1, 2, 3, 4, 5, 6].map((i) => thinkingAt(i * THINKING_MS + 100))
    expect(seen.slice(0, 5)).toEqual([...THINKING])
    expect(seen[5]).toBe(THINKING[0])
    expect(seen[6]).toBe(THINKING[1])
  })
  it('holds a line for the whole of its time and is safe on odd input', () => {
    expect(thinkingAt(0)).toBe(THINKING[0])
    expect(thinkingAt(THINKING_MS - 1)).toBe(THINKING[0])
    expect(thinkingAt(THINKING_MS)).toBe(THINKING[1])
    expect(thinkingAt(-500)).toBe(THINKING[0])
  })
  it('never mentions the teacher’s notes', () => {
    expect(THINKING.join(' ')).not.toMatch(/teacher|notes/i)
  })
})
