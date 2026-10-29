# Kế hoạch: chế độ phim "keyframe" (22/10)

Lời người dùng: "nên là chọn chế độ. Chúng ta có nhiều chế độ, và với mẫu mới này thì bổ sung thêm 1 chế độ chia theo
keyframe … hệ thống chúng ta chỉ nâng cấp tối ưu update, bổ sung các chế độ vào để đa dạng hơn. Đồng ý bước 2-3-4."
Mẫu: quảng cáo Artlist "New Kling 4.0" (phân tích: knowledge/playbook/samples/kling-artlist/phan-tich.md).

Ba chế độ, người dùng chọn trên node ý tưởng: `cut` (cắt cảnh, mặc định cũ) · `continuous` (liền mạch, 09) ·
`keyframe` (mới, 10). Không bỏ chế độ nào.

## Các bước
1. ✅ Kiến thức: phân tích mẫu, sổ tay 10, lời dặn B13.
2. ✅ Kịch bản: Shot thêm `keyframe` (ảnh khung mở), `join_in` (cách nối từ shot trước), `use_s` (đoạn dùng 1–5s);
   lint chế độ keyframe; vai director/dp đọc sổ tay 10.
3. ✅ Tạo: bước KEYFRAMES (ảnh khung mở mỗi shot, từ ảnh nhân vật/bối cảnh) + cổng duyệt; video i2v khung đầu =
   ảnh shot i, khung cuối = ảnh shot i+1 khi shot i+1 nối (`join_in` ≠ cut) → Omni first+last; chọn chế độ trên canvas.
4. ✅ Dựng: cắt mỗi shot theo `use_s`; trong chuỗi nối không thêm hiệu ứng.
5. (chờ duyệt, tốn credit) Thử phim ~30s, 8–10 shot; Agent Review so với mẫu.

## Quyết định
- Một ảnh keyframe cho mỗi shot (khung mở). Khung cuối của shot i = khung mở của shot i+1 (cùng ảnh) → chỗ nối khớp
  từ lúc tạo. Shot cuối hoặc shot trước một cú cắt cứng: chỉ khung đầu (Omni frame → video).
- Ảnh keyframe = ảnh cảnh (GENERATE_IMAGE) có ảnh tham chiếu nhân vật/bối cảnh → giữ đồng nhất; người dùng duyệt ảnh
  trước khi tốn credit video (rủi ro 15/10 "ảnh khung đầu → nhân vật lệch" được chặn bằng ảnh tham chiếu + cổng duyệt).

## Đã làm (22/10)
- Bước 2: `Shot.keyframe/join_in/use_s`; lint `kf_*` (lint.py `_lint_kf_shot`, `_lint_kf_chain`, `_lint_prompts_kf`);
  director/dp có mục keyframe; các vai nhận sổ tay 10 (`brain.keyframe_playbook`).
- Bước 3: chặng `KEYFRAMES` (bỏ qua ở chế độ khác) tạo ảnh `GENERATE_IMAGE` mỗi shot (ngân sách `images`, cấp cùng
  video ở cổng ASSETS) → cổng `KEYFRAMES` (thiếu ảnh thì không duyệt được) → `VIDEOS`: `_pin_keyframes` đặt
  `end_scene` = ảnh shot sau khi nối, `GENERATE_VIDEO` (Omni first+last / first frame). Ingest ghi
  `image_prompt = keyframe + style_block`, project `video_mode=image` (nút Gen lại ảnh trên cảnh).
  Canvas: ô "Chế độ phim" ở hộp thoại ý tưởng mới và node 💡; cổng duyệt keyframe trên node kịch bản.
- Bước 4: `cut.keyframe_trims` (giữ `use_s` sát hai keyframe ghim), `keyframe_edit` (không thêm hiệu ứng ở chỗ nối).
- Còn mở: ước tính "≈ N clip · credit" trong hộp thoại vẫn tính theo chế độ cắt cảnh; QC chế độ keyframe chỉ báo.
