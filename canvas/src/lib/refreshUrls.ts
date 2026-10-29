import { api } from '../api/client'

// Flow signed URLs expire (~6h). Every broken image on a page may ask for a
// refresh at once, and a link that is still broken afterwards would ask again
// forever — so share one call per project and hold its result for a cooldown.
const COOLDOWN_MS = 60_000
const cache = new Map<string, { at: number; p: Promise<void> }>()

export function refreshProjectUrls(pid: string): Promise<void> {
  const hit = cache.get(pid)
  if (hit && Date.now() - hit.at < COOLDOWN_MS) return hit.p
  const p = api.refreshUrls(pid).then(() => undefined)
  cache.set(pid, { at: Date.now(), p })
  return p
}

export function resetRefreshCache() { cache.clear() }
