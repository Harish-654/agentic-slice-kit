import { useEffect, type FC } from 'react'
import { AuiIf, ComposerPrimitive, MessagePrimitive, ThreadPrimitive, useAuiState } from '@assistant-ui/react'
import { m } from 'motion/react'
import { ArrowUpIcon, ChevronDownIcon } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Mark } from '@/components/shell/Mark'
import { rise } from '@/design/motion'
import { MarkdownText } from '@/components/assistant-ui/elements/markdown-text'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { ChoicesCard, CodeTaskCard, DiagramView, EndCard, FeedbackCard, LessonHeader, NoticeCard, OpenQuestionCard, PlanMapCard, QuizCard } from './cards'
import type { CardMsg, LessonMsg } from '@/lib/api'
import { useCodeStatus } from '@/lib/useCodeStatus'
import { useTutor } from './context'

const TOOLS = {
  by_name: {
    lesson_header: LessonHeader,
    diagram: DiagramView,
    quiz: QuizCard,
    open_question: OpenQuestionCard,
    code_task: CodeTaskCard,
    choices: ChoicesCard,
    plan_map: PlanMapCard,
    feedback: FeedbackCard,
    end: EndCard,
    notice: NoticeCard,
  },
}

const AssistantMessage: FC = () => (
  <MessagePrimitive.Root>
    <m.div {...rise} className="text-[0.95rem] leading-relaxed">
      <MessagePrimitive.Parts components={{ Text: MarkdownText, tools: TOOLS }} />
    </m.div>
  </MessagePrimitive.Root>
)

/** The student's answer, written into the margin of the page like an annotation, not sent as a chat bubble. */
const UserMessage: FC = () => (
  <MessagePrimitive.Root className="flex justify-end">
    <m.div {...rise} className="border-route/70 max-w-[85%] border-r-2 pr-4 text-right">
      <p className="eyebrow mb-0.5">You answered</p>
      <div className="font-heading text-[1.05rem] italic">
        <MessagePrimitive.Parts components={{ Text: ({ text }) => <p className="whitespace-pre-wrap">{text}</p> }} />
      </div>
    </m.div>
  </MessagePrimitive.Root>
)

const Message: FC = () => {
  const role = useAuiState((s) => s.message.role)
  return role === 'user' ? <UserMessage /> : <AssistantMessage />
}

/** Shown while the tutor is writing. The wording says what it is doing, because
 * a lesson takes ten seconds or more and a bare spinner reads as "stuck". */
const Working: FC = () => {
  const { snap } = useTutor()
  const started = snap.messages.some((m) => m.kind === 'lesson')
  const graded = snap.messages.at(-1)?.kind === 'answer'
  const label = !started
    ? 'Reading your teacher’s notes and preparing your first lesson…'
    : graded
      ? 'Checking your answer…'
      : 'Writing your next lesson…'
  return (
    <div className="text-muted-foreground flex items-center gap-3 text-sm" role="status" aria-live="polite">
      <m.span aria-hidden animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: 'linear' }} className="text-route inline-flex">
        <Mark className="size-6" />
      </m.span>
      <span className="font-heading italic">{label}</span>
    </div>
  )
}

/** The answer box, for a question the student writes an answer to. Enter and Send both wait
 * until they have said how sure they are. */
const TextAnswer: FC = () => {
  const { confidence } = useTutor()
  return (
    <ComposerPrimitive.Root className="bg-card focus-within:border-route/60 focus-within:ring-route/20 flex items-end gap-2 rounded-2xl border p-2 shadow-[var(--shadow-page)] transition focus-within:ring-3">
      <ComposerPrimitive.Input
        placeholder="Explain it in your own words…"
        className="font-heading placeholder:text-muted-foreground/60 max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2.5 py-2 text-base leading-6 outline-none"
        rows={1}
        autoFocus
        aria-label="Your answer"
        submitMode={confidence ? 'enter' : 'none'}
      />
      <ComposerPrimitive.Send
        render={<Button type="button" size="icon" className="size-9 rounded-full" aria-label="Send answer" disabled={!confidence} />}
      >
        <ArrowUpIcon className="size-4" />
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  )
}

const Footer: FC = () => {
  const { snap, canAnswer, setMode, confidence } = useTutor()
  // The box follows the question ON SCREEN; the switch is about the NEXT one.
  // In a guided session the check arrives in a card after "quiz me", not with the lesson.
  const lesson = snap.messages.findLast((m): m is LessonMsg | CardMsg => m.kind === 'lesson' || m.kind === 'card')
  const writing = canAnswer && lesson?.open != null
  const nextWritten = snap.progress.answer_mode === 'text'
  const nextProgram = snap.progress.answer_mode === 'code'
  const code = useCodeStatus()
  const wide = window.matchMedia('(min-width: 768px)').matches
  return (
    <div className="flex flex-col gap-3">
      {writing ? <TextAnswer /> : null}
      {writing ? (
        <p className="text-xs text-muted-foreground">
          {confidence ? 'Write your answer, then press Enter.' : 'Say how sure you are, in the question above, to unlock this box.'}
        </p>
      ) : null}
      {canAnswer && !writing && nextWritten ? (
        <p className="text-center text-xs text-muted-foreground">Your next question will be in your own words.</p>
      ) : null}
      {canAnswer && nextProgram ? (
        <p className="text-center text-xs text-muted-foreground">Your next question will be a program to write.</p>
      ) : null}
      {/* Open on wide screens, where there is room and the switches should be seen; folded on a phone. */}
      <Collapsible defaultOpen={wide} className="bg-card rounded-xl border border-dashed px-3 py-2">
        <CollapsibleTrigger className="flex w-full items-center justify-between">
          <span className="eyebrow">Next question</span>
          <span className="text-muted-foreground flex items-center gap-1 text-xs">
            {nextProgram ? 'A program' : nextWritten ? 'In your own words' : 'Multiple choice'}
            <ChevronDownIcon className="size-3.5" />
          </span>
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2 flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="own-words" className="text-muted-foreground text-sm font-normal">
              Ask my next questions in my own words
            </Label>
            <Switch id="own-words" checked={nextWritten} disabled={!canAnswer} onCheckedChange={(on) => setMode(on ? 'text' : 'mcq')} />
          </div>
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="program-mode" className="text-muted-foreground text-sm font-normal">
              {code && !code.available ? 'Programs need the code sandbox (switched off here)' : 'Ask my next question as a program to write'}
            </Label>
            <Switch id="program-mode" checked={nextProgram} disabled={!canAnswer || !code?.available} onCheckedChange={(on) => setMode(on ? 'code' : 'mcq')} />
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

/** A new lesson should start at its top, because the student has to read it. Anything
 * else (their answer, the feedback, the "writing" note) belongs at the bottom. */
function useScrollToNewest() {
  const { snap } = useTutor()
  const last = snap.messages.at(-1)
  const key = last?.id
  const kind = last?.kind
  const working = snap.status === 'working'
  useEffect(() => {
    if (!key) return
    // The message may not be in the page yet when this runs (a feedback card and the next lesson can
    // arrive together), so keep looking for a moment rather than giving up after one frame. Giving up
    // left the new lesson hidden under the footer until the student scrolled to find it.
    let frame = 0
    let tries = 0
    let following = true
    let watcher: ResizeObserver | undefined
    const find = () =>
      kind === 'lesson' ? document.getElementById(`${key}-lesson_header`) : document.getElementById('thread-end')
    const align = (behavior: ScrollBehavior) =>
      find()?.scrollIntoView({ block: kind === 'lesson' ? 'start' : 'end', behavior })
    const go = () => {
      if (!find()) {
        if (tries++ < 60) frame = requestAnimationFrame(go)
        return
      }
      align('smooth')
      // A diagram or a web font finishes drawing after this and makes the lesson taller, which would
      // leave its menu off the bottom of the screen. Stay aligned while the page settles, and stop the
      // moment the student takes over the scrolling themselves.
      const content = document.getElementById('thread-end')?.parentElement
      if (content && typeof ResizeObserver !== 'undefined') {
        watcher = new ResizeObserver(() => following && align('auto'))
        watcher.observe(content)
      }
    }
    const stopFollowing = () => {
      following = false
    }
    const events = ['wheel', 'touchmove', 'keydown', 'mousedown'] as const
    events.forEach((e) => window.addEventListener(e, stopFollowing, { passive: true }))
    const settled = window.setTimeout(stopFollowing, 4000)
    frame = requestAnimationFrame(go)
    return () => {
      cancelAnimationFrame(frame)
      window.clearTimeout(settled)
      watcher?.disconnect()
      events.forEach((e) => window.removeEventListener(e, stopFollowing))
    }
  }, [key, kind, working])
}

export const Thread: FC = () => {
  useScrollToNewest()
  return <ThreadView />
}

const ThreadView: FC = () => (
  <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
    <ThreadPrimitive.Viewport
      autoScroll={false}
      scrollToBottomOnRunStart={false}
      scrollToBottomOnInitialize={false}
      scrollToBottomOnThreadSwitch={false}
      className="relative flex flex-1 flex-col overflow-y-auto scroll-smooth">
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-4 pt-8">
        <ThreadPrimitive.Messages>{() => <Message />}</ThreadPrimitive.Messages>
        <AuiIf condition={(s) => s.thread.isRunning}>
          <Working />
        </AuiIf>
        <ThreadPrimitive.ViewportFooter className="from-background via-background sticky bottom-0 mt-auto bg-gradient-to-t to-transparent pt-6 pb-4 md:pb-6">
          <Footer />
        </ThreadPrimitive.ViewportFooter>
        {/* After the footer, not before it: scrolling here stops with the footer BELOW the last message.
            Before it, the sticky footer covered the last ~90px of the thread, which is where the menu sits. */}
        <div id="thread-end" />
      </div>
    </ThreadPrimitive.Viewport>
  </ThreadPrimitive.Root>
)
