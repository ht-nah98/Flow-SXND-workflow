import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { NodeFrame } from '../components/NodeFrame'
import { useState } from 'react'
import { api, mediaCrossOrigin, mediaUrl } from '../api/client'
import type { AmbientChoice, Creativity, DirectorRun, FilmMode, FilmLanguage, ImageUse, Orientation, VoiceChoice } from '../api/types'
import { CREATIVITY_LABEL, CreativitySelect } from '../components/CreativitySelect'
import { AmbientOptions, FILM_MODE_LABEL, FilmModeSelect } from '../components/FilmModeSelect'
import { AgentToggles, DEFAULT_AGENTS } from '../components/AgentToggles'
import { StyleSelect } from '../components/StyleSelect'
import { LanguageSelect } from '../components/LanguageSelect'
import type { IdeaNodeData } from '../graph/mapping'
import { WritingTimeline } from '../components/WritingTimeline'
import { IDEA_MAX_CHARS } from '../pages/IdeaDialog'
import { CancelRunButton, STAGE_LABEL, WRITING_STAGES, useRunAction } from './RunControls'
import { approxLength } from '../lib/duration'

const USE_LABEL: Record<ImageUse, string> = {
  character: 'Nhân vật', location: 'Bối cảnh', visual_asset: 'Đạo cụ', mood: 'Tham khảo',
}
const btn = 'rounded px-2 py-1 disabled:opacity-40'

/** The user's idea. Nothing runs until "Viết kịch bản"; approvals after that live on the 📜 script node. */
export function IdeaNode({ id, data, selected }: NodeProps<Node<IdeaNodeData>>) {
  const { run } = data
  const draft = run.status === 'WAITING_GATE' && run.gate === 'IDEA'
  return (
    <div data-testid={`node-${id}`} className="flex h-full w-full flex-col overflow-y-auto gap-2 rounded-xl border-2 border-yellow-500 bg-zinc-900 p-2 shadow-lg">
      <NodeFrame selected={selected} minWidth={300} minHeight={200} />
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold text-yellow-300">💡 Ý tưởng</span>
        <span className="text-zinc-400">
          {approxLength(run.brief.target_s ?? 60)} · {run.brief.orientation === 'VERTICAL' ? '9:16' : '16:9'}
        </span>
      </div>
      {draft ? <IdeaEditor run={run} /> : <IdeaView run={run} />}
      <RunAgents run={run} />
      {draft && !!data.reuse?.length && (
        <p className="text-[11px] text-emerald-300" title="Kéo thêm asset từ Thư viện vào canvas để dùng lại">
          ♻ Dùng lại asset có sẵn (không tạo ảnh mới): {data.reuse.join(', ')}
        </p>
      )}
      <Handle type="source" position={Position.Bottom} id="idea" className="!h-3 !w-3 !bg-yellow-400" isConnectable={false} />
    </div>
  )
}

function IdeaView({ run }: { run: DirectorRun }) {
  const { busy, act } = useRunAction(run)
  const uses = new Map((run.plan.brief?.images ?? []).map((i) => [i.file, i]))
  const writing = WRITING_STAGES.includes(run.stage) && !(run.status === 'WAITING_GATE' && run.gate === 'SCRIPT')
  return (
    <>
      <p className="nodrag nowheel max-h-[140px] overflow-y-auto whitespace-pre-wrap text-[12px] text-zinc-200">{run.brief.text}</p>
      <p className="text-[10px] text-zinc-400">Chế độ: {FILM_MODE_LABEL[run.brief.film_mode ?? 'cut']}
        {run.brief.film_mode === 'ambient' && run.brief.reel_s && ` · vòng hình ${run.brief.reel_s / 60} phút`}</p>
      <p className="text-[10px] text-zinc-400">Sáng tạo: {CREATIVITY_LABEL[run.brief.creativity ?? 'balanced']}</p>
      {!!run.brief.images?.length && (
        <div className="grid grid-cols-3 gap-1">
          {run.brief.images.map((img) => {
            const u = uses.get(img.file)
            return (
              <figure key={img.file} className="flex flex-col gap-0.5" title={u?.description ?? img.note ?? ''}>
                <img src={mediaUrl(`file://${img.file}`)!} crossOrigin={mediaCrossOrigin(`file://${img.file}`)} alt=""
                     className="aspect-square w-full rounded object-cover" />
                <figcaption className="truncate text-[10px] text-zinc-400">
                  {u ? `${USE_LABEL[u.use]}${u.name ? `: ${u.name}` : ''}` : img.note || 'Chưa phân loại'}
                </figcaption>
              </figure>
            )
          })}
        </div>
      )}
      <div className="nodrag flex flex-col gap-1 text-[11px] text-zinc-300">
        {writing && run.status === 'FAILED' && (
          <>
            <div className="rounded bg-red-950 px-2 py-1 text-red-200">⚠️ Lỗi khi viết kịch bản ({run.stage}): {run.error}</div>
            <button disabled={busy} className={`${btn} bg-amber-700`} onClick={() => void act(() => api.retryRun(run.id))}>Viết lại từ bước này</button>
          </>
        )}
        {writing && run.status === 'RUNNING' && !['BRIEF', 'STORY', 'SHOTLIST', 'PROMPTS', 'EDIT_REVIEW'].includes(run.stage)
          && <span>⏳ {STAGE_LABEL[run.stage] ?? run.stage}</span>}
        {writing && <WritingTimeline runId={run.id} />}
        {writing && run.status === 'RUNNING' && !!run.plan.edit_loops && (
          <span className="text-amber-300" title={(run.plan.editor?.fixes ?? []).map((f) => `• ${f.issue}`).join('\n')}>
            ✏️ Biên tập chấm {run.plan.editor?.score ?? '?'}/100, yêu cầu sửa {run.plan.editor?.fixes?.length ?? 0} chỗ — đang viết lại (vòng {run.plan.edit_loops}/2, mỗi vòng vài phút)
          </span>
        )}
        {writing && run.status === 'PAUSED' && (
          <button disabled={busy} className={`${btn} bg-zinc-700`} onClick={() => void act(() => api.resumeRun(run.id))}>Chạy tiếp</button>
        )}
        {writing && <CancelRunButton run={run} />}
        {run.status === 'CANCELLED' ? <span className="text-zinc-400">🛑 Run đã huỷ.</span>
          : !writing && <span>✅ Kịch bản đã viết xong — duyệt và tạo ở node 📜 Kịch bản.</span>}
      </div>
    </>
  )
}

function IdeaEditor({ run }: { run: DirectorRun }) {
  const { busy, act } = useRunAction(run)
  const [text, setText] = useState(run.brief.text)
  const [target, setTarget] = useState(run.brief.target_s ?? 60)
  const [orientation, setOrientation] = useState<Orientation>(run.brief.orientation ?? 'HORIZONTAL')
  const [voice, setVoice] = useState<VoiceChoice>(run.brief.voice ?? 'auto')
  const [language, setLanguage] = useState<FilmLanguage>(run.brief.language ?? 'en')
  const [creativity, setCreativity] = useState<Creativity>(run.brief.creativity ?? 'balanced')
  const [stylePack, setStylePack] = useState(run.brief.style_pack ?? '')
  const [filmMode, setFilmMode] = useState<FilmMode>(run.brief.film_mode ?? 'cut')   // a run without it was made as cut
  const [ambient, setAmbient] = useState<AmbientChoice>({ venue: run.brief.venue, reel_s: run.brief.reel_s })
  const [notes, setNotes] = useState<Record<string, string>>(
    Object.fromEntries((run.brief.images ?? []).map((i) => [i.file, i.note ?? ''])))

  const write = () => act(async () => {
    const changed = text.trim() !== run.brief.text || target !== (run.brief.target_s ?? 60)
      || orientation !== (run.brief.orientation ?? 'HORIZONTAL') || voice !== (run.brief.voice ?? 'auto')
      || language !== (run.brief.language ?? 'en') || creativity !== (run.brief.creativity ?? 'balanced') || stylePack !== (run.brief.style_pack ?? '')
      || filmMode !== (run.brief.film_mode ?? 'cut')
      || (filmMode === 'ambient' && (ambient.venue !== run.brief.venue || ambient.reel_s !== run.brief.reel_s))
      || (run.brief.images ?? []).some((i) => (notes[i.file] ?? '') !== (i.note ?? ''))
    if (changed) await api.patchIdea(run.id, { text: text.trim(), target_s: target, orientation, voice, language, creativity, style_pack: stylePack, film_mode: filmMode, notes, ...(filmMode === 'ambient' ? ambient : {}) })
    await api.approveRun(run.id, 'IDEA')
  })

  return (
    <div className="nodrag flex flex-col gap-1.5 text-[11px]">
      <textarea aria-label="Ý tưởng" rows={4} maxLength={IDEA_MAX_CHARS} value={text} onChange={(e) => setText(e.target.value)}
                className="nowheel rounded bg-zinc-800 px-2 py-1 text-[12px] text-zinc-100" />
      {!!run.brief.images?.length && (
        <div className="grid grid-cols-3 gap-1">
          {run.brief.images.map((img) => (
            <figure key={img.file} className="flex flex-col gap-0.5">
              <img src={mediaUrl(`file://${img.file}`)!} crossOrigin={mediaCrossOrigin(`file://${img.file}`)} alt=""
                   className="aspect-square w-full rounded object-cover" />
              <input aria-label="Ghi chú ảnh" value={notes[img.file] ?? ''} placeholder="ảnh này là…"
                     onChange={(e) => setNotes({ ...notes, [img.file]: e.target.value })}
                     className="rounded bg-zinc-800 px-1 py-0.5 text-[10px]" />
            </figure>
          ))}
        </div>
      )}
      <div className="flex gap-1">
        <select aria-label="Thời lượng" value={target} onChange={(e) => setTarget(Number(e.target.value))}
                className="flex-1 rounded bg-zinc-800 px-1 py-1">
          {[...new Set([15, 30, 45, 60, 90, 120, 180, 240, 300, target])].sort((a, b) => a - b).map((s) => <option key={s} value={s}>{approxLength(s)} (linh hoạt)</option>)}
        </select>
        <select aria-label="Khổ video" value={orientation} onChange={(e) => setOrientation(e.target.value as Orientation)}
                className="flex-1 rounded bg-zinc-800 px-1 py-1">
          <option value="HORIZONTAL">16:9 ngang</option>
          <option value="VERTICAL">9:16 dọc</option>
        </select>
      </div>
      <select aria-label="Giọng nói" value={voice} onChange={(e) => setVoice(e.target.value as VoiceChoice)}
              className="rounded bg-zinc-800 px-1 py-1">
        <option value="auto">🔊 Giọng nói: tự nhận diện theo ý tưởng</option>
        <option value="voiceover">🎙 Có lồng tiếng (giọng đọc ngoài hình)</option>
        <option value="dialogue">🗣 Nhân vật nói trước camera</option>
        <option value="none">🔇 Không lời (chỉ âm thanh, nhạc)</option>
      </select>
      <LanguageSelect value={language} onChange={setLanguage} />
      <FilmModeSelect value={filmMode} onChange={setFilmMode} />
      {filmMode === 'ambient' && <AmbientOptions value={ambient} onChange={setAmbient} />}
      {filmMode !== 'ambient' && <CreativitySelect value={creativity} onChange={setCreativity} />}
      <StyleSelect value={stylePack} onChange={setStylePack} />
      <button disabled={busy || text.trim().length < 3} className={`${btn} bg-yellow-600 font-semibold text-zinc-950`}
              onClick={() => void write()}>
        ✍️ Viết kịch bản (không tốn credit)
      </button>
    </div>
  )
}

/** Directive A5: switch the optional roles on or off; free, and it applies to the stages still to come. */
function RunAgents({ run }: { run: DirectorRun }) {
  const { busy, act } = useRunAction(run)
  const done = run.status === 'DONE' || run.status === 'CANCELLED'
  return (
    <AgentToggles value={{ ...DEFAULT_AGENTS, ...run.brief.agents }} targetS={run.brief.target_s ?? 60}
                  disabled={busy || done} onChange={(a) => void act(() => api.setAgents(run.id, a))} />
  )
}
