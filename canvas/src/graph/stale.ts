import type { Character, FlowRequest, Orientation, Scene } from '../api/types'
import { matchesName } from './mapping'

const IMAGE = new Set(['GENERATE_IMAGE', 'REGENERATE_IMAGE', 'EDIT_IMAGE'])
const ASSET = new Set(['GENERATE_CHARACTER_IMAGE', 'REGENERATE_CHARACTER_IMAGE', 'EDIT_CHARACTER_IMAGE', 'UPLOAD_IMAGE'])

function latest(reqs: FlowRequest[], pred: (r: FlowRequest) => boolean): string | null {
  let best: string | null = null
  for (const r of reqs) {
    if (r.status === 'COMPLETED' && pred(r) && r.updated_at && (!best || r.updated_at > best)) best = r.updated_at
  }
  return best
}

export function computeStale(scenes: Scene[], characters: Character[], requests: FlowRequest[],
                             orientation: Orientation): Set<string> {
  const byId = new Map(scenes.map((s) => [s.id, s]))
  const imgAt = new Map(scenes.map((s) => [s.id, latest(requests, (r) =>
    r.scene_id === s.id && IMAGE.has(r.type) && (!r.orientation || r.orientation === orientation))]))
  const assetAt = new Map(characters.map((c) => [c.id, latest(requests, (r) =>
    r.character_id === c.id && ASSET.has(r.type))]))
  const stale = new Set<string>()
  const visiting = new Set<string>()

  const check = (id: string): boolean => {
    if (stale.has(id)) return true
    if (visiting.has(id)) return false
    visiting.add(id)
    const s = byId.get(id)!
    const mine = imgAt.get(id)
    let result = false
    if (mine) {
      const parent = s.parent_scene_id ? byId.get(s.parent_scene_id) : undefined
      if (parent) {
        const pAt = imgAt.get(parent.id)
        if ((pAt && pAt > mine) || check(parent.id)) result = true
      }
      for (const name of s.character_names ?? []) {
        const c = characters.find((x) => matchesName(x, name))
        const at = c ? assetAt.get(c.id) : null
        if (at && at > mine) result = true
      }
    }
    visiting.delete(id)
    if (result) stale.add(id)
    return result
  }
  scenes.forEach((s) => check(s.id))
  return stale
}
