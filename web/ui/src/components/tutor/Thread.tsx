import { useEffect, type FC } from 'react'
import { AuiIf, ComposerPrimitive, MessagePrimitive, ThreadPrimitive, useAuiState } from '@assistant-ui/react'
import { ArrowUpIcon } from 'lucide-react'
import { MarkdownText } from '@/components/assistant-ui/elements/markdown-text'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { DiagramView, EndCard, FeedbackCard, LessonHeader, NoticeCard, QuizCard } from './cards'
import { useTutor } from './context'

const TOOLS = {
  by_name: {
    lesson_header: LessonHeader,
    diagram: DiagramView,
    quiz: QuizCard,
    feedback: FeedbackCard,
    end: EndCard,
    notice: NoticeCard,
  },
}

const AssistantMessage: FC = () => (
  <MessagePrimitive.Root className="fade-in slide-in-from-bottom-1 animate-in duration-200">
    <div className="text-[0.95rem] leading-relaxed">
      <MessagePrimitive.Parts components={{ Text: MarkdownText, tools: TOOLS }} />
    </div>
  </MessagePrimitive.Root>
)

const UserMessage: FC = () => (
  <MessagePrimitive.Root className="fade-in slide-in-from-bottom-1 animate-in flex justify-end duration-200">
    <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground">
      <MessagePrimitive.Parts components={{ Text: ({ text }) => <p className="whitespace-pre-wrap">{text}</p> }} />
    </div>
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
    <div className="flex items-center gap-3 text-sm text-muted-foreground" role="status" aria-live="polite">
      <span className="flex gap-1" aria-hidden>
        {[0, 150, 300].map((d) => (
          <span key={d} className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: `${d}ms` }} />
        ))}
      </span>
      {label}
    </div>
  )
}

/** The answer box, for students who chose to answer in their own words. */
const TextAnswer: FC = () => (
  <ComposerPrimitive.Root className="flex items-end gap-2 rounded-2xl border bg-muted/30 p-2 focus-within:border-foreground/30">
    <ComposerPrimitive.Input
      placeholder="Explain it in your own words…"
      className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2.5 py-2 text-base leading-6 outline-none placeholder:text-muted-foreground/60"
      rows={1}
      autoFocus
      aria-label="Your answer"
    />
    <ComposerPrimitive.Send render={<Button type="button" size="icon" className="size-9 rounded-full" aria-label="Send answer" />}>
      <ArrowUpIcon className="size-4" />
    </ComposerPrimitive.Send>
  </ComposerPrimitive.Root>
)

const Footer: FC = () => {
  const { snap, canAnswer, setMode } = useTutor()
  const text = snap.progress.answer_mode === 'text'
  return (
    <div className="flex flex-col gap-3">
      {canAnswer && text ? <TextAnswer /> : null}
      {canAnswer && !text ? (
        <p className="text-center text-sm text-muted-foreground">Pick an answer in the card above.</p>
      ) : null}
      <div className="flex items-center justify-end gap-2">
        <Label htmlFor="own-words" className="text-sm font-normal text-muted-foreground">
          Answer in my own words
        </Label>
        <Switch
          id="own-words"
          checked={text}
          disabled={!canAnswer}
          onCheckedChange={(on) => setMode(on ? 'text' : 'mcq')}
        />
      </div>
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
    // One frame later, so the message has been rendered and its header exists.
    const frame = requestAnimationFrame(() => {
      const target =
        kind === 'lesson' ? document.getElementById(`${key}-lesson_header`) : document.getElementById('thread-end')
      target?.scrollIntoView({ block: kind === 'lesson' ? 'start' : 'end', behavior: 'smooth' })
    })
    return () => cancelAnimationFrame(frame)
  }, [key, kind, working])
}

export const Thread: FC = () => {
  useScrollToNewest()
  return <ThreadView />
}

const ThreadView: FC = () => (
  <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col bg-background">
    <ThreadPrimitive.Viewport
      autoScroll={false}
      scrollToBottomOnRunStart={false}
      scrollToBottomOnInitialize={false}
      scrollToBottomOnThreadSwitch={false}
      className="relative flex flex-1 flex-col overflow-y-auto scroll-smooth">
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 pt-6">
        <ThreadPrimitive.Messages>{() => <Message />}</ThreadPrimitive.Messages>
        <AuiIf condition={(s) => s.thread.isRunning}>
          <Working />
        </AuiIf>
        <div id="thread-end" />
        <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto bg-background pb-4 pt-2 md:pb-6">
          <Footer />
        </ThreadPrimitive.ViewportFooter>
      </div>
    </ThreadPrimitive.Viewport>
  </ThreadPrimitive.Root>
)
