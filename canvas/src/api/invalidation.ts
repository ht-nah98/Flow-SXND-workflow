import type { FlowEvent } from './events'

type Key = readonly unknown[]
/** Which cached queries an event makes stale; null = none. */
export type Stale = ((key: Key) => boolean) | null

const everything: Stale = (k) => k[0] !== 'health'
const project = (pid: string): Stale => (k) => k[0] === 'p' && k[1] === pid
const anyProject: Stale = (k) => k[0] === 'p'
const roots = (...names: string[]): Stale => (k) => names.includes(String(k[0]))
const either = (...ps: Stale[]): Stale => (k) => ps.some((p) => p?.(k))

/**
 * Perf (19/10): every event used to refetch every query and redraw every node — and the worker sends a
 * `worker_tick` every 5 seconds, so an idle canvas reloaded ~10 queries every 5s. Now a tick changes nothing and
 * each event refreshes only the film it is about.
 */
export function staleFor(e: FlowEvent): Stale {
  const pid = typeof e.data?.project_id === 'string' ? e.data.project_id : null
  switch (e.type) {
    case 'worker_tick':
      return null
    case 'request_update':
      return pid ? either(project(pid), roots('credits', 'projects', 'library')) : everything
    case 'entity_changed':
      if (pid && e.data.entity === 'canvas') return (k) => k[0] === 'p' && k[1] === pid && k[2] === 'canvas'
      return pid ? either(project(pid), roots('projects')) : either(anyProject, roots('library', 'projects'))
    case 'director_stage':
    case 'director_gate':
    case 'director_error':
      // Events name the run, not the film; only the open film's queries are mounted, so this stays cheap.
      return either(anyProject, roots('timeline', 'projects', 'credits', 'edit'))
    case 'account_exhausted':
      return either(pid ? project(pid) : anyProject, roots('flow-accounts', 'projects'))
    case 'director_log':       // the run's 📋 Nhật ký; names the run only
      return (k) => k[0] === 'p' && k[2] === 'runlog'
    case 'film_review':        // names the run only; the review query lives under the open film
      return (k) => k[0] === 'p' && k[2] === 'film-review'
    case 'urls_refreshed':
      return either(anyProject, roots('library'))
    default:
      return everything
  }
}

/** Several events inside one debounce window: a query is stale if any of them says so. */
export const mergeStale = (ps: Stale[]): Stale => {
  const live = ps.filter((p): p is NonNullable<Stale> => p !== null)
  return live.length ? (k) => live.some((p) => p(k)) : null
}
