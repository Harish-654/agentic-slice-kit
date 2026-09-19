import { useEffect, useRef, useState, type FC, type ReactNode } from 'react'
import { PlayIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError, type CodeRun, type Suggest } from '@/lib/api'
import { useTutor } from './context'

/** How long the student must stop typing before we ask for suggestions. */
const PAUSE_MS = 1000

/** Continue the code with a chip. A chip that starts indented belongs on a new line. */
export const append = (code: string, chip: string) =>
  code && !code.endsWith('\n') && /^\s/.test(chip) ? `${code}\n${chip}` : code + chip

type Chips = { forCode: string } & Suggest

/** The compiler: a code box, Run, its output and hints, and a bar of suggestion chips.
 * The server decides whether chips are shown: it only helps a student the twin says
 * already knows this topic. Using a chip marks the work as assisted, so it counts for less. */
export const CodeEditor: FC<{
  code: string
  setCode: (code: string) => void
  assisted: boolean
  setAssisted: (on: boolean) => void
  /** Free play can say what the code should print, so a matching run counts as evidence. */
  allowExpected?: boolean
  placeholder?: string
  children?: ReactNode
}> = ({ code, setCode, assisted, setAssisted, allowExpected, placeholder, children }) => {
  const { snap, refresh } = useTutor()
  const [expected, setExpected] = useState('')
  const [busy, setBusy] = useState(false)
  const [out, setOut] = useState<CodeRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [chips, setChips] = useState<Chips | null>(null)
  const latest = useRef(code)
  latest.current = code
  const cache = useRef(new Map<string, Suggest>())
  // Mastery decides help, so a "not yet" answer stays valid until mastery moves.
  const stateKey = JSON.stringify(snap.progress.concepts.map((c) => c.mastery))
  const blocked = useRef<{ key: string; reason: string } | null>(null)

  useEffect(() => {
    if (!code.trim() || snap.status === 'working') return
    if (blocked.current?.key === stateKey) return
    const hit = cache.current.get(code)
    if (hit) {
      setChips({ forCode: code, ...hit })
      return
    }
    const t = setTimeout(() => {
      api.suggest(snap.id, code).then(
        (r) => {
          if (!r.enabled) blocked.current = { key: stateKey, reason: r.reason }
          else cache.current.set(code, r)
          if (latest.current === code) setChips({ forCode: code, ...r })
        },
        () => undefined, // a missing chip must never get in the way of typing
      )
    }, PAUSE_MS)
    return () => clearTimeout(t)
  }, [code, snap.id, snap.status, stateKey])

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      setOut(await api.runCode(snap.id, code, expected.trim() ? expected : null, assisted))
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not run that.')
    } finally {
      setBusy(false)
    }
  }

  const shown = chips && chips.forCode === code && chips.enabled ? chips.suggestions : []
  const evidence =
    out?.correct === true
      ? 'Matched what you expected. That counts towards this topic.'
      : out?.correct === false
        ? 'That counts as a mistake the tutor will watch for.'
        : out
          ? 'Ran, but it proves nothing yet.'
          : null

  return (
    <div className="space-y-2">
      {shown.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Suggestions">
          <span className="text-xs text-muted-foreground">Next:</span>
          {shown.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setCode(append(code, s))
                setAssisted(true)
              }}
              className="max-w-full truncate rounded-md border bg-muted/50 px-2 py-1 font-mono text-xs hover:bg-muted"
              title={s}
            >
              {s.trim().split('\n')[0]}
              {s.trim().includes('\n') ? ' …' : ''}
            </button>
          ))}
        </div>
      ) : blocked.current?.key === stateKey && code.trim() ? (
        <p className="text-xs text-muted-foreground">{blocked.current.reason}</p>
      ) : null}
      <Textarea
        aria-label="Your Python code"
        spellCheck={false}
        className="min-h-40 font-mono text-xs"
        placeholder={placeholder ?? 'Write some Python and run it.'}
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />
      {allowExpected ? (
        <Input
          aria-label="What it should print (optional)"
          className="text-xs"
          placeholder="What should it print? (optional)"
          value={expected}
          onChange={(e) => setExpected(e.target.value)}
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="outline" disabled={busy || !code.trim()} onClick={run}>
          <PlayIcon className="size-4" />
          {busy ? 'Running…' : 'Run'}
        </Button>
        {children}
        {assisted ? <span className="text-xs text-muted-foreground">Used a suggestion: this counts for less.</span> : null}
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      {out && (
        <div className="space-y-1.5 text-xs">
          {(out.stdout || out.stderr) && (
            <pre className="max-h-40 overflow-auto rounded-md bg-muted p-2 whitespace-pre-wrap">
              {out.stdout}
              {out.stderr}
            </pre>
          )}
          {out.timed_out && <p>Stopped: it ran too long.</p>}
          {out.hint && <p className="font-medium">{out.hint}</p>}
          {allowExpected && evidence && <p className="text-muted-foreground">{evidence}</p>}
        </div>
      )}
    </div>
  )
}
