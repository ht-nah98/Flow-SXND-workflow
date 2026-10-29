import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { refreshProjectUrls, resetRefreshCache } from './refreshUrls'

beforeEach(() => resetRefreshCache())
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

it('collapses concurrent refreshes of one project into a single backend call', async () => {
  const spy = vi.spyOn(api, 'refreshUrls').mockResolvedValue({})
  await Promise.all([refreshProjectUrls('p1'), refreshProjectUrls('p1'), refreshProjectUrls('p1')])
  expect(spy).toHaveBeenCalledTimes(1)
})

it('does not call again within the cooldown, so a still-broken image cannot loop', async () => {
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'refreshUrls').mockResolvedValue({})
  await refreshProjectUrls('p1')
  await refreshProjectUrls('p1')
  expect(spy).toHaveBeenCalledTimes(1)
  vi.advanceTimersByTime(61_000)
  await refreshProjectUrls('p1')
  expect(spy).toHaveBeenCalledTimes(2)
})

it('refreshes each project independently', async () => {
  const spy = vi.spyOn(api, 'refreshUrls').mockResolvedValue({})
  await refreshProjectUrls('p1')
  await refreshProjectUrls('p2')
  expect(spy).toHaveBeenCalledTimes(2)
})

it('rejects when the backend fails (caller decides how to report it)', async () => {
  vi.spyOn(api, 'refreshUrls').mockRejectedValue(new Error('503 Extension not connected'))
  await expect(refreshProjectUrls('p1')).rejects.toThrow('503')
})
