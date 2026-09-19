// The app's motion vocabulary. Components import from here rather than inventing timings, so
// everything moves like the same hand made it. Reduced motion is handled once, by
// <MotionConfig reducedMotion="user"> in main.tsx.
export const ease = [0.22, 1, 0.36, 1] as const
export const dur = { fast: 0.15, base: 0.28, slow: 0.7 } as const
export const spring = { type: 'spring', stiffness: 240, damping: 30, mass: 0.9 } as const

/** A page or card arriving: rises a few pixels and fades in. */
export const rise = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: dur.base, ease },
} as const

/** A stamp landing: tips in with a small overshoot, then lies flat. Used for feedback. */
export const stamp = {
  initial: { opacity: 0, scale: 1.12, rotate: -3 },
  animate: { opacity: 1, scale: 1, rotate: 0 },
  transition: { type: 'spring', stiffness: 380, damping: 22 },
} as const

/** Staggered children, for lists that draw in one after another. */
export const stagger = (step = 0.06) => ({ animate: { transition: { staggerChildren: step } } })
export const item = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: { duration: dur.base, ease } },
} as const
