# Kế hoạch: phim liền mạch theo mẫu "SIU Phẩm Giáng Sinh 1" (21/10)

Nguồn: video người dùng tự làm (`~/Downloads/SIU Phẩm Giáng Sinh 1.mp4`, xem 0:00–2:05) và 26 prompt gốc trong project Flow
b4962c1f (đã lưu: `backend/agent/director/knowledge/playbook/samples/siu-giang-sinh/prompts.md`).

## Video làm gì (đo được)
- 125s chỉ có ~4 cú cắt cứng (scdet). Cả đoạn là **một chuyến đi liên tục của máy quay**: phố → Clara → cửa sổ → ký ức
  (cây thông → chị gái → món quà → mẹ → bố mẹ → bàn tiệc → cả nhà) → về lại cửa sổ → Clara bước đi, máy cẩu lên phố.
- Clip 8–10s **dùng gần trọn**, không cắt còn 3–7s.
- Chuyển cảnh nằm **trong clip, ở giữa clip (giây 3–5)**, do chính máy quay tạo ra:
  - che tiền cảnh: áo khoác người qua đường lướt sát ống kính (5.75s), khung cửa/tường tối (61s, 75s, 81s, 90s), mâm/nến;
  - loá sáng: phản chiếu đèn cây thông trên kính phóng to thành trắng vàng → vào ký ức (37–38s); ngọn nến/bokeh → về hiện tại (104s);
  - chuyển động có động cơ: tiếng mẹ gọi, tiếng bố gọi, ánh mắt chị gái nhìn xuống → máy đi theo sang người kế.
- Mỗi clip **chuyền "gậy tiếp sức"** sự chú ý: Clara → chị → mẹ → bố → bàn tiệc → cả nhà.

## Prompt làm gì (26 prompt, 550–1.050 từ)
1. Mở đầu: "Use the exact ending frame of the previous shot as the starting point" + danh sách **giữ nguyên** (cùng người,
   áo, tóc, mặt dây chuyền, cầu thang, giấy dán tường, ánh sáng…).
2. r2v (`abra_r2v_8s/10s`) với **ảnh khung cuối của clip trước làm ảnh tham chiếu #1** (+ ảnh nhân vật).
3. Dòng thời gian `SECOND a TO b` 5–7 nhịp; chuyển cảnh đặt ở giữa, ghi rõ "không để tới giây cuối".
4. **FINAL FRAME CONTRACT**: mô tả chính xác khung cuối, vì nó là khung mở của clip sau.
5. Khối cố định lặp lại mỗi prompt: Camera language (một dòng mũi tên), Performance, Sound/lời thoại trong ngoặc kép,
   Visual style (bảng màu chung), Avoid (teleport, xuất hiện từ hư không, đổi trang phục, sepia, ghosting, text…).
6. Sửa theo lỗi thấy được: thêm "father must enter through the exact doorway" sau khi bố hiện ra từ hư không; mỗi clip ~2 lần tạo.

## Khác với hệ thống hiện tại
| Hệ thống đang làm | Mẫu của anh |
|---|---|
| Các shot viết độc lập, tạo song song, ghép bằng ffmpeg | Chuỗi tuần tự: clip sau mở từ khung cuối clip trước |
| Prompt ≤ 1.000 ký tự, ≤ 2 hành động, ≤ 1 chuyển cảnh sau ≥ 2s mở ổn định | 550–1.050 từ, 5–7 nhịp có giây, chuyển cảnh = chuyển động máy |
| Cắt mỗi clip còn 3–7s, chuyển cảnh ở khâu dựng | Dùng gần trọn clip, chuyển cảnh nằm sẵn trong clip |
| "Bridge" giữa hai cú cắt | Gậy tiếp sức + hợp đồng khung cuối |

## Các bước (anh duyệt từng bước)
1. ✅ (21/10) **Kiến thức**: playbook mới `09-phim-lien-mach.md` (cách làm ở trên, kèm mẫu), sửa 00/01/03/04/06 để không còn mâu
   thuẫn (luật cũ chỉ áp cho chế độ "cắt cảnh"); bài học vào 07.
2. ✅ (21/10) **Kịch bản (writer + director)**: kịch bản = các *chuỗi* (sequence); mỗi shot có `opens_from` (khung cuối shot trước),
   `beats` theo giây, `handoff` (động cơ chuyển: giọng nói / ánh mắt / ánh sáng / che tiền cảnh / đi theo người),
   `transition_at` (3–5s), `final_frame` (hợp đồng), lời thoại. Lint mới: chuyển cảnh không ở 1.5s cuối, mỗi người mới
   phải có lối vào nhìn thấy được, nhảy thời gian phải qua ánh sáng/vật xuất hiện ở cả hai phía.
3. ✅ (21/10) **Prompt (dp)**: mẫu prompt mới đúng 7 khối như trên; nâng giới hạn độ dài; khối style và Avoid sinh một lần cho cả phim
   rồi chép nguyên văn vào mọi prompt.
4. ✅ (21/10) **Pipeline tạo video theo chuỗi**: clip N xong → QC kiểm hợp đồng khung cuối → cắt khung cuối → tải lên làm ảnh tham
   chiếu → tạo clip N+1. Các chuỗi khác nhau vẫn chạy song song. Tuỳ chọn 2 bản/clip (tốn gấp đôi credit, anh quyết).
5. ✅ (21/10, phần dựng; đo mối nối trong Agent Review để sau) **Dựng**: nối gần trọn clip, chỉ bỏ vài khung lặp ở đầu clip sau và phần chết ở cuối; đen giữa các chuỗi; Agent Review
   thêm phép đo mối nối (độ giống khung cuối ↔ khung đầu).
6. **Thử thật** một phim ngắn 4–5 clip (cần anh duyệt credit).

## Rủi ro
- Tuần tự nên chậm: ~15 clip × (2–5 phút + QC) ≈ 1–1.5 giờ cho 2 phút phim.
- Một clip hỏng chặn các clip sau trong chuỗi → QC phải dừng chuỗi và hỏi.
- Bài học cũ "prompt dài sinh thêm cốc / tripod": prompt dài của anh chạy được nhờ có khung trước làm ảnh #1 và khối giữ
  nguyên; vẫn giữ lint tripod/đồ vật số nhiều.
- Tôi không nghe được âm thanh; cần anh cho biết nhạc nền / lời thoại Veo được xử lý thế nào.

## Quyết định của người dùng (21/10)
- Liền mạch là **mặc định** cho mọi phim; cắt-ghép cũ chỉ khi người dùng chọn.
- **1 bản/clip**, QC kiểm khung kết, hỏng mới tạo lại.

## Ghi chú triển khai (21/10)
- Bước 4: `director/chain.py` — khung cuối đặt vào `<hướng>_end_scene_media_id` của cảnh sau (r2v đã đưa ô này lên ảnh tham chiếu #1).
- QC ở chế độ liền mạch chỉ báo lỗi, không tự tạo lại (bản mới của một clip giữa chuỗi sẽ lệch với clip sau).
- Mặc định vẫn `cut` cho tới khi chạy thử thật (bước 6) đạt.
