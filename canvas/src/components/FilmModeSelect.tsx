import { useVenues } from '../api/queries'
import type { AmbientChoice, FilmMode } from '../api/types'

/** Directive B13 (22/10): the user picks how the film is made; every mode stays available. Continuous is the default
 *  (B12, repeated 24/10). Directive G2 (24/10): every choice is explained in Vietnamese so the user knows what to pick. */
export const DEFAULT_FILM_MODE: FilmMode = 'continuous'

export const FILM_MODE_LABEL: Record<FilmMode, string> = {
  continuous: '🎞 Liền mạch — clip nối khung cuối, chuyển cảnh bằng máy quay',
  keyframe: '🖼 Keyframe — ghim ảnh từng shot, shot ngắn nối bằng chuyển động',
  cut: '✂️ Cắt cảnh — clip riêng, dựng cắt ghép',
  ambient: '🎵 Không khí buổi diễn — không truyện, lặp theo nhạc',
}
export const FILM_MODE_HINT: Record<FilmMode, string> = {
  continuous: 'Như phim "SIU Giáng Sinh": mỗi clip 8–10s mở từ khung cuối clip trước.',
  keyframe: 'Như mẫu Kling/Artlist: ảnh keyframe mỗi shot (duyệt trước khi tạo video), shot 1–5s, nối bằng che ống kính, xuyên màn hình, cắt giữa hành động.',
  cut: 'Mỗi clip một ý, dựng cắt và hiệu ứng chuyển.',
  ambient: 'Như kênh nhạc worship: các cảnh quay của một buổi diễn đang diễn ra, người xem chỉ nghe nhạc. Không có truyện, không nhân vật, không lời.',
}
/** The longer "what does this mode do" text: what it suits, how the system makes it, what it costs. */
export const FILM_MODE_HELP: Record<FilmMode, { suits: string; how: string; cost: string }> = {
  continuous: {
    suits: 'Phim có câu chuyện, cần trôi như một cú máy dài: gia đình, tình cảm, ký ức, Giáng Sinh.',
    how: 'Biên kịch viết truyện; mỗi clip 8–10s mở đúng từ khung cuối của clip trước, chuyển cảnh nằm trong clip (che ống kính, loá sáng, đi theo giọng nói). Clip được tạo lần lượt trong mỗi đoạn và dùng gần trọn.',
    cost: '~15 credit mỗi clip; phim 1 phút ≈ 7–8 clip.',
  },
  keyframe: {
    suits: 'Quảng cáo, trailer nhịp nhanh, một nhân vật chạy qua nhiều nơi.',
    how: 'Mỗi shot có một ảnh keyframe (bạn duyệt ảnh trước khi tốn credit video); Flow chỉ lấp chuyển động giữa hai ảnh. Shot ngắn 1–5s, nối bằng chuyển động.',
    cost: '~1 credit mỗi ảnh keyframe + ~15 credit mỗi clip; phim 30s ≈ 8–12 shot.',
  },
  cut: {
    suits: 'Video kể chuyện kiểu MV / quảng cáo dựng cắt nhanh, nhiều góc máy.',
    how: 'Mỗi clip 10s một ý; khi dựng giữ 3–7s đẹp nhất của mỗi clip, ghép bằng cắt thẳng hoặc hiệu ứng chuyển.',
    cost: '~15 credit mỗi clip; phim 1 phút ≈ 11 clip.',
  },
  ambient: {
    suits: 'Video nghe nhạc dài (worship, jazz, giao hưởng, acoustic…): người xem để nghe, hình chỉ tạo không khí.',
    how: 'Không có biên kịch truyện: hệ thống viết một tờ bối cảnh, chia các shot 8s luân phiên toàn cảnh → khán giả → chi tiết → sân khấu, mỗi clip một chuyển động máy chậm, khán giả vô danh, không lộ mặt người biểu diễn. Ghép thành một vòng hình 1–2 phút rồi lặp cho đủ độ dài bản nhạc (nhạc bạn tự ghép hoặc đính kèm).',
    cost: '~15 credit mỗi clip; vòng 1 phút ≈ 8 clip (~120 credit), 2 phút ≈ 15 clip (~225 credit) — video dài bao nhiêu cũng chỉ tốn chừng đó.',
  },
}

export const REEL_CHOICES = [60, 90, 120]
export const DEFAULT_REEL_S = 120
/** The finished video = the reel repeated to this length (s); the music the user adds outside sets the mood (E6). */
export const LOOP_CHOICES = [600, 1800, 3600]
export const DEFAULT_LOOP_S = 1800

export function FilmModeSelect({ value, onChange }: { value: FilmMode; onChange: (v: FilmMode) => void }) {
  const help = FILM_MODE_HELP[value]
  return (
    <span className="flex flex-col gap-0.5">
      <select aria-label="Chế độ phim" value={value} onChange={(e) => onChange(e.target.value as FilmMode)}
              className="rounded bg-zinc-800 px-1 py-1">
        {(Object.keys(FILM_MODE_LABEL) as FilmMode[]).map((k) =>
          <option key={k} value={k}>{FILM_MODE_LABEL[k]}{k === DEFAULT_FILM_MODE ? ' (mặc định)' : ''}</option>)}
      </select>
      <span className="text-[10px] text-zinc-400">{FILM_MODE_HINT[value]}</span>
      <details className="text-[10px] text-zinc-400">
        <summary className="cursor-pointer text-zinc-300">ℹ️ Chế độ này làm gì?</summary>
        <p><b className="text-zinc-300">Hợp với:</b> {help.suits}</p>
        <p><b className="text-zinc-300">Cách làm:</b> {help.how}</p>
        <p><b className="text-zinc-300">Chi phí:</b> {help.cost}</p>
      </details>
    </span>
  )
}

/** Ambient mode only: which performance, and how long the reel that loops is (directive B14). */
export function AmbientOptions({ value, onChange }: { value: AmbientChoice; onChange: (v: AmbientChoice) => void }) {
  const venues = useVenues().data ?? []
  const venue = value.venue ?? venues[0]?.id ?? ''
  const reel = value.reel_s ?? DEFAULT_REEL_S
  const loop = value.loop_s ?? DEFAULT_LOOP_S
  const pick = venues.find((v) => v.id === venue)
  const set = (patch: AmbientChoice) => onChange({ venue, reel_s: reel, loop_s: loop, ...patch })
  return (
    <span className="flex flex-col gap-0.5">
      <select aria-label="Loại buổi diễn" value={venue} onChange={(e) => set({ venue: e.target.value })}
              className="rounded bg-zinc-800 px-1 py-1">
        {venues.map((v) => <option key={v.id} value={v.id}>🎤 {v.name}</option>)}
      </select>
      {pick && <span className="text-[10px] text-zinc-400">{pick.explain}</span>}
      <select aria-label="Độ dài vòng hình" value={reel} onChange={(e) => set({ reel_s: Number(e.target.value) })}
              className="rounded bg-zinc-800 px-1 py-1">
        {REEL_CHOICES.map((s) => <option key={s} value={s}>🔁 Vòng hình {s / 60} phút (≈ {Math.round(s / 8)} clip, ≈ {Math.round(s / 8) * 15} credit)</option>)}
      </select>
      <select aria-label="Độ dài video cuối" value={loop} onChange={(e) => set({ loop_s: Number(e.target.value) })}
              className="rounded bg-zinc-800 px-1 py-1">
        {LOOP_CHOICES.map((s) => <option key={s} value={s}>⏱ Video cuối {s / 60} phút (vòng hình lặp lại)</option>)}
      </select>
      <span className="text-[10px] text-zinc-400">Hệ thống ra 2 file: reel.mp4 (một vòng) và final.mp4 (vòng hình lặp tới độ dài đã chọn, không tiếng — bạn ghép nhạc ngoài). Lặp lại không tốn thêm credit.</span>
    </span>
  )
}
