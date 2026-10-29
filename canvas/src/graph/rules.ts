import type { Connection } from '@xyflow/react'
import type { Character, Scene } from '../api/types'
import { parseKey } from './keys'
import { matchesName } from './mapping'

export interface RuleContext { scenes: Map<string, Scene>; characters: Map<string, Character> }
export interface ScenePatch { sceneId: string; patch: Partial<Scene> }
export type ConnectionResult = { ok: true; mutation: ScenePatch } | { ok: false; reason: string }

const no = (reason: string): ConnectionResult => ({ ok: false, reason })

function isAncestor(candidate: string, of: string, scenes: Map<string, Scene>): boolean {
  let cur = scenes.get(of)?.parent_scene_id ?? null
  const seen = new Set<string>()
  while (cur && !seen.has(cur)) {
    if (cur === candidate) return true
    seen.add(cur)
    cur = scenes.get(cur)?.parent_scene_id ?? null
  }
  return false
}

export function checkConnection(c: Connection, ctx: RuleContext): ConnectionResult {
  if (!c.source || !c.target) return no('Thiếu điểm nối')
  const from = parseKey(c.source)
  const to = parseKey(c.target)

  if (from.kind === 'character' && to.kind === 'scene') {
    const ch = ctx.characters.get(from.id)
    const sc = ctx.scenes.get(to.id)
    if (!ch || !sc) return no('Không tìm thấy asset hoặc cảnh')
    const names = sc.character_names ?? []
    if (names.some((n) => matchesName(ch, n))) return no(`Cảnh đã dùng "${ch.name}"`)
    return { ok: true, mutation: { sceneId: sc.id, patch: { character_names: [...names, ch.name] } } }
  }

  if (from.kind === 'scene' && to.kind === 'scene') {
    const parent = ctx.scenes.get(from.id)
    const child = ctx.scenes.get(to.id)
    if (!parent || !child) return no('Không tìm thấy cảnh')
    if (parent.id === child.id) return no('Không thể nối cảnh với chính nó')
    if (parent.video_id !== child.video_id) return no('Hai cảnh thuộc hai video khác nhau')
    if (child.parent_scene_id && child.parent_scene_id !== parent.id) return no('Cảnh này đã có cảnh trước')
    if (child.parent_scene_id === parent.id) return no('Hai cảnh đã được nối')
    if (isAncestor(child.id, parent.id, ctx.scenes)) return no('Nối như vậy sẽ tạo vòng lặp')
    return { ok: true, mutation: { sceneId: child.id, patch: { parent_scene_id: parent.id, chain_type: 'CONTINUATION' } } }
  }

  return no('Chỉ nối được: asset → cảnh, hoặc cảnh → cảnh tiếp theo')
}

export function edgeRemoval(edgeId: string, ctx: RuleContext): ScenePatch | null {
  const [kind, rest] = edgeId.split(':', 2) as [string, string]
  const [a, b] = rest.split('->')
  if (kind === 'ref') {
    const ch = ctx.characters.get(a)
    const sc = ctx.scenes.get(b)
    if (!ch || !sc) return null
    return { sceneId: b, patch: { character_names: (sc.character_names ?? []).filter((n) => !matchesName(ch, n)) } }
  }
  if (kind === 'chain') return { sceneId: b, patch: { parent_scene_id: null, chain_type: 'ROOT' } }
  return null
}
