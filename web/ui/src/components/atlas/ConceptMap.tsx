import { useState, type FC } from 'react'
import { MermaidView } from '@/components/tutor/MermaidView'
import type { Progress } from '@/lib/api'
import { cn } from '@/lib/utils'

/** The plan as a picture that follows the student: a flowchart (green known, amber shaky, grey new,
 * blue outline for where they are now) or a mind map with the percentages. Built by the server,
 * redrawn as it changes. */
export const ConceptMap: FC<{ map: NonNullable<Progress['map']> }> = ({ map }) => {
  const [tab, setTab] = useState<'map' | 'mind'>('map')
  return (
    <div className="flex flex-col gap-2">
      <div className="inline-flex self-start rounded-lg border p-0.5 text-xs" role="tablist" aria-label="Map style">
        {([['map', 'Map'], ['mind', 'Mind map']] as const).map(([value, name]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn('rounded-md px-2 py-0.5 transition-colors', tab === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')}
          >
            {name}
          </button>
        ))}
      </div>
      <MermaidView key={tab} source={tab === 'map' ? map.flowchart : map.mindmap} className="flex justify-center overflow-x-auto" />
      {tab === 'map' ? <p className="text-muted-foreground text-xs">Green: you know it. Amber: shaky. Grey: new. Blue outline: now.</p> : null}
    </div>
  )
}
