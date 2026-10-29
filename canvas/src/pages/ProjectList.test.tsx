import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { resetRefreshCache } from '../lib/refreshUrls'
import { project, scene, video } from '../test/fixtures'
import { ProjectCard } from './ProjectList'

beforeEach(() => resetRefreshCache())
afterEach(() => vi.restoreAllMocks())

function setup() {
  vi.spyOn(api, 'listVideos').mockResolvedValue([video()])
  vi.spyOn(api, 'listScenes').mockResolvedValue([scene()])
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter>
    <ProjectCard project={project} />
  </MemoryRouter></QueryClientProvider>)
}

it('refreshes expired signed URLs when the cover fails, then hides the broken image', async () => {
  const refresh = vi.spyOn(api, 'refreshUrls').mockResolvedValue({})
  const { container } = setup()
  await waitFor(() => expect(container.querySelector('img, video')).not.toBeNull())
  const first = container.querySelector('img, video')!
  fireEvent.error(first)
  await waitFor(() => expect(refresh).toHaveBeenCalledWith('p1'))
  // The refreshed link still fails: no second call, no broken-image icon. Wait for the re-keyed element — an error
  // fired on the old one before it is replaced counts as the first failure again (the old flaky race).
  await waitFor(() => expect(container.querySelector('img, video')).not.toBe(first))
  expect(container.querySelector('img, video')).not.toBeNull()
  fireEvent.error(container.querySelector('img, video')!)
  await waitFor(() => expect(container.querySelector('img, video')).toBeNull())
  expect(refresh).toHaveBeenCalledTimes(1)
})
