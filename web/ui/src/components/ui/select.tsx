import * as React from 'react'
import { cn } from 'cn'

/** The browser's own <select>, dressed like Input. Native on purpose: it works with a keyboard, a screen
 * reader and a phone's picker with nothing extra to load. */
function Select({ className, ...props }: React.ComponentProps<'select'>) {
  return (
    <select
      data-slot="select"
      className={cn(
        'border-input dark:bg-input/30 h-8 w-full min-w-0 rounded-lg border bg-transparent px-2 py-1 text-base transition-colors outline-none md:text-sm',
        'focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export { Select }
