import type { FC, ReactNode } from 'react'
import { ActivityProvider } from '@/lib/useActivity'
import { LoginScreen } from './LoginScreen'
import { useAuth } from './useAuth'

/** Nothing of the tutor is shown until somebody has signed in. Once they have, the app gets the student's
 * name, and the activity data (streak, heatmap) is loaded for that student and thrown away when they leave. */
export const AuthGate: FC<{ children: (student: string) => ReactNode }> = ({ children }) => {
  const { status, student } = useAuth()
  if (status === 'loading') {
    return <div className="text-muted-foreground flex h-full items-center justify-center text-sm">Checking your sign-in…</div>
  }
  if (status === 'signed-out' || !student) return <LoginScreen />
  return <ActivityProvider key={student}>{children(student)}</ActivityProvider>
}
