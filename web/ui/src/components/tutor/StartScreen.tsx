import { useRef, useState, type FC, type FormEvent } from 'react'
import { FileTextIcon, GraduationCapIcon, Loader2Icon, PaperclipIcon, XIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, api } from '@/lib/api'

const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)

export const StartScreen: FC<{
  initialName: string
  onStarted: (id: string, student: string) => void
}> = ({ initialName, onStarted }) => {
  const [name, setName] = useState(initialName)
  const [topics, setTopics] = useState('')
  const [interests, setInterests] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [sample, setSample] = useState(false)
  const [existing, setExisting] = useState<string[]>([]) // documents this name already has
  const [useDocs, setUseDocs] = useState(false)
  const [guided, setGuided] = useState(false)
  const [exam, setExam] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pick = useRef<HTMLInputElement>(null)

  const haveDocs = files.length > 0 || sample || existing.length > 0
  // Guided mode takes one topic, or a pasted exam question that names its own topic.
  const examText = exam.trim()
  const topicList = split(topics)
  const ready = !!name.trim() && (guided ? topicList.length === 1 || (topicList.length === 0 && !!examText) : topicList.length > 0)

  // A returning student may already have documents on the server.
  const lookUp = () => {
    const who = name.trim()
    if (!who) return setExisting([])
    api.docs(who).then((r) => setExisting(r.docs), () => setExisting([]))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const who = name.trim()
    if (!ready) return
    setBusy(true)
    setError(null)
    try {
      if (files.length) await api.upload(who, files)
      if (sample) await api.sample(who)
      const { id } = await api.start(
        who,
        topicList,
        split(interests),
        useDocs && haveDocs,
        guided ? 'guided' : 'quick',
        guided && examText ? examText : null,
      )
      onStarted(id, who)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start a session.')
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <div className="mb-2 flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <GraduationCapIcon className="size-5" />
          </div>
          <CardTitle className="text-xl">What do you want to learn?</CardTitle>
          <CardDescription>
            Short lessons, then a quick check. The tutor remembers what you get wrong and teaches it a different way.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <Label htmlFor="name">Your name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={lookUp}
                placeholder="So it can remember you next time"
                required
                autoFocus
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="topics">Topics</Label>
              <Input
                id="topics"
                value={topics}
                onChange={(e) => setTopics(e.target.value)}
                placeholder={guided ? 'e.g. inheritance' : 'e.g. recursion, list slicing, how decorators work'}
                required={!guided || !examText}
              />
              <p className="text-xs text-muted-foreground">
                {guided
                  ? 'One topic. Or leave this empty and paste an exam question below.'
                  : 'Anything you like, separated by commas. Questions are made for you, based on what you already know.'}
              </p>
            </div>

            <div className="flex flex-col gap-3 rounded-lg border p-3">
              <div className="flex items-start justify-between gap-3">
                <Label htmlFor="guided" className="flex-col items-start gap-0.5 text-sm font-medium leading-snug">
                  Check what it builds on first
                  <span className="text-xs font-normal text-muted-foreground">
                    Guided: it asks about the ideas this topic needs, and only explains the ones you miss.
                  </span>
                </Label>
                <Switch id="guided" checked={guided} onCheckedChange={setGuided} />
              </div>
              {guided ? (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="exam" className="text-sm font-normal">
                    An exam question to work towards <span className="text-muted-foreground">(optional)</span>
                  </Label>
                  <Textarea
                    id="exam"
                    value={exam}
                    onChange={(e) => setExam(e.target.value)}
                    placeholder="Paste it here. The tutor works out which topic it tests."
                    rows={3}
                    maxLength={2000}
                  />
                </div>
              ) : null}
            </div>

            <div className="flex flex-col gap-3 rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Your own documents (optional)</p>
                <p className="text-xs text-muted-foreground">
                  Notes or slides from your teacher, as PDF, Word, Markdown or text.
                </p>
              </div>

              <input
                ref={pick}
                type="file"
                multiple
                accept=".md,.txt,.pdf,.docx"
                className="hidden"
                onChange={(e) => {
                  // Read the files BEFORE clearing the input: a state updater runs after this
                  // handler returns, by which time the cleared input would hand back nothing.
                  const chosen = Array.from(e.target.files ?? [])
                  e.target.value = ''
                  setFiles((f) => [...f, ...chosen])
                }}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => pick.current?.click()}>
                  <PaperclipIcon className="size-3.5" />
                  Add documents
                </Button>
                <Button type="button" size="sm" variant={sample ? 'secondary' : 'ghost'} onClick={() => setSample((s) => !s)}>
                  {sample ? 'Sample notes added' : 'Try sample notes'}
                </Button>
              </div>

              {existing.length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Already saved for {name.trim()}: {existing.join(', ')}
                </p>
              ) : null}
              {files.length > 0 ? (
                <ul className="flex flex-col gap-1">
                  {files.map((f, i) => (
                    <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-2 text-sm">
                      <span className="flex min-w-0 items-center gap-1.5">
                        <FileTextIcon className="size-3.5 shrink-0 text-muted-foreground" />
                        <span className="truncate">{f.name}</span>
                      </span>
                      <button
                        type="button"
                        aria-label={`Remove ${f.name}`}
                        onClick={() => setFiles((all) => all.filter((_, j) => j !== i))}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <XIcon className="size-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}

              <div className="flex items-start justify-between gap-3">
                <Label htmlFor="use-docs" className="flex-col items-start gap-0.5 text-sm font-normal leading-snug">
                  Use my documents as the source of truth
                  <span className="text-xs text-muted-foreground">
                    {haveDocs
                      ? 'Lessons then come only from them, with citations.'
                      : 'Add a document first. Until then, lessons come from the AI’s own knowledge.'}
                  </span>
                </Label>
                <Switch id="use-docs" checked={useDocs && haveDocs} disabled={!haveDocs} onCheckedChange={setUseDocs} />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="interests">
                What do you enjoy? <span className="font-normal text-muted-foreground">(optional)</span>
              </Label>
              <Input
                id="interests"
                value={interests}
                onChange={(e) => setInterests(e.target.value)}
                placeholder="Films, football, chess… lessons will use them for analogies"
              />
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" disabled={busy || !ready} size="lg">
              {busy ? <Loader2Icon className="size-4 animate-spin" /> : null}
              Start learning
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
