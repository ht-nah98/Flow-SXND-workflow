import * as Dialog from '@radix-ui/react-dialog'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, mediaCrossOrigin, mediaUrl } from '../api/client'
import { useMaterials, useProjects } from '../api/queries'
import type { DirectorRun, Orientation, Project } from '../api/types'
import { STAGE_LABEL } from '../nodes/RunControls'
import { useToast } from '../components/Toast'
import { orientationOf, sceneMedia } from '../graph/mapping'
import { explainError } from '../lib/errors'
import { refreshProjectUrls } from '../lib/refreshUrls'
import { IdeaDialog } from './IdeaDialog'
import { FlowAccountsButton } from '../components/FlowAccounts'

/** Where a project stands, in one short label. */
export function runBadge(run: DirectorRun | undefined, hasFilm: boolean) {
  if (!run) return hasFilm ? '✅ Có phim' : '✋ Làm tay'
  if (run.status === 'DONE') return '✅ Có phim'
  if (run.status === 'FAILED') return '⚠️ Lỗi — mở để xử lý'
  if (run.status === 'PAUSED') return '⏸ Tạm dừng'
  if (run.status === 'CANCELLED') return '🛑 Đã huỷ'
  if (run.status === 'WAITING_GATE') {
    return ({ IDEA: '💡 Ý tưởng nháp', SCRIPT: '📜 Chờ duyệt kịch bản', ASSETS: '🖼 Chờ duyệt ảnh',
              SHOT_FAILED: '⚠️ Clip lỗi — chờ bạn', BUDGET_EXCEEDED: '💳 Hết lượt đã duyệt',
              ACCOUNT_EXHAUSTED: '⛔ Tài khoản hết credit' } as Record<string, string>)[run.gate ?? '']
      ?? `✋ Chờ duyệt ${run.gate}`
  }
  return `⏳ ${(STAGE_LABEL[run.stage] ?? run.stage).replace(/…$/, '')}`
}

export function ProjectCard({ project }: { project: Project }) {
  const qc = useQueryClient()
  const [coverFailed, setCoverFailed] = useState(0)
  const videos = useQuery({ queryKey: ['p', project.id, 'videos'], queryFn: () => api.listVideos(project.id) })
  const first = videos.data?.[0]
  const scenes = useQuery({
    queryKey: ['p', project.id, 'scenes', first?.id], queryFn: () => api.listScenes(first!.id), enabled: !!first })
  const list = scenes.data ?? []
  const o = first ? orientationOf(first) : 'HORIZONTAL'
  const film = first ? (o === 'VERTICAL' ? first.vertical_url : first.horizontal_url) : null
  const cover = list.map((s) => sceneMedia(s, o).imageUrl).find(Boolean)
  const clip = list.map((s) => sceneMedia(s, o).videoUrl).find(Boolean)
  const withVideo = list.filter((s) => sceneMedia(s, o).videoStatus === 'COMPLETED').length
  const runs = useQuery({ queryKey: ['p', project.id, 'runs'], queryFn: () => api.listRuns(project.id) })
  const run = [...(runs.data ?? [])].sort((a, b) => (a.created_at ?? '').localeCompare(b.created_at ?? '')).at(-1)
  const spent = useQuery({ queryKey: ['credits', project.id], queryFn: () => api.credits(project.id) }).data?.project
  const still = film ?? clip   // a frame of the film (or of a clip) beats an empty box
  // A cover that fails is usually an expired Flow link: re-sign once, then
  // fall back to the empty placeholder instead of a broken-image icon.
  const onCoverError = () => {
    if (coverFailed > 0) { setCoverFailed(2); return }
    refreshProjectUrls(project.id)
      .then(() => qc.invalidateQueries({ queryKey: ['p', project.id] }))
      .catch(() => {})
      .finally(() => setCoverFailed(1))
  }
  return (
    <Link to={`/p/${project.id}`} data-testid={`project-${project.id}`}
          className="block overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 hover:border-sky-500">
      <div className="relative">
        {still && coverFailed < 2
          ? <video key={`${still}-${coverFailed}`} src={`${mediaUrl(still)!}#t=1`} crossOrigin={mediaCrossOrigin(still)}
                   muted preload="metadata" className="aspect-video w-full bg-black object-contain" onError={onCoverError} />
          : cover && coverFailed < 2
            ? <img key={coverFailed} src={mediaUrl(cover)!} crossOrigin={mediaCrossOrigin(cover)} alt=""
                   className="aspect-video w-full object-cover" onError={onCoverError} />
            : <div className="aspect-video w-full bg-zinc-800" />}
        <span className="absolute left-2 top-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px]">{runBadge(run, !!film)}</span>
        {film && first?.duration && (
          <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 text-[11px]">🎞 {first.duration.toFixed(0)}s</span>
        )}
      </div>
      <div className="p-3">
        <div className="line-clamp-2 font-medium">{project.name}</div>
        <div className="text-xs text-zinc-400">
          {list.length} cảnh · {withVideo} có video{o === 'VERTICAL' ? ' · 9:16' : ' · 16:9'}{spent ? ` · ~${spent} credit` : ''}
          {project.flow_account && <span className="block truncate" title={project.flow_account}>👤 {project.flow_account}</span>}
        </div>
      </div>
    </Link>
  )
}

function NewProjectDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const materials = useMaterials()
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [story, setStory] = useState('')
  const [material, setMaterial] = useState('realistic')
  const [orientation, setOrientation] = useState<Orientation>('HORIZONTAL')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    try {
      // Each project gets its own Flow project (reusing one id collides with the project that already has it).
      const p = await api.createProject({ name: name.trim(), story, material })
      await api.createVideo({ project_id: p.id, title: name.trim(), orientation, display_order: 0 })
      await qc.invalidateQueries({ queryKey: ['projects'] })
      onOpenChange(false)
      navigate(`/p/${p.id}`)
    } catch (err) {
      toast(explainError(err instanceof Error ? err.message : String(err)).message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(480px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-zinc-900 p-5 text-sm">
          <Dialog.Title className="mb-3 text-base font-semibold">Project mới</Dialog.Title>
          <Dialog.Description className="sr-only">Tạo project và video đầu tiên</Dialog.Description>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1">Tên
              <input required value={name} onChange={(e) => setName(e.target.value)} className="rounded bg-zinc-800 px-2 py-1" />
            </label>
            <label className="flex flex-col gap-1">Cốt truyện ngắn
              <textarea rows={3} value={story} onChange={(e) => setStory(e.target.value)} className="rounded bg-zinc-800 px-2 py-1" />
            </label>
            <label className="flex flex-col gap-1">Chất liệu hình ảnh (ảnh thật / 3D / hoạt hình…)
              <select value={material} onChange={(e) => setMaterial(e.target.value)} className="rounded bg-zinc-800 px-2 py-1">
                {(materials.data ?? [{ id: 'realistic', name: 'Photorealistic' }]).map((m) =>
                  <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
            <fieldset className="flex gap-4">
              <legend className="mb-1">Khung hình</legend>
              {(['HORIZONTAL', 'VERTICAL'] as const).map((o) => (
                <label key={o} className="flex items-center gap-1">
                  <input type="radio" checked={orientation === o} onChange={() => setOrientation(o)} />
                  {o === 'HORIZONTAL' ? 'Ngang 16:9' : 'Dọc 9:16'}
                </label>
              ))}
            </fieldset>
            <button disabled={busy} className="mt-2 rounded-lg bg-sky-600 px-3 py-1.5 text-white disabled:opacity-50">
              {busy ? 'Đang tạo…' : 'Tạo project'}
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function ProjectList() {
  const projects = useProjects()
  const [open, setOpen] = useState(false)
  const [idea, setIdea] = useState(false)
  return (
    <main className="mx-auto max-w-5xl p-4 sm:p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Flow Canvas</h1>
        <div className="flex gap-2">
          <FlowAccountsButton />
          <Link to="/hoc" className="rounded-lg bg-zinc-800 px-3 py-1.5 text-sm">📚 Học từ video mẫu</Link>
          <button onClick={() => setIdea(true)} className="rounded-lg bg-yellow-600 px-3 py-1.5 text-sm font-medium text-black">💡 Ý tưởng mới</button>
          <button onClick={() => setOpen(true)} className="rounded-lg bg-zinc-700 px-3 py-1.5 text-sm text-white">+ Project trống</button>
        </div>
      </header>
      {projects.isLoading && <p className="text-zinc-400">Đang tải…</p>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(projects.data ?? []).filter((p) => p.status !== 'DELETED').map((p) => <ProjectCard key={p.id} project={p} />)}
      </div>
      <NewProjectDialog open={open} onOpenChange={setOpen} />
      <IdeaDialog open={idea} onOpenChange={setIdea} />
    </main>
  )
}
