import { useConnection } from '../api/connection'
import { useHealth } from '../api/queries'

export function useCanGenerate() {
  const h = useHealth()
  return !!h.data && (h.data.extension_connected || h.data.media_provider === 'assistant')
}

export function StatusBar() {
  const h = useHealth()
  const { wsOpen, wsDownSince } = useConnection()
  let msg: string | null = null
  let tone = 'bg-amber-900 text-amber-100'
  if (h.error) {
    msg = 'Backend chưa chạy. Chạy ./start.sh trong thư mục flow-canvas. Canvas đang ở chế độ chỉ xem.'
    tone = 'bg-red-900 text-red-100'
  } else if (h.data && !h.data.extension_connected && h.data.media_provider !== 'assistant') {
    msg = 'Extension chưa kết nối. Mở tab flow.google.com trong profile Chrome của Flow. Các nút tạo đang bị khoá.'
  } else if (!wsOpen && wsDownSince && Date.now() - wsDownSince > 10_000) {
    msg = 'Mất kết nối trực tiếp, đang tự làm mới mỗi 5 giây.'
  }
  return msg ? <div role="alert" className={`px-4 py-2 text-sm ${tone}`}>{msg}</div> : null
}
