# Kế hoạch: chế độ "🎵 Không khí buổi diễn" (`ambient`, 24/10)

Lời người dùng: "Video đại khái chỉ giống như các cảnh quay trong 1 bối cảnh cụ thể, cùng không gian. Không có câu
chuyện nào ở đây cả chỉ là quay lại cảnh quay đang diễn và nghe biểu diễn âm nhạc." · "Họ làm video có 1p-2p rồi lặp
ấy mà. nên mình cũng chỉ cần làm như vậy thôi." · Bối cảnh: "Nhiều loại buổi diễn". Đồng ý kế hoạch: "OKKK tôi đồng ý".
Mẫu: `playbook/samples/heaven-sound-worship/phan-tich.md`. Luật: `playbook/11-phim-khong-khi.md`, lời dặn B14.

Chế độ thứ tư, cạnh `cut` · `continuous` · `keyframe` (B13: không bỏ chế độ nào).

## Các bước (mỗi bước chờ người dùng OK)
1. ✅ Kiến thức: phân tích mẫu, B14, sổ tay 11; dọn các chỗ tài liệu tự mâu thuẫn (chế độ mặc định, docs cũ).
2. ✅ (24/10) Kịch bản: `film_mode = "ambient"` + `brief.venue` (loại buổi diễn) + `brief.reel_s` (60–120s) + độ dài đích /
   nhạc. Không viết truyện: biên kịch chỉ viết tờ bối cảnh (1 nơi + ≤2 chi tiết, `lint_story_ambient`), không `lint_story`;
   đạo diễn chia `reel_s / 8` shot có `kind` (wide/people/detail/stage); DP viết
   prompt theo §5 của 11. Lint riêng (`lint/ambient.py`): một bối cảnh, `style_block` chung, luân phiên loại, một chuyển
   động máy, không mặt người biểu diễn/chữ, 50–150 từ. Rà mọi nhánh `film_mode` (mẫu lỗi #11) + test mỗi nhánh.
   Canvas: ô chế độ + chọn buổi diễn + độ dài vòng trên 💡.
3. ✅ (24/10) Tạo (tốn credit, chờ duyệt): ảnh bối cảnh → **thử 2–3 clip** (ghế trống và có khán giả) → người dùng xem → cả reel.
   Clip r2v 8s. Không bước nhân vật, không KEYFRAMES.
4. ✅ (24/10, code + thử trên 2 clip) Dựng: cắt thẳng, tắt tiếng clip, `reel.mp4` + `final.mp4` (lặp `-stream_loop`, nhạc nếu có, một lần encode);
   node 🎞 phát cả hai.

## Quyết định
- Không viết truyện → biên kịch chỉ viết tờ bối cảnh (một lượt ngắn, vì bối cảnh phải theo lời ý tưởng của người
  dùng, bảng buổi diễn chỉ là điểm xuất phát); không vòng sửa truyện. Ít lượt AI hơn (A6).
- Không nhân vật chính → không character sheet; người tiền cảnh vô danh, mỗi shot người khác.
- Một vòng 1–2 phút lặp lại thay vì hàng trăm clip: ~120–225 credit/video.
- Danh sách buổi diễn ở MỘT chỗ: `agent/director/venues.py` (tên + lời giải thích tiếng Việt, G2), canvas đọc qua `GET /venues`.

## Còn mở
- ✅ Đám đông làm phông nền: được (cận khán giả); ảnh bối cảnh phải **có khán giả** — ảnh ghế trống làm shot toàn cảnh
  trống (thử 24/10, lint `amb_venue_crowd`).
- ✅ Video thử "Worship Arena Night" (run c2d82b5b) xong 24/10: `phim/dem_nhac_tho_phuong_trong_san_van_dong_l_5524d38e/`
  `reel.mp4` (2 phút) + `final.mp4` (30 phút). Việc còn lại sau khi người dùng xem: xem 07 dòng 24/10.

## Đã làm (24/10, bước 2)
- Backend: `film_mode = "ambient"` + `venue` / `reel_s` / `loop_s` (API kiểm hợp lệ, `GET /venues` từ `venues.py`);
  STORY chỉ viết tờ bối cảnh (`AMBIENT_STORY`, `lint_story_ambient`); `lint/ambient.py` cho shot list và prompt;
  `Shot.kind`; các vai writer/director/dp/editor/reshoot/qc/reviewer đọc sổ tay 11; prompt ghép `style_block` +
  `avoid_block` như liền mạch; viết lại prompt một clip theo luật ambient; tên tiếng Việt cho 20 luật mới (📋 Nhật ký).
  Cổng SCRIPT của phim ambient chưa cho duyệt (bước 3 chưa làm) — báo rõ, không tốn credit.
- Ý tưởng mới mặc định `continuous` (người dùng: "Liền mạch là mặc định", 24/10); phim cũ không ghi chế độ vẫn là `cut`.
- Canvas: chế độ "🎵 Không khí buổi diễn", chọn loại buổi diễn (lời giải thích lấy từ backend) + độ dài vòng 1 / 1,5 / 2
  phút kèm số clip và credit; mỗi chế độ có "ℹ️ Chế độ này làm gì?" (hợp với / cách làm / chi phí, lời dặn G2); ambient ẩn
  giọng nói, mức sáng tạo, thời lượng; node kịch bản ambient báo vì sao chưa có nút tạo.
- Còn mở: ước tính "~N lần gọi AI" ở khối Agent vẫn tính như phim có truyện.
