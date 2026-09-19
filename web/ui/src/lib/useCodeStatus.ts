import { useEffect, useState } from 'react'
import { api } from './api'

/** Whether the server may run code at all (null until it answers). Shared by the code coach
 * and the "program" question switch, so neither offers what the server would refuse. */
export function useCodeStatus() {
  const [status, setStatus] = useState<{ available: boolean; reason: string } | null>(null)
  useEffect(() => {
    api.codeStatus().then(setStatus, () => setStatus({ available: false, reason: 'Could not reach the tutor.' }))
  }, [])
  return status
}
