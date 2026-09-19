import { useRef, useState, type FC } from 'react'
import { FileTextIcon, Loader2Icon, PlusIcon, XIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useTutor } from './context'

/** The student's own documents, and the switch that makes them the source of truth. */
export const Documents: FC<{ docs: string[]; useDocs: boolean }> = ({ docs, useDocs }) => {
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

      <div className="flex items-start justify-between gap-3 rounded-lg border bg-background/60 p-3">
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

