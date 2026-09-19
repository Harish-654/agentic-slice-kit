import type { FC } from 'react'
import { m } from 'motion/react'
import { AwardIcon, LockKeyholeOpenIcon } from 'lucide-react'
import { SkillMap } from '@/components/atlas/SkillMap'
import { item, stagger } from '@/design/motion'
import { humanize } from '@/lib/format'
import { milestones, missionRoute } from '@/lib/derive'
import { cn } from '@/lib/utils'
import { useTutor } from '@/components/tutor/context'

/** The mission: where the student is going and what they have done on the way. The route is the
 * guided plan (what it builds on, the parts, the final check); the markers are facts about this
 * session, not points. */
export const MissionRoute: FC<{ onStudy: () => void }> = ({ onStudy }) => {
  const { snap } = useTutor()
  const { progress } = snap
  const steps = missionRoute(progress)
  const marks = milestones(snap)
  const done = steps.filter((s) => s.band === 'got-it').length
  const now = steps.find((s) => s.current)
  const target = progress.plan?.target

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <header className="mb-8">
        <p className="eyebrow">{progress.plan ? 'Your mission' : 'Your practice'}</p>
        <h1 className="mt-1 text-3xl font-semibold sm:text-4xl">{target ? `Reach ${humanize(target)}` : 'Work through your topics'}</h1>
        <p className="text-muted-foreground mt-2 max-w-prose text-[0.95rem]">
          {progress.plan
            ? 'The tutor checked what this topic builds on, then planned the route below. Each stop is filled in as you show you have got it.'
            : 'Each topic is a stop. The ring fills as the tutor becomes sure you understand it.'}
        </p>
        <p className="mt-4 flex items-center gap-3 text-sm">
          <span className="font-heading text-2xl font-semibold tabular-nums">
            {done}<span className="text-muted-foreground text-lg"> / {steps.length}</span>
          </span>
          <span className="text-muted-foreground">stops at “got it”</span>
        </p>
      </header>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section aria-label="Route" className="rounded-2xl border bg-card p-4 shadow-[var(--shadow-page)] sm:p-6">
          <SkillMap steps={steps} threshold={progress.threshold} />
        </section>

        <div className="flex flex-col gap-8">
          {now ? (
            <section aria-label="Next stop" className="rounded-xl border border-route/40 bg-route/8 p-4">
              <p className="eyebrow text-route">Next stop</p>
              <p className="font-heading mt-1 text-xl font-semibold">{humanize(now.concept)}</p>
              <p className="text-muted-foreground mt-1 text-sm">
                {now.pct === 0 ? 'Not started yet.' : `${now.pct}% of the way, and “got it” is ${Math.round(progress.threshold * 100)}%.`}
              </p>
              <button type="button" onClick={onStudy} className="mt-3 text-sm font-medium underline underline-offset-4 hover:text-route">
                Back to the lesson
              </button>
            </section>
          ) : (
            <section className="border-correct/40 bg-correct/8 rounded-xl border p-4">
              <p className="eyebrow text-correct">Route complete</p>
              <p className="mt-1 text-sm">Every stop is at “got it”.</p>
            </section>
          )}

          <section aria-label="Markers">
            <h2 className="eyebrow mb-3 font-normal">Markers from this session</h2>
            <m.ul variants={stagger(0.05)} initial="initial" animate="animate" className="flex flex-col gap-2">
              {marks.map((k) => (
                <m.li key={k.id} variants={item} className={cn('flex gap-3 rounded-lg border p-3', k.earned ? 'bg-card' : 'border-dashed opacity-60')}>
                  <span className={cn('mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full', k.earned ? 'bg-highlight/60 text-ink' : 'bg-muted text-muted-foreground')}>
                    {k.earned ? <AwardIcon className="size-4" /> : <LockKeyholeOpenIcon className="size-4" />}
                  </span>
                  <span className="text-sm leading-snug">
                    <span className="block font-medium">{k.title}</span>
                    <span className="text-muted-foreground text-xs">{k.detail}</span>
                  </span>
                </m.li>
              ))}
            </m.ul>
            <p className="text-muted-foreground mt-3 text-xs">These are worked out from this session only. Nothing is stored between sessions.</p>
          </section>
        </div>
      </div>
    </div>
  )
}
