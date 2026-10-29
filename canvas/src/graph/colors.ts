import type { Character } from '../api/types'

/** Distinct, dark-background-friendly hues. An asset keeps its colour for the life of the project:
 *  its node, its wires and its chips on every scene all use it. */
export const ASSET_PALETTE = [
  '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#38bdf8', '#facc15',
  '#f87171', '#2dd4bf', '#c084fc', '#a3e635', '#fdba74', '#60a5fa',
]

const TYPE_ORDER: Record<string, number> = { character: 0, location: 1, visual_asset: 2 }

/** Characters first, then locations, then props — the order assets are listed everywhere. */
export const sortAssets = (cs: Character[]) =>
  [...cs].sort((a, b) => (TYPE_ORDER[a.entity_type] ?? 3) - (TYPE_ORDER[b.entity_type] ?? 3)
    || (a.created_at ?? '').localeCompare(b.created_at ?? '') || a.name.localeCompare(b.name))

export function assetColors(cs: Character[]): Map<string, string> {
  return new Map(sortAssets(cs).map((c, i) => [c.id, ASSET_PALETTE[i % ASSET_PALETTE.length]]))
}

export const TYPE_ICON: Record<string, string> = { character: '👤', location: '🏞', visual_asset: '📦' }
