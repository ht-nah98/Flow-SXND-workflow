import * as Dialog from '@radix-ui/react-dialog'
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

interface ChoiceRequest { title: string; body: string; options: { value: string; label: string }[] }
type Choose = (r: ChoiceRequest) => Promise<string | null>
const Ctx = createContext<Choose>(async () => null)
export const useChoice = () => useContext(Ctx)

export function ChoiceDialogProvider({ children }: { children: ReactNode }) {
  const [req, setReq] = useState<(ChoiceRequest & { resolve: (v: string | null) => void }) | null>(null)
  const choose = useCallback<Choose>((r) => new Promise((resolve) => setReq({ ...r, resolve })), [])
  const close = (v: string | null) => { req?.resolve(v); setReq(null) }
  return (
    <Ctx.Provider value={choose}>
      {children}
      <Dialog.Root open={!!req} onOpenChange={(o) => { if (!o) close(null) }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-zinc-900 p-5 text-sm shadow-xl">
            <Dialog.Title className="mb-2 text-base font-semibold">{req?.title}</Dialog.Title>
            <Dialog.Description className="mb-4 whitespace-pre-line text-zinc-300">{req?.body}</Dialog.Description>
            <div className="flex flex-wrap justify-end gap-2">
              <button className="rounded-lg px-3 py-1.5 text-zinc-300 hover:bg-zinc-800" onClick={() => close(null)}>Huỷ</button>
              {req?.options.map((o) => (
                <button key={o.value} className="rounded-lg bg-sky-600 px-3 py-1.5 text-white hover:bg-sky-500"
                        onClick={() => close(o.value)}>{o.label}</button>
              ))}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </Ctx.Provider>
  )
}
