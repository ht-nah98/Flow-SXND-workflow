import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { API_BASE } from './client'
import { connectEvents } from './events'
import { mergeStale, staleFor, type Stale } from './invalidation'

interface ConnectionState { wsOpen: boolean; wsDownSince: number | null }
const Ctx = createContext<ConnectionState>({ wsOpen: false, wsDownSince: null })
export const useConnection = () => useContext(Ctx)

export function ConnectionProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [state, setState] = useState<ConnectionState>({ wsOpen: false, wsDownSince: Date.now() })
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null)
  const batch = useRef<Stale[]>([])

  useEffect(() => {
    const refresh = (stale: Stale) => {
      if (!stale) return
      batch.current.push(stale)
      if (pending.current) return
      pending.current = setTimeout(() => {
        pending.current = null
        const p = mergeStale(batch.current)
        batch.current = []
        if (p) void qc.invalidateQueries({ predicate: (q) => p(q.queryKey) })
      }, 300)
    }
    return connectEvents({
      url: API_BASE.replace(/^http/, 'ws') + '/ws/dashboard',
      onEvent: (e) => refresh(staleFor(e)),
      onStatus: (open) => {
        setState({ wsOpen: open, wsDownSince: open ? null : Date.now() })
        if (open) refresh((k) => k[0] !== 'health')   // back online: anything may have changed meanwhile
      },
    })
  }, [qc])

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>
}
