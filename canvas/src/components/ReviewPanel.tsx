import { useState } from 'react'
import type { ReviewError, Scene, SceneReview } from '../api/types'
import { useCanvasActions } from '../canvas/actions-context'
import { explainError } from '../lib/errors'

const SEVERITY: Record<string, [string, string]> = {
  CRITICAL: ['Nặng', 'border-red-500 text-red-200'], HIGH: ['Rõ', 'border-orange-400 text-orange-200'],
  MINOR: ['Nhẹ', 'border-zinc-500 text-zinc-300'],
}
const RANK: Record<string, number> = { CRITICAL: 0, HIGH: 1, MINOR: 2 }
const startOf = (e: ReviewError) => parseFloat(e.time_range ?? '') || 0
/** Worst first, then in time order. */
export const sortErrors = (errors: ReviewError[]) => errors.slice().sort((a, b) =>
  (RANK[a.severity ?? ''] ?? 3) - (RANK[b.severity ?? ''] ?? 3) || startOf(a) - startOf(b))

/** "Claude đánh giá" on a scene. 22/10: the panel said "5 lỗi" without listing them, and its only fix was pasting the
 *  generic advice into the prompt. Now: every error with its time; a director's scene gets Claude to rewrite the
 *  prompt from those errors (`onRewrite`, free, shown as a diff before anything changes). */
export function ReviewPanel({ scene, hasVideo, onRewrite }: {
  scene: Scene; hasVideo: boolean; onRewrite?: (review: SceneReview) => void
}) {
  const a = useCanvasActions()
  const [state, setState] = useState<{ loading: boolean; result: SceneReview | null; error: string | null }>(
    { loading: false, result: null, error: null })
  const run = async () => {
    setState({ loading: true, result: null, error: null })
    try { setState({ loading: false, result: await a.review(scene), error: null }) }
    catch (e) { setState({ loading: false, result: null, error: explainError(e instanceof Error ? e.message : String(e)).message }) }
  }
  const r = state.result
  const errors = r ? sortErrors(r.errors ?? []) : []
  return (
    <div className="nodrag flex flex-col gap-1 text-[11px]">
      <button disabled={!hasVideo || state.loading} onClick={() => void run()}
              className="rounded bg-zinc-700 px-2 py-1 disabled:opacity-40">
        {state.loading ? 'Claude đang xem video…' : 'Claude đánh giá'}
      </button>
      {state.error && <div className="text-red-300">{state.error}</div>}
      {r && (
        <div className="flex flex-col gap-1 rounded bg-zinc-800 p-2">
          <div><b>Điểm {r.overall_score.toFixed(1)}/10</b> · {r.verdict} · {errors.length} lỗi</div>
          {errors.length > 0 && (
            <ol className="nowheel flex max-h-40 flex-col gap-1 overflow-y-auto" aria-label="Lỗi trong video">
              {errors.map((e, i) => {
                const [word, tone] = SEVERITY[e.severity ?? ''] ?? [e.severity ?? '?', 'border-zinc-600 text-zinc-300']
                return (
                  <li key={i} className={`border-l-2 pl-1.5 ${tone}`}>
                    <span className="font-semibold">{e.time_range ? `${e.time_range} · ` : ''}{word}</span>
                    <span className="text-zinc-300"> — {e.description ?? e.type ?? ''}</span>
                  </li>
                )
              })}
            </ol>
          )}
          {r.fix_guide && <div className="whitespace-pre-line text-zinc-400">{r.fix_guide}</div>}
          {onRewrite && errors.length > 0 && (
            <button className="rounded bg-sky-700 px-2 py-1" onClick={() => onRewrite(r)}>
              ✏️ Claude viết lại prompt theo đánh giá (miễn phí)
            </button>
          )}
          {!onRewrite && r.fix_guide && (
            <button className="rounded bg-sky-700 px-2 py-0.5"
                    onClick={() => void a.patchScene(scene.id, {
                      video_prompt: `${scene.video_prompt ?? ''}\n\nFix: ${r.fix_guide}`.trim() })}>
              Chèn gợi ý vào prompt video
            </button>
          )}
        </div>
      )}
    </div>
  )
}
