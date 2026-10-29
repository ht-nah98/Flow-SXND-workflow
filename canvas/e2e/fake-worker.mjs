// Claims assistant provider jobs from the E2E FlowKit and completes them with fixture media.
const BASE = process.env.FK_URL ?? 'http://127.0.0.1:8120'
const IMG = process.env.FK_IMG
const VID = process.env.FK_VID
let n = 0
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

for (;;) {
  try {
    const r = await fetch(`${BASE}/api/provider-jobs/wait-next?provider=assistant&worker_id=e2e&timeout_s=5`)
    if (r.status !== 200) continue
    const job = await r.json()
    n += 1
    const isVideo = ['video', 'video_refs'].includes(job.kind)
    const media_id = `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
    await sleep(300)
    await fetch(`${BASE}/api/provider-jobs/${job.id}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ worker_id: 'e2e', result: { output_url: `file://${isVideo ? VID : IMG}`, media_id } }),
    })
  } catch {
    await sleep(1000)
  }
}
