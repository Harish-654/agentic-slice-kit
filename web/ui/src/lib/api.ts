// The shape of web/tutor_api.py. If one changes, so must the other.

export type Status =
  | 'working' // a lesson or a grade is being written
  | 'waiting_student'
  | 'waiting_choice' // a topic is not in the student's documents; they decide what to do
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

/** A question answered in the student's own words. The rubric stays on the server. */
export type OpenQ = { question: string; code: string | null; answered: Answered | null }

export type LessonMsg = {
  id: string
  role: 'assistant'
  kind: 'lesson'
  concept: string
  style: string
  source: 'general' | 'docs'
  citations: string[]
  explanation: string
  diagram: string | null
  quiz: Quiz | null // exactly one of quiz and open
  open: OpenQ | null
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
export type Gap = { concept: string; answer: 'general' | 'skip' | null }
export type NoticeMsg = {
  id: string
  role: 'assistant'
  kind: 'notice'
  text: string
  problem: boolean
  gap: Gap | null // set when the student is being asked what to do about a topic
}
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
  answer_mode: 'mcq' | 'text' // the type of the NEXT question
  interests: string[]
  use_docs: boolean
  docs: string[]
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
  const json = typeof init?.body === 'string'
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: json ? { 'Content-Type': 'application/json' } : undefined,
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

const enc = encodeURIComponent

export const api = {
  start: (student: string, concepts: string[], interests: string[], use_docs: boolean) =>
    call<{ id: string }>('/sessions', post({ student, concepts, interests, use_docs })),
  get: (id: string) => call<Snapshot>(`/sessions/${id}`),
  answerChoice: (id: string, choice: number) => call<Snapshot>(`/sessions/${id}/answer`, post({ choice })),
  answerText: (id: string, text: string) => call<Snapshot>(`/sessions/${id}/answer`, post({ text })),
  setMode: (id: string, mode: 'mcq' | 'text') => call<Snapshot>(`/sessions/${id}/mode`, post({ mode })),
  setSource: (id: string, use_docs: boolean) => call<Snapshot>(`/sessions/${id}/source`, post({ use_docs })),
  fallback: (id: string, choice: 'general' | 'skip') => call<Snapshot>(`/sessions/${id}/fallback`, post({ choice })),
  resume: (id: string) => call<Snapshot>(`/sessions/${id}/resume`, post({})),

  // A student's own documents
  docs: (student: string) => call<{ docs: string[] }>(`/students/${enc(student)}/docs`),
  upload: (student: string, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return call<{ docs: string[] }>(`/students/${enc(student)}/docs`, { method: 'POST', body: form })
  },
  sample: (student: string) => call<{ docs: string[] }>(`/students/${enc(student)}/docs/sample`, post({})),
  removeDoc: (student: string, name: string) =>
    call<{ docs: string[] }>(`/students/${enc(student)}/docs/${enc(name)}`, { method: 'DELETE' }),
}
