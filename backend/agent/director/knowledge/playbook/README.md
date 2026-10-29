# Sổ tay sản xuất video AI (Flow Omni Flash + FlowKit + Canvas)

Bộ kinh nghiệm đúc kết từ dự án thực tế. Mỗi lần học thêm một video mẫu → thêm 1 file vào `samples/`
và cập nhật kỹ thuật mới vào file chủ đề tương ứng. Kỹ thuật nào đã được chứng minh trên clip thật thì
ghi kèm "✅ đã kiểm chứng (<dự án>)"; chưa thử thì ghi "🧪 chưa kiểm chứng".

## ĐỌC TRƯỚC
- [00-loi-dan-nguoi-dung.md](00-loi-dan-nguoi-dung.md) — **mọi lời dặn của người dùng**, kèm lời gốc và ngày. Nguồn sự
  thật cao nhất, được nạp vào MỌI vai trò AI. Lời dặn mới ghi vào đây ngay.
- [07-nhat-ky-bai-hoc.md](07-nhat-ky-bai-hoc.md) — mỗi lần làm phim: kết quả, sai gì, vì sao, đã sửa ở đâu.
- [08-quy-tac-lam-viec.md](08-quy-tac-lam-viec.md) — cách Claude Code làm việc với người dùng (credit, token, thư mục).
- [11-phim-khong-khi.md](11-phim-khong-khi.md) — chế độ không kể chuyện (B14): một buổi diễn, một bối cảnh, reel 1–2 phút 12–16 clip 8s, lặp dưới bản nhạc.
- [10-phim-keyframe.md](10-phim-keyframe.md) — chế độ keyframe (B13): ghim ảnh keyframe mỗi shot, shot 1–5s một việc, nối bằng che ống kính / xuyên màn hình / cắt giữa hành động / nhoè (mẫu Kling/Artlist, [phân tích](samples/kling-artlist/phan-tich.md)).
- [09-phim-lien-mach.md](09-phim-lien-mach.md) — ⭐ chế độ mặc định (B12): phim liền mạch, clip mở từ khung cuối clip trước, chuyển cảnh bằng máy quay giữa clip (mẫu SIU Giáng Sinh).

## Quy trình 5 bước (thứ tự bắt buộc — chế độ `cut`; các chế độ khác xem 09, 10, 11)

| # | Bước | Đầu ra | File |
|---|------|--------|------|
| 1 | Kịch bản hoàn chỉnh | Danh sách prompt từng clip + ảnh tham chiếu dùng cho clip đó | [01-kich-ban.md](01-kich-ban.md) |
| 2 | Asset nhân vật / đạo cụ | 1 character sheet / nhân vật (cận mặt + toàn thân trước + nghiêng + sau) | [02-asset.md](02-asset.md) |
| 3 | Bối cảnh | 1 ảnh thật / địa điểm, đúng tỉ lệ video (16:9 hoặc 9:16) | [02-asset.md](02-asset.md) |
| 4 | Video | Mỗi clip 10s, **r2v**: prompt + ảnh asset, KHÔNG tạo ảnh khung đầu | [03-prompt-video.md](03-prompt-video.md) |
| 5 | Dựng phim + xử lý lỗi | Cắt 3–7s/clip, chuyển cảnh, màu, xuất file | [04-dung-phim.md](04-dung-phim.md), [06-hieu-ung.md](06-hieu-ung.md), [05-xu-ly-loi.md](05-xu-ly-loi.md) |

Hai cách tạo video: (1) từ ảnh (i2v — tạo ảnh khung đầu rồi làm video) và (2) **prompt + asset tham chiếu (r2v)**.
**Mặc định luôn là (2)**: ảnh khung đầu trói tay mô hình video, các cảnh không khớp nhau. Asset (character sheet,
ảnh bối cảnh, đạo cụ) chỉ là tham chiếu, không phải khung hình.
Ngôn ngữ phim chọn trên node 💡 (mặc định **tiếng Anh**: bối cảnh nước ngoài, prompt và lời thoại tiếng Anh — mô
hình hiểu prompt tiếng Anh tốt hơn). Phim Việt Nam → tiếng Việt.
**Bám vật lý**: mỗi hành động là một nguyên nhân – kết quả thật; không vật nào tự hiện, biến mất, biến dạng, lơ lửng.

Nguyên tắc gốc: **ảnh sai thì video sai** → đầu tư vào asset sạch, rồi dùng lại đúng các asset đó cho mọi clip.
Câu chuyện được kể ở bàn dựng (sắp xếp, cắt ngắn), không nhồi vào một clip.

## Học video mẫu mới
Làm theo [samples/_cach-hoc-video-mau.md](samples/_cach-hoc-video-mau.md). Mẫu đã học:
- [samples/fmv-banh-kem.md](samples/fmv-banh-kem.md) — MV tình cảm "Bánh kem & tình yêu", 53s, 11 prompt. ✅ đã làm lại thành công.
- [samples/siu-giang-sinh/prompts.md](samples/siu-giang-sinh/prompts.md) — ⭐ phim người dùng tự làm, 26 prompt gốc 550–1.050 từ: khung cuối làm ảnh #1, SECOND a–b, FINAL FRAME CONTRACT. ✅
- [samples/bottomless-trailer.md](samples/bottomless-trailer.md) — trailer hoạt hình "BOTTOMLESS", 127s: nhịp cỡ cảnh xa↔sát, từ vật mở ra toàn cảnh, lời dẫn V.O., motif nắp chai. 🧪
- [samples/heaven-sound-worship/phan-tich.md](samples/heaven-sound-worship/phan-tich.md) — dạng KHÔNG kể chuyện (B14): một sân vận động, đêm nhạc, clip 8s cắt thẳng, một bản nhạc phủ cả phim. 🧪

## Công cụ
- `agent/director/effects.py` — thư viện hiệu ứng kiểu CapCut (bộ lọc, hiệu ứng, chuyển tiếp), cả phim một lần encode.
- `tools/edit_fmv.py` — dựng phim bằng ffmpeg theo EDL (danh sách cắt), xuất yuv420p. `python3 edit_fmv.py <thư mục clip> <out.mp4>`
