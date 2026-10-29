const HINTS: [RegExp, string][] = [
  [/UNSAFE_GENERATION/, 'Bộ lọc của Google chặn nội dung. Thử đổi góc máy (nhìn nghiêng/sau lưng) hoặc bỏ tên riêng khỏi prompt.'],
  [/MINOR_INPUT_IMAGE/, 'Ảnh hoặc prompt có trẻ em. Bỏ các chi tiết về trẻ em rồi thử lại.'],
  [/UNUSUAL_ACTIVITY/, 'Flow đang giới hạn tần suất. Chờ khoảng 2 phút rồi thử lại.'],
  [/UNSUPPORTED_ON_BATCH_API/, 'Chế độ này chưa chạy trên Flow mới. Bật FLOW_ALLOW_DEGRADED=1 trong .env hoặc đổi model.'],
  [/CAPTCHA|NO_AT_TOKEN/, 'Tab Flow mất phiên. Tải lại tab flow.google.com rồi thử lại.'],
  [/Extension not connected|NO_FLOW_TAB/, 'Extension chưa kết nối. Mở tab flow.google.com trong profile Chrome của Flow.'],
  [/NETWORK|FlowKit chưa chạy/, 'Backend chưa chạy. Chạy ./start.sh trong thư mục flow-canvas.'],
  [/NO_FLOW_PROJECT/, 'Chưa ghim project Flow. Đặt FLOW_PROJECT_ID trong .env.'],
]

export function explainError(msg: string | null | undefined) {
  const message = msg || 'Lỗi không rõ'
  return { message, hint: HINTS.find(([re]) => re.test(message))?.[1] ?? null }
}
