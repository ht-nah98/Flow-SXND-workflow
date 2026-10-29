# 5. Xử lý sự cố

**Luôn bắt đầu bằng đèn hệ thống** (giữa đáy canvas). Dòng nào ❌ thì có ghi cách sửa ngay bên cạnh.

![Đèn hệ thống](anh/09-den-he-thong.jpg)

Hoặc từ terminal:

```bash
curl -s localhost:8110/health          # cần "extension_connected": true
tail -50 ../du-lieu/logs/backend-*.log # log backend mới nhất
```

## Cài đặt và kết nối

| Triệu chứng | Cách sửa |
|-------------|----------|
| `./start.sh` báo `Missing .env` | `cp .env.example .env` rồi điền `FLOW_PROJECT_ID` |
| Canvas mở được nhưng trống, báo lỗi mạng | Backend chưa chạy: `./start.sh backend`, xem log trong `du-lieu/logs/` |
| `extension_connected: false` | Chrome chưa mở tab https://flow.google.com, hoặc extension chưa nạp / bị tắt. Mở `chrome://extensions`, bấm ↻ trên Flow Kit, tải lại tab Flow |
| Đèn **Claude (đạo diễn)** đỏ | `claude` không có trong PATH hoặc chưa đăng nhập: chạy `claude` một lần trong terminal |
| Đèn **ffmpeg** đỏ | Cài ffmpeg (`sudo apt install ffmpeg` / `brew install ffmpeg`) |
| Cổng 8110 / 5180 đang bị dùng | Đổi `API_PORT` / `CANVAS_PORT` trong `.env` |

## Lỗi khi tạo ảnh, video

| Lỗi | Nguyên nhân | Cách sửa |
|-----|-------------|----------|
| `CAPTCHA_FAILED` | Tab Flow cũ, ngủ, hoặc mất mạng | Hệ thống tự tải lại tab một lần. Vẫn lỗi: F5 tab Flow, kiểm tra còn đăng nhập, bấm **Chạy tiếp**. **Đừng bấm gửi lại liên tục**, Google sẽ coi là bot |
| "Unusual activity" / Google chặn tạm | Gửi quá dồn | Chờ 15–30 phút. Hệ thống vốn gửi từng lệnh một; đừng chạy hai phim cùng lúc trên một tài khoản |
| `NO_MEDIA_CREATED` ở **một cảnh**, lặp lại | Flow chặn nội dung: trẻ em một mình trong khung, dao, máu, thương tích | Dùng **✏️ Sửa clip bằng lời** để đổi hành động sang thứ an toàn tương đương; trẻ em thì thêm người lớn vào khung |
| `NO_MEDIA_CREATED` ở cảnh **giống bản tin TV** | Flow chặn vì "rủi ro xuyên tạc sự kiện" | Bỏ chữ ON AIR, màn hình tin, bàn dẫn; dùng phòng trơn |
| `NO_MEDIA_CREATED` chỉ ở cảnh **thấy rõ mặt** một nhân vật | Mặt giống người nổi tiếng | Gen lại ảnh nhân vật với nét riêng (kiểu đầu, kính, râu), ghi "ordinary unfamous face" |
| `NO_MEDIA_CREATED` ở **mọi** video của một phim | Project Flow không thuộc tài khoản đang dùng | **đổi tài khoản** về đúng tài khoản của phim (xem [Credit và tài khoản](04-credit-va-tai-khoan.md)) |
| `operation payload carried no record` (hỏng sau 2–4 giây) | Chưa rõ; thường ngay sau khi chuyển tài khoản | Gửi lại cảnh đó như **lệnh mới**, giữ nguyên prompt; thường qua ngay lần đầu |
| `QUOTA_REACHED` / hết credit | Tài khoản hết credit | Xem [Credit và tài khoản](04-credit-va-tai-khoan.md) |
| Clip tạo xong rồi biến mất (`MEDIA_REMOVED`) | Bộ lọc của Flow xoá sau khi tạo | Hệ thống tự gửi lại 1 lần. Vẫn bị xoá → viết lại prompt |

## Phim ra không như ý

| Triệu chứng | Cách sửa |
|-------------|----------|
| Nhân vật đổi mặt, đổi áo giữa các clip | Kiểm tra character sheet đúng một người; cảnh đó phải gắn chip nhân vật. Gen lại clip |
| Đồ vật thừa (3 viên thay vì 1) | Ảnh đạo cụ có nhiều vật → **Upload** ảnh chỉ một vật rồi gen lại clip |
| Hành động méo, lộn xộn | Clip có quá 2 hành động → ✏️ sửa clip, tách ý |
| Vật lơ lửng, tự hiện ra | Prompt tả "phép màu" → viết lại bằng hành động vật lý (tay đặt, nước chảy, kéo lên) |
| Phim dài hơn dự kiến | Clip có thoại không bị cắt giữa câu. Bớt thoại, hoặc chọn bản clip khác rồi **🎬 Dựng lại phim** (miễn phí) |
| Giọng nhân vật lệch giữa clip | Mô tả giọng phải giống hệt nhau ở mọi clip; nhân vật ít thoại thì cân nhắc để người khác nói |
| Phim đen màn hình khi phát | Trình phát không hỗ trợ; phim chuẩn là H.264 yuv420p. Báo lỗi kèm log |

## Muốn dừng

- **⏸ Tạm dừng**: xong việc đang chạy thì dừng; lệnh chưa gửi Flow không bị gửi. **Chạy tiếp** làm nốt phần còn thiếu.
- **🛑 Huỷ toàn bộ run**: bỏ hẳn, không chạy tiếp được.

## Vẫn không được?

Trong Claude Code, đứng ở thư mục `flow-canvas/backend` và gõ `/fk-doctor`: Claude đọc log, kiểm tra extension, worker
và đề xuất cách sửa. Bảng lỗi đầy đủ ở [`playbook/05-xu-ly-loi.md`](../backend/agent/director/knowledge/playbook/05-xu-ly-loi.md).

---
← [4. Credit và tài khoản](04-credit-va-tai-khoan.md) · [Về README](../README.md)
