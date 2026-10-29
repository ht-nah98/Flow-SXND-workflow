/** Ước tính credit Flow cho mỗi video. veo: 8s (FlowKit skills/fk-change-model.md). omni_flash: clip 10s 720p = 15, đo trên Flow 2026-10-15. */
export const CREDITS_PER_VIDEO: Record<string, number> = { veo: 20, omni_flash: 15 }

export const estimateCredits = (videos: number, family: string) =>
  videos * (CREDITS_PER_VIDEO[family] ?? 20)

export const creditMessage = (videos: number, family: string) =>
  `Sẽ tạo ${videos} video, khoảng ${estimateCredits(videos, family)} credit Flow (ước tính).`
