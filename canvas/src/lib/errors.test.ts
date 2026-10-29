import { describe, expect, it } from 'vitest'
import { explainError } from './errors'

describe('explainError', () => {
  it.each([
    ['PUBLIC_ERROR_UNSAFE_GENERATION', /góc máy/],
    ['PUBLIC_ERROR_MINOR_INPUT_IMAGE', /trẻ em/],
    ['PUBLIC_ERROR_UNUSUAL_ACTIVITY', /2 phút/],
    ['UNSUPPORTED_ON_BATCH_API: x', /FLOW_ALLOW_DEGRADED/],
    ['Extension not connected', /flow\.google\.com/],
  ])('%s', (msg, hint) => {
    expect(explainError(msg).hint).toMatch(hint)
  })

  it('unknown errors keep the message and have no hint', () => {
    expect(explainError('boom')).toEqual({ message: 'boom', hint: null })
    expect(explainError(null).message).toBe('Lỗi không rõ')
  })
})
