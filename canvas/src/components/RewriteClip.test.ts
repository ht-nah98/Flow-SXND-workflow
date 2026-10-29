import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { createElement } from 'react'
import { ChainNote, changedLines } from './RewriteClip'
import { chainedAfter } from '../graph/mapping'

describe('changedLines', () => {
  it('flags only the lines the rewrite changed', () => {
    const r = changedLines('Bối cảnh: vườn\nÂm thanh: gió', 'Bối cảnh: vườn\nÂm thanh: gió, tiếng cười')
    expect(r.map((l) => l.changed)).toEqual([false, true])
  })
})

describe('ChainNote', () => {
  it('warns about scenes already made from the old take, otherwise says to settle this one first', () => {
    const made = render(createElement(ChainNote, { chained: [2, 3], made: [2] }))
    expect(made.container.textContent).toMatch(/cảnh 2 đã tạo từ bản cũ/)
    made.unmount()
    const none = render(createElement(ChainNote, { chained: [2, 3] }))
    expect(none.container.textContent).toMatch(/chốt cảnh này ưng ý trước/)
  })
})

describe('chainedAfter', () => {
  const run = (mode: string) => ({ plan: { brief: { film_mode: mode }, shotlist: { shots: [
    { id: 'a', order: 1 }, { id: 'b', order: 2, continues: true }, { id: 'c', order: 3, continues: true },
    { id: 'd', order: 4 }, { id: 'e', order: 5, continues: true }] } } })
  it('names the scenes that open on this clip, up to the next chain', () => {
    expect(chainedAfter(run('continuous'), 'a')).toEqual([2, 3])
    expect(chainedAfter(run('continuous'), 'c')).toEqual([])
    expect(chainedAfter(run('continuous'), 'd')).toEqual([5])
    expect(chainedAfter(run('cut'), 'a')).toEqual([])
  })
})
