import { useState, type FC, type FormEvent } from 'react'
import { EyeIcon, EyeOffIcon, Loader2Icon } from 'lucide-react'
import { Mark } from '@/components/shell/Mark'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAuth } from './useAuth'

const tidy = (s: string) => s.trim().replace(/\s+/g, ' ')
/** The same rule the server applies to a new name, so a mistake is caught before it is sent. */
const nameProblem = (raw: string) => {
  const s = tidy(raw)
  return /^[A-Za-z0-9 ._-]{2,40}$/.test(s) && (s.match(/[A-Za-z0-9]/g) ?? []).length >= 2
    ? null
    : 'Use 2 to 40 letters, numbers, spaces, dots, dashes or underscores.'
}

type Mode = 'in' | 'up'

/** Sign in, or make an account. A name belongs to one person once it has an account, so what a student
 * studies, their documents and their streak are theirs alone. */
export const LoginScreen: FC = () => {
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState<Mode>('in')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const creating = mode === 'up'
  const problem = creating && name ? nameProblem(name) : null
  const short = creating && password.length > 0 && password.length < 8
  const mismatch = creating && again.length > 0 && again !== password
  const ready = creating ? !nameProblem(name) && password.length >= 8 && again === password : !!tidy(name) && !!password

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!ready || busy) return
    setBusy(true)
    setError(null)
    try {
      await (creating ? signUp : signIn)(tidy(name), password)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the tutor. Is it running?')
      setBusy(false)
    }
  }

  const switchTo = (m: Mode) => {
    setMode(m)
    setError(null)
    setAgain('')
  }

  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-route mb-6 flex items-center justify-center gap-2.5">
          <Mark className="size-9" />
          <span className="font-heading text-foreground text-xl font-semibold">Tutor</span>
        </div>
        <Card className="shadow-[var(--shadow-page)]">
          <CardContent>
            <p className="eyebrow">{creating ? 'Start your journey' : 'Welcome back'}</p>
            <h1 className="mt-1 text-2xl leading-tight font-semibold">{creating ? 'Create your account' : 'Sign in to keep learning'}</h1>
            <p className="text-muted-foreground mt-2 text-sm">
              Your progress, your notes and your streak are kept under your name, and only you can open them.
            </p>

            <div role="tablist" aria-label="Sign in or create an account" className="bg-muted mt-5 grid grid-cols-2 gap-1 rounded-lg p-1">
              {(
                [
                  ['in', 'Sign in'],
                  ['up', 'Create account'],
                ] as const
              ).map(([m, label]) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => switchTo(m)}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                    mode === m ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="mt-5 flex flex-col gap-4" noValidate>
              <div className="flex flex-col gap-2">
                <Label htmlFor="login-name">Your name</Label>
                <Input
                  id="login-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  maxLength={40}
                  aria-invalid={!!problem}
                  aria-describedby={problem ? 'login-name-help' : undefined}
                  placeholder={creating ? 'e.g. Asha K' : 'The name you signed up with'}
                />
                {problem ? (
                  <p id="login-name-help" className="text-destructive text-xs">
                    {problem}
                  </p>
                ) : creating ? (
                  <p className="text-muted-foreground text-xs">A name that was used before accounts existed is locked, so pick a new one.</p>
                ) : null}
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="login-password">Password</Label>
                <div className="relative">
                  <Input
                    id="login-password"
                    type={show ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={creating ? 'new-password' : 'current-password'}
                    maxLength={200}
                    aria-invalid={short}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShow((s) => !s)}
                    aria-label={show ? 'Hide password' : 'Show password'}
                    aria-pressed={show}
                    className="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 flex w-10 items-center justify-center"
                  >
                    {show ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                  </button>
                </div>
                {creating ? (
                  <p className={cn('text-xs', short ? 'text-destructive' : 'text-muted-foreground')}>At least 8 characters.</p>
                ) : null}
              </div>

              {creating ? (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="login-again">Type it again</Label>
                  <Input
                    id="login-again"
                    type={show ? 'text' : 'password'}
                    value={again}
                    onChange={(e) => setAgain(e.target.value)}
                    autoComplete="new-password"
                    maxLength={200}
                    aria-invalid={mismatch}
                  />
                  {mismatch ? <p className="text-destructive text-xs">The two passwords do not match.</p> : null}
                </div>
              ) : null}

              {error ? (
                <p role="alert" className="text-destructive text-sm">
                  {error}
                </p>
              ) : null}

              <Button type="submit" size="lg" disabled={busy || !ready}>
                {busy ? <Loader2Icon className="size-4 animate-spin" /> : null}
                {creating ? 'Create account' : 'Sign in'}
              </Button>
            </form>

            <p className="text-muted-foreground mt-4 text-xs">
              {creating
                ? 'There is no email, so nobody can recover a forgotten password by themselves. Choose one you will remember.'
                : 'Forgotten your password? Ask your teacher or the person who runs this tutor to reset it.'}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
