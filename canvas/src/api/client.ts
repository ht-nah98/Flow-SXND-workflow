import type { RunLog,
  SampleAnalysis, SampleMeta,
  CreditSummary,
  RunTimeline, SystemCheck,
  EffectsCatalog, FilmEdit,
  VoiceChoice, FilmLanguage, Creativity, Agents,
  CanvasNodeRecord, DirectorRun, FilmReviewState, IdeaImageIn, Character, ConcatResult, ExportResult, FlowRequest, Health, Material, Orientation,
  Project, RequestCreate, Scene, SceneReview, Version, Video, FilmMode, AmbientChoice, Venue } from './types'

export const API_BASE: string = import.meta.env.VITE_FLOWKIT_URL ?? 'http://127.0.0.1:8110'

const CODE_RE = /(PUBLIC_ERROR_[A-Z_]+|UNSUPPORTED_ON_BATCH_API|NO_FLOW_PROJECT|NO_AT_TOKEN|CAPTCHA|Extension not connected)/

export class FlowKitError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body === undefined || isForm ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    })
  } catch {
    throw new FlowKitError(0, 'NETWORK', 'FlowKit chưa chạy')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
    } catch { /* non-JSON error body */ }
    throw new FlowKitError(res.status, detail.match(CODE_RE)?.[1] ?? 'HTTP', detail)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const q = (params: Record<string, string>) => `?${new URLSearchParams(params)}`

export const api = {
  health: () => call<Health>('GET', '/health'),
  uploadSample: (f: File) => { const fd = new FormData(); fd.append('file', f); return call<SampleMeta>('POST', '/api/learn/samples', fd) },
  listSamples: () => call<SampleMeta[]>('GET', '/api/learn/samples'),
  getSample: (sid: string) => call<SampleMeta & { analysis: SampleAnalysis | null }>('GET', `/api/learn/samples/${sid}`),
  retrySample: (sid: string) => call<SampleMeta>('POST', `/api/learn/samples/${sid}/retry`),
  adoptSample: (sid: string, techniques: number[]) => call<SampleMeta>('POST', `/api/learn/samples/${sid}/adopt`, { techniques }),
  sampleVideoUrl: (sid: string) => `${API_BASE}/api/learn/samples/${sid}/video`,
  systemCheck: () => call<SystemCheck>('GET', '/api/system/check'),
  credits: (projectId?: string) => call<CreditSummary>('GET', `/api/system/credits${projectId ? q({ project_id: projectId }) : ''}`),
  setDailyCap: (cap: number) => call<{ daily_credit_cap: number }>('PUT', '/api/system/settings', { daily_credit_cap: cap }),
  runTimeline: (rid: string) => call<RunTimeline>('GET', `/api/director/runs/${rid}/timeline`),
  runLog: (rid: string) => call<RunLog>('GET', `/api/director/runs/${rid}/log`),
  listProjects: () => call<Project[]>('GET', '/api/projects'),
  getProject: (pid: string) => call<Project>('GET', `/api/projects/${pid}`),
  createProject: (body: { name: string; story: string; material: string; flow_project_id?: string }) =>
    call<Project>('POST', '/api/projects', body),
  listMaterials: () => call<Material[]>('GET', '/api/materials'),
  listVideos: (pid: string) => call<Video[]>('GET', `/api/videos${q({ project_id: pid })}`),
  createVideo: (body: { project_id: string; title: string; orientation: Orientation; display_order: number }) =>
    call<Video>('POST', '/api/videos', body),
  createRun: (body: { text: string; target_s: number; orientation: Orientation; style: string; voice?: VoiceChoice; language?: FilmLanguage; creativity?: Creativity; style_pack?: string | null; agents?: Agents; film_mode?: FilmMode; images: IdeaImageIn[] } & AmbientChoice) =>
    call<DirectorRun>('POST', '/api/director/runs', body),
  listRuns: (pid: string) => call<DirectorRun[]>('GET', `/api/director/runs${q({ project_id: pid })}`),
  approveRun: (rid: string, gate: string, opts: { budget?: Record<string, number>; mode?: 'step' | 'auto' } = {}) =>
    call<DirectorRun>('POST', `/api/director/runs/${rid}/approve`, { gate, ...opts }),
  patchIdea: (rid: string, patch: { text?: string; target_s?: number; orientation?: Orientation; voice?: VoiceChoice; language?: FilmLanguage; creativity?: Creativity; style_pack?: string; film_mode?: FilmMode; notes?: Record<string, string | null> } & AmbientChoice) =>
    call<DirectorRun>('PATCH', `/api/director/runs/${rid}/idea`, patch),
  makeMissingRefs: (rid: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/refs`),
  rewriteShot: (rid: string, shotId: string, feedback: string, review?: SceneReview) =>
    call<{ shot_id: string; feedback: string; old: string; new: string }>('POST', `/api/director/runs/${rid}/shots/${shotId}/rewrite`,
      review ? { feedback, review: { score: review.overall_score, verdict: review.verdict, errors: review.errors, fix_guide: review.fix_guide } } : { feedback }),
  applyRewrite: (rid: string, shotId: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/shots/${shotId}/apply-rewrite`),
  filmReviews: (rid: string) => call<FilmReviewState>('GET', `/api/director/runs/${rid}/film-review`),
  startFilmReview: (rid: string, note: string) => call<FilmReviewState['job']>('POST', `/api/director/runs/${rid}/film-review`, { note }),
  recutRun: (rid: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/recut`),
  effectsCatalog: () => call<EffectsCatalog>('GET', '/api/director/effects'),
  getEdit: (rid: string) => call<FilmEdit>('GET', `/api/director/runs/${rid}/edit`),
  putEdit: (rid: string, edit: FilmEdit) => call<FilmEdit>('PUT', `/api/director/runs/${rid}/edit`, edit),
  setAgents: (rid: string, agents: Agents) => call<DirectorRun>('PUT', `/api/director/runs/${rid}/agents`, agents),
  assist: (body: { project_id: string; instruction: string; model?: string; targets: { kind: 'scene' | 'character'; id: string }[] }) =>
    call<{ answer: string; changes: { kind: 'scene' | 'character'; id: string; field: string; value: string; why: string }[] }>('POST', '/api/director/assist', body),
  flowAccounts: () => call<{ accounts: import('../components/FlowAccounts').FlowAccount[]; unidentified_connections: number; unidentified_reasons?: string[] }>('GET', '/api/flow/accounts'),
  moveFlowAccount: (pid: string, account: string) =>
    call<{ from: string | null; to: string; flow_project_id: string; pictures: string[] }>('POST', `/api/flow/projects/${pid}/move-account`, { account }),
  patchFlowAccount: (email: string, patch: { label?: string | null; status?: string; priority?: number }) =>
    call<unknown>('PATCH', `/api/flow/accounts/${encodeURIComponent(email)}`, patch),
  listVenues: () => call<Venue[]>('GET', '/api/director/venues'),
  listStyles: () => call<{ id: string; name: string; suits: string; core: string[] }[]>('GET', '/api/director/styles'),
  scriptPackage: (rid: string) =>
    call<{ folder: string | null; files: { name: string; content: string }[] }>('GET', `/api/director/runs/${rid}/package`),
  cancelRun: (rid: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/cancel`),
  pauseRun: (rid: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/pause`),
  reviseRun: (rid: string, feedback: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/revise`, { feedback }),
  resolveShotFailure: (rid: string, action: 'drop' | 'stop' | 'retry') =>
    call<DirectorRun>('POST', `/api/director/runs/${rid}/shot-failure`, { action }),
  retryRun: (rid: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/retry`),
  resumeRun: (rid: string) => call<DirectorRun>('POST', `/api/director/runs/${rid}/resume`),
  patchProject: (pid: string, patch: Partial<Project>) => call<Project>('PATCH', `/api/projects/${pid}`, patch),
  patchVideo: (vid: string, patch: Partial<Video>) => call<Video>('PATCH', `/api/videos/${vid}`, patch),
  concatVideo: (vid: string, orientation: Orientation) =>
    call<ConcatResult>('POST', `/api/videos/${vid}/concat`, { orientation }),
  listScenes: (vid: string) => call<Scene[]>('GET', `/api/scenes${q({ video_id: vid })}`),
  createScene: (body: Partial<Scene> & { video_id: string; display_order: number }) =>
    call<Scene>('POST', '/api/scenes', body),
  patchScene: (sid: string, patch: Partial<Scene>) => call<Scene>('PATCH', `/api/scenes/${sid}`, patch),
  deleteScene: (sid: string) => call<{ ok: boolean }>('DELETE', `/api/scenes/${sid}`),
  listAllCharacters: () => call<Character[]>('GET', '/api/characters'),
  listProjectCharacters: (pid: string) => call<Character[]>('GET', `/api/projects/${pid}/characters`),
  createCharacter: (body: Omit<Partial<Character>, 'entity_type'> & { name: string; entity_type: string }) =>
    call<Character>('POST', '/api/characters', body),
  patchCharacter: (cid: string, patch: Partial<Character>) =>
    call<Character>('PATCH', `/api/characters/${cid}`, patch),
  attachCharacter: (pid: string, cid: string) => call<unknown>('POST', `/api/projects/${pid}/characters/${cid}`),
  characterProjects: (cid: string) => call<{ id: string; name: string }[]>('GET', `/api/characters/${cid}/projects`),
  cloneCharacter: (cid: string, pid: string) =>
    call<Character>('POST', `/api/characters/${cid}/clone`, { project_id: pid }),
  uploadCharacterImage: (cid: string, pid: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    form.append('project_id', pid)
    return call<Character>('POST', `/api/characters/${cid}/upload`, form)
  },
  submitRequests: (requests: RequestCreate[]) =>
    call<FlowRequest[]>('POST', '/api/requests/batch', { requests }),
  getRequest: (rid: string) => call<FlowRequest>('GET', `/api/requests/${rid}`),
  listRequests: (vid: string) => call<FlowRequest[]>('GET', `/api/requests${q({ video_id: vid })}`),
  listProjectRequests: (pid: string) => call<FlowRequest[]>('GET', `/api/requests${q({ project_id: pid })}`),
  characterVersions: (cid: string) => call<Version[]>('GET', `/api/characters/${cid}/versions`),
  sceneVersions: (sid: string, kind: 'image' | 'video', orientation: Orientation) =>
    call<Version[]>('GET', `/api/scenes/${sid}/versions${q({ kind, orientation })}`),
  restoreCharacter: (cid: string, requestId: string, restorePrompt: boolean) =>
    call<Character>('POST', `/api/characters/${cid}/restore`, { request_id: requestId, restore_prompt: restorePrompt }),
  restoreScene: (sid: string, requestId: string, kind: 'image' | 'video', orientation: Orientation, restorePrompt: boolean) =>
    call<Scene>('POST', `/api/scenes/${sid}/restore`, {
      request_id: requestId, kind, orientation, restore_prompt: restorePrompt,
    }),
  reviewScene: (vid: string, sid: string, pid: string) =>
    call<SceneReview>('POST', `/api/videos/${vid}/scenes/${sid}/review${q({ project_id: pid })}`),
  refreshUrls: (pid: string) => call<unknown>('POST', `/api/flow/refresh-urls/${pid}`),
  detachCharacter: (pid: string, cid: string) => call<unknown>('DELETE', `/api/projects/${pid}/characters/${cid}`),
  flowStatus: () => call<{ flow_project_id: string | null }>('GET', '/api/flow/status'),
  getCanvas: (pid: string) => call<{ nodes: CanvasNodeRecord[] }>('GET', `/api/projects/${pid}/canvas`),
  putCanvasNode: (pid: string, key: string, body: { x: number; y: number; data?: Record<string, unknown> }) =>
    call<CanvasNodeRecord>('PUT', `/api/projects/${pid}/canvas/nodes/${encodeURIComponent(key)}`, body),
  putCanvasNodes: (pid: string, nodes: { node_key: string; x: number; y: number; w?: number; h?: number; data?: Record<string, unknown> }[]) =>
    call<{ nodes: CanvasNodeRecord[] }>('PUT', `/api/projects/${pid}/canvas/nodes`, { nodes }),
  deleteCanvasNode: (pid: string, key: string) =>
    call<{ ok: boolean }>('DELETE', `/api/projects/${pid}/canvas/nodes/${encodeURIComponent(key)}`),
  exportProject: (pid: string) => call<ExportResult>('POST', `/api/projects/${pid}/export`),
}

export function mediaUrl(url: string | null | undefined): string | null {
  if (!url) return null
  return url.startsWith('file://') ? `${API_BASE}/api/files?path=${encodeURIComponent(url)}` : url
}

// Local media is served by FlowKit at another origin; its origin guard rejects no-cors loads, so request with CORS.
export const mediaCrossOrigin = (url: string | null | undefined): 'anonymous' | undefined =>
  url?.startsWith('file://') ? 'anonymous' : undefined
