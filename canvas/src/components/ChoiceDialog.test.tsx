import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ChoiceDialogProvider, useChoice } from './ChoiceDialog'

function Harness({ onResult }: { onResult: (v: string | null) => void }) {
  const choose = useChoice()
  return <button onClick={async () => onResult(await choose({
    title: 'Xác nhận', body: 'Nội dung', options: [{ value: 'ok', label: 'Đồng ý' }] }))}>open</button>
}

describe('ChoiceDialog', () => {
  it('resolves with the chosen value', async () => {
    let got: string | null | undefined
    render(<ChoiceDialogProvider><Harness onResult={(v) => { got = v }} /></ChoiceDialogProvider>)
    fireEvent.click(screen.getByText('open'))
    expect(await screen.findByText('Nội dung')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Đồng ý'))
    await screen.findByText('open')
    await new Promise((r) => setTimeout(r, 0))
    expect(got).toBe('ok')
  })

  it('resolves null on Huỷ', async () => {
    let got: string | null | undefined = 'unset'
    render(<ChoiceDialogProvider><Harness onResult={(v) => { got = v }} /></ChoiceDialogProvider>)
    fireEvent.click(screen.getByText('open'))
    fireEvent.click(await screen.findByText('Huỷ'))
    await new Promise((r) => setTimeout(r, 0))
    expect(got).toBeNull()
  })
})
