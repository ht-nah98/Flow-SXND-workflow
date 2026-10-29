import { describe, expect, it } from 'vitest'
import { approxLength, estimatedFilmS } from './duration'

describe('approximate film length (directive E1b)', () => {
  it('reads as a rough size', () => {
    expect(approxLength(45)).toBe('~45s')
    expect(approxLength(120)).toBe('~2 phút')
    expect(approxLength(150)).toBe('~2,5 phút')
    expect(approxLength(240)).toBe('~4 phút')
  })
  it('estimates from the clip count', () => {
    expect(estimatedFilmS(22)).toBe(121)
  })
})
