// The shape of web/tutor_api.py. If one changes, so must the other.

export type Status =
  | 'working' // a lesson or a grade is being written
  | 'waiting_student'
  | 'waiting_teacher'
  | 'stalled' // mid-step with nothing driving it; the page resumes it
  | 'complete'
  | 'failed'

export type Answered = { chosen: number | null; correct_index: number | null; correct: boolean }

export type Quiz = {
  question: string
  code: string | null
  options: { text: string }[]
  answered: Answered | null
}

export type LessonMsg = {
  id: string
  role: 'assistant'
  kind: 'lesson'
  concept: string
  style: string
  citations: string[]
  explanation: string
  diagram: string | null
  quiz: Quiz
}
export type AnswerMsg = { id: string; role: 'user'; kind: 'answer'; text: string }
export type FeedbackMsg = {
  id: string
  role: 'assistant'
  kind: 'feedback'
  correct: boolean
  text: string
  misconception: string | null
  via: 'mcq' | 'text'
}
export type EndMsg = { id: string; role: 'assistant'; kind: 'end'; reason: string }
export type NoticeMsg = { id: string; role: 'assistant'; kind: 'notice'; text: string; problem: boolean }
export type Msg = LessonMsg | AnswerMsg | FeedbackMsg | EndMsg | NoticeMsg

export type ConceptProgress = {
  concept: string
  mastery: number
  mastered: boolean
  seen: boolean
  review_due: boolean
  beliefs: [string, number][]
}
export type Progress = {
  concepts: ConceptProgress[]
  threshold: number
  answer_mode: 'mcq' | 'text'
  interests: string[]
}
export type Snapshot = {
  id: string
  student: string
  status: Status
  messages: Msg[]
  progress: Progress
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  notes: () => call<{ concepts: string[] }>('/notes'),
  start: (student: string, concepts: string[], interests: string[]) =>
    call<{ id: string }>('/sessions', post({ student, concepts, interests })),
  get: (id: string) => call<Snapshot>(`/sessions/${id}`),
  answerChoice: (id: string, choice: number) => call<Snapshot>(`/sessions/${id}/answer`, post({ choice })),
  answerText: (id: string, text: string) => call<Snapshot>(`/sessions/${id}/answer`, post({ text })),
  setMode: (id: string, mode: 'mcq' | 'text') => call<Snapshot>(`/sessions/${id}/mode`, post({ mode })),
  resume: (id: string) => call<Snapshot>(`/sessions/${id}/resume`, post({})),
}
