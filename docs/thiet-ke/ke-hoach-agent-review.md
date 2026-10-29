# Agent Review — đánh giá cả phim ngay trên canvas (21/10)

Người dùng: "thay vì tôi bắt bạn review ở trong claude chat". Chốt: chạy khi BẤM NÚT (không tự chạy), bản đầu đủ 4 tầng.

## Cách làm
- Vai `reviewer` (opus, high), `agent/director/film_review.py`, `knowledge/roles/reviewer.md`.
- Đầu vào: ý tưởng, brief, story, mỗi clip một ảnh cắt khung (1 khung/giây, 5 khung/hàng), mỗi chỗ nối một ảnh
  (khung cuối clip N | khung đầu clip N+1, theo cửa sổ cắt thật), ảnh asset, prompt, cửa sổ cắt, chuyển cảnh, góp ý người dùng.
- 4 tầng có điểm 0–10: kịch bản · từng clip · nối cảnh · dựng. Mỗi phát hiện: bằng chứng, gốc lỗi
  (prompt/asset/blocking/script/edit/model_limit/policy), đề xuất, hành động (rewrite_prompt, regen_video, add_asset,
  revise_script, edit_cut, add_lesson), quy tắc tiếng Anh nếu lỗi sẽ lặp.
- Lưu: `du-lieu/film_review/<run>.json` (10 bản gần nhất) — không ghi vào plan để bản dựng lại không xoá mất.
- API: `POST /api/director/runs/{rid}/film-review {note}` (chạy nền) · `GET …/film-review` → {job, reviews}.
- Chi phí: chỉ lượt Claude, không credit Flow.

## Các bước (người dùng duyệt từng bước)
1. ✅ Lõi backend + chạy thật trên "Daniel — Cảnh 1" (21/10): 10 phát hiện, tôi kiểm lại F1 (SH11 nghiêng bình rót
   vào cốc xanh) và F3 (cửa sổ cắt luôn lấy ~5s đầu clip → mất hành động chính) — đều đúng.
2. ✅ (21/10, commit cb81744) Node "🔍 Đánh giá phim" trên canvas, bên phải 🎞: nút + ô góp ý, điểm 4 tầng, dải thời gian có dấu lỗi, danh sách phát hiện.
3. Nút thực hiện cho từng đề xuất (viết lại prompt → xem trước/áp dụng; tạo asset; tạo lại video; sửa beat; cắt lại).
   Kèm sửa F3 (c2c3474): cửa sổ cắt bám hành động / kết ở điểm trả (payoff), không còn lấy ~5s đầu.
4. Bài học → sổ tay/lint; so điểm giữa các bản phim.
