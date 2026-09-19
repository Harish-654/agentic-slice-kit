import type { FC } from 'react'
import { m } from 'motion/react'
import type { CalibrationRead } from '@/lib/derive'
import { ease } from '@/design/motion'

/** A half-circle gauge: how much of the time “how sure I am” matched “whether I was right”. */
export const CalibrationDial: FC<{ read: CalibrationRead }> = ({ read }) => {
  const { counts, answered, dontKnow } = read
  const share = answered ? counts.calibrated / answered : 0
  const r = 52
  const arc = `M ${60 - r} 62 A ${r} ${r} 0 0 1 ${60 + r} 62`
  const sentence =
    answered === 0
      ? 'Answer a question and say how sure you are. The twin compares the two.'
      : counts.overconfident > 0
        ? `You were certain and wrong ${counts.overconfident} time${counts.overconfident > 1 ? 's' : ''}. That is the idea most worth fixing.`
        : counts.underconfident > 0
          ? `${counts.underconfident} right answer${counts.underconfident > 1 ? 's were' : ' was'} only a guess, so ${counts.underconfident > 1 ? 'they' : 'it'} will come back for practice.`
          : 'How sure you said you were matched how right you were.'
  return (
    <div className="flex items-center gap-5">
      <figure className="w-36 shrink-0" aria-label={`Calibration: ${counts.calibrated} of ${answered} answers matched`}>
        <svg viewBox="0 0 120 72" className="w-full overflow-visible">
          <path d={arc} fill="none" strokeWidth="9" strokeLinecap="round" className="stroke-border" />
          <m.path d={arc} fill="none" strokeWidth="9" strokeLinecap="round" className="stroke-twin" initial={{ pathLength: 0 }} animate={{ pathLength: share }} transition={{ duration: 0.9, ease }} />
          <text x="60" y="52" textAnchor="middle" className="fill-foreground font-heading text-[22px] font-semibold">
            {answered ? `${counts.calibrated}/${answered}` : '–'}
          </text>
          <text x="60" y="66" textAnchor="middle" className="fill-muted-foreground text-[7px] tracking-widest uppercase">matched</text>
        </svg>
      </figure>
      <div className="min-w-0 text-sm">
        <p className="leading-snug">{sentence}</p>
        <p className="text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
          <span>Certain & wrong: {counts.overconfident}</span>
          <span>Guess & right: {counts.underconfident}</span>
          <span>“I don’t know”: {dontKnow}</span>
        </p>
      </div>
    </div>
  )
}
