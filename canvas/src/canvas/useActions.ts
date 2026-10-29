import { useQueryClient } from '@tanstack/react-query'
import { useReactFlow } from '@xyflow/react'
import { useCallback, useMemo, useRef } from 'react'
import { api, mediaUrl } from '../api/client'
import { projectKey } from '../api/queries'
import type { FlowRequest, RequestCreate, Scene, Video } from '../api/types'
import { useChoice } from '../components/ChoiceDialog'
import { useCanGenerate } from '../components/StatusBar'
import { useToast } from '../components/Toast'
import { nodeKey } from '../graph/keys'
import { orientationOf, videoModeOf, type GraphInput } from '../graph/mapping'
import { buildRequests, countVideos } from '../lib/actions'
import { creditMessage } from '../lib/credits'
import { explainError } from '../lib/errors'
import { refreshProjectUrls } from '../lib/refreshUrls'
import type { CanvasActions } from './actions-context'

const IMAGE_TYPES = /^image\/(png|jpeg|webp)$/
const MAX_UPLOAD = 20 * 1024 * 1024

const IMAGE_REQUEST_TYPES = new Set([
  'GENERATE_IMAGE', 'REGENERATE_IMAGE', 'EDIT_IMAGE', 'GENERATE_CHARACTER_IMAGE', 'REGENERATE_CHARACTER_IMAGE',
])
const VIDEO_REQUEST_TYPES = new Set(['GENERATE_VIDEO', 'REGENERATE_VIDEO', 'GENERATE_VIDEO_REFS'])
const WAVE_POLL_MS = 2000
const WAVE_TIMEOUT_MS = 10 * 60 * 1000

/** Polls each request id until it reaches a terminal status (or the timeout elapses). */
async function waitForRequests(ids: string[]): Promise<Map<string, FlowRequest>> {
  const done = new Map<string, FlowRequest>()
  let remaining = ids
  const deadline = Date.now() + WAVE_TIMEOUT_MS
  while (remaining.length > 0 && Date.now() < deadline) {
    const results = await Promise.all(remaining.map((id) => api.getRequest(id)))
    remaining = []
    for (const r of results) {
      if (r.status === 'COMPLETED' || r.status === 'FAILED') done.set(r.id, r)
      else remaining.push(r.id)
    }
    if (remaining.length > 0) await new Promise((res) => setTimeout(res, WAVE_POLL_MS))
  }
  return done
}

/**
 * A video request built alongside its own scene's image request (video-stale,
 * video-missing) must not be submitted until that image is done — FlowKit's
 * worker only checks that *some* image exists, not that it's the new one, so
 * submitting both together can waste a video credit on the old image.
 */
async function submitInWaves(reqs: RequestCreate[]): Promise<{ sent: RequestCreate[]; failedScenes: number }> {
  const images = reqs.filter((r) => IMAGE_REQUEST_TYPES.has(r.type))
  const videos = reqs.filter((r) => VIDEO_REQUEST_TYPES.has(r.type))
  if (images.length === 0 || videos.length === 0) {
    await api.submitRequests(reqs)
    return { sent: reqs, failedScenes: 0 }
  }
  const createdImages = await api.submitRequests(images)
  const results = await waitForRequests(createdImages.map((r) => r.id))
  const failedSceneIds = new Set(
    [...results.values()].filter((r) => r.status === 'FAILED').map((r) => r.scene_id).filter((id) => id != null))
  const toSubmit = videos.filter((r) => !r.scene_id || !failedSceneIds.has(r.scene_id))
  const sent = [...images]
  if (toSubmit.length > 0) {
    await api.submitRequests(toSubmit)
    sent.push(...toSubmit)
  }
  return { sent, failedScenes: failedSceneIds.size }
}

export function useActions(pid: string, data: GraphInput | undefined): CanvasActions {
  const qc = useQueryClient()
  const toast = useToast()
  const choose = useChoice()
  const rf = useReactFlow()
  const canGenerate = useCanGenerate()
  const sharedOk = useRef(new Set<string>())
  // Perf (19/10): the actions read the latest data through a ref, so the context value stays the same object and a
  // data refresh does not redraw every node that uses the actions.
  const dataRef = useRef(data)
  dataRef.current = data
  const family = data?.project.video_model_family ?? 'veo'

  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: projectKey(pid) })
    void qc.invalidateQueries({ queryKey: ['library'] })
  }, [qc, pid])
  const fail = useCallback((e: unknown) => {
    const { message, hint } = explainError(e instanceof Error ? e.message : String(e))
    toast(hint ? `${message}. ${hint}` : message, 'error')
  }, [toast])
  const guard = useCallback(async <T,>(fn: () => Promise<T>): Promise<T> => {
    try { const r = await fn(); refresh(); return r } catch (e) { fail(e); throw e }
  }, [refresh, fail])

  /** Spec §4.6: the first change to an asset shared by several projects asks "all vs clone". Returns the id to change. */
  const ownAsset = useCallback(async (id: string): Promise<string> => {
    if (sharedOk.current.has(id)) return id
    const used = await api.characterProjects(id)
    let target = id
    if (used.length > 1) {
      const pick = await choose({
        title: 'Asset đang dùng chung',
        body: `Asset này đang dùng ở ${used.length} project: ${used.map((p) => p.name).join(', ')}.`,
        options: [{ value: 'clone', label: 'Nhân bản để sửa riêng' }, { value: 'all', label: 'Sửa cho tất cả' }],
      })
      if (pick === null) throw new Error('Đã huỷ sửa asset')
      if (pick === 'clone') {
        const old = rf.getNode(nodeKey.character(id))
        const copy = await api.cloneCharacter(id, pid)
        await api.putCanvasNode(pid, nodeKey.character(copy.id), { x: old?.position.x ?? 0, y: old?.position.y ?? 0 })
        toast(`Đã nhân bản thành "${copy.name}"`)
        target = copy.id
      }
    }
    sharedOk.current.add(target)
    return target
  }, [choose, rf, pid, toast])

  return useMemo<CanvasActions>(() => ({
    projectId: pid,
    family,
    canGenerate,
    patchScene: (id, patch) => guard(() => api.patchScene(id, patch)),
    patchVideo: (id, patch) => guard(() => api.patchVideo(id, patch)),
    patchProject: (patch) => guard(() => api.patchProject(pid, patch)),

    patchCharacter: (id, patch) => guard(async () => api.patchCharacter(await ownAsset(id), patch)),

    run: async (a) => {
      try {
        if (a.kind === 'asset-image') {
          const cid = await ownAsset(a.character.id)
          if (cid !== a.character.id) a = { ...a, character: { ...a.character, id: cid } }
        }
        const reqs = buildRequests(a, pid, videoModeOf(dataRef.current?.project))
        if (!reqs.length) { toast('Không có gì cần tạo'); return }
        const n = countVideos(reqs)
        if (n > 0) {
          const ok = await choose({ title: 'Xác nhận tạo video', body: creditMessage(n, family),
                                    options: [{ value: 'ok', label: `Tạo ${n} video` }] })
          if (ok !== 'ok') return
        }
        if (a.kind === 'video-stale' || a.kind === 'video-missing') {
          toast(`Đang gửi ${reqs.length} yêu cầu tạo`)
          const { sent, failedScenes } = await submitInWaves(reqs)
          toast(`Đã gửi ${sent.length} yêu cầu tạo`)
          if (failedScenes > 0) {
            toast(`${failedScenes} cảnh tạo ảnh thất bại, bỏ qua video cho các cảnh đó`, 'error')
          }
        } else {
          await api.submitRequests(reqs)
          toast(`Đã gửi ${reqs.length} yêu cầu tạo`)
        }
        refresh()
      } catch (e) { fail(e) }
    },

    concat: async (v) => {
      try {
        const r = await api.concatVideo(v.id, orientationOf(v))
        toast(r.scenes_missing ? `Đã ghép, thiếu ${r.scenes_missing} cảnh chưa có video` : 'Đã ghép video')
        refresh()
      } catch (e) { fail(e) }
    },

    uploadCharacterImage: async (cid, file) => {
      if (!IMAGE_TYPES.test(file.type) || file.size > MAX_UPLOAD) {
        toast('Chỉ nhận ảnh PNG, JPG hoặc WEBP, tối đa 20 MB', 'error')
        return
      }
      try {
        await api.uploadCharacterImage(await ownAsset(cid), pid, file)
        toast('Đã upload ảnh tham chiếu')
        refresh()
      } catch (e) { fail(e) }
    },

    restore: async (t, v) => {
      const sceneImage = t.kind === 'scene' && t.media === 'image'
      const canPrompt = !!v.prompt_snapshot && !v.prompt_snapshot.startsWith('upload:')
      const pick = await choose({
        title: 'Dùng phiên bản này?',
        body: (v.prompt_snapshot ? `Prompt lúc đó:\n${v.prompt_snapshot}` : 'Không rõ prompt của phiên bản này.') +
              (sceneImage ? '\n\nVideo hiện tại của cảnh sẽ bị xoá để tạo lại từ ảnh này.' : ''),
        options: [{ value: 'media', label: 'Chỉ dùng kết quả' },
                  ...(canPrompt ? [{ value: 'both', label: 'Dùng cả prompt cũ' }] : [])],
      })
      if (!pick) return
      try {
        if (t.kind === 'character') await api.restoreCharacter(t.id, v.request_id, pick === 'both')
        else await api.restoreScene(t.id, v.request_id, t.media, t.orientation, pick === 'both')
        toast('Đã khôi phục phiên bản')
        refresh()
      } catch (e) { fail(e) }
    },

    review: (s) => api.reviewScene(s.video_id, s.id, pid),
    refreshUrls: async () => { try { await refreshProjectUrls(pid); refresh() } catch (e) { fail(e) } },

    setNoteText: async (key, text) => {
      const n = rf.getNode(key)
      const rec = await api.putCanvasNode(pid, key, { x: n?.position.x ?? 0, y: n?.position.y ?? 0, data: { text } })
      return { updated_at: rec.updated_at }
    },

    addNote: (at) => guard(async () => {
      await api.putCanvasNode(pid, nodeKey.note(crypto.randomUUID()), { ...at, data: { text: '' } })
    }),

    addScene: (video, at) => guard(async () => {
      const order = Math.max(-1, ...(dataRef.current?.scenesByVideo[video.id] ?? []).map((s) => s.display_order)) + 1
      const s = await api.createScene({ video_id: video.id, display_order: order, chain_type: 'ROOT',
                                        prompt: '', video_prompt: '', character_names: [] })
      await api.putCanvasNode(pid, nodeKey.scene(s.id), at)
    }),

    addContinuation: (parent, at) => guard(async () => {
      const siblings = [...(dataRef.current?.scenesByVideo[parent.video_id] ?? [])]
        .filter((s) => s.display_order > parent.display_order)
        .sort((a, b) => b.display_order - a.display_order)
      for (const s of siblings) await api.patchScene(s.id, { display_order: s.display_order + 1 })
      const s = await api.createScene({
        video_id: parent.video_id, display_order: parent.display_order + 1, chain_type: 'CONTINUATION',
        parent_scene_id: parent.id, character_names: parent.character_names ?? [], prompt: '', video_prompt: '',
      })
      await api.putCanvasNode(pid, nodeKey.scene(s.id), at)
    }),

    moveScene: (_video: Video, scenes: Scene[], sceneId, dir) => guard(async () => {
      const sorted = [...scenes].sort((a, b) => a.display_order - b.display_order)
      const i = sorted.findIndex((s) => s.id === sceneId)
      const j = i + dir
      if (i < 0 || j < 0 || j >= sorted.length) return
      await api.patchScene(sorted[i].id, { display_order: sorted[j].display_order })
      await api.patchScene(sorted[j].id, { display_order: sorted[i].display_order })
    }),

    placeCharacter: (cid, at) => guard(async () => {
      if (!dataRef.current?.characters.some((c) => c.id === cid)) await api.attachCharacter(pid, cid)
      await api.putCanvasNode(pid, nodeKey.character(cid), at)
    }),

    createAsset: (input, at, file) => guard(async () => {
      const c = await api.createCharacter(input)
      await api.attachCharacter(pid, c.id)
      await api.putCanvasNode(pid, nodeKey.character(c.id), at)
      if (file) await api.uploadCharacterImage(c.id, pid, file)
    }),

    exportProject: async () => {
      try {
        const r = await api.exportProject(pid)
        toast(r.skipped.length
          ? `Đã xuất ${r.downloaded} file, bỏ qua ${r.skipped.length} (hết hạn/thiếu)`
          : `Đã xuất ${r.downloaded} file`)
        window.open(mediaUrl(r.zip_path) ?? undefined, '_blank')
      } catch (e) { fail(e) }
    },
  }), [pid, family, canGenerate, guard, ownAsset, choose, rf, toast, refresh, fail])
}
