import { useRef, useState, type FC } from 'react'
import { FileTextIcon, Loader2Icon, PlusIcon, RefreshCwIcon, SparklesIcon, XIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useTutor } from './context'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { humanize } from '@/lib/format'
import type { ConceptProgress, Progress as ProgressData } from '@/lib/api'

function state(c: ConceptProgress): { label: string; tone: string } {
  if (c.review_due) return { label: 'Review due', tone: 'bg-amber-500/15 text-amber-700 dark:text-amber-300' }
  if (c.mastered) return { label: 'Got it', tone: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' }
  if (c.seen) return { label: 'Learning', tone: 'bg-sky-500/15 text-sky-700 dark:text-sky-300' }
  return { label: 'New', tone: 'bg-muted text-muted-foreground' }
}

/** The student's own documents, and the switch that makes them the source of truth. */
const Documents: FC<{ docs: string[]; useDocs: boolean }> = ({ docs, useDocs }) => {
  const { snap, addDocs, addSample, removeDoc, setSource } = useTutor()
  const pick = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const idle = snap.status !== 'working' && snap.status !== 'stalled'

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Your documents</p>
      {docs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          None yet. Without documents, lessons come from the AI’s own knowledge.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {docs.map((d) => (
            <li key={d} className="flex items-center justify-between gap-2 text-sm">
              <span className="flex min-w-0 items-center gap-1.5">
                <FileTextIcon className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate">{d}</span>
              </span>
              <button
                type="button"
                aria-label={`Remove ${d}`}
                disabled={busy}
                onClick={() => run(() => removeDoc(d))}
                className="text-muted-foreground hover:text-foreground"
              >
                <XIcon className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <input
        ref={pick}
        type="file"
        multiple
        accept=".md,.txt,.pdf,.docx"
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          e.target.value = ''
          if (files.length) void run(() => addDocs(files))
        }}
      />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={busy} onClick={() => pick.current?.click()}>
          {busy ? <Loader2Icon className="size-3.5 animate-spin" /> : <PlusIcon className="size-3.5" />}
          Add documents
        </Button>
        {docs.length === 0 ? (
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => run(addSample)}>
            Try sample notes
          </Button>
        ) : null}
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}

      <div className="flex items-start justify-between gap-3 rounded-lg border p-3">
        <Label htmlFor="use-docs" className="flex-col items-start gap-0.5 text-sm font-medium leading-snug">
          Use my documents as the source of truth
          <span className="text-xs font-normal text-muted-foreground">
            {docs.length === 0
              ? 'Add a document to switch this on.'
              : useDocs
                ? 'Lessons come only from them, with citations.'
                : 'Off: lessons come from general knowledge.'}
          </span>
        </Label>
        <Switch
          id="use-docs"
          checked={useDocs}
          disabled={docs.length === 0 || !idle}
          onCheckedChange={setSource}
        />
      </div>
      <p className="text-xs text-muted-foreground">Changes apply from the next lesson.</p>
    </div>
  )
}

/** The learner model, made visible: how well the student knows each concept and
 * which wrong beliefs they keep coming back to. */
export const ProgressPanel: FC<{ progress: ProgressData; student: string }> = ({ progress, student }) => {
  const beliefs = progress.concepts.flatMap((c) => c.beliefs.map(([tag, n]) => ({ tag, n, concept: c.concept })))
  return (
    <div className="flex flex-col gap-5 p-5">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Learning as</p>
        <p className="mt-0.5 font-semibold">{student}</p>
        {progress.interests.length > 0 ? (
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
            <SparklesIcon className="size-3.5" />
            Analogies from {progress.interests.join(', ')}
          </p>
        ) : null}
      </div>

      <Separator />

      <Documents docs={progress.docs} useDocs={progress.use_docs} />

      <Separator />

      <div className="flex flex-col gap-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">What you know</p>
        {progress.concepts.map((c) => {
          const s = state(c)
          return (
            <div key={c.concept} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{humanize(c.concept)}</span>
                <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', s.tone)}>
                  {c.review_due ? <RefreshCwIcon className="size-3" /> : null}
                  {s.label}
                </span>
              </div>
              <div className="relative">
                <Progress value={c.seen ? Math.round(c.mastery * 100) : 0} aria-label={`${humanize(c.concept)} mastery`} />
                {/* where "got it" starts */}
                <span
                  className="absolute -top-0.5 h-2.5 w-px bg-foreground/40"
                  style={{ left: `${progress.threshold * 100}%` }}
                  aria-hidden
                />
              </div>
            </div>
          )
        })}
      </div>

      {beliefs.length > 0 ? (
        <>
          <Separator />
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Ideas to watch</p>
            <p className="text-xs text-muted-foreground">Wrong ideas your answers have pointed to. The tutor aims lessons at these.</p>
            <div className="flex flex-wrap gap-1.5">
              {beliefs.map((b) => (
                <Badge key={`${b.concept}-${b.tag}`} variant="outline" className="font-normal">
                  {humanize(b.tag)}
                  {b.n > 1 ? <span className="ml-1 text-muted-foreground">×{b.n}</span> : null}
                </Badge>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
