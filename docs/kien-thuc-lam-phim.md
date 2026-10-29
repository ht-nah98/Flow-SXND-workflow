# Kiến thức làm phim (đúc kết)

Những gì đã học được khi làm phim bằng Google Flow Omni Flash. Phần chi tiết Claude dùng khi làm việc nằm
trong [sổ tay](../backend/agent/director/knowledge/playbook/) (đọc trước [lời dặn của người dùng](../backend/agent/director/knowledge/playbook/00-loi-dan-nguoi-dung.md)) và [quy tắc](../backend/agent/director/knowledge/rules.md);
trang này là bản tóm tắt cho người.

> Cập nhật 24/10: mục 1–3 là chế độ **cắt cảnh** (`cut`). Các chế độ khác: liền mạch (sổ tay 09), keyframe (10),
> không kể chuyện / buổi diễn (11). Chọn trên node 💡.

## 1. Cách làm đúng: kiểu FMV

Học từ video mẫu *FMV bánh kem* (xem `playbook/samples/fmv-banh-kem.md`):

- **Mọi clip đều là r2v** (tạo video từ ảnh tham chiếu). Không tạo ảnh khung đầu trước — ảnh sai thì video sai.
- **Ảnh tham chiếu quyết định sự nhất quán:**
  - Nhân vật = **một character sheet**: cận mặt + toàn thân trước + nghiêng + sau, nền trắng.
  - Bối cảnh = một ảnh thật của nơi quay, đúng khổ phim (16:9 hoặc 9:16).
  - Đạo cụ / sản phẩm = ảnh sản phẩm sạch (ảnh thật của bạn thì dùng luôn).
  - Cùng bộ ảnh này đưa vào gần như mọi clip → cùng người, cùng phòng.
- **Clip 10 giây, mỗi clip một ý.** Khi dựng chỉ giữ ~5 giây đẹp nhất của mỗi clip; câu chuyện được kể
  bằng cách cắt ghép.
- **Trong mỗi đoạn, quay một nơi từ nhiều góc** (toàn cảnh, cận, từ trên trần, từ trong lò, ngoài cửa sổ, sát sàn,
  selfie) → đoạn đó liền mạch. Cả phim vẫn đi qua nhiều nơi, nhiều thời như truyện cần (lời dặn B3b).
- Số clip ≈ thời lượng phim / 5.5 (30s → 5–6 clip, 60s → 11).

## 2. Giới hạn của Omni Flash (vượt là hỏng)

- **Tối đa 2 hành động và 1 chuyển cảnh trong một clip.** "Quay lại, cười và bước đi" là 3 hành động.
- Chuyển cảnh cần **2–3 giây khung hình đứng yên trước**, sau đó mới chuyển và còn ≥ 1.5 giây sau.
- Clip có chuyển cảnh thì không thêm chuyển động máy nào khác.
- Tránh làm ý chính bằng: thao tác tay nhỏ, chữ đọc được, đám đông, nhiều người chuyển động nhanh.
- Máy quay phải "nhìn thấy" được hành động; đặt máy dưới nước, sau vật… phải dặn ống kính khô, hình rõ.

## 3. Prompt video (đúng thứ tự)

Mặc định viết **tiếng Anh** (lời dặn B4), cùng thứ tự các dòng (References / Character / Location / Camera /
Action / …, xem `knowledge/roles/dp.md`). Khuôn tiếng Việt dưới đây chỉ dùng cho phim tiếng Việt:

```
Ảnh tham chiếu: <tên nhân vật, bối cảnh, đạo cụ>
Nhân vật & trang phục: Giữ nguyên đúng như ảnh tham chiếu … <trang phục>
Bối cảnh: <nơi> như ảnh tham chiếu — <giờ, ánh sáng, không khí>
Góc quay: <cỡ cảnh + vị trí máy + bố cục>
Hành động: 0-4s: <hành động 1>. 4-10s: <hành động 2>.
Chuyển động camera: Oneshot liền mạch, <rig>, <một chuyển động chính>.
Ánh sáng & màu sắc: <nguồn sáng, bảng màu, hạt bụi, cảm giác>
Âm thanh: <tiếng môi trường> — hoặc câu thoại (mục 4)
Thời lượng: 10 giây, <nhịp>, không cắt cảnh.
```

## 4. Giọng nói / lồng tiếng

Omni Flash tạo được tiếng nói ngay trong clip.

- Chọn trên node Ý tưởng: tự nhận diện · 🎙 lồng tiếng · 🗣 nhân vật nói · 🔇 không lời.
  Ý tưởng có chữ "lồng tiếng / giọng đọc / thuyết minh" thì luôn có giọng.
- **Mỗi clip tối đa một câu ≤ 15 chữ**, nói trong khoảng giây 1.5–6.
- **Mô tả giọng giống hệt nhau ở mọi clip** (vd. "giọng nữ trẻ miền Bắc, trong, ấm…") để nghe như một người.
- Quảng cáo: câu mở thu hút → công dụng → lời kêu gọi mua.
- Khi dựng, clip có lời **không bị cắt ngắn** (giữ trọn câu), nên phim có thể dài hơn mục tiêu vài giây.

## 5. Dựng phim & chất lượng

- Flow Omni Flash cao nhất **720p, 24 hình/giây**.
- Phim cuối: cắt + phóng lên **1080p (lanczos)** + nén **một lần duy nhất** (x264 CRF 16, preset slow),
  giữ 24 hình/giây, âm thanh AAC 192k → ~8 Mbps. Phóng lên 1080p không thêm chi tiết nhưng YouTube/TikTok
  nén video 1080p nhẹ tay hơn 720p.
- Cần tránh: nén nhiều lần, đổi 24 → 30 hình/giây (lặp khung), để mức nén mặc định (mất nửa bitrate).
- **Hiệu ứng kiểu CapCut** (quan sát trên CapCut, dựng lại bằng ffmpeg, không dùng tài sản CapCut):
  một bộ lọc màu cho cả phim, chuyển tiếp ở chỗ câu chuyện nhảy (nháy trắng, bùng sáng vàng, hòa tan…),
  hiệu ứng trong clip khi có ý nghĩa (rung khi va chạm, mất màu khi hồi tưởng, tối dần khi kết).
  Phần lớn chỗ nối vẫn là cắt thẳng. Chi tiết: `playbook/06-hieu-ung.md`. Cả phim vẫn chỉ nén một lần.

## 6. Credit và lỗi Flow

- Ước tính: ảnh asset ~1 credit/ảnh, video 10s r2v ~15 credit/clip (720p; dự toán × 1.2 dự phòng).
- Mọi bước tốn credit đều chờ duyệt; ngân sách mỗi cổng giới hạn số lượt.
- **Unusual activity:** gửi dồn nhiều lệnh một lúc khiến Google chặn tạm → luôn gửi từng lệnh, cách nhau ≥ 15s.
- **Tạo trùng:** Google có thể đã tạo video dù trả lỗi → backend dò mã client trước khi gửi lại.
- **Thiếu ảnh tham chiếu:** video r2v không được chạy khi asset chưa có ảnh (đã từng mất ~60 credit vì vậy).
- `NO_INJECTION_RESULT`, mất kết nối extension: kiểm tra tab Flow còn mở, `/health` có
  `extension_connected:true`.

## 7. Học từ video mẫu mới

Làm theo `playbook/samples/_cach-hoc-video-mau.md`: xem từng shot (cỡ cảnh, góc, chuyển động, ánh sáng,
độ dài), chuyển cảnh, màu, âm thanh, cấu trúc; ghi kỹ thuật mới vào playbook (🧪 → ✅ khi đã kiểm chứng).
