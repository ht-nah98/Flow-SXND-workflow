# Kế hoạch tài liệu + đẩy GitHub (29/10)

Mục tiêu: bạn bè clone repo, cài đặt trong ~30 phút, làm được phim đầu tiên mà không cần hỏi.
Quyết định của người dùng (29/10): **lịch sử git mới, sạch** (1 commit đầu) · **repo private**, mời bạn vào.

## Đã dọn (29/10)
- Máy: `du-lieu/` 614MB → 128MB (bỏ khung QC cũ, film_review, log cũ, backup DB cũ; giữ 2 backup mới nhất).
- Repo: bỏ script dùng một lần, truyện Hồng Nhật, `backend/PLAN.md` gốc, `docs/thiet-ke/lich-su/`;
  sửa đường dẫn cũ (`YOUTUBE/`, `luu-tru/`); thay email/tên tài khoản Flow thật trong test và tài liệu.

## Bộ tài liệu

| # | File | Người đọc | Nội dung | Ảnh |
|---|------|-----------|----------|-----|
| 1 | `README.md` (viết lại) | ai mở repo | Đây là gì, phim mẫu, cần gì, cài nhanh 5 lệnh, mục lục tài liệu, ghi công FlowKit | ảnh canvas + 3 khung phim mẫu |
| 2 | `docs/01-cai-dat.md` | người cài | Python/Node/ffmpeg/Chrome, Claude Code đăng nhập, clone, `.env`, nạp extension, mở tab Flow, kiểm `/health`; ghi chú macOS / Windows (WSL) | ảnh chrome://extensions, đèn hệ thống xanh |
| 3 | `docs/02-lam-phim-dau-tien.md` | người dùng | Đi từng node: 💡 ý tưởng → 📜 kịch bản → duyệt credit → asset → video → 🎞 phim; chọn chế độ phim, giọng, khổ | ảnh chụp từng node (phim xơ dừa TikTok làm ví dụ) |
| 4 | `docs/03-meo-lam-phim.md` | người làm nội dung | Bản rút gọn cẩm nang A–Z: viết ý tưởng tốt, ảnh tham chiếu, ≤2 hành động/clip, physics, giọng nói, độ dài; trỏ sang sổ tay `playbook/` | ảnh asset đúng/sai |
| 5 | `docs/04-credit-va-tai-khoan.md` | người trả tiền | Giá ~15 credit/clip 10s, 1/ảnh; dự toán; trần credit ngày; nhiều tài khoản, chuyển phim sang tài khoản khác | ảnh 💳 |
| 6 | `docs/05-xu-ly-su-co.md` | ai gặp lỗi | Bảng lỗi hay gặp (extension mất kết nối, CAPTCHA, NO_MEDIA_CREATED, "payload carried no record", hết credit) + cách sửa; rút từ playbook 05 | — |
| 7 | `CONTRIBUTING.md` | người muốn góp | Chạy test, quy tắc commit, cách thêm bài học vào sổ tay (00 / 07), không commit `.env` / dữ liệu | — |
| 8 | `.claude/skills/flow-video-playbook/` | Claude Code của bạn | Đưa skill sổ tay vào repo, đường dẫn tương đối (bản hiện tại trỏ thư mục cũ `YOUTUBE/`) | — |

Giữ nguyên: `docs/kien-truc.md`, `docs/kien-thuc-lam-phim.md`, sổ tay `playbook/`, `backend/README.md` (tài liệu FlowKit gốc).
Cẩm nang PDF (25 trang) đưa vào `docs/cam-nang.pdf` hoặc link artifact — người dùng chọn.

## Thứ tự làm
1. Chụp ảnh canvas thật (Chrome CDP riêng) cho tài liệu 2–3 → `docs/anh/`.
2. Viết 2 → 3 → 6 → 5 → 4 → 1 (README viết sau cùng, khi biết đủ mục lục) → 7 → 8.
3. Tự kiểm: làm theo `01-cai-dat.md` trên bản clone sạch trong thư mục tạm (venv mới, `npm ci`, chạy test).
4. Quét lần cuối: email, token, đường dẫn `/home/`, file > 1MB.
5. Đẩy: `git checkout --orphan` → 1 commit → `gh repo create <tên> --private` → push → mời bạn
   (`gh api repos/<chủ>/<tên>/collaborators/<username> -X PUT`). Repo hiện tại giữ nguyên lịch sử đầy đủ ở máy.

## Cần người dùng trả lời trước bước 5
- Tên repo (gợi ý `flow-canvas`) và tài khoản GitHub chủ (`gh` đang đăng nhập `ht-nah98`).
- Username GitHub của bạn bè để mời.
