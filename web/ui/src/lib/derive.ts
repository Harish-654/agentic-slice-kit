// Everything the atlas shows that is not a raw field of the snapshot. Pure functions of the
// session, so they are easy to test and there is exactly one place where "mission", "calibration"
// and "milestone" are defined.
//
// Nothing here is invented. The server has no XP, streaks or history across sessions, so
// everything below is worked out from this session's snapshot and says so.
import type { ConceptProgress, FeedbackMsg, LessonMsg, Msg, Progress, Snapshot } from './api'
import { band, pct, type Band } from '@/design/status'

// ---------------------------------------------------------------- the route

export type StepRole = 'prerequisite' | 'part' | 'final' | 'topic'
export type RouteStep = {
  concept: string
  role: StepRole
  band: Band
  pct: number
  /** The first step that is not mastered yet: where the student is on the route. */
  current: boolean
  beliefs: number
}

const placeholder = (concept: string): ConceptProgress => ({ concept, mastery: 0, mastered: false, seen: false, review_due: false, beliefs: [] })

/** The route through the topics: what it builds on, the parts, then the final check. Without a
 * plan (quick practice) it is just the topics, in the order they were given. */
export function missionRoute(progress: Progress): RouteStep[] {
  const by = new Map(progress.concepts.map((c) => [c.concept, c]))
  const plan = progress.plan
  const order: [string, StepRole][] = plan
    ? [
        ...plan.prereqs.map((c) => [c, 'prerequisite'] as [string, StepRole]),
        ...plan.subtopics.map((c) => [c, 'part'] as [string, StepRole]),
        [plan.target, 'final'],
      ]
    : progress.concepts.map((c) => [c.concept, 'topic'] as [string, StepRole])
  const seen = new Set(order.map(([c]) => c))
  for (const c of progress.concepts) if (!seen.has(c.concept)) order.push([c.concept, 'topic'])

  const steps = order.map(([concept, role]) => {
    const c = by.get(concept) ?? placeholder(concept)
    return { concept, role, band: band(c), pct: pct(c), current: false, beliefs: c.beliefs.reduce((n, [, k]) => n + k, 0) }
  })
  const now = steps.findIndex((s) => s.band !== 'got-it')
  if (now >= 0) steps[now].current = true
  return steps
}

// ---------------------------------------------------------------- calibration

export type Calibration = 'overconfident' | 'underconfident' | 'calibrated'
export type CalibrationRead = { counts: Record<Calibration, number>; dontKnow: number; answered: number }

const feedback = (messages: Msg[]) => messages.filter((m): m is FeedbackMsg => m.kind === 'feedback')

/** How well "how sure I am" tracked "whether I was right". Certain and wrong is the most useful
 * thing to learn from; a right answer that was a guess has not been learnt yet. */
export function calibration(messages: Msg[]): CalibrationRead {
  const counts: Record<Calibration, number> = { overconfident: 0, underconfident: 0, calibrated: 0 }
  let dontKnow = 0
  let answered = 0
  for (const f of feedback(messages)) {
    if (f.dont_know) {
      dontKnow++
      continue
    }
    if (!f.confidence) continue
    answered++
    if (!f.correct && f.confidence === 'high') counts.overconfident++
    else if (f.correct && f.confidence === 'low') counts.underconfident++
    else counts.calibrated++
  }
  return { counts, dontKnow, answered }
}

// ---------------------------------------------------------------- explanations tried

export type Tried = { id: string; concept: string; style: string; outcome: 'landed' | 'missed' | 'pending' }

/** Each explanation the tutor has given, and whether the first check after it went well. The
 * twin's rule is that a wrong answer means the last explanation did not land, so it changes style. */
export function explanationsTried(messages: Msg[]): Tried[] {
  const out: Tried[] = []
  messages.forEach((m, i) => {
    if (m.kind !== 'lesson') return
    const l = m as LessonMsg
    let outcome: Tried['outcome'] = 'pending'
    for (const n of messages.slice(i + 1)) {
      if (n.kind === 'lesson') break
      if (n.kind === 'feedback' && !n.dont_know) {
        outcome = n.correct ? 'landed' : 'missed'
        break
      }
    }
    out.push({ id: l.id, concept: l.concept, style: l.style, outcome })
  })
  return out
}

// ---------------------------------------------------------------- ideas to watch

export type Mark = { tag: string; count: number }

/** The wrong ideas the answers have pointed to, most frequent first. */
export function misconceptionMarks(progress: Progress): Mark[] {
  const counts = new Map<string, number>()
  for (const c of progress.concepts) for (const [tag, n] of c.beliefs) counts.set(tag, (counts.get(tag) ?? 0) + n)
  return [...counts].map(([tag, count]) => ({ tag, count })).sort((a, b) => b.count - a.count)
}

// ---------------------------------------------------------------- milestones

export type Milestone = { id: string; title: string; detail: string; earned: boolean }

/** Small, honest "you did a thing" markers. Each one is a fact about this session. */
export function milestones(snap: Snapshot): Milestone[] {
  const fb = feedback(snap.messages)
  const route = missionRoute(snap.progress)
  const graded = fb.filter((f) => !f.dont_know)
  const done = route.length > 0 && route.every((s) => s.band === 'got-it')
  return [
    { id: 'first-answer', title: 'First answer', detail: 'You gave the tutor something to work with.', earned: graded.length > 0 },
    {
      id: 'misconception',
      title: 'Found a wrong idea',
      detail: 'An answer showed a belief worth fixing. Finding it is the first half of fixing it.',
      earned: misconceptionMarks(snap.progress).length > 0,
    },
    { id: 'honest', title: 'Honest “I don’t know”', detail: 'Saying so beats guessing, and the tutor treats it that way.', earned: fb.some((f) => f.dont_know) },
    { id: 'sure-and-right', title: 'Certain and right', detail: 'You said you were sure, and you were.', earned: graded.some((f) => f.correct && f.confidence === 'high') },
    { id: 'first-got-it', title: 'First topic got', detail: 'One topic has crossed the “got it” line.', earned: route.some((s) => s.band === 'got-it') },
    { id: 'route-complete', title: 'Route complete', detail: 'Every stop on the route is at “got it”.', earned: done },
  ]
}
