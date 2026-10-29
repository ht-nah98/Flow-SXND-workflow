# 08 — Quy tắc làm việc cho Claude Code (người xây và vận hành hệ thống)

Không nạp vào các vai trò làm phim. Đây là cách Claude Code làm việc với người dùng.

- **Credit**: chỉ tiêu credit Flow khi người dùng duyệt rõ ràng (cổng SCRIPT / ASSETS). Duyệt IDEA (viết kịch bản) miễn phí.
  Báo trước số credit dự kiến (clip 10s ≈ 15 credit, × ~1.2 dự phòng).
- **Không dùng subagent**, làm tuần tự, tiết kiệm token. — "quay về không dùng subagent nữa nhé. Tốn token quá." (15/10)
- **Trả lời tiếng Việt, ngắn gọn**; báo khi xong việc dài. — "Khi nào xong bảo tôi nhé." (14/10)
- **Lời dặn mới → ghi ngay vào 00** (kèm lời gốc và ngày) → ép bằng code/lint nếu được → nhật ký 07 → commit.
- **Kết quả xem được để trên Desktop**: phim ở `~/Desktop/Workflow Video Omini Making/phim/<dự-án>_<id8>/final.mp4`, mở bằng xdg-open.
  Hệ thống phải rõ ràng, minh bạch, sẵn sàng đẩy GitHub (repo private). (15–16/10)
- **Chrome**: dùng profile Olya của người dùng để quan sát/sửa lỗi (CDP chỉ quan sát). Không nhập mật khẩu.
  Không tải tài sản CapCut. — "bạn có thể sử dụng chrome của tôi để fixbug" (15/10)
- **Cổng 8100 là app khác, không đụng.** Tắt tiến trình theo PID. Khởi động lại backend chỉ khi không có request
  PENDING/PROCESSING và không có run RUNNING (xem `docs/` và README).
- **Lời dặn nhắc lần 2 = kiểm tra máy**, không thêm chữ. Đọc bảng "mẫu lỗi lặp lại" trong 07 trước khi làm
  phim hoặc tính năng mới. Sửa lỗi xong: kiểm lại dữ liệu cũ đã bị lỗi đó (phiên bản trùng, phim chưa gắn tài khoản…).
- **Làm hộ người dùng** (tạo phim, duyệt cổng): dùng mặc định của 💡, không chép cài đặt phim cũ; báo credit trước.
- **Đo trước khi tối ưu** (CDP Performance/Profiler, nhật ký token, thời gian từng bước); báo số trước/sau.
- **Canvas hằng ngày chạy bản build** (`./start.sh canvas`); `./start.sh canvas-dev` chỉ khi code. Sửa giao diện xong:
  `npx vite build` để người dùng F5 là có bản mới.
- **Thao tác chính luôn hiện** (nút duyệt, tạo ảnh, tạo video); mỗi nút phải ra kết quả mới hoặc báo rõ vì sao không.
- **Mỗi thay đổi**: test backend (`pytest tests/unit`) + canvas (`tsc` + `vitest`) xanh rồi mới commit.
- **Model theo vai trò**: đạo diễn AI không chạy Opus cho mọi bước. Bảng và lý do ở `docs/thiet-ke/model-theo-vai-tro.md`;
  chỉnh dựa trên `du-lieu/logs/brain-usage.jsonl`, không đoán. — "Không phải task vụ nào cũng cần dùng Opus 5.5" (16/10)
- **⚠️ Tự review giao diện bằng Chrome trước khi báo** — mở Chrome riêng HEADLESS (profile trống, `--headless=new
  --disable-extensions`, CDP cổng 9555 — cửa sổ thật sẽ cướp phím người dùng đang gõ), thao tác thật, chụp màn hình, xem lại; không bảo người dùng F5 rồi tự kiểm. — "Bạn có thể tự bật
  chrome để review mà. bạn không nhớ à." (19/10)

