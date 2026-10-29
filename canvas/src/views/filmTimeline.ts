import type { DirectorRun } from '../api/types'

/** How a shot is entered from the one before it in the film (the Storyboard draws it between the two). */
export type Join = 'cut' | 'chain' | 'occlusion' | 'screen' | 'action' | 'whip'
export const JOIN_ICON: Record<Join, string> = { cut: '✂', chain: '🔗', occlusion: '👤', screen: '📺', action: '✋', whip: '💨' }
export const JOIN_LABEL: Record<Join, string> = {
  cut: 'Cắt', chain: 'Liền mạch (khung cuối clip trước)', occlusion: 'Che ống kính', screen: 'Xuyên màn hình',
  action: 'Cắt giữa hành động', whip: 'Nhoè chuyển động',
}

export interface Segment { sceneId: string; order: number; start: number; len: number; join: Join }

type PlanShot = { id: string; order: number; continues?: boolean; join_in?: string }

/** Where each shot sits in the cut film, from the run's plan (`trims` follow the shots used, in order). Empty when the
 *  film was not cut by the director (nothing to follow while it plays). */
export function filmTimeline(run: DirectorRun | null | undefined): Segment[] {
  const trims = run?.plan.trims
  const shots = ((run?.plan.shotlist?.shots ?? []) as PlanShot[]).slice().sort((a, b) => a.order - b.order)
  const scenes = run?.plan.ids?.scenes ?? {}
  if (!trims?.length || !shots.length) return []
  const drop = new Set(run?.plan.drop ?? [])
  const used = shots.filter((s) => !drop.has(s.id))
  if (used.length !== trims.length) return []
  const mode = run?.plan.brief?.film_mode
  let t = 0
  return used.map((s, i) => {
    const [a, b] = trims[i]
    const adjacent = i > 0 && used[i - 1].order === s.order - 1
    const join: Join = !adjacent ? 'cut'
      : mode === 'keyframe' ? ((s.join_in ?? 'cut') as Join)
      : mode === 'continuous' && s.continues ? 'chain' : 'cut'
    const seg = { sceneId: scenes[s.id] ?? '', order: s.order, start: t, len: Math.max(0, b - a), join }
    t += seg.len
    return seg
  })
}

/** The segment playing at film time `t` (seconds), or -1. */
export const segmentAt = (segs: Segment[], t: number) => segs.findIndex((s) => t >= s.start && t < s.start + s.len)
