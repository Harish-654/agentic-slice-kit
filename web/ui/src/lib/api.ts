// The shape of web/tutor_api.py. If one changes, so must the other.

export type Status =
  | 'working' // a lesson or a grade is being written
  | 'waiting_student'
  | 'waiting_choice' // a topic is not in the student's documents; they decide what to do
  | 'stalled' // mid-step with nothing driving it; the page resumes it
  | 'complete'
  | 'failed'

export type AnswerMode = 'mcq' | 'text' | 'code'

/** Suggestion chips. `enabled` is the twin's call: false means "try it yourself first". */
export type Suggest = { enabled: boolean; reason: string; suggestions: string[] }

/** How sure the student says they are. It changes how far an answer moves their mastery. */
export type Confidence = 'low' | 'medium' | 'high'

export type Answered = {
  chosen: number | null
  correct_index: number | null
  correct: boolean
  dont_know?: boolean
}

export type Quiz = {
  question: string
  code: string | null
  options: { text: string }[]
  answered: Answered | null
}

/** A question answered in the student's own words. The rubric stays on the server. */
export type OpenQ = { question: string; code: string | null; answered: Answered | null }

/** A question answered by writing a program. The hidden tests never leave the server. `stdio` programs read
 * their input and print their answer (every language but Python); `function` ones define a function. */
export type CodeTaskQ = {
  question: string
  starter: string
  style: 'function' | 'stdio'
  language: SessionLanguage | null // what it was written in; its editor runs it there whatever the sandbox picker says now
  answered: Answered | null
}

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
  quiz: Quiz | null // exactly one of quiz, open and code_task
  open: OpenQ | null
  code_task: CodeTaskQ | null
}
export type AnswerMsg = { id: string; role: 'user'; kind: 'answer'; text: string }
export type FeedbackMsg = {
  id: string
  role: 'assistant'
  kind: 'feedback'
  correct: boolean
  text: string
  misconception: string | null
  via: 'mcq' | 'text' | 'code'
  confidence: Confidence | null
  dont_know: boolean
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
/** Guided sessions: what to do after an explanation. `chosen` is set once they have picked. */
export type ChoicesMsg = {
  id: string
  role: 'assistant'
  kind: 'choices'
  options: Choice[]
  chosen: Choice | null
}
/** The check that was held back with an explanation, shown when the student asks to be quizzed. */
export type CardMsg = {
  id: string
  role: 'assistant'
  kind: 'card'
  concept: string
  quiz: Quiz | null
  open: OpenQ | null
  code_task: CodeTaskQ | null
}
export type Choice = 'quiz' | 'example' | 'more_detail' | 'deeper' | 'skip' | 'stop'
/** A guided session's plan as pictures, drawn once when it starts. Both are Mermaid source made by the server. */
export type MapMsg = { id: string; role: 'assistant'; kind: 'map'; flowchart: string; mindmap: string }
export type Msg = LessonMsg | AnswerMsg | FeedbackMsg | EndMsg | NoticeMsg | ChoicesMsg | CardMsg | MapMsg

export type ConceptProgress = {
  concept: string
  mastery: number
  mastered: boolean
  seen: boolean
  review_due: boolean
  beliefs: [string, number][]
}
export type LangRef = { id: string; version: string }

/** The code sandbox's language and version, or the one a program question was written in. `label`: "Java 17". */
export type SessionLanguage = { id: string; name: string; version: string; label: string }

/** One language the code sandbox can run, and which of its versions this server has. */
export type LanguageInfo = { id: string; name: string; versions: string[]; default: string; installed: Record<string, boolean> }
export type Languages = {
  languages: LanguageInfo[]
  docker: boolean // false: Docker cannot be reached, so nothing can run
}

export type Progress = {
  language: SessionLanguage
  concepts: ConceptProgress[]
  threshold: number
  mode: 'quick' | 'guided'
  /** Guided sessions: what the topic builds on, worked out once at the start. */
  plan: { target: string; prereqs: string[]; subtopics: string[] } | null
  /** The plan coloured by what the student knows now, as a flowchart and as a mind map. */
  map: { flowchart: string; mindmap: string } | null
  answer_mode: AnswerMode // the type of the NEXT question
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

/** One run of the student's code in the sandbox, and what the coach made of it. */
export type CodeRun = {
  stdout: string
  stderr: string
  exit_code: number | null
  timed_out: boolean
  correct: boolean | null // null: the run proves nothing, so the learner model was left alone
  misconception: string | null
  hint: string | null
  progress: Progress
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Fired when the server says nobody is signed in (a sign-in that expired, say), so the app can go back
 * to the sign-in screen instead of showing a half-working page. */
export const SIGNED_OUT = 'tutor:signed-out'

/** One day's worth of what a student did, and the streak that follows. See demo/tutor/activity.py. */
export type Activity = {
  today: string // the student's own date, YYYY-MM-DD
  days: Record<string, number> // non-zero days in the heatmap's window: date -> answered questions + code runs
  current_streak: number
  longest_streak: number
  at_risk: boolean // the streak is alive but today has nothing yet
  checked_in_today: boolean
  today_count: number
  active_days: number
  total: number
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const json = typeof init?.body === 'string'
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: 'same-origin', // the sign-in is a cookie
    headers: json ? { 'Content-Type': 'application/json' } : undefined,
  })
  if (res.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event(SIGNED_OUT))
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
  // Who is signed in. `student` is null only when the server runs with login off (tests).
  me: () => call<{ student: string | null; login_required: boolean }>('/auth/me'),
  signUp: (name: string, password: string) => call<{ student: string }>('/auth/signup', post({ name, password })),
  signIn: (name: string, password: string) => call<{ student: string }>('/auth/login', post({ name, password })),
  signOut: () => call<{ ok: boolean }>('/auth/logout', post({})),
  /** `tz` is the browser's offset, so a day is the student's own day. */
  activity: () => call<Activity>(`/me/activity?tz=${new Date().getTimezoneOffset()}`),

  start: (
    student: string,
    concepts: string[],
    interests: string[],
    use_docs: boolean,
    mode: 'quick' | 'guided' = 'quick',
    exam_question: string | null = null,
  ) => call<{ id: string }>('/sessions', post({ student, concepts, interests, use_docs, mode, exam_question })),
  get: (id: string) => call<Snapshot>(`/sessions/${id}`),
  answerChoice: (id: string, choice: number, confidence: Confidence) =>
    call<Snapshot>(`/sessions/${id}/answer`, post({ choice, confidence })),
  answerText: (id: string, text: string, confidence: Confidence) =>
    call<Snapshot>(`/sessions/${id}/answer`, post({ text, confidence })),
  dontKnow: (id: string) => call<Snapshot>(`/sessions/${id}/answer`, post({ dont_know: true })),
  answerCode: (id: string, code: string, confidence: Confidence, assisted: boolean) =>
    call<Snapshot>(`/sessions/${id}/answer`, post({ code, confidence, assisted })),
  setMode: (id: string, mode: AnswerMode) => call<Snapshot>(`/sessions/${id}/mode`, post({ mode })),
  setSource: (id: string, use_docs: boolean) => call<Snapshot>(`/sessions/${id}/source`, post({ use_docs })),
  fallback: (id: string, choice: 'general' | 'skip') => call<Snapshot>(`/sessions/${id}/fallback`, post({ choice })),
  choose: (id: string, choice: Choice) => call<Snapshot>(`/sessions/${id}/choice`, post({ choice })),
  resume: (id: string) => call<Snapshot>(`/sessions/${id}/resume`, post({})),

  // The code coach
  codeStatus: (language: string, version: string) =>
    call<{ available: boolean; reason: string }>(`/code/status?language=${enc(language)}&version=${enc(version)}`),
  languages: () => call<Languages>('/languages'),
  /** Pick the sandbox's language and version. It applies to the editor and to the NEXT program question only. */
  setLanguage: (id: string, language: string, version: string | null) =>
    call<Snapshot>(`/sessions/${id}/language`, post({ language, version })),
  /** `lang` is a program question's own language; without it the sandbox's is used. */
  runCode: (id: string, code: string, expected: string | null, assisted = false, stdin = '', lang?: LangRef) =>
    call<CodeRun>(`/sessions/${id}/code`, post({ code, expected, assisted, stdin, language: lang?.id, version: lang?.version })),
  suggest: (id: string, code: string, lang?: LangRef) =>
    call<Suggest>(`/sessions/${id}/suggest`, post({ code, language: lang?.id, version: lang?.version })),

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
