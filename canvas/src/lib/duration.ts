/** Directive E1b: the chosen length is a rough size; the cut follows the story. Each 10s clip gives ~5.5s of film. */
export const FILM_PER_CLIP_S = 5.5

/** "~45s", "~2 phút", "~2,5 phút". */
export function approxLength(s: number): string {
  if (s < 90) return `~${s}s`
  const m = Math.round((s / 60) * 2) / 2
  return `~${String(m).replace('.', ',')} phút`
}

/** What a film made from `clips` clips will roughly run. */
export const estimatedFilmS = (clips: number) => Math.round(clips * FILM_PER_CLIP_S)
