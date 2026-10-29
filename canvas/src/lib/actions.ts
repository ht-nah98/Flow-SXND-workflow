import type { Character, RequestCreate, Scene, Video } from '../api/types'
import { isRefsScene, orientationOf, sceneMedia, type VideoMode } from '../graph/mapping'

export type GenAction =
  | { kind: 'asset-image'; character: Character }
  | { kind: 'scene-image' | 'scene-video'; scene: Scene; video: Video }
  | { kind: 'video-missing'; video: Video; scenes: Scene[]; busy?: Set<string> }
  | { kind: 'video-stale'; video: Video; scenes: Scene[]; stale: Set<string>; busy?: Set<string> }

const VIDEO_TYPES = new Set(['GENERATE_VIDEO', 'REGENERATE_VIDEO', 'GENERATE_VIDEO_REFS'])

function imageReq(s: Scene, v: Video, pid: string, force: boolean): RequestCreate {
  const o = orientationOf(v)
  const done = sceneMedia(s, o).imageStatus === 'COMPLETED'
  const type = s.chain_type === 'CONTINUATION' && s.parent_scene_id
    ? 'EDIT_IMAGE' : done || force ? 'REGENERATE_IMAGE' : 'GENERATE_IMAGE'
  return { type, scene_id: s.id, video_id: v.id, project_id: pid, orientation: o }
}

function videoReq(s: Scene, v: Video, pid: string, force: boolean, mode: VideoMode): RequestCreate {
  const o = orientationOf(v)
  const done = sceneMedia(s, o).videoStatus === 'COMPLETED'
  const type = isRefsScene(s, o, mode) ? 'GENERATE_VIDEO_REFS' : done || force ? 'REGENERATE_VIDEO' : 'GENERATE_VIDEO'
  return { type,
           scene_id: s.id, video_id: v.id, project_id: pid, orientation: o }
}

export function buildRequests(a: GenAction, pid: string, mode: VideoMode): RequestCreate[] {
  switch (a.kind) {
    case 'asset-image':
      return [{ type: a.character.media_id ? 'REGENERATE_CHARACTER_IMAGE' : 'GENERATE_CHARACTER_IMAGE',
                character_id: a.character.id, project_id: pid }]
    case 'scene-image':
      return mode === 'image' ? [imageReq(a.scene, a.video, pid, false)] : []  // refs mode: no image step
    case 'scene-video':
      return [videoReq(a.scene, a.video, pid, false, mode)]
    case 'video-missing': {
      const o = orientationOf(a.video)
      return [...a.scenes].sort((x, y) => x.display_order - y.display_order)
        .filter((s) => !a.busy?.has(s.id))
        .flatMap((s) => {
          const m = sceneMedia(s, o)
          const out: RequestCreate[] = []
          if (m.imageStatus !== 'COMPLETED' && !isRefsScene(s, o, mode)) out.push(imageReq(s, a.video, pid, false))
          if (m.videoStatus !== 'COMPLETED') out.push(videoReq(s, a.video, pid, false, mode))
          return out
        })
    }
    case 'video-stale':
      return [...a.scenes].sort((x, y) => x.display_order - y.display_order)
        .filter((s) => a.stale.has(s.id) && !a.busy?.has(s.id))
        .flatMap((s) => isRefsScene(s, orientationOf(a.video), mode)
          ? [videoReq(s, a.video, pid, true, mode)]
          : [imageReq(s, a.video, pid, true), videoReq(s, a.video, pid, true, mode)])
  }
}

export const countVideos = (reqs: RequestCreate[]) => reqs.filter((r) => VIDEO_TYPES.has(r.type)).length
