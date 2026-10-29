import { describe, expect, it } from 'vitest'
import { buildRequests, countVideos } from './actions'
import { estimateCredits } from './credits'
import { character, scene, video } from '../test/fixtures'

const v = video()
const root = scene({ id: 's1' })
const child = scene({ id: 's2', display_order: 1, parent_scene_id: 's1', chain_type: 'CONTINUATION', horizontal_image_status: 'PENDING', horizontal_image_url: null })

describe('buildRequests (project in image → video mode)', () => {
  it('asset image: GENERATE when no media, REGENERATE otherwise', () => {
    expect(buildRequests({ kind: 'asset-image', character: character({ media_id: null }) }, 'p1', 'image')[0].type)
      .toBe('GENERATE_CHARACTER_IMAGE')
    expect(buildRequests({ kind: 'asset-image', character: character() }, 'p1', 'image')[0])
      .toEqual({ type: 'REGENERATE_CHARACTER_IMAGE', character_id: 'c1', project_id: 'p1' })
  })

  it('scene image: EDIT for continuation, REGENERATE for completed root', () => {
    expect(buildRequests({ kind: 'scene-image', scene: child, video: v }, 'p1', 'image')[0].type).toBe('EDIT_IMAGE')
    expect(buildRequests({ kind: 'scene-image', scene: root, video: v }, 'p1', 'image')[0]).toEqual({
      type: 'REGENERATE_IMAGE', scene_id: 's1', video_id: 'v1', project_id: 'p1', orientation: 'HORIZONTAL' })
  })

  it('scene video: GENERATE when none yet', () => {
    expect(buildRequests({ kind: 'scene-video', scene: root, video: v }, 'p1', 'image')[0].type).toBe('GENERATE_VIDEO')
  })

  it('r2v: a root scene with refs and no image goes straight to GENERATE_VIDEO_REFS', () => {
    const r2v = scene({ id: 's3', horizontal_image_status: null, horizontal_image_url: null })
    expect(buildRequests({ kind: 'scene-video', scene: r2v, video: v }, 'p1', 'image')[0].type).toBe('GENERATE_VIDEO_REFS')
    const reqs = buildRequests({ kind: 'video-missing', video: v, scenes: [r2v] }, 'p1', 'image')
    expect(reqs.map((r) => r.type)).toEqual(['GENERATE_VIDEO_REFS'])
    expect(countVideos(reqs)).toBe(1)
  })

  it('video-missing queues missing images and all missing videos in display order', () => {
    const reqs = buildRequests({ kind: 'video-missing', video: v, scenes: [child, root] }, 'p1', 'image')
    expect(reqs.map((r) => `${r.type}:${r.scene_id}`)).toEqual(
      ['GENERATE_VIDEO:s1', 'EDIT_IMAGE:s2', 'GENERATE_VIDEO:s2'])
    expect(countVideos(reqs)).toBe(2)
  })

  it('video-stale regenerates image and video of stale scenes only', () => {
    const reqs = buildRequests({ kind: 'video-stale', video: v, scenes: [root, child], stale: new Set(['s2']) }, 'p1', 'image')
    expect(reqs.map((r) => `${r.type}:${r.scene_id}`)).toEqual(['EDIT_IMAGE:s2', 'REGENERATE_VIDEO:s2'])
  })

  it('video-missing skips a scene that already has an active request (no double-spend)', () => {
    const reqs = buildRequests(
      { kind: 'video-missing', video: v, scenes: [child, root], busy: new Set(['s1']) }, 'p1', 'image')
    expect(reqs.map((r) => `${r.type}:${r.scene_id}`)).toEqual(['EDIT_IMAGE:s2', 'GENERATE_VIDEO:s2'])
  })

  it('video-stale skips a stale scene that already has an active request', () => {
    const reqs = buildRequests(
      { kind: 'video-stale', video: v, scenes: [root, child], stale: new Set(['s1', 's2']), busy: new Set(['s2']) }, 'p1', 'image')
    expect(reqs.map((r) => `${r.type}:${r.scene_id}`)).toEqual(['REGENERATE_IMAGE:s1', 'REGENERATE_VIDEO:s1'])
  })
})

describe('estimateCredits', () => {
  it('uses the model family rate', () => {
    expect(estimateCredits(3, 'veo')).toBe(60)
    expect(estimateCredits(3, 'omni_flash')).toBe(45)
    expect(estimateCredits(1, 'unknown')).toBe(20)
  })
})

describe('buildRequests (default refs mode: prompt + assets, directive D1)', () => {
  it('never makes a scene image, even for continuation or scenes that already had one', () => {
    expect(buildRequests({ kind: 'scene-image', scene: root, video: v }, 'p1', 'refs')).toEqual([])
    expect(buildRequests({ kind: 'scene-video', scene: root, video: v }, 'p1', 'refs')[0].type).toBe('GENERATE_VIDEO_REFS')
    const missing = buildRequests({ kind: 'video-missing', video: v, scenes: [child, root] }, 'p1', 'refs')
    expect(missing.map((r) => `${r.type}:${r.scene_id}`)).toEqual(['GENERATE_VIDEO_REFS:s1', 'GENERATE_VIDEO_REFS:s2'])
    const stale = buildRequests({ kind: 'video-stale', video: v, scenes: [root, child], stale: new Set(['s1', 's2']) }, 'p1', 'refs')
    expect(stale.every((r) => r.type === 'GENERATE_VIDEO_REFS')).toBe(true)
  })
})
