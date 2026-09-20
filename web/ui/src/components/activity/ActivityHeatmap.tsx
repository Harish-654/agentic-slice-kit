import { useEffect, useId, useMemo, useRef, useState, type FC, type KeyboardEvent } from 'react'
import { WEEKDAYS, buildGrid, describeCell, type Cell } from '@/lib/heatmap'
import { useActivity } from '@/lib/useActivity'
import { cn } from '@/lib/utils'

const CELL = 12
const GAP = 3
const STEP = CELL + GAP
const LEFT = 30 // room for the weekday names
const TOP = 18 // room for the month names
const RADIUS = 'rounded-[3px]'

type Spot = { col: number; row: number; cell: Cell }

/** "Learning Activity": one square for every day of the last year, a column per week and a row per weekday
 * (Monday first). An empty day is muted; the more the student did, the brighter the green. Hover, tap or use the
 * arrow keys on a square to read its exact date and count. It scrolls sideways when the screen is narrow, opening
 * on the newest weeks. The look is our own; it is not a copy of any other product's graph. */
export const ActivityHeatmap: FC<{ bare?: boolean; className?: string }> = ({ bare, className }) => {
  const { activity, failed } = useActivity()
  const grid = useMemo(() => (activity ? buildGrid(activity.days, activity.today) : null), [activity])
  const [spot, setSpot] = useState<Spot | null>(null) // the square whose tooltip is showing
  const [byKeyboard, setByKeyboard] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const gridEl = useRef<HTMLDivElement>(null)
  const id = useId()

  // Open on the right-hand end, where today is, and stay there while the window changes size (a phone being
  // turned, say), until the student scrolls somewhere else on purpose. Scrolling back to the end re-attaches it.
  const atEnd = useRef(true)
  const ready = grid !== null
  useEffect(() => {
    const el = scroller.current
    if (!el) return
    const toEnd = () => {
      el.scrollLeft = el.scrollWidth
    }
    const onScroll = () => {
      atEnd.current = el.scrollLeft >= el.scrollWidth - el.clientWidth - 2
    }
    toEnd()
    el.addEventListener('scroll', onScroll, { passive: true })
    const watch = new ResizeObserver(() => {
      if (atEnd.current) toEnd()
    })
    watch.observe(el)
    return () => {
      el.removeEventListener('scroll', onScroll)
      watch.disconnect()
    }
  }, [ready])
  // Fresh numbers must not yank the view back if the student has scrolled to read older weeks.
  useEffect(() => {
    const el = scroller.current
    if (el && atEnd.current) el.scrollLeft = el.scrollWidth
  }, [grid])

  // A tap anywhere else puts a touch tooltip away (a finger has no "pointer leave").
  useEffect(() => {
    const away = (e: PointerEvent) => {
      if (!gridEl.current?.contains(e.target as Node)) setSpot(null)
    }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [])

  if (!activity || !grid) {
    return (
      <section className={cn(!bare && 'bg-card rounded-2xl border p-5', className)}>
        {failed ? (
          <p className="text-muted-foreground text-sm">Could not load your activity just now.</p>
        ) : (
          <div className="bg-muted h-32 animate-pulse rounded-md" aria-label="Loading your activity" />
        )}
      </section>
    )
  }

  const cols = grid.weeks.length
  const width = LEFT + cols * STEP - GAP
  const height = TOP + 7 * STEP - GAP
  const at = (col: number, row: number): Cell | null => grid.weeks[col]?.[row] ?? null
  const put = (col: number, row: number) => {
    const cell = at(col, row)
    if (cell) setSpot({ col, row, cell })
  }
  const today = (() => {
    for (let c = cols - 1; c >= 0; c--) for (let r = 6; r >= 0; r--) if (at(c, r)) return { col: c, row: r }
    return { col: 0, row: 0 }
  })()

  const onKey = (e: KeyboardEvent) => {
    const here = spot ?? { ...today, cell: at(today.col, today.row)! }
    const to: Record<string, [number, number]> = {
      ArrowLeft: [here.col - 1, here.row],
      ArrowRight: [here.col + 1, here.row],
      ArrowUp: [here.col, here.row - 1],
      ArrowDown: [here.col, here.row + 1],
      Home: [0, 0],
      End: [today.col, today.row],
    }
    if (e.key === 'Escape') return setSpot(null)
    const next = to[e.key]
    if (!next) return
    e.preventDefault()
    setByKeyboard(true)
    put(next[0], next[1])
  }

  const below = spot ? spot.row < 3 : false // the top rows have no room above them, so their tooltip goes underneath
  const summary = `${activity.total.toLocaleString()} ${activity.total === 1 ? 'activity' : 'activities'} on ${activity.active_days} ${activity.active_days === 1 ? 'day' : 'days'} in the last year`

  return (
    <section aria-labelledby={`${id}-title`} className={cn('min-w-0', !bare && 'bg-card rounded-2xl border p-5 shadow-[var(--shadow-page)]', className)}>
      {bare ? (
        <h3 id={`${id}-title`} className="sr-only">
          Learning activity
        </h3>
      ) : (
        <header className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <div>
            <h2 id={`${id}-title`} className="eyebrow">
              Learning activity
            </h2>
            <p className="text-muted-foreground mt-1 text-xs">{summary}</p>
          </div>
          <p className="text-muted-foreground text-xs">
            Longest streak <span aria-hidden>🔥</span> {activity.longest_streak} {activity.longest_streak === 1 ? 'day' : 'days'}
          </p>
        </header>
      )}
      {bare ? <p className="text-muted-foreground mb-3 text-xs">{summary}</p> : null}

      <div ref={scroller} className="overflow-x-auto pb-2">
        <div className="relative" style={{ width, height }}>
          {grid.months.map((m) => (
            <span key={`${m.label}-${m.col}`} className="text-muted-foreground absolute text-[10px] leading-none" style={{ left: LEFT + m.col * STEP, top: 0 }}>
              {m.label}
            </span>
          ))}
          {/* The weekday names stay put while the weeks scroll under them. */}
          <div className="sticky left-0 z-[1]" style={{ width: LEFT - 4, height }}>
            {/* Paper behind the day rows only, so a month name scrolling past is not chopped off mid-word. */}
            <div className="bg-card absolute inset-x-0 bottom-0" style={{ top: TOP }} />
            {[0, 2, 4].map((r) => (
              <span key={r} className="text-muted-foreground absolute text-[10px] leading-none" style={{ left: 0, top: TOP + r * STEP + 1 }}>
                {WEEKDAYS[r]}
              </span>
            ))}
          </div>

          <div
            ref={gridEl}
            role="group"
            tabIndex={0}
            aria-label="Learning activity, one square for each day. Use the arrow keys to move between days."
            aria-describedby={`${id}-live`}
            onKeyDown={onKey}
            onFocus={() => {
              if (!spot) {
                setByKeyboard(true)
                put(today.col, today.row)
              }
            }}
            onBlur={() => {
              setByKeyboard(false)
              setSpot(null)
            }}
            onPointerLeave={(e) => {
              if (e.pointerType === 'mouse') setSpot(null)
            }}
            className="focus-visible:ring-ring/60 absolute rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-card"
            style={{ left: LEFT, top: TOP, display: 'grid', gridTemplateRows: `repeat(7, ${CELL}px)`, gridAutoFlow: 'column', gridAutoColumns: `${CELL}px`, gap: GAP }}
          >
            {grid.weeks.flatMap((week, c) =>
              week.map((cell, r) =>
                cell ? (
                  <span
                    key={cell.date}
                    aria-hidden
                    data-date={cell.date}
                    data-level={cell.level}
                    data-count={cell.count}
                    onPointerEnter={() => {
                      setByKeyboard(false)
                      put(c, r)
                    }}
                    className={cn(
                      RADIUS,
                      cell.today && 'ring-route ring-offset-card ring-2 ring-offset-1',
                      spot?.col === c && spot.row === r && (byKeyboard ? 'ring-foreground ring-2' : 'ring-foreground/50 ring-1'),
                    )}
                    style={{ background: `var(--heat-${cell.level})` }}
                  />
                ) : (
                  <span key={`${c}-${r}`} aria-hidden />
                ),
              ),
            )}
          </div>

          {spot ? (
            <div
              aria-hidden
              data-tooltip
              className="bg-popover text-popover-foreground pointer-events-none absolute z-10 rounded-md border px-2 py-1 text-xs whitespace-nowrap shadow-md"
              style={{
                left: Math.min(Math.max(LEFT + spot.col * STEP + CELL / 2, 100), width - 100),
                top: below ? TOP + (spot.row + 1) * STEP + 2 : TOP + spot.row * STEP - 6,
                transform: below ? 'translateX(-50%)' : 'translate(-50%, -100%)',
              }}
            >
              {describeCell(spot.cell)}
            </div>
          ) : null}
        </div>
      </div>

      <p id={`${id}-live`} className="sr-only" aria-live="polite">
        {byKeyboard && spot ? describeCell(spot.cell) : ''}
      </p>

      <div className="text-muted-foreground mt-2 flex items-center justify-between gap-3 text-xs">
        <span>{activity.total === 0 ? 'Nothing yet. Every answered question and every code run lights up a square.' : ' '}</span>
        <span className="flex items-center gap-1.5" aria-hidden>
          Less
          {[0, 1, 2, 3, 4].map((l) => (
            <span key={l} className={cn('size-3', RADIUS)} style={{ background: `var(--heat-${l})` }} />
          ))}
          More
        </span>
      </div>
    </section>
  )
}
