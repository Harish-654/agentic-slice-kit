import type { FC, ReactNode } from 'react'
import { m } from 'motion/react'
import { CheckIcon, CircleDashedIcon, RotateCcwIcon, SparklesIcon } from 'lucide-react'
import { MasteryRing } from '@/components/atlas/MasteryRing'
import { useTutor } from '@/components/tutor/context'
import { BAND, band, pct } from '@/design/status'
import { item, stagger } from '@/design/motion'
import { calibration, explanationsTried, misconceptionMarks } from '@/lib/derive'
import { STYLE_LABEL, humanize } from '@/lib/format'
import { cn } from '@/lib/utils'
import { CalibrationDial } from './CalibrationDial'
import { IdeasToWatch } from './IdeasToWatch'

const Panel: FC<{ title: string; note?: string; children: ReactNode; className?: string }> = ({ title, note, children, className }) => (
  <section className={cn('rounded-2xl border bg-card p-5 shadow-[var(--shadow-page)]', className)}>
    <h2 className="eyebrow">{title}</h2>
    {note ? <p className="text-muted-foreground mt-1 mb-4 text-xs">{note}</p> : <div className="mb-4" />}
    {children}
  </section>
)

const OUTCOME = {
  landed: { label: 'Landed', Icon: CheckIcon, tone: 'text-correct' },
  missed: { label: 'Did not land', Icon: RotateCcwIcon, tone: 'text-destructive' },
  pending: { label: 'Waiting on a check', Icon: CircleDashedIcon, tone: 'text-muted-foreground' },
} as const

/** The cognitive twin, made visible. Everything here is what the tutor currently believes about
 * this student: how well they know each idea, which wrong ideas keep coming back, how honest their
 * confidence is, and which ways of explaining have worked. It changes after every answer. */
export const TwinView: FC = () => {
  const { snap } = useTutor()
  const { progress } = snap
  const marks = misconceptionMarks(progress)
  const read = calibration(snap.messages)
  const tried = explanationsTried(snap.messages)

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <header className="mb-8 max-w-2xl">
        <p className="eyebrow text-twin">Your twin</p>
        <h1 className="mt-1 text-3xl font-semibold sm:text-4xl">What the tutor believes about {snap.student}</h1>
        <p className="text-muted-foreground mt-2 text-[0.95rem]">
          After every answer the tutor updates this picture, then uses it to pick the next question and the next way of explaining. You are looking at the same notes it is.
        </p>
        {progress.interests.length > 0 ? (
          <p className="text-muted-foreground mt-3 flex items-center gap-1.5 text-sm">
            <SparklesIcon className="text-highlight size-4" />
            Analogies drawn from {progress.interests.join(', ')}
          </p>
        ) : null}
      </header>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="What you know" note={`“Got it” is ${Math.round(progress.threshold * 100)}%. Untouched topics read 0%: the tutor’s starting guess is not something you earned.`} className="lg:col-span-2">
          <m.ul variants={stagger(0.06)} initial="initial" animate="animate" className="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
            {progress.concepts.map((c) => {
              const b = band(c)
              return (
                <m.li key={c.concept} variants={item} className="flex items-center gap-3">
                  <MasteryRing value={pct(c) / 100} band={b} threshold={progress.threshold} size={60}>
                    <span className="text-xs font-semibold tabular-nums">{pct(c)}%</span>
                  </MasteryRing>
                  <span className="min-w-0">
                    <span className="font-heading block truncate text-base font-semibold">{humanize(c.concept)}</span>
                    <span className={cn('inline-flex rounded-full px-2 py-0.5 text-xs font-medium', BAND[b].chip)}>{BAND[b].label}</span>
                  </span>
                </m.li>
              )
            })}
          </m.ul>
        </Panel>

        <Panel title="Ideas to watch" note="Wrong ideas your answers have pointed to. The tutor aims lessons at these.">
          <IdeasToWatch marks={marks} />
        </Panel>

        <Panel title="How sure you are" note="Certain and wrong is the most useful thing to learn from. A right guess has not been learnt yet.">
          <CalibrationDial read={read} />
        </Panel>

        <Panel title="Explanations tried" note="A wrong answer means the last explanation did not land, so the tutor switches style rather than repeating it louder." className="lg:col-span-2">
          {tried.length === 0 ? (
            <p className="text-muted-foreground text-sm">Nothing yet.</p>
          ) : (
            <ol className="flex flex-col">
              {tried.map((t, i) => {
                const o = OUTCOME[t.outcome]
                return (
                  <li key={t.id} className="flex items-center gap-3 border-b border-dashed py-2 text-sm last:border-0">
                    <span className="text-muted-foreground w-5 font-mono text-xs tabular-nums">{i + 1}</span>
                    <span className="font-heading min-w-0 flex-1 truncate font-medium">{humanize(t.concept)}</span>
                    <span className="text-muted-foreground hidden sm:inline">{STYLE_LABEL[t.style] ?? humanize(t.style)}</span>
                    <span className={cn('flex w-36 items-center justify-end gap-1.5 text-xs', o.tone)}>
                      <o.Icon className="size-3.5" />
                      {o.label}
                    </span>
                  </li>
                )
              })}
            </ol>
          )}
        </Panel>
      </div>
    </div>
  )
}
