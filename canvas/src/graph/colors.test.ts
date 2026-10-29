import { describe, expect, it } from 'vitest'
import type { Character } from '../api/types'
import { ASSET_PALETTE, assetColors, sortAssets } from './colors'

const c = (id: string, entity_type: Character['entity_type'], created_at: string): Character =>
  ({ id, name: id, slug: null, entity_type, description: null, image_prompt: null, voice_description: null,
     reference_image_url: null, media_id: null, created_at, updated_at: null })

describe('asset colours', () => {
  it('orders characters, locations, props and gives each a distinct stable colour', () => {
    const cs = [c('prop', 'visual_asset', '1'), c('place', 'location', '2'), c('hero', 'character', '3')]
    expect(sortAssets(cs).map((x) => x.id)).toEqual(['hero', 'place', 'prop'])
    const m = assetColors(cs)
    expect([m.get('hero'), m.get('place'), m.get('prop')]).toEqual(ASSET_PALETTE.slice(0, 3))
    expect(assetColors([...cs].reverse())).toEqual(m)
  })
})
