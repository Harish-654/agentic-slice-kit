// Dev-only. `MOCK=1 npm run dev` serves these fixtures instead of the Python API, so every
// screen can be designed and screenshotted without a model key. It lives outside src/, so it
// is never part of the production bundle. Start a session with the fixture's name as the
// student ("quiz", "wrong", "open", ...): the session id is `fx-<name>`.
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import type { ConceptProgress, Msg, Progress, Snapshot } from '../src/lib/api.ts'

const concept = (c: string, mastery: number, o: Partial<ConceptProgress> = {}): ConceptProgress => ({
  concept: c,
  mastery,
  mastered: mastery >= 0.75,
  seen: true,
  review_due: false,
  beliefs: [],
  ...o,
})

const progress = (concepts: ConceptProgress[], o: Partial<Progress> = {}): Progress => ({
  concepts,
  threshold: 0.75,
  mode: 'guided',
  plan: {
    target: 'inheritance',
    prereqs: ['classes-and-objects', 'method-calls'],
    subtopics: ['overriding-methods', 'super-calls'],
  },
  answer_mode: 'mcq',
  interests: ['chess', 'football'],
  use_docs: true,
  docs: ['week3-oop-notes.pdf', 'lecture-slides.md'],
  ...o,
})

const journey = [
  concept('classes-and-objects', 0.86),
  concept('method-calls', 0.78, { review_due: true }),
  concept('overriding-methods', 0.42, { beliefs: [['override-replaces-class', 2], ['super-is-optional', 1]] }),
  concept('super-calls', 0, { seen: false }),
  concept('inheritance', 0, { seen: false }),
]

const lesson = (id: string, o: Record<string, unknown> = {}): Msg =>
  ({
    id,
    role: 'assistant',
    kind: 'lesson',
    concept: 'overriding-methods',
    style: 'analogy',
    source: 'docs',
    citations: ['week3-oop-notes.pdf#4', 'lecture-slides.md#2'],
    explanation:
      'A subclass can **replace** a method it inherits by defining one with the same name. Think of a chess club where every member knows the standard opening; the *coach* teaches a variation, and when someone asks the coach for “the opening” they get the coach’s version, not the textbook one.\n\n```python\nclass Player:\n    def opening(self):\n        return "e4"\n\nclass Coach(Player):\n    def opening(self):\n        return "d4"\n```\n\nCalling `Coach().opening()` returns `"d4"`. The parent’s method is still there; it is just not the one Python finds first.',
    diagram: 'graph TD; Player-->Coach',
    quiz: {
      question: 'What does Coach().opening() return?',
      code: null,
      options: [{ text: '"e4", because the parent defined it first' }, { text: '"d4", because the subclass version is found first' }, { text: 'An error: the method is defined twice' }],
      answered: null,
    },
    open: null,
    code_task: null,
    ...o,
  }) as Msg

const answered = (chosen: number, correct: boolean) => ({ chosen, correct_index: 1, correct })

const wrongTrail: Msg[] = [
  lesson('1', { style: 'plain', quiz: { question: 'What does Coach().opening() return?', code: null, options: [{ text: '"e4", because the parent defined it first' }, { text: '"d4", because the subclass version is found first' }, { text: 'An error: the method is defined twice' }], answered: answered(0, false) } }),
  { id: '2', role: 'user', kind: 'answer', text: '"e4", because the parent defined it first' },
  { id: '3', role: 'assistant', kind: 'feedback', correct: false, text: 'Python looks in the subclass first, so the overriding method wins. The parent’s version is still there, but it is only reached through super().', misconception: 'override-replaces-class', via: 'mcq', confidence: 'high', dont_know: false },
  lesson('4'),
]

const base = (messages: Msg[], status: Snapshot['status'] = 'waiting_student', p = progress(journey)): Snapshot => ({
  id: 'fx',
  student: 'Ada',
  status,
  messages,
  progress: p,
})

const FIXTURES: Record<string, Snapshot> = {
  quiz: base([lesson('1')]),
  wrong: base(wrongTrail),
  correct: base([
    lesson('1', { quiz: { question: 'What does Coach().opening() return?', code: null, options: [{ text: '"e4"' }, { text: '"d4"' }, { text: 'An error' }], answered: answered(1, true) } }),
    { id: '2', role: 'user', kind: 'answer', text: '"d4"' },
    { id: '3', role: 'assistant', kind: 'feedback', correct: true, text: 'Right: the subclass’s method is found first.', misconception: null, via: 'mcq', confidence: 'low', dont_know: false },
    lesson('4', { style: 'worked_example', concept: 'super-calls' }),
  ]),
  open: base([lesson('1', { quiz: null, open: { question: 'In your own words: why does Coach().opening() not return "e4"?', code: null, answered: null } })]),
  code: base([lesson('1', { quiz: null, code_task: { question: 'Write a class Rook(Player) whose opening() returns "Nf3".', starter: 'class Rook(Player):\n    ', answered: null } })], 'waiting_student', progress(journey, { answer_mode: 'code' })),
  guided: base([
    lesson('1', { quiz: null }),
    { id: '2', role: 'assistant', kind: 'choices', options: ['quiz', 'example', 'more_detail', 'deeper', 'skip', 'stop'], chosen: null },
  ], 'waiting_choice'),
  gap: base([
    { id: '1', role: 'assistant', kind: 'notice', text: '“super-calls” is not covered in your documents. What would you like to do?', problem: false, gap: { concept: 'super-calls', answer: null } },
  ], 'waiting_choice'),
  working: base([], 'working', progress(journey.map((c) => ({ ...c, seen: false, mastery: 0.3, review_due: false, mastered: false, beliefs: [] })))),
  end: base([...wrongTrail.slice(0, 3), { id: '9', role: 'assistant', kind: 'end', reason: 'mastery' }], 'complete', progress(journey.map((c) => concept(c.concept, 0.9)))),
  failed: base([{ id: '1', role: 'assistant', kind: 'notice', text: 'Both models unreachable. Run `python scripts/doctor.py`: this is usually the network or a provider outage, not your code.', problem: true, gap: null }], 'failed'),
  quick: base([lesson('1')], 'waiting_student', progress(journey.slice(0, 3), { mode: 'quick', plan: null })),
}

const send = (res: ServerResponse, body: unknown, status = 200) => {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify(body))
}

async function readBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = []
  for await (const c of req) chunks.push(c as Buffer)
  try {
    return JSON.parse(Buffer.concat(chunks).toString() || '{}')
  } catch {
    return {}
  }
}

export function mockApi(): Plugin {
  return {
    name: 'tutor-mock-api',
    configureServer(server) {
      server.middlewares.use('/api', async (req, res) => {
        const url = new URL(req.url ?? '/', 'http://x')
        const path = url.pathname
        const body = req.method === 'POST' ? await readBody(req) : {}
        const snap = (id: string) => ({ ...(FIXTURES[id.replace(/^fx-/, '')] ?? FIXTURES.quiz), id })

        if (path === '/sessions' && req.method === 'POST') return send(res, { id: `fx-${String(body.student ?? 'quiz').toLowerCase()}` })
        const m = path.match(/^\/sessions\/([^/]+)(?:\/(\w+))?$/)
        if (m) {
          const [, id, action] = m
          if (!action) return send(res, snap(id))
          if (action === 'code') return send(res, { stdout: 'Nf3\n', stderr: '', exit_code: 0, timed_out: false, correct: true, misconception: null, hint: null, progress: FIXTURES.quiz.progress })
          if (action === 'suggest') return send(res, { enabled: false, reason: 'You are still building this idea, so try it yourself first.', suggestions: [] })
          if (action === 'answer') return send(res, snap(id === 'fx-quiz' ? 'fx-wrong' : id))
          return send(res, snap(id))
        }
        if (path === '/code/status') return send(res, { available: true, reason: '' })
        if (/^\/students\/[^/]+\/docs/.test(path)) return send(res, { docs: ['week3-oop-notes.pdf'] })
        if (path === '/notes') return send(res, { concepts: [] })
        return send(res, { detail: 'mock: not found' }, 404)
      })
    },
  }
}
