import { useEffect, useRef, useState, type FC, type FormEvent } from 'react'
import { FileTextIcon, Loader2Icon, PaperclipIcon, XIcon } from 'lucide-react'
import { ActivityHeatmap } from '@/components/activity/ActivityHeatmap'
import { CheckInCard } from '@/components/activity/CheckInCard'
import { LearningDashboard } from '@/components/dashboard/LearningDashboard'
import { StreakChip } from '@/components/activity/StreakChip'
import { MasteryRing } from '@/components/atlas/MasteryRing'
import { Mark } from '@/components/shell/Mark'
import { SignOutButton } from '@/components/shell/SignOutButton'
import { ThemeToggle } from '@/components/shell/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, api } from '@/lib/api'

const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)

/** `student` is whoever is signed in; the tutor never asks for a name any more. */
export const StartScreen: FC<{
  student: string
  onStarted: (id: string) => void
}> = ({ student, onStarted }) => {
  const [topics, setTopics] = useState('')
  const [interests, setInterests] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [sample, setSample] = useState(false)
  const [existing, setExisting] = useState<string[]>([]) // documents this name already has
  const [useDocs, setUseDocs] = useState(false)
  // On by default: it is the mode with the "what next?" menu, and a switch nobody finds is a feature nobody sees.
  const [guided, setGuided] = useState(true)
  const [exam, setExam] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pick = useRef<HTMLInputElement>(null)

  const haveDocs = files.length > 0 || sample || existing.length > 0
  // Guided mode takes one topic, or a pasted exam question that names its own topic.
  const examText = exam.trim()
  const topicList = split(topics)
  const ready = guided ? topicList.length === 1 || (topicList.length === 0 && !!examText) : topicList.length > 0

  // A returning student may already have documents on the server.
  useEffect(() => {
    api.docs(student).then((r) => setExisting(r.docs), () => setExisting([]))
  }, [student])

  /** "Study again" on a dashboard card: put that topic in the box, and take the student to it. */
  function study(topic: string) {
    setTopics(topic)
    requestAnimationFrame(() => {
      const box = document.getElementById('topics')
      box?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      box?.focus()
    })
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!ready) return
    setBusy(true)
    setError(null)
    try {
      if (files.length) await api.upload(student, files)
      if (sample) await api.sample(student)
      const { id } = await api.start(
        student,
        topicList,
        split(interests),
        useDocs && haveDocs,
        guided ? 'guided' : 'quick',
        guided && examText ? examText : null,
      )
      onStarted(id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start a session.')
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col px-4 sm:px-8">
      <div className="flex items-center justify-between gap-3 pt-4">
        <p className="eyebrow">Learning as {student}</p>
        <div className="flex items-center gap-1">
          <StreakChip className="mr-1" />
          <ThemeToggle />
          <SignOutButton />
        </div>
      </div>
      {/* Returning students see what they have learnt first; a new student has nothing to show, so nothing is drawn. */}
      <LearningDashboard onStudy={study} />
      <div className="grid items-center gap-10 py-8 lg:grid-cols-[minmax(0,1fr)_32rem] lg:gap-16">
      <div className="max-w-xl">
        <div className="text-route flex items-center gap-2.5">
          <Mark className="size-9" />
          <span className="font-heading text-foreground text-xl font-semibold">Tutor</span>
        </div>
        <p className="eyebrow mt-10">Begin an expedition</p>
        <h1 className="mt-2 text-4xl leading-[1.08] font-semibold sm:text-5xl">What do you want to learn?</h1>
        <p className="text-muted-foreground mt-4 max-w-md text-[1.05rem] leading-relaxed">
          Short lessons, then a quick check. The tutor keeps a model of you: it remembers what you get wrong and teaches it a different way.
        </p>
        <ul className="mt-8 flex flex-col gap-4">
          {[
            ['Your twin', 'What the tutor believes about you, in plain view and changing after every answer.'],
            ['Your route', 'It finds what your topic builds on, then plans the way there.'],
            ['Your sources', 'Teach from your own notes, with citations, or say so when it is using general knowledge.'],
          ].map(([t, d]) => (
            <li key={t} className="flex gap-3">
              <span className="bg-route mt-2.5 size-1.5 shrink-0 rounded-full" aria-hidden />
              <span>
                <span className="font-heading block text-lg font-semibold">{t}</span>
                <span className="text-muted-foreground text-sm">{d}</span>
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-10 hidden items-center gap-4 lg:flex" aria-hidden>
          {([['Builds on', 0.9, 'got-it'], ['Part', 0.5, 'learning'], ['Final check', 0, 'new']] as const).map(([label, v, b], i) => (
            <div key={label} className="flex items-center gap-4">
              {i > 0 ? <span className="border-route/50 w-10 border-t border-dashed" /> : null}
              <div className="flex flex-col items-center gap-1.5">
                <MasteryRing value={v} band={b} size={52} />
                <span className="eyebrow text-[0.625rem]">{label}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Card className="w-full shadow-[var(--shadow-page)]">
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <Label htmlFor="topics">Topics</Label>
              <Input
                id="topics"
                autoFocus
                value={topics}
                onChange={(e) => setTopics(e.target.value)}
                placeholder={guided ? 'e.g. inheritance' : 'e.g. recursion, list slicing, how decorators work'}
                required={!guided || !examText}
              />
              <p className="text-xs text-muted-foreground">
                {guided
                  ? topicList.length > 1
                    ? 'A guided lesson takes one topic. Keep one, or turn guided off below to practise several.'
                    : 'One topic. Or leave this empty and paste an exam question below.'
                  : 'Anything you like, separated by commas. Questions are made for you, based on what you already know.'}
              </p>
            </div>

            <div className="flex flex-col gap-3 rounded-lg border p-3">
              <div className="flex items-start justify-between gap-3">
                <Label htmlFor="guided" className="flex-col items-start gap-0.5 text-sm font-medium leading-snug">
                  Guided lesson
                  <span className="text-xs font-normal text-muted-foreground">
                    Checks what the topic builds on, explains only what you miss, then lets you choose what
                    next: a quiz, an example, more detail, or go deeper. Turn off for quick practice on
                    several topics.
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
                  Already saved for {student}: {existing.join(', ')}
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

      {/* Where the student stands: today's check-in, and everything they have done over the year. */}
      <div className="grid grid-cols-1 gap-5 pb-12 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <CheckInCard />
        <ActivityHeatmap />
      </div>
    </div>
  )
}
