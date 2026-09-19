import { useEffect, useState, type FC, type FormEvent } from 'react'
import { GraduationCapIcon, Loader2Icon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { humanize } from '@/lib/format'
import { api } from '@/lib/api'

const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)

export const StartScreen: FC<{
  initialName: string
  onStarted: (id: string, student: string) => void
}> = ({ initialName, onStarted }) => {
  const [name, setName] = useState(initialName)
  const [topics, setTopics] = useState<string[] | null>(null)
  const [picked, setPicked] = useState<string[]>([])
  const [extra, setExtra] = useState('')
  const [interests, setInterests] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .notes()
      .then((r) => {
        setTopics(r.concepts)
        setPicked(r.concepts.slice(0, 3))
      })
      .catch(() => setTopics([]))
  }, [])

  const concepts = [...picked, ...split(extra)]
  const toggle = (t: string) => setPicked((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]))

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim() || concepts.length === 0) return
    setBusy(true)
    setError(null)
    try {
      const { id } = await api.start(name.trim(), concepts, split(interests))
      onStarted(id, name.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start a session.')
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
          <CardTitle className="text-xl">Learn Python from your teacher’s notes</CardTitle>
          <CardDescription>
            Short lessons, then a quick check. The tutor remembers what you get wrong and teaches it a different way.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <Label htmlFor="name">Your name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="So it can remember you next time" required autoFocus />
            </div>

            <div className="flex flex-col gap-2">
              <Label>What to learn</Label>
              {topics === null ? (
                <p className="text-sm text-muted-foreground">Looking at your teacher’s notes…</p>
              ) : topics.length > 0 ? (
                <div className="flex flex-wrap gap-2" role="group" aria-label="Topics in your teacher’s notes">
                  {topics.map((t) => (
                    <button key={t} type="button" onClick={() => toggle(t)} aria-pressed={picked.includes(t)}>
                      <Badge
                        variant={picked.includes(t) ? 'default' : 'outline'}
                        className={cn('cursor-pointer px-3 py-1 text-sm font-normal', !picked.includes(t) && 'text-muted-foreground')}
                      >
                        {humanize(t)}
                      </Badge>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No notes found yet. Type the topics you want below.</p>
              )}
              <Input
                value={extra}
                onChange={(e) => setExtra(e.target.value)}
                placeholder="Something else? Separate topics with commas"
                aria-label="Other topics"
              />
              {split(extra).length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Topics your notes do not cover are sent to your teacher, and are never answered from the internet.
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="interests">
                What do you enjoy? <span className="font-normal text-muted-foreground">(optional)</span>
              </Label>
              <Input id="interests" value={interests} onChange={(e) => setInterests(e.target.value)} placeholder="Films, football, chess… lessons will use them for analogies" />
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" disabled={busy || !name.trim() || concepts.length === 0} size="lg">
              {busy ? <Loader2Icon className="size-4 animate-spin" /> : null}
              Start learning
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
