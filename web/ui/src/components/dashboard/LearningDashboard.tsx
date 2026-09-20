import { useEffect, useState, type FC } from 'react'
import { CheckIcon, RotateCcwIcon } from 'lucide-react'
import { MasteryRing } from '@/components/atlas/MasteryRing'
import { Button } from '@/components/ui/button'
import { BAND, type Band } from '@/design/status'
import { api, type IdeaBand, type Learning, type LearningTopic, type TopicState } from '@/lib/api'
import { humanize, timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'

const SHOWN = 6

/** A topic's state in the atlas's own words. "Learnt" is "Got it" for a whole topic. */
const TOPIC_BAND: Record<TopicState, Band> = { learnt: 'got-it', review: 'review', learning: 'learning', new: 'new' }
const TOPIC_WORD: Record<TopicState, string> = { learnt: 'Learnt', review: 'Review due', learning: 'Learning', new: 'Not started' }

/** A mark for one part. The word beside it says the same thing, so colour is never the only signal. */
const Mark: FC<{ band: IdeaBand }> = ({ band }) =>
  band === 'got-it' ? (
    <CheckIcon aria-hidden className="text-correct size-4 shrink-0" />
  ) : band === 'review' ? (
    <RotateCcwIcon aria-hidden className="text-caution size-4 shrink-0" />
  ) : (
    <span
      aria-hidden
      className={cn('size-3 shrink-0 rounded-full border-2', band === 'learning' ? 'border-twin bg-twin/30' : 'border-border')}
    />
  )

const Figure: FC<{ value: string | number; label: string }> = ({ value, label }) => (
  <div className="bg-card min-w-0 rounded-xl border px-4 py-3">
    <p className="font-heading text-2xl leading-none font-semibold tabular-nums">{value}</p>
    <p className="text-muted-foreground mt-1.5 text-xs">{label}</p>
  </div>
)

const TopicCard: FC<{ topic: LearningTopic; onStudy: (name: string) => void }> = ({ topic, onStudy }) => {
  const band = TOPIC_BAND[topic.state]
  const hasParts = topic.parts_total > 0
  // A topic with parts is measured by how many are done; quick practice, which has none, by how well it is known.
  const value = hasParts ? topic.parts_done / topic.parts_total : topic.mastery
  const name = humanize(topic.name)
  return (
    <li className="bg-card flex min-w-0 flex-col gap-3 rounded-2xl border p-5 shadow-[var(--shadow-page)]">
      <div className="flex items-start gap-3">
        <MasteryRing value={value} band={band} size={52}>
          <span className="text-[0.7rem] font-semibold tabular-nums">
            {hasParts ? `${topic.parts_done}/${topic.parts_total}` : `${Math.round(topic.mastery * 100)}%`}
          </span>
        </MasteryRing>
        <div className="min-w-0">
          <h3 className="font-heading text-lg leading-tight font-semibold break-words">{name}</h3>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', BAND[band].chip)}>{TOPIC_WORD[topic.state]}</span>
            {topic.due > 0 ? (
              <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', BAND.review.chip)}>{topic.due} to review</span>
            ) : null}
          </div>
        </div>
      </div>

      {hasParts ? (
        <>
          <p className="text-sm">
            <span className="font-semibold tabular-nums">{topic.parts_done}</span> of{' '}
            <span className="font-semibold tabular-nums">{topic.parts_total}</span> parts done
          </p>
          <ul className="flex flex-col gap-1.5" aria-label={`Parts of ${name}`}>
            {topic.parts.map((p) => (
              <li key={p.concept} className="flex items-center gap-2 text-sm">
                <Mark band={p.band} />
                <span className="min-w-0 flex-1 break-words">{humanize(p.concept)}</span>
                <span className={cn('shrink-0 text-xs', BAND[p.band].text)}>{BAND[p.band].label}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-muted-foreground text-sm">Quick practice: {Math.round(topic.mastery * 100)}% known.</p>
      )}

      {topic.prereqs.length > 0 ? (
        <p className="text-muted-foreground text-xs">
          Builds on: {topic.prereqs.map((p) => `${humanize(p.concept)} (${BAND[p.band].label.toLowerCase()})`).join(', ')}
        </p>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        <p className="text-muted-foreground text-xs">
          Last studied {timeAgo(topic.last_studied)}
          {topic.sessions > 1 ? ` · ${topic.sessions} sessions` : ''}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={() => onStudy(topic.name)} aria-label={`Study ${name} again`}>
          Study again
        </Button>
      </div>
    </li>
  )
}

/** What the student has already learnt, and which parts of each topic they have completed. It is worked out on
 * the server from their twin and past sessions, and shows nothing at all for a student with no history. */
export const LearningDashboard: FC<{ onStudy: (topic: string) => void; onStart: () => void }> = ({ onStudy, onStart }) => {
  const [data, setData] = useState<Learning | null>(null)
  const [failed, setFailed] = useState(false)
  const [tries, setTries] = useState(0)
  const [all, setAll] = useState(false)
  useEffect(() => {
    setFailed(false)
    api.learning().then(setData, () => setFailed(true))
  }, [tries])

  if (failed)
    return (
      <section aria-labelledby="learning-title" className="pt-6">
        <h2 id="learning-title" className="font-heading text-2xl font-semibold">
          Your learning
        </h2>
        <p role="status" className="text-muted-foreground mt-3 text-sm">
          Could not load your learning just now.
        </p>
        <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => setTries((n) => n + 1)}>
          Try again
        </Button>
      </section>
    )
  if (!data)
    return (
      <p role="status" className="text-muted-foreground pt-6 text-sm">
        Loading your learning…
      </p>
    )
  if (data.topics.length === 0)
    return (
      <section aria-labelledby="learning-title" className="pt-6">
        <p className="eyebrow">Your learning</p>
        <h2 id="learning-title" className="font-heading mt-1 text-2xl font-semibold sm:text-3xl">
          Nothing here yet
        </h2>
        <p className="text-muted-foreground mt-2 max-w-prose">
          Learn your first topic and it will show up here, with the parts you complete and the ideas that are due for review.
        </p>
        <Button type="button" className="mt-4" onClick={onStart}>
          Start learning
        </Button>
      </section>
    )

  const { totals, topics } = data
  const shown = all ? topics : topics.slice(0, SHOWN)
  return (
    <section aria-labelledby="learning-title" className="pt-6">
      <p className="eyebrow">Your learning</p>
      <h2 id="learning-title" className="font-heading mt-1 text-2xl font-semibold sm:text-3xl">
        What you have learnt so far
      </h2>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Figure value={`${totals.learnt} of ${totals.topics}`} label={totals.topics === 1 ? 'topic learnt' : 'topics learnt'} />
        <Figure value={totals.parts_done} label={totals.parts_done === 1 ? 'part completed' : 'parts completed'} />
        <Figure value={totals.to_review} label={totals.to_review === 1 ? 'idea to review' : 'ideas to review'} />
        <Figure value={totals.sessions} label={totals.sessions === 1 ? 'session' : 'sessions'} />
      </div>
      <ul className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((t) => (
          <TopicCard key={t.name} topic={t} onStudy={onStudy} />
        ))}
      </ul>
      {topics.length > SHOWN ? (
        <div className="mt-4">
          <Button type="button" variant="ghost" size="sm" aria-expanded={all} onClick={() => setAll((a) => !a)}>
            {all ? 'Show fewer' : `Show all ${topics.length} topics`}
          </Button>
        </div>
      ) : null}
    </section>
  )
}
