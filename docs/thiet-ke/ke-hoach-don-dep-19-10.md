# Kế hoạch dọn dẹp (19/10) — theo góp ý của người dùng

Mỗi bước làm xong → người dùng review → mới sang bước sau. Không tạo video, không tiêu credit trong toàn bộ kế hoạch.

## Góp ý đã sắp xếp (đã ghi vào playbook/00)
| # | Góp ý | Gốc lỗi tìm được | Lời dặn |
|---|-------|------------------|---------|
| 1 | Người dùng chỉ đưa ý tưởng, AI dựng kịch bản | Bản sửa trước (B6) lệch sang "chuyển thể truyện người dùng viết" | A1 ⚠️, B6 |
| 2 | Thời lượng linh hoạt | `lint_shotlist` ép tổng số shot theo `target_s`; cắt dựng ép đúng thời lượng | E1b |
| 3 | Box co dãn, xem kịch bản ngang | Node kích thước cố định, kịch bản một cột hẹp | G1 |
| 4 | Đa bối cảnh, sáng tạo; chỉnh mức sáng tạo | rules.md "Cover a main location from many angles"; 01 "nhiều góc của CÙNG một không gian"; director.md "main location"; bộ nhớ "coverage of one place" | B3b ⚠️⚠️, B9 |
| 5 | Vẫn thấy "Prompt ảnh" | Phim đạo diễn thực tế chỉ gửi `GENERATE_VIDEO_REFS` (r2v), không tạo ảnh khung đầu. Nhưng `SceneNode` hiện ý tưởng shot dưới nhãn "Prompt ảnh" → nhìn như ảnh→video | D1 ⚠️⚠️⚠️ |
| 6 | Bật/tắt agent trong luồng | Chưa có | A5 |
| 7 | Gọn tư duy, tài liệu, quy trình; bớt token | Chỉ dẫn hệ thống mỗi vai ~nhiều file chồng chéo; 5 lần gọi AI trước khi có kịch bản | A6 |

## Trạng thái (19/10): ✅ cả 7 bước — commit a43c89b, 8c6bbc6, 979b238, 20289ea, d189306, 822f79f, 7d48ef8, 9f35176

## Các bước
**Bước 1 — Dọn tư duy & tài liệu (không đụng code chạy).**
Viết lại `rules.md`, `01-kich-ban.md`, `writer.md`, `director.md`, `editor.md` cho gọn: một nguyên tắc chỉ nằm ở một
chỗ; bỏ mọi câu "một nơi chính"; thêm "đa bối cảnh, đa thời điểm, chuyển cảnh giữa các đoạn"; biên kịch PHÁT TRIỂN
ý tưởng (B6 chỉ áp khi người dùng dán sẵn truyện). Đo kích thước chỉ dẫn hệ thống mỗi vai trước/sau. Sửa bộ nhớ +
skill cho khớp.

**Bước 2 — Bỏ dấu vết ảnh→video ở phim đạo diễn.**
`SceneNode`: phim đạo diễn chỉ hiện "Ý tưởng shot" + "Prompt video" + danh sách asset tham chiếu; không có ô
"Prompt ảnh", không nút tạo ảnh khung đầu. Dự án thủ công: chế độ mặc định r2v, ảnh→video thành tuỳ chọn tắt sẵn
(hoặc bỏ hẳn — người dùng chọn). Test: node đạo diễn không render "Prompt ảnh"; pipeline chỉ tạo GENERATE_VIDEO_REFS.

**Bước 3 — Thời lượng linh hoạt.**
`target_s` thành ước lượng: lint shot chỉ chặn trường hợp quá xa (ví dụ < 0.6× hoặc > 1.6×), cắt dựng theo nhịp
truyện chứ không ép đúng giây; giao diện ghi "~2 phút". Test lint + cut.

**Bước 4 — Mức sáng tạo trên 💡.**
Ba mức: *Bám sát* (giữ đúng ý), *Cân bằng* (mặc định), *Bay bổng* (tự do thêm tuyến phụ, nơi chốn, thời gian). Lưu
trong brief, truyền tới biên kịch. Test API + node.

**Bước 5 — Box co dãn + xem kịch bản ngang.**
NodeResizer cho node ý tưởng, kịch bản, cảnh; nhớ kích thước theo node. Node kịch bản có chế độ đọc rộng (bảng shot
theo hàng ngang / mở toàn màn hình). Test tsc + vitest, xem thật trên canvas.

**Bước 6 — Bật/tắt agent trong luồng.**
Trên 💡 có danh sách vai: producer, biên kịch (bắt buộc), đạo diễn (bắt buộc), DP, editor duyệt kịch bản, QC clip,
coach rút bài học. Vai tắt thì bước đó bỏ qua (ví dụ tắt editor → không chấm điểm kịch bản; tắt producer → brief lấy
thẳng từ lựa chọn trên 💡 không gọi AI). Hiện số lần gọi AI dự kiến. Test pipeline bỏ qua đúng bước.

**Bước 7 — Gộp bớt bước AI (tiết kiệm token).** Sau khi đo ở bước 1 và 6: cân nhắc bỏ producer (thay bằng form),
gộp writer+director thành một lần gọi khi phim ngắn. Chỉ làm khi số liệu cho thấy lợi.
