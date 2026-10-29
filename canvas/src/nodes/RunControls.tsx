import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { projectKey } from '../api/queries'
import type { DirectorRun } from '../api/types'
import { useChoice } from '../components/ChoiceDialog'
import { useToast } from '../components/Toast'
import type { IdeaProgress } from '../graph/mapping'
import { explainError } from '../lib/errors'
import { approxLength, estimatedFilmS } from '../lib/duration'

export const STAGE_LABEL: Record<string, string> = {
  BRIEF: 'Claude đang đọc ý tưởng…',
  STORY: 'Biên kịch đang viết câu chuyện…',
  SHOTLIST: 'Đạo diễn đang chia cảnh quay…',
  PROMPTS: 'Đang viết prompt từng clip…',
  EDIT_REVIEW: 'Biên tập đang duyệt kịch bản…',
  INGEST: 'Đang đưa kịch bản lên canvas…',
  REFS: 'Đang tạo ảnh nhân vật, bối cảnh… (lần lượt từng ảnh)',
  KEYFRAMES: 'Đang tạo ảnh keyframe từng shot… (lần lượt từng ảnh)',
  VIDEOS: 'Đang tạo video… (gửi lần lượt, Flow render song song)',
  QC: 'Claude đang xem lại từng clip…',
  CUT: 'Đang dựng phim…',
  PUBLISH: 'Đang xuất phim…',
  RETRO: 'Đang rút kinh nghiệm…',
  DONE: '✅ Xong — phim ở node 🎞 Phim hoàn chỉnh',
}
/** Stages that write the script; their progress and failures belong to the idea node. */
export const WRITING_STAGES = ['BRIEF', 'STORY', 'SHOTLIST', 'PROMPTS', 'EDIT_REVIEW', 'INGEST']
const num = (v: unknown) => (typeof v === 'number' ? v : 0)
const btn = 'rounded px-2 py-1 disabled:opacity-40'

export function useRunAction(run: DirectorRun) {
  const qc = useQueryClient()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      await qc.invalidateQueries({ queryKey: projectKey(run.project_id ?? '') })
    } catch (e) {
      toast(explainError(e instanceof Error ? e.message : String(e)).message, 'error')
      // a refused action usually means this view is stale (22/10: "no failed shots to resolve" on a cut film)
      void qc.invalidateQueries({ queryKey: projectKey(run.project_id ?? '') })
    } finally { setBusy(false) }
  }
  return { busy, act }
}

const VOICE: Record<string, string> = { voiceover: 'Lồng tiếng', dialogue: 'Nhân vật nói' }
const voiceLabel = (run: DirectorRun) => {
  const v = run.plan.brief?.voice
  return v && VOICE[v] ? `${VOICE[v]}${run.plan.brief?.voice_style ? ` — ${run.plan.brief.voice_style}` : ''}` : 'Không (phim không lời)'
}

/** One-glance summary of the script: what the user approves before any credit is spent. */
export function ScriptSummary({ run }: { run: DirectorRun }) {
  const cast = run.plan.story?.cast ?? []
  const names = (k: string) => cast.filter((c) => c.entity_type === k).map((c) => c.name).join(', ')
  const shots = run.plan.shotlist?.shots.length ?? 0
  const p = run.plan.gate_payload ?? {}
  const rows: [string, string][] = [
    ['Thời lượng', `${approxLength(run.brief.target_s ?? 60)} chọn → phim ước ~${estimatedFilmS(shots)}s (${shots} clip × 10s, dựng theo nhịp truyện) · ${run.brief.orientation === 'VERTICAL' ? '9:16' : '16:9'}`],
    ['Nhân vật', names('character') || '—'],
    ['Bối cảnh', names('location') || '—'],
    ['Đạo cụ', names('visual_asset') || '—'],
    ['Giọng nói', voiceLabel(run)],
    ['Ngôn ngữ', (run.plan.brief?.language ?? run.brief.language) === 'vi' ? 'Tiếng Việt' : 'Tiếng Anh'],
  ]
  const spent = useQuery({ queryKey: ['credits', run.project_id], enabled: !!run.project_id, refetchInterval: 15_000,
                          queryFn: () => api.credits(run.project_id ?? undefined) }).data?.project
  if (spent) rows.push(['Đã tiêu', `~${spent} credit (ước tính theo số lệnh Flow đã chạy)`])
  if (run.gate === 'SCRIPT') {
    const keyframes = num(p.keyframes) > 0 ? ` · ${num(p.keyframes)} keyframe ≈${num(p.keyframe_credits_est)}` : ''
    rows.push(['Credit ước tính', `ảnh ≈${num(p.credits_est)}${keyframes} · video ≈${num(p.video_credits_est)} · tổng ≈${num(p.total_credits_est)}`])
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 rounded bg-zinc-800/60 px-2 py-1 text-[11px]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents"><dt className="text-zinc-400">{k}</dt><dd className="text-zinc-200">{v}</dd></div>
      ))}
    </dl>
  )
}

/** 🛑 Ends the whole run after a confirmation: nothing more is written or sent to Flow, and it cannot restart. */
export function CancelRunButton({ run }: { run: DirectorRun }) {
  const { busy, act } = useRunAction(run)
  const choose = useChoice()
  if (run.status === 'DONE' || run.status === 'CANCELLED') return null
  const cancel = async () => {
    const ok = await choose({
      title: 'Huỷ toàn bộ run?',
      body: 'Dừng ngay việc đang chạy, bỏ mọi lệnh chưa gửi Flow. Clip Flow đang tạo dở vẫn hoàn tất và giữ trên canvas.\n'
        + 'Run đã huỷ không chạy tiếp được — muốn làm lại thì tạo ý tưởng mới.',
      options: [{ value: 'yes', label: '🛑 Huỷ toàn bộ' }],
    })
    if (ok === 'yes') await act(() => api.cancelRun(run.id))
  }
  return (
    <button disabled={busy} className={`${btn} border border-red-800 bg-transparent text-red-300 hover:bg-red-950`}
            onClick={() => void cancel()}>🛑 Huỷ toàn bộ run</button>
  )
}

/** Progress, approvals and recovery for everything after the script is written, plus the cancel button. */
export function RunControls(props: { run: DirectorRun; progress: IdeaProgress | null; missingRefs?: string[]; doneScenes?: number[] }) {
  if (props.run.status === 'CANCELLED') {
    return <div className="nodrag rounded bg-zinc-800 px-2 py-1 text-[11px] text-zinc-400">🛑 Run đã huỷ — không gửi thêm gì sang Flow.</div>
  }
  return (
    <div className="flex flex-col gap-1">
      <RunState {...props} />
      <CancelRunButton run={props.run} />
    </div>
  )
}

function RunState({ run, progress, missingRefs = [], doneScenes }: { run: DirectorRun; progress: IdeaProgress | null; missingRefs?: string[]; doneScenes?: number[] }) {
  const { busy, act } = useRunAction(run)
  const [revising, setRevising] = useState(false)
  const [feedback, setFeedback] = useState('')
  const p = run.plan.gate_payload ?? {}

  if (run.status === 'FAILED') {
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px]">
        <div className="rounded bg-red-950 px-2 py-1 text-red-200">⚠️ Lỗi ở bước {run.stage}: {run.error}</div>
        <button disabled={busy} className={`${btn} bg-amber-700`} onClick={() => void act(() => api.retryRun(run.id))}>Chạy lại bước</button>
      </div>
    )
  }
  if (run.status === 'PAUSED') {
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px]">
        <span className="text-zinc-300">⏸ Đang tạm dừng ở bước {STAGE_LABEL[run.stage] ?? run.stage}</span>
        <button disabled={busy} className={`${btn} bg-zinc-700`} onClick={() => void act(() => api.resumeRun(run.id))}>Chạy tiếp</button>
      </div>
    )
  }
  if (run.status === 'RUNNING' || run.status === 'DONE') {
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px] text-zinc-300">
        <span>
          {run.status === 'RUNNING' && '⏳ '}{STAGE_LABEL[run.stage] ?? run.stage}
          {run.status === 'RUNNING' && run.plan.mode === 'auto' && ' · chạy toàn bộ'}
        </span>
        {progress && progress.total > 0 && (
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded bg-zinc-800">
              <div className="h-full bg-sky-400" style={{ width: `${(100 * progress.done) / progress.total}%` }} />
            </div>
            <span>{progress.label} {progress.done}/{progress.total}</span>
          </div>
        )}
        {run.status === 'RUNNING' && (
          <button disabled={busy} className={`${btn} bg-zinc-700`} onClick={() => void act(() => api.pauseRun(run.id))}>
            ⏸ Tạm dừng (xong việc đang chạy thì dừng)
          </button>
        )}
      </div>
    )
  }
  // WAITING_GATE
  if (run.gate === 'SCRIPT') {
    const refs = num(p.refs)
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px]">
        <div className="text-zinc-300">
          ✋ Đọc kịch bản rồi chọn cách tạo.{num(p.provided) > 0 && ` ${num(p.provided)} asset dùng ảnh của bạn.`}
        </div>
        <button disabled={busy} className={`${btn} bg-emerald-700 text-left`}
                onClick={() => void act(() => api.approveRun(run.id, 'SCRIPT', { mode: 'step' }))}>
          ▶ Tạo từng bước — {refs > 0 ? `tạo ${refs} ảnh asset trước (≈${num(p.credits_est)} credit)` : 'sang bước duyệt ảnh'}, xem xong mới tạo video
        </button>
        <button disabled={busy} className={`${btn} bg-sky-700 text-left`}
                onClick={() => void act(() => api.approveRun(run.id, 'SCRIPT', { mode: 'auto' }))}>
          {run.plan.brief?.film_mode === 'keyframe'
            ? <>⏩ Chạy toàn bộ — ảnh → keyframe (dừng cho bạn duyệt) → {num(p.videos)} video → dựng phim (≈{num(p.total_credits_est)} credit)</>
            : <>⏩ Chạy toàn bộ — ảnh → {num(p.videos)} video → dựng phim (≈{num(p.total_credits_est)} credit, tự xếp hàng)</>}
        </button>
        {!revising && <button disabled={busy} className={`${btn} bg-zinc-700`} onClick={() => setRevising(true)}>Yêu cầu sửa kịch bản</button>}
        {revising && (
          <>
            <textarea aria-label="Góp ý cho kịch bản" rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)}
                      placeholder="Ví dụ: thêm cảnh ở biển, kết thúc vui hơn…" className="nowheel rounded bg-zinc-800 px-2 py-1" />
            <div className="flex gap-1">
              <button disabled={busy || feedback.trim().length < 2} className={`${btn} flex-1 bg-sky-700`}
                      onClick={() => void act(async () => { await api.reviseRun(run.id, feedback.trim()); setRevising(false); setFeedback('') })}>
                Gửi góp ý — viết lại
              </button>
              <button className={`${btn} bg-zinc-700`} onClick={() => setRevising(false)}>Huỷ</button>
            </div>
          </>
        )}
      </div>
    )
  }
  if (run.gate === 'ASSETS') {
    const prepaid = run.plan.mode === 'auto'
    const keyframe = run.plan.brief?.film_mode === 'keyframe'
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px]">
        <div className="text-zinc-300">
          ✋ Xem ảnh nhân vật, bối cảnh, đạo cụ. Ảnh nào chưa ưng: bấm "Gen lại ảnh" trên node đó (từng ảnh một).
        </div>
        {missingRefs.length > 0 && (
          <>
            <div className="rounded bg-amber-950 px-2 py-1 text-amber-200">
              Còn thiếu ảnh: {missingRefs.join(', ')} — tạo xong mới tạo video được.
            </div>
            <button disabled={busy} className={`${btn} bg-violet-700`} onClick={() => void act(() => api.makeMissingRefs(run.id))}>
              🖼 Tạo {missingRefs.length} ảnh còn thiếu (≈{missingRefs.length} credit, lần lượt từng ảnh)
            </button>
          </>
        )}
        <button disabled={busy || missingRefs.length > 0} className={`${btn} bg-emerald-700`}
                onClick={() => void act(() => api.approveRun(run.id, 'ASSETS'))}>
          {keyframe
            ? (prepaid ? `Ảnh ổn — tạo ${num(p.images)} ảnh keyframe (credit đã duyệt), xem rồi mới tạo video`
                       : `Ảnh ổn — tạo ${num(p.images)} ảnh keyframe + ${num(p.videos)} video (≈${num(p.credits_est)} credit); dừng cho anh xem keyframe trước khi tạo video`)
            : prepaid ? `Ảnh ổn — tiếp tục tạo ${num(p.videos)} video (credit đã duyệt)`
                      : `Ảnh ổn — tạo ${num(p.videos)} video (≈${num(p.credits_est)} credit)`}
        </button>
      </div>
    )
  }
  if (run.gate === 'KEYFRAMES') {
    const failedScenes = Array.isArray(p.failed_scenes) ? (p.failed_scenes as number[]) : []
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px]">
        <div className="text-zinc-300">
          ✋ Xem ảnh keyframe trên từng node cảnh — đó là khung mở của shot, và khung cuối của shot trước khi hai shot
          nối nhau. Ảnh nào chưa ưng: bấm "Gen lại ảnh" trên cảnh đó (~1 credit).
        </div>
        {failedScenes.length > 0 && (
          <div className="rounded bg-amber-950 px-2 py-1 text-amber-200">
            Cảnh {failedScenes.join(', ')} chưa có ảnh keyframe — bấm "Gen ảnh" trên cảnh đó rồi duyệt.
          </div>
        )}
        <button disabled={busy} className={`${btn} bg-emerald-700`} onClick={() => void act(() => api.approveRun(run.id, 'KEYFRAMES'))}>
          Keyframe ổn — tạo {num(p.keyframes)} video (credit đã duyệt)
        </button>
      </div>
    )
  }
  if (run.gate === 'SHOT_FAILED') return <ShotFailed run={run} done={doneScenes} />
  if (run.gate === 'BUDGET_EXCEEDED') {
    const kind = String(p.kind ?? 'videos')
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px]">
        <div className="text-amber-300">Hết ngân sách đã duyệt ({kind}).</div>
        <button disabled={busy} className={`${btn} bg-amber-700`}
                onClick={() => void act(() => api.approveRun(run.id, 'BUDGET_EXCEEDED', { budget: { [kind]: 2 } }))}>
          Cấp thêm 2 lượt và chạy tiếp
        </button>
      </div>
    )
  }
  if (run.gate === 'ACCOUNT_EXHAUSTED') return <AccountExhausted run={run} />
  return <div className="text-[11px] text-zinc-300">Đang chờ: {run.gate}</div>
}

/** Some clips have no video. Shown on the 📜 script node and on the 🎞 film node (20/10: the user looked for a merge
 *  button on the film node and found only "the film will appear here"). Both buttons are ffmpeg only, no credit. */
export function ShotFailed({ run, done }: { run: DirectorRun; done?: number[] }) {
  const { busy, act } = useRunAction(run)
  const p = run.plan.gate_payload ?? {}
  const scenes = Array.isArray(p.scenes) ? (p.scenes as number[]) : []
  const n = scenes.length || (Array.isArray(p.shots) ? p.shots.length : 0)
  const which = scenes.length ? `Cảnh ${scenes.join(', ')}` : `${n} clip`
  // 21/10: the clip was re-made but the note still said "no video" — the gate only knows what failed at the time.
  const ready = scenes.length > 0 && done != null && scenes.every((s) => done.includes(s))
  const merge = (
    <button disabled={busy} className={`${btn} bg-emerald-700`} onClick={() => void act(() => api.resolveShotFailure(run.id, 'retry'))}>
      {ready ? '🎬 Ghép phim (miễn phí)' : `🎬 Ghép phim — đã tạo lại ${which.toLowerCase()} (miễn phí)`}
    </button>
  )
  if (ready) {
    return (
      <div className="nodrag flex flex-col gap-1 text-[11px]" data-testid="shot-failed">
        <div className="rounded bg-emerald-950 px-2 py-1 text-emerald-200">✅ {which} đã có video — đủ clip, bấm ghép phim.</div>
        {merge}
      </div>
    )
  }
  return (
    <div className="nodrag flex flex-col gap-1 text-[11px]" data-testid="shot-failed">
      <div className="rounded bg-amber-950 px-2 py-1 text-amber-200">
        ⚠️ {which} chưa có video. Bấm "Gen lại video" ở cảnh đó, xong rồi ghép; hoặc ghép luôn không có cảnh đó.
      </div>
      {merge}
      <button disabled={busy} className={`${btn} bg-zinc-700`} onClick={() => void act(() => api.resolveShotFailure(run.id, 'drop'))}>
        🎬 Ghép phim, bỏ {which.toLowerCase()} (miễn phí)
      </button>
    </div>
  )
}

/** Account rotation, step 3: Flow said the film's Google account is out of credit; its queue is held. */
function AccountExhausted({ run }: { run: DirectorRun }) {
  const { busy, act } = useRunAction(run)
  const p = run.plan.gate_payload ?? {}
  const accounts = useQuery({ queryKey: ['flow-accounts'], queryFn: api.flowAccounts })
  const others = (accounts.data?.accounts ?? []).filter((a) => a.email !== p.account && a.status === 'ACTIVE' && a.connected > 0)
  return (
    <div className="nodrag flex flex-col gap-1 text-[11px]">
      <div className="rounded bg-red-950 px-2 py-1 text-red-200">
        ⛔ Tài khoản {String(p.account ?? '')} hết credit. {num(p.waiting)} việc đang giữ lại, chưa gửi đi (không mất gì).
      </div>
      <div className="text-zinc-400">
        {others.length ? `Tài khoản còn credit đang kết nối: ${others.map((a) => a.label || a.email).join(', ')}.`
                       : 'Chưa có tài khoản nào khác còn credit đang kết nối.'}
      </div>
      <button disabled={busy} className={`${btn} bg-emerald-700`}
              onClick={() => void act(() => api.approveRun(run.id, 'ACCOUNT_EXHAUSTED'))}>
        Tài khoản này đã có credit lại — chạy tiếp
      </button>
    </div>
  )
}
