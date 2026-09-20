import { createContext, useCallback, useContext, useEffect, useMemo, useState, type FC, type ReactNode } from 'react'
import { SIGNED_OUT, api } from '@/lib/api'
import { KEY, write } from '@/lib/storage'

type State = { status: 'loading' | 'signed-out' | 'signed-in'; student: string | null }
type Ctx = State & {
  signIn: (name: string, password: string) => Promise<void>
  signUp: (name: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}
const AuthContext = createContext<Ctx | null>(null)

const OUT: State = { status: 'signed-out', student: null }

/** Who is signed in. Asks the server once on load (the sign-in is a cookie the page cannot read), and drops
 * back to signed-out whenever any request comes back 401, such as a sign-in that has expired. */
export const AuthProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<State>({ status: 'loading', student: null })

  useEffect(() => {
    api.me().then(
      (r) => setState(r.student ? { status: 'signed-in', student: r.student } : OUT),
      () => setState(OUT),
    )
  }, [])

  useEffect(() => {
    const out = () => setState(OUT)
    window.addEventListener(SIGNED_OUT, out)
    return () => window.removeEventListener(SIGNED_OUT, out)
  }, [])

  const signIn = useCallback(async (name: string, password: string) => {
    const r = await api.signIn(name, password)
    setState({ status: 'signed-in', student: r.student })
  }, [])
  const signUp = useCallback(async (name: string, password: string) => {
    const r = await api.signUp(name, password)
    setState({ status: 'signed-in', student: r.student })
  }, [])
  const signOut = useCallback(async () => {
    try {
      await api.signOut()
    } finally {
      // The open session belongs to the person leaving; the next one to sign in on this computer must not inherit it.
      write(KEY.session, null)
      write(KEY.student, null)
      setState(OUT)
    }
  }, [])

  const value = useMemo(() => ({ ...state, signIn, signUp, signOut }), [state, signIn, signUp, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): Ctx {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
