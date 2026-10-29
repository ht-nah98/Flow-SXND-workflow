# Mẫu quy trình: SciCloud AGI (Trung Quốc) — demo "《三分心动》3 phút phim ngắn học đường" (19/10)

Không phải một phim mà là demo QUY TRÌNH (2:25) của một app canvas giống Flow Canvas. Nguồn: video người dùng gửi
(`~/Downloads/Video ComfyUI của Trung quốc.mp4`) + thư viện skill gonghaosnail.com. Học cách họ tổ chức, không chép.

## App có 5 tab: Ảnh · Video · Canvas · Dựng trước (预演) · Dựng (剪辑)
1. **Ô chữ trên canvas + thanh hỏi AI** ở đáy: "@ tham chiếu node đang chọn", Enter gửi; đổi agent/model tuỳ ý
   (Kimi K3, Claude Opus…). Mỗi ô chữ có nút: *Tối ưu prompt ảnh · Tối ưu prompt video · Dịch*.
2. **Ý tưởng 212 chữ** ("phim ngắn ~3 phút, tôi gặp 3 đàn chị ở trường, tôi là cầu thủ bóng rổ 182cm; bạn là đạo
   diễn, biên kịch, bậc thầy máy quay, bậc thầy cảm xúc; viết kịch bản + phân cảnh theo skill chính thức").
3. **Gói giao (交付包) = 3 file .md thành 3 ô chữ trên canvas, sửa trực tiếp:**
   - `README.md` — danh sách file; **Ý đồ sáng tạo (lời đạo diễn)**: (1) chống sáo rỗng — "3 đàn chị" không viết
     thành chọn 1 trong 3 mà thành 3 KIỂU thích (tấn công / đứng ngoài / âm thầm); (2) tuyến trưởng thành của nam
     chính; (3) câu chủ đề làm tựa; (4) **7 câu "kim cú" cảm xúc rải đều 180s, cứ 25–30s một câu** (giữ người xem
     nền tảng video ngắn, cắt riêng làm poster). Cách tạo bằng Seedance: giữ nhân vật (tạo ảnh chuẩn trước, chế độ
     ảnh tham chiếu), **tạo theo 4 khúc thời gian** (0–30/30–60/60–120/120–180s), đầu mỗi khúc có sẵn mô tả neo
     nhân vật; thoại & lồng tiếng; gợi ý nhạc theo mốc (0–60s guitar nhẹ → 60–120 dây → 120–148 cao trào → kết
     piano); **điểm sửa tự do** (tên, số áo, cái kết…); **trạng thái kiểm chứng** (đã viết theo skill, chưa render).
   - `Kịch bản.md` — loại/độ dài/bối cảnh/tông/logline; **nhân vật**: tuổi, ngoại hình, tính cách, động tác đặc
     trưng, và "cô ấy thích theo kiểu…"; thân kịch bản chia **màn có mốc giờ** (Màn 1: 0:00–1:00), cảnh, thoại,
     độc thoại nội tâm (V.O.).
   - `Phân cảnh + prompt Seedance.md` — 18 shot gom theo 4 khúc thời gian; mỗi shot: **Hình · Cỡ cảnh/máy ·
     Thoại · Prompt** (prompt viết liền, có mốc giây của shot, ví dụ "Shot 8 (60–70s)").
4. **Nhân vật**: ô "nhà thiết kế nhân vật" + ảnh tham chiếu (@ảnh 1) → **sheet chuẩn 4 góc**: chính diện, nghiêng,
   sau lưng + cận mặt, nền xám trung tính. Người dùng có thể đưa ảnh mình làm nam chính.
5. **Dựng trước 3D (预演台)**: AI dựng cảnh từ một câu ("nhà thi đấu đại học, nữ cổ vũ tóc đuôi ngựa đáp xuống trước
   nam sinh áo trắng số 7…") → 37 vật thể, người gỗ, đặt máy quay, vẽ đường máy bằng keyframe, xuất bản xem trước.
6. **Dựng**: timeline nhiều track, kéo clip từ canvas, cắt, chuyển cảnh vào/ra, âm lượng, xuất MP4.
7. Ô nhạc (MiniMax music: lời / không lời).

## Thư viện skill (gonghaosnail.com)
93 "gói phong cách" ảnh (chân dung, võ hiệp, cảm xúc, kiến trúc…). Mỗi gói = ảnh mẫu gốc + **phân tích thị giác +
quy tắc lõi (không đổi) + biến số (được đổi: nhân vật, trang phục, tư thế, đạo cụ, bối cảnh, khung, phía ánh sáng)
+ khuôn prompt + hướng dẫn sửa lệch**. Ví dụ "Thanh xuân · ánh sáng tự nhiên điện ảnh" cho phim học đường.

## Áp dụng cho mình (đề xuất, chưa làm — xem trả lời 19/10)
| Điều học được | Mình đang có | Áp dụng |
|---------------|--------------|---------|
| Kim cú mỗi 25–30s, màn có mốc giờ | spine, beats | biên kịch thêm `time_blocks` + khoảnh khắc giữ chân |
| Ý đồ sáng tạo (lời đạo diễn) | — | `director_notes`: chống sáo rỗng, vì sao chọn cấu trúc này |
| Nhân vật có "kiểu" riêng tương phản | mô tả ngoại hình | thêm tính cách, động tác đặc trưng, cách thể hiện cảm xúc |
| Gói giao .md đọc/sửa được | JSON + bảng đọc | xuất README + Kịch bản + Phân cảnh ra thư mục phim |
| Sheet 4 góc | 3 góc | thêm góc nghiêng |
| Hỏi AI @node + tối ưu prompt | "Viết lại clip", góp ý | thanh hỏi AI chung trên canvas |
| Gói phong cách (lõi/biến số/sửa lệch) | `material` + `film_look` | thư viện look cho prompt |
| Timeline dựng tay | dựng tự động + hiệu ứng | (sau) chỉnh cắt từng clip bằng tay |
| Dựng trước 3D | — | không: Omni Flash không nhận đường máy/ảnh blocking (trái C3/D1) |
