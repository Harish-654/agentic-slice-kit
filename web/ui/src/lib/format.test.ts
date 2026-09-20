import { describe, expect, it } from 'vitest'
import { humanize, timeAgo } from './format'

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
