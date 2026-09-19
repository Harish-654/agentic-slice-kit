import { createContext, useContext } from 'react'
import type { Confidence, Snapshot } from '@/lib/api'

export type TutorApi = {
  snap: Snapshot
  /** It is the student's turn: a quiz is open and nothing is being written. */
  canAnswer: boolean
  /** The option picked on the card, and how sure the student says they are. Both reset
   * with each new lesson. Nothing is sent until they submit. */
  picked: number | null
  setPicked: (choice: number) => void
  confidence: Confidence | null
  setConfidence: (c: Confidence) => void
  submitChoice: () => void
  /** "I don't know": honest, never graded. */
  dontKnow: () => void
  /** The type of the NEXT question; the one on screen is left alone. */
  setMode: (mode: 'mcq' | 'text') => void
  setSource: (useDocs: boolean) => void
  /** The answer to "that topic is not in your documents". */
  fallback: (choice: 'general' | 'skip') => void
  /** Document changes reject with a message that is safe to show. */
  addDocs: (files: File[]) => Promise<void>
  addSample: () => Promise<void>
  removeDoc: (name: string) => Promise<void>
  restart: () => void
}

export const TutorContext = createContext<TutorApi | null>(null)

export function useTutor(): TutorApi {
  const ctx = useContext(TutorContext)
  if (!ctx) throw new Error('useTutor must be used inside <TutorRuntime>')
  return ctx
}
