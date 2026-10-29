import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { character, project, request, scene, video } from '../test/fixtures'
import { useProjectData } from './queries'

afterEach(() => vi.unstubAllGlobals())

const routes: [RegExp, unknown][] = [
  [/\/api\/projects\/p1\/characters$/, [character()]],
  [/\/api\/projects\/p1\/canvas$/, { nodes: [] }],
  [/\/api\/projects\/p1$/, project],
  [/\/api\/videos\?project_id=p1$/, [video()]],
  [/\/api\/scenes\?video_id=v1$/, [scene()]],
  [/\/api\/requests\?project_id=p1$/, [request()]],
]

it('returns the same data object across re-renders when nothing changed', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const hit = routes.find(([re]) => re.test(url))
    return new Response(JSON.stringify(hit ? hit[1] : null), { status: hit ? 200 : 404 })
  }))
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  const { result, rerender } = renderHook(() => useProjectData('p1'), { wrapper })
  await waitFor(() => expect(result.current.data).toBeDefined())
  const first = result.current.data
  rerender()
  expect(result.current.data).toBe(first)
  expect(first!.scenesByVideo.v1[0].id).toBe('s1')
  expect(first!.requests).toHaveLength(1)
})
