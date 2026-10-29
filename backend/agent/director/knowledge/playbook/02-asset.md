# Bước 2–3 — Asset: nhân vật, đạo cụ, bối cảnh

Asset tạo MỘT lần, dùng lại cho mọi clip. Đây là thứ giữ nhân vật giống nhau giữa các clip. ✅ đã kiểm chứng (FMV remake: 11/11 clip giữ đúng mặt + trang phục).

## Nhân vật — character sheet (1 ảnh / nhân vật)
- 4 panel cạnh nhau trên nền studio trắng trơn: **cận mặt (đầu–vai), toàn thân chính diện, toàn thân nghiêng (profile), toàn thân phía sau**.
  Góc nghiêng thêm 19/10 (mẫu SciCloud): clip quay ngang/profile giữ đúng dáng, mũi, tóc.
- Cùng mặt, tóc, trang phục trong cả 4 panel; ánh sáng đều, ảnh chân thực, không chữ.
- Mô tả trang phục thật cụ thể (màu, chất liệu, phụ kiện) — mọi clip dựa vào đúng tờ này.
- Nhân vật hư cấu ("fictional"), không dùng người thật/người nổi tiếng.
- Cùng một người ở 2 độ tuổi = 2 nhân vật riêng, 2 sheet riêng.
- Tỉ lệ ảnh sheet: ngang (16:9) để 4 panel đủ rộng.

Prompt mẫu:
> Character sheet of a fictional young woman, four panels side by side on a seamless plain white studio
> background: a head-and-shoulders close-up, a full-body front view, a full-body side profile view, a full-body back view. Same face,
> hair and exact outfit in every panel: <tóc>, <áo>, <quần/váy>, <giày>, <phụ kiện>. Soft even light, photorealistic, no text.

## Bối cảnh — 1 ảnh thật / địa điểm
- Ảnh trông như chụp thật của bối cảnh TRỐNG, góc rộng, ánh sáng tự nhiên: **không nhân vật, không con vật, không
  hành động, không khoảnh khắc kịch tính, không phép màu**. Ảnh bối cảnh là phông sân khấu, không phải khung đầu
  của clip (lời dặn C3, D1 trong [00](00-loi-dan-nguoi-dung.md)).
- Có sẵn chi tiết kịch bản cần dùng (cửa sổ có nắng, bàn bếp, lò nướng, cầu thang…), **đúng cỡ và đúng chỗ** như phim dùng: Old Walt 22/10 ảnh phòng khách có bàn quá nhỏ cho cảnh mở album → Flow đổi bàn, đổi cả cây đèn.
- **Tỉ lệ = tỉ lệ video**: 16:9 cho YouTube ngang, 9:16 cho Shorts/TikTok. Không trộn.
- Bối cảnh Việt Nam phải trông Việt Nam thật (nhà, phố, đồ vật).
- Cùng địa điểm nhưng khác giờ (ngày/đêm mưa): dùng CHUNG ảnh bối cảnh, đổi ánh sáng trong prompt (mẫu FMV clip 9). ✅

## Đạo cụ quan trọng
- Ảnh sản phẩm sạch của vật (xe Cub, bánh kem…). Chỉ thêm khi đạo cụ xuất hiện ở nhiều clip hoặc là motif.

## Số ảnh tham chiếu mỗi clip
- Mẫu FMV dùng 2–3 ảnh/clip; tối đa 4: [nhân vật, bối cảnh (luôn có), đạo cụ, đạo cụ] (lint `too_many_refs`, `location_ref`).
- Chỉ đưa ảnh của thứ THỰC SỰ xuất hiện trong clip (clip 9 chỉ có anh + bếp → 2 ảnh).

## Quy mô
Theo câu chuyện: thường 2–6 nhân vật, 2–6 địa điểm, 0–3 đạo cụ (mỗi asset ~1 credit ảnh). Không cắt người hay nơi mà
truyện cần chỉ để ít asset (lời dặn B3b). Cùng nơi khác giờ thì dùng chung ảnh bối cảnh.
