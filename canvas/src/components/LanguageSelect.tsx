import type { FilmLanguage } from '../api/types'

/** The film's language. English: an English-speaking world, English voice and English prompts (the video model
 *  follows English best). Vietnamese: a Vietnamese world and voice. */
export function LanguageSelect({ value, onChange }: { value: FilmLanguage; onChange: (v: FilmLanguage) => void }) {
  return (
    <select aria-label="Ngôn ngữ phim" value={value} onChange={(e) => onChange(e.target.value as FilmLanguage)}
            className="rounded bg-zinc-800 px-1 py-1">
      <option value="en">🇬🇧 Tiếng Anh (bối cảnh nước ngoài, prompt tiếng Anh)</option>
      <option value="vi">🇻🇳 Tiếng Việt (bối cảnh Việt Nam)</option>
    </select>
  )
}
