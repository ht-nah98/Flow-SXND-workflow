import { expect, test } from '@playwright/test'
import { FK, seedProject } from './seed'

test.describe.configure({ mode: 'serial' })

test('criteria 1, 2, 3, 4, 8: render, generate, stale, restore, credit confirm', async ({ page, request }) => {
  const w = await seedProject(request, 'E2E A')
  await page.goto(`/p/${w.pid}`)
  // 1. nodes render
  await expect(page.getByTestId(`node-character:${w.cid}`)).toBeVisible()
  await expect(page.getByTestId(`node-scene:${w.s1}`)).toBeVisible()
  await expect(page.getByTestId(`node-scene:${w.s2}`)).toBeVisible()

  // asset image, then all missing scenes (credit dialog: 8)
  await page.getByTestId(`node-character:${w.cid}`).getByRole('button', { name: 'Gen ảnh' }).click()
  const charImg = page.getByTestId(`node-character:${w.cid}`).getByTestId('media-image').locator('img[src*="/api/files"]')
  await expect(charImg).toBeVisible({ timeout: 30_000 })
  await expect.poll(() => charImg.evaluate((el) => (el as HTMLImageElement).naturalWidth), { timeout: 15_000 }).toBeGreaterThan(0)

  const video = page.getByTestId(`node-video:${w.vid}`)
  await video.getByRole('button', { name: /Tạo tất cả cảnh còn thiếu/ }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('ước tính')
  await dialog.getByRole('button', { name: 'Huỷ' }).click()
  const afterCancel = await (await request.get(`${FK}/api/requests?video_id=${w.vid}`)).json()
  expect(afterCancel.filter((r: { type: string }) => r.type.includes('VIDEO'))).toHaveLength(0)

  await video.getByRole('button', { name: /Tạo tất cả cảnh còn thiếu/ }).click()
  await page.getByRole('dialog').getByRole('button', { name: /Tạo 2 video/ }).click()
  // 2. results appear without reload
  const sceneVideo = page.getByTestId(`node-scene:${w.s2}`).getByTestId('media-video').locator('video[src*="/api/files"]')
  await expect(sceneVideo).toBeVisible({ timeout: 60_000 })
  await expect.poll(() => sceneVideo.evaluate((el) => (el as HTMLVideoElement).readyState), { timeout: 15_000 }).toBeGreaterThanOrEqual(1)

  // 3. regenerate parent image → child stale
  await page.getByTestId(`node-scene:${w.s1}`).getByRole('button', { name: 'Gen lại ảnh' }).click()
  await expect(page.getByTestId(`node-scene:${w.s2}`).getByText('cần tạo lại')).toBeVisible({ timeout: 30_000 })

  // 4. restore the first image version of scene 1
  const versions = page.getByTestId(`node-scene:${w.s1}`).getByRole('button', { name: /Phiên bản/ })
  await expect(versions).toHaveCount(2 + 1, { timeout: 30_000 })   // 2 image versions + 1 video version
  await page.getByTestId(`node-scene:${w.s1}`).getByRole('button', { name: 'Phiên bản 1' }).first().click()
  await page.getByRole('dialog').getByRole('button', { name: 'Chỉ dùng kết quả' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Đã khôi phục phiên bản' })).toBeVisible()
})

test('criterion 5: drag a shared asset from another project onto the canvas', async ({ page, request }) => {
  const a = await seedProject(request, 'E2E B')
  const mentor = await (await request.post(`${FK}/api/characters`, { data: { name: 'Mentor', entity_type: 'character', description: 'x' } })).json()
  const other = await seedProject(request, 'E2E C')
  await request.post(`${FK}/api/projects/${other.pid}/characters/${mentor.id}`)
  await page.goto(`/p/${a.pid}`)
  await page.getByTestId(`lib-${mentor.id}`).dragTo(page.getByTestId('canvas'), { targetPosition: { x: 600, y: 300 } })
  await expect(page.getByTestId(`node-character:${mentor.id}`)).toBeVisible({ timeout: 10_000 })
})

test('criterion 7: external edit appears within 2 s', async ({ page, request }) => {
  const w = await seedProject(request, 'E2E D')
  await page.goto(`/p/${w.pid}`)
  await expect(page.getByTestId(`node-scene:${w.s1}`)).toBeVisible()
  await request.patch(`${FK}/api/scenes/${w.s1}`, { data: { video_prompt: 'EDITED BY CLAUDE' } })
  await expect(page.getByTestId(`node-scene:${w.s1}`).getByLabel('Prompt video')).toHaveValue('EDITED BY CLAUDE', { timeout: 2_000 })
})

test('connecting an asset to a scene updates character_names', async ({ page, request }) => {
  const w = await seedProject(request, 'E2E E')
  const loc = await (await request.post(`${FK}/api/characters`, { data: { name: 'Classroom', entity_type: 'location', description: 'x' } })).json()
  await request.post(`${FK}/api/projects/${w.pid}/characters/${loc.id}`)
  await page.goto(`/p/${w.pid}`)
  // The asset library floats top-left and can overlap a freshly auto-laid-out
  // node there, intercepting the drag's pointer events — collapse it first.
  await page.getByRole('button', { name: 'Thu gọn thư viện' }).click()
  const src = page.getByTestId(`node-character:${loc.id}`).locator('.react-flow__handle[data-handleid="out"]')
  const dst = page.getByTestId(`node-scene:${w.s1}`).locator('.react-flow__handle[data-handleid="refs"]')

  // React Flow draws its own connection line from raw mouse events — a single
  // dragTo() jump can land before React Flow's drag threshold registers the
  // gesture as a connection attempt. Step through it by hand. The retry loop
  // is defense-in-depth for simulated handle-to-handle drags, which can be a
  // little flaky under headless Chromium even once positions are correct.
  const connected = async () =>
    (await (await request.get(`${FK}/api/scenes/${w.s1}`)).json()).character_names

  for (let attempt = 0; attempt < 5; attempt++) {
    const from = await src.boundingBox()
    const to = await dst.boundingBox()
    if (!from || !to) throw new Error('handle not found')
    const fx = from.x + from.width / 2, fy = from.y + from.height / 2
    const tx = to.x + to.width / 2, ty = to.y + to.height / 2
    await page.mouse.move(fx, fy)
    await page.mouse.down()
    await page.mouse.move(fx + (tx - fx) / 2, fy + (ty - fy) / 2, { steps: 10 })
    await page.mouse.move(tx, ty, { steps: 10 })
    await page.mouse.up()
    if (JSON.stringify(await connected()) === JSON.stringify(['Teacher Lan', 'Classroom'])) break
    await page.waitForTimeout(300)
  }
  await expect.poll(connected, { timeout: 5_000 }).toEqual(['Teacher Lan', 'Classroom'])
})
