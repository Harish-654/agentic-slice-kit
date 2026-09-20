import { useEffect, useState, type FC } from 'react'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { api, ApiError, type Languages } from '@/lib/api'
import { useCodeStatus } from '@/lib/useCodeStatus'
import { CodeEditor } from './CodeEditor'
import { useTutor } from './context'

/** The code sandbox, on every topic: run your own code beside the lesson, in the language and version you pick here.
 * This is the only place a language is chosen. It changes what the editor runs and what the next program question is
 * written in, never what a lesson is about. The sandbox fails closed: if the chosen runtime cannot prove it is
 * isolated, the editor gives way to the reason, and the picker stays so you can switch to one that works. A failure
 * teaches the tutor which idea you are missing; a run that only works counts for nothing unless you say what it
 * should print. */
export const CodeCoach: FC = () => {
  const { snap, refresh } = useTutor()
  const { language } = snap.progress
  const status = useCodeStatus(language.id, language.version)
  const [langs, setLangs] = useState<Languages | null>(null)
  const [code, setCode] = useState('')
  const [assisted, setAssisted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.languages().then(setLangs, () => setLangs(null))
  }, [])

  const chosen = langs?.languages.find((l) => l.id === language.id)
  // A lesson being written owns the learner model for a moment; the server would refuse a change, so do not offer one.
  const locked = snap.status === 'working'

  async function pick(id: string, version: string | null) {
    setError(null)
    try {
      await api.setLanguage(snap.id, id, version)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not change the language.')
    }
  }

  return (
    <section className="space-y-3 p-5">
      <h3 className="eyebrow">Code sandbox</h3>
      {chosen && langs ? (
        <div className="grid grid-cols-2 gap-3">
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor="sandbox-language" className="text-xs">
              Language
            </Label>
            <Select id="sandbox-language" value={language.id} disabled={locked} onChange={(e) => pick(e.target.value, null)}>
              {langs.languages.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor="sandbox-version" className="text-xs">
              Version
            </Label>
            <Select id="sandbox-version" value={language.version} disabled={locked} onChange={(e) => pick(language.id, e.target.value)}>
              {chosen.versions.map((v) => (
                <option key={v} value={v}>
                  {v}
                  {chosen.installed[v] ? '' : ' (no code)'}
                </option>
              ))}
            </Select>
          </div>
        </div>
      ) : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      {!status ? null : !status.available ? (
        <p className="text-muted-foreground text-xs">
          Running {language.label} is switched off on this server. {status.reason}
        </p>
      ) : (
        <CodeEditor
          code={code}
          setCode={(c) => {
            setCode(c)
            if (!c.trim()) setAssisted(false)
          }}
          assisted={assisted}
          setAssisted={setAssisted}
          allowExpected
        />
      )}
    </section>
  )
}
