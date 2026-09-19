import { createContext, useContext } from 'react'
import type { Snapshot } from '@/lib/api'

export type TutorApi = {
  snap: Snapshot
  /** It is the student's turn: a quiz is open and nothing is being written. */
  canAnswer: boolean
  answerChoice: (choice: number) => void
  answerText: (text: string) => void
  setMode: (mode: 'mcq' | 'text') => void
  restart: () => void
}

export const TutorContext = createContext<TutorApi | null>(null)

export function useTutor(): TutorApi {
  const ctx = useContext(TutorContext)
  if (!ctx) throw new Error('useTutor must be used inside <TutorRuntime>')
  return ctx
}
