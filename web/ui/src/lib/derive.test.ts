import { describe, expect, it } from 'vitest'
import type { ConceptProgress, FeedbackMsg, LessonMsg, Msg, Progress, Snapshot } from './api'
import { calibration, explanationsTried, milestones, misconceptionMarks, missionRoute } from './derive'

const c = (concept: string, mastery: number, o: Partial<ConceptProgress> = {}): ConceptProgress => ({
  concept, mastery, mastered: mastery >= 0.75, seen: true, review_due: false, beliefs: [], ...o,
})
const progress = (concepts: ConceptProgress[], plan: Progress['plan'] = null): Progress => ({
  concepts, threshold: 0.75, mode: plan ? 'guided' : 'quick', plan, answer_mode: 'mcq', interests: [], use_docs: false, docs: [],
})
const fb = (id: string, correct: boolean, confidence: FeedbackMsg['confidence'], dont_know = false): FeedbackMsg => ({
  id, role: 'assistant', kind: 'feedback', correct, text: '', misconception: null, via: 'mcq', confidence, dont_know,
})
const lesson = (id: string, style = 'plain'): LessonMsg => ({
  id, role: 'assistant', kind: 'lesson', concept: 'x', style, source: 'general', citations: [], explanation: '', diagram: null, quiz: null, open: null, code_task: null,
})
const snap = (messages: Msg[], p: Progress): Snapshot => ({ id: 's', student: 'a', status: 'waiting_student', messages, progress: p })

describe('missionRoute', () => {
  const plan = { target: 'final', prereqs: ['a'], subtopics: ['b', 'c'] }
  it('orders the plan: builds on, the parts, then the final check', () => {
    const r = missionRoute(progress([c('final', 0), c('c', 0), c('b', 0.5), c('a', 0.9)], plan))
    expect(r.map((s) => [s.concept, s.role])).toEqual([['a', 'prerequisite'], ['b', 'part'], ['c', 'part'], ['final', 'final']])
  })
  it('marks the first stop that is not mastered as the current one', () => {
    const r = missionRoute(progress([c('a', 0.9), c('b', 0.4), c('c', 0), c('final', 0)], plan))
    expect(r.filter((s) => s.current).map((s) => s.concept)).toEqual(['b'])
  })
  it('has no current stop once everything is mastered', () => {
    const r = missionRoute(progress([c('a', 0.9), c('b', 0.9), c('c', 0.9), c('final', 0.9)], plan))
    expect(r.some((s) => s.current)).toBe(false)
  })
  it('without a plan, keeps the topics in the order given', () => {
    const r = missionRoute(progress([c('z', 0), c('y', 0)]))
    expect(r.map((s) => [s.concept, s.role])).toEqual([['z', 'topic'], ['y', 'topic']])
  })
  it('does not invent progress for a planned stop the server has not listed', () => {
    const r = missionRoute(progress([c('a', 0.9)], plan))
    expect(r.find((s) => s.concept === 'final')).toMatchObject({ pct: 0, band: 'new' })
  })
  it('reads an unseen topic as 0%, whatever the starting guess', () => {
    const r = missionRoute(progress([c('a', 0.3, { seen: false })]))
    expect(r[0].pct).toBe(0)
  })
})

describe('calibration', () => {
  it('flags certain-and-wrong and guess-and-right, and counts the rest as matched', () => {
    const r = calibration([fb('1', false, 'high'), fb('2', true, 'low'), fb('3', true, 'high'), fb('4', false, 'low')])
    expect(r.counts).toEqual({ overconfident: 1, underconfident: 1, calibrated: 2 })
    expect(r.answered).toBe(4)
  })
  it('counts “I don’t know” separately and never as an answer', () => {
    const r = calibration([fb('1', false, null, true)])
    expect(r).toMatchObject({ dontKnow: 1, answered: 0 })
  })
})

describe('explanationsTried', () => {
  it('says whether the first check after each explanation went well', () => {
    const t = explanationsTried([lesson('1', 'plain'), fb('2', false, 'high'), lesson('3', 'analogy'), fb('4', true, 'high'), lesson('5', 'worked_example')])
    expect(t.map((x) => x.outcome)).toEqual(['missed', 'landed', 'pending'])
  })
  it('does not let one explanation take credit for the next one’s check', () => {
    const t = explanationsTried([lesson('1'), lesson('2'), fb('3', true, 'medium')])
    expect(t.map((x) => x.outcome)).toEqual(['pending', 'landed'])
  })
})

describe('misconceptionMarks', () => {
  it('adds a tag up across concepts, most frequent first', () => {
    const p = progress([c('a', 0.2, { beliefs: [['t1', 1], ['t2', 3]] }), c('b', 0.2, { beliefs: [['t1', 1]] })])
    expect(misconceptionMarks(p)).toEqual([{ tag: 't2', count: 3 }, { tag: 't1', count: 2 }])
  })
})

describe('milestones', () => {
  const earned = (s: Snapshot) => milestones(s).filter((m) => m.earned).map((m) => m.id)
  it('earns nothing on a fresh session', () => {
    expect(earned(snap([], progress([c('a', 0, { seen: false })])))).toEqual([])
  })
  it('earns only what actually happened', () => {
    const s = snap([fb('1', true, 'high')], progress([c('a', 0.9)]))
    expect(earned(s)).toEqual(['first-answer', 'sure-and-right', 'first-got-it', 'route-complete'])
  })
  it('treats an honest “I don’t know” as a marker but not as a first answer', () => {
    expect(earned(snap([fb('1', false, null, true)], progress([c('a', 0.2)])))).toEqual(['honest'])
  })
})
