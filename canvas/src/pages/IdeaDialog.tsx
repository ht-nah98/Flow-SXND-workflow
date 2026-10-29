import * as Dialog from '@radix-ui/react-dialog'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useMaterials } from '../api/queries'
import type { AmbientChoice, Creativity, FilmLanguage, Orientation, VoiceChoice, FilmMode } from '../api/types'
import { CreativitySelect } from '../components/CreativitySelect'
import { AmbientOptions, DEFAULT_FILM_MODE, FilmModeSelect } from '../components/FilmModeSelect'
import { AgentToggles, DEFAULT_AGENTS } from '../components/AgentToggles'
import { StyleSelect } from '../components/StyleSelect'
import { LanguageSelect } from '../components/LanguageSelect'
import { useToast } from '../components/Toast'
import { explainError } from '../lib/errors'
import { IDEA_TEMPLATES } from '../lib/templates'
import { approxLength, FILM_PER_CLIP_S } from '../lib/duration'

export const MAX_IMAGES = 6
export const IDEA_MAX_CHARS = 20000   // same as the backend's RunCreate.text
const MAX_BYTES = 10 * 1024 * 1024
const TYPES = ['image/jpeg', 'image/png', 'image/webp']

interface Picked { file: File; preview: string; note: string }

const toBase64 = (f: File) => new Promise<string>((resolve, reject) => {
  const r = new FileReader()
  r.onload = () => resolve(String(r.result).split(',', 2)[1] ?? '')
  r.onerror = () => reject(r.error)
  r.readAsDataURL(f)
})

/** "Bạn chỉ là người lên ý tưởng": text (+ pictures) in, Claude writes, directs and films the rest. */
export function IdeaDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const materials = useMaterials()
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [images, setImages] = useState<Picked[]>([])
  const [orientation, setOrientation] = useState<Orientation>('HORIZONTAL')
  const [targetS, setTargetS] = useState(60)
  const [style, setStyle] = useState('realistic')
  const [voice, setVoice] = useState<VoiceChoice>('auto')
  const [language, setLanguage] = useState<FilmLanguage>('en')
  const [creativity, setCreativity] = useState<Creativity>('balanced')
  const [filmMode, setFilmMode] = useState<FilmMode>(DEFAULT_FILM_MODE)
  const [ambient, setAmbient] = useState<AmbientChoice>({})
  const isAmbient = filmMode === 'ambient'
  const [agents, setAgents] = useState(DEFAULT_AGENTS)
  const [stylePack, setStylePack] = useState('')
  const [templateId, setTemplateId] = useState<string | null>(null)
  const applyTemplate = (id: string) => {
    const t = IDEA_TEMPLATES.find((x) => x.id === id)!
    setTemplateId(id); setTargetS(t.target_s); setOrientation(t.orientation); setVoice(t.voice)
    if (!text.trim() || IDEA_TEMPLATES.some((x) => x.text === text)) setText(t.text)
  }
  const [busy, setBusy] = useState(false)

  useEffect(() => () => images.forEach((i) => URL.revokeObjectURL(i.preview)), [images])

  const add = (files: FileList | File[]) => {
    const next = [...images]
    for (const f of Array.from(files)) {
      if (!TYPES.includes(f.type)) { toast(`${f.name}: chỉ nhận ảnh jpg, png, webp`, 'error'); continue }
      if (f.size > MAX_BYTES) { toast(`${f.name}: ảnh quá lớn (tối đa 10 MB)`, 'error'); continue }
      if (next.length >= MAX_IMAGES) { toast(`Tối đa ${MAX_IMAGES} ảnh`, 'error'); break }
      next.push({ file: f, preview: URL.createObjectURL(f), note: '' })
    }
    setImages(next)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (text.trim().length < 3) return
    setBusy(true)
    try {
      const run = await api.createRun({
        text: text.trim(), target_s: targetS, orientation, style, voice, language, creativity, agents, style_pack: stylePack || null, film_mode: filmMode,
        ...(isAmbient ? ambient : {}),
        images: await Promise.all(images.map(async (i) => ({
          base64: await toBase64(i.file), filename: i.file.name, note: i.note.trim() || null }))),
      })
      await qc.invalidateQueries({ queryKey: ['projects'] })
      onOpenChange(false)
      navigate(`/p/${run.project_id}`)
    } catch (err) {
      toast(explainError(err instanceof Error ? err.message : String(err)).message, 'error')
    } finally { setBusy(false) }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-32px)] w-[min(560px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl bg-zinc-900 p-5 text-sm">
          <Dialog.Title className="mb-1 text-base font-semibold">💡 Ý tưởng mới</Dialog.Title>
          <Dialog.Description className="mb-3 text-xs text-zinc-400">
            Bạn đưa ý tưởng, Claude viết kịch bản, dựng nhân vật, bối cảnh và quay phim. Bạn chỉ duyệt kịch bản và credit.
          </Dialog.Description>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <span>Bắt đầu từ mẫu (tuỳ chọn)</span>
              <div className="flex flex-wrap gap-1.5">
                {IDEA_TEMPLATES.map((t) => (
                  <button key={t.id} type="button" title={t.hint} aria-pressed={templateId === t.id} onClick={() => applyTemplate(t.id)}
                          className={`rounded-full px-2.5 py-1 text-xs ${templateId === t.id ? 'bg-yellow-600 text-black' : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700'}`}>
                    {t.icon} {t.name}
                  </button>
                ))}
              </div>
              {templateId && <span className="text-[11px] text-zinc-400">Thay các chỗ [trong ngoặc] bằng nội dung của bạn.</span>}
            </div>
            <label className="flex flex-col gap-1">Ý tưởng
              <textarea required minLength={3} maxLength={IDEA_MAX_CHARS} rows={4} value={text} onChange={(e) => setText(e.target.value)}
                        placeholder="Ví dụ: Hai bạn trẻ cùng làm bánh kem, rồi một người ra đi. Kết buồn, ấm áp."
                        className="rounded bg-zinc-800 px-2 py-1" />
              <span className="self-end text-[11px] text-zinc-500">{text.length.toLocaleString('vi')} / {IDEA_MAX_CHARS.toLocaleString('vi')} ký tự</span>
            </label>
            <div className="flex flex-col gap-1">
              <span>Ảnh kèm theo (tuỳ chọn, tối đa {MAX_IMAGES})</span>
              <label data-testid="idea-drop"
                     onDragOver={(e) => e.preventDefault()}
                     onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files) }}
                     className="cursor-pointer rounded border border-dashed border-zinc-600 px-2 py-3 text-center text-xs text-zinc-400 hover:border-sky-500">
                Kéo thả ảnh vào đây hoặc bấm để chọn — nhân vật, bối cảnh, đạo cụ thật, hoặc ảnh tham khảo tông màu
                <input type="file" accept={TYPES.join(',')} multiple className="sr-only" aria-label="Chọn ảnh"
                       onChange={(e) => { if (e.target.files) add(e.target.files); e.target.value = '' }} />
              </label>
              {images.length > 0 && (
                <ul className="flex flex-col gap-2">
                  {images.map((img, i) => (
                    <li key={img.preview} className="flex items-center gap-2">
                      <img src={img.preview} alt="" className="h-14 w-14 shrink-0 rounded object-cover" />
                      <input aria-label={`Ghi chú ảnh ${i + 1}`} value={img.note}
                             onChange={(e) => setImages(images.map((x, j) => (j === i ? { ...x, note: e.target.value } : x)))}
                             placeholder="Ghi chú (vd: đây là quán cà phê của tôi)"
                             className="min-w-0 flex-1 rounded bg-zinc-800 px-2 py-1 text-xs" />
                      <button type="button" aria-label={`Bỏ ảnh ${i + 1}`} className="px-1 text-zinc-400 hover:text-white"
                              onClick={() => { URL.revokeObjectURL(img.preview); setImages(images.filter((_, j) => j !== i)) }}>✕</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <fieldset className="flex flex-wrap gap-3">
                <legend className="mb-1">Khung hình</legend>
                {(['HORIZONTAL', 'VERTICAL'] as const).map((o) => (
                  <label key={o} className="flex items-center gap-1">
                    <input type="radio" checked={orientation === o} onChange={() => setOrientation(o)} />
                    {o === 'HORIZONTAL' ? 'Ngang 16:9' : 'Dọc 9:16'}
                  </label>
                ))}
              </fieldset>
              {!isAmbient && <label className="flex flex-col gap-1">Thời lượng phim: {approxLength(targetS)} (linh hoạt)
                <input type="range" min={15} max={300} step={5} value={targetS} onChange={(e) => setTargetS(Number(e.target.value))} />
                <span className="text-[11px] text-zinc-400">≈ {Math.round(targetS / FILM_PER_CLIP_S)} clip 10s · ≈ {Math.round(targetS / FILM_PER_CLIP_S) * 15} credit video · phim dài/ngắn hơn tuỳ câu chuyện và bản dựng</span>
              </label>}
            </div>
            {!isAmbient && <label className="flex flex-col gap-1">Giọng nói
              <select aria-label="Giọng nói" value={voice} onChange={(e) => setVoice(e.target.value as VoiceChoice)}
                      className="rounded bg-zinc-800 px-2 py-1">
                <option value="auto">🔊 Tự nhận diện theo ý tưởng</option>
                <option value="voiceover">🎙 Có lồng tiếng (giọng đọc ngoài hình)</option>
                <option value="dialogue">🗣 Nhân vật nói trước camera</option>
                <option value="none">🔇 Không lời</option>
              </select>
            </label>}
            <label className="flex flex-col gap-1">Ngôn ngữ phim
              <LanguageSelect value={language} onChange={setLanguage} />
            </label>
            <div className="flex flex-col gap-1">Chế độ phim
              <FilmModeSelect value={filmMode} onChange={setFilmMode} />
              {isAmbient && <AmbientOptions value={ambient} onChange={setAmbient} />}
            </div>
            {!isAmbient && <label className="flex flex-col gap-1">Mức sáng tạo của biên kịch
              <CreativitySelect value={creativity} onChange={setCreativity} />
            </label>}
            <label className="flex flex-col gap-1">Gói phong cách (một look cho cả phim)
              <StyleSelect value={stylePack} onChange={setStylePack} />
            </label>
            <AgentToggles value={agents} onChange={setAgents} targetS={targetS} />
            <label className="flex flex-col gap-1">Chất liệu hình ảnh (ảnh thật / 3D / hoạt hình…)
              <select value={style} onChange={(e) => setStyle(e.target.value)} className="rounded bg-zinc-800 px-2 py-1">
                {(materials.data ?? [{ id: 'realistic', name: 'Photorealistic' }]).map((m) =>
                  <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
            <button disabled={busy || text.trim().length < 3} className="mt-1 rounded-lg bg-yellow-600 px-3 py-1.5 font-medium text-black disabled:opacity-50">
              {busy ? 'Đang lưu…' : 'Lưu ý tưởng lên canvas'}
            </button>
            <p className="text-[11px] text-zinc-500">Chưa chạy gì: trên canvas bạn còn sửa được ý tưởng, rồi bấm “Viết kịch bản”. Duyệt kịch bản xong mới tạo ảnh và video.</p>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
