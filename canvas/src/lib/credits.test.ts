import { expect, it } from 'vitest'
import { creditMessage } from './credits'

it('creditMessage states count, estimate and the word ước tính', () => {
  expect(creditMessage(3, 'veo')).toBe('Sẽ tạo 3 video, khoảng 60 credit Flow (ước tính).')
})
