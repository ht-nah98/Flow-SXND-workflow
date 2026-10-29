import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

type Tone = 'info' | 'error'
interface Item { id: number; text: string; tone: Tone }
const Ctx = createContext<(text: string, tone?: Tone) => void>(() => {})
export const useToast = () => useContext(Ctx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([])
  const push = useCallback((text: string, tone: Tone = 'info') => {
    const id = Date.now() + Math.random()
    setItems((x) => [...x, { id, text, tone }])
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), tone === 'error' ? 9000 : 4000)
  }, [])
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} role="status"
               className={`rounded-lg px-3 py-2 text-sm shadow-lg ${t.tone === 'error' ? 'bg-red-900 text-red-100' : 'bg-zinc-800 text-zinc-100'}`}>
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}
