# 11 — Chế độ "🎵 Không khí buổi diễn" (`brief.film_mode = "ambient"`, lời dặn B14)

Chỉ áp dụng khi người dùng chọn chế độ này trên node ý tưởng. Đây là dạng **không kể chuyện**: các cảnh quay của một
buổi diễn âm nhạc đang diễn ra, trong **một** bối cảnh, người xem nghe nhạc. Mẫu: [samples/heaven-sound-worship/phan-tich.md](samples/heaven-sound-worship/phan-tich.md).

**Không áp dụng** ở chế độ này: B1–B11 (tuyến truyện, thông điệp, đa bối cảnh, flashback, cầu nối, `source_map`),
character sheet (C1), khung cuối / keyframe (09, 10), lời thoại, lồng tiếng (B5, B8).
**Vẫn áp dụng**: A (từng bước, duyệt credit, Flow nhận từng lệnh), C2–C4 (ảnh bối cảnh đúng tỉ lệ, một look), D1 (r2v),
D4 (vật lý), D6 (một prompt = một video), D7 (đúng tỉ lệ), E2 (1080p, một lần encode), E5 (phim ở `phim/`), 05 (lỗi Flow).

## 1. Sản phẩm
- **Một vòng hình (reel) 1–2 phút** (`reel_s` 60–120s) gồm `reel_s / 8` shot (±2: 60s ≈ 8, 120s ≈ 15), rồi **lặp** cho tới độ dài người dùng chọn (hoặc độ dài file nhạc).
  Mẫu: vòng 124,75s lặp suốt 45 phút. — "Họ làm video có 1p-2p rồi lặp ấy mà" (24/10).
- Ra hai file: `reel.mp4` (một vòng) và `final.mp4` (đã lặp, nhạc nếu người dùng đưa).
- Tiếng của clip **tắt hết**; âm thanh là một bản nhạc ngoài (E6: người dùng tự ghép, hoặc đính kèm ở 💡).
- Credit: ~8–15 clip × 15 ≈ 120–225 credit / video, bất kể video dài bao nhiêu.

## 2. Một bối cảnh, một look
- Một nơi, một thời điểm, một buổi diễn. Không đổi nơi, không đổi giờ, không đổi thời tiết giữa các shot.
- **Một khối look** (`style_block`) viết một lần, chép vào mọi prompt: bảng màu, nguồn sáng, khói/bụi, độ sâu trường
  ảnh. Mẫu: "deep purple and magenta stage wash, cool white spotlight beams from the lighting truss, thousands of phone
  lights in the stands, light haze, shallow depth of field".
- Loại buổi diễn do người dùng chọn (nhiều loại, mỗi video một loại):

| Buổi diễn | Bối cảnh | Look gợi ý | Chi tiết riêng cho shot |
|---|---|---|---|
| Worship sân vận động | khán đài trong nhà nhiều tầng, sân khấu xa, màn LED | tím–hồng, đèn pha trắng xanh, đèn điện thoại | tay mở, tay đặt lên ngực, mắt nhắm |
| Nhà thờ / hợp xướng | gian giữa vòm cao, hàng ghế gỗ, cửa kính màu | ấm vàng nến + vệt sáng xuyên kính màu | nến, sách thánh ca, dàn đồng ca từ sau lưng |
| Quán jazz | phòng nhỏ, bàn tròn, sân khấu thấp | hổ phách, khói, đèn bàn | ly rượu, phím piano, kèn đồng loá sáng |
| Dàn nhạc giao hưởng | khán phòng gỗ, ban công | vàng ấm, sân khấu sáng, khán phòng tối | cần đàn violin, nhạc trưởng từ sau lưng |
| Acoustic ngoài trời | bãi cỏ / bờ hồ lúc hoàng hôn, dây đèn | hoàng hôn cam → xanh | đốm đèn dây, guitar, người ngồi trên chăn |
| Lễ hội rock | sân khấu lớn ngoài trời, đêm | đỏ–xanh, đèn quét, pháo giấy | tay giơ, vai người phía trước |

## 3. Bảng shot — luân phiên, không kể chuyện
Mỗi shot thuộc một **loại**; reel đi vòng qua các loại, không hai shot cùng loại liền nhau:

| Loại (`kind`) | Cỡ / góc | Tỉ lệ trong reel | Mẫu |
|---|---|---|---|
| `wide` toàn cảnh | cực rộng từ khán đài cao, hoặc từ sau đám đông nhìn lên sân khấu | ~1/3 | shot 1, 5, 7, 14 |
| `people` khán giả | trung / cận nghiêng, nét nông, nền bokeh | ~1/3–1/2 | shot 2, 8, 9, 12 |
| `detail` chi tiết | một bàn tay giơ lên, đèn điện thoại, nhạc cụ | ~1/6 | shot 13 |
| `stage` sân khấu / đèn | từ sau lưng người biểu diễn nhìn ra, giàn đèn | ~1/6 | shot 3, 11 |

- Shot 1 của reel là `wide` (người xem biết mình đang ở đâu). Shot cuối nối được về shot 1 khi lặp, nên shot cuối không
  phải `wide`.
- **Không có hành động, chỉ có trạng thái**: nhắm mắt, đung đưa nhẹ, giơ tay chậm, vỗ tay chậm, hát theo. Mỗi người tối
  đa một cử động chậm.
- **Không nhân vật chính**: mỗi shot `people` là người khác, vô danh, đời thường ("ordinary unfamous faces"). Không
  character sheet. Ở tiền cảnh rõ mặt tối đa 1–3 người; còn lại là đám đông làm phông nền.
- **Người biểu diễn không bao giờ rõ mặt**: thấy từ sau lưng, ngược sáng, hoặc rất xa trên sân khấu (05: rủi ro danh
  tiếng; mẫu cũng làm vậy).
- Không chữ đọc được (biển, màn LED chỉ là ánh sáng mờ), không logo, không người dẫn, không dấu hiệu bản tin (05).

## 4. Máy quay
- **Một chuyển động máy chậm duy nhất mỗi clip**, cả clip: trôi chậm, trượt ngang, đẩy vào chậm, lùi chậm, cẩu qua đám
  đông, hạ máy từ giàn đèn xuống. Hoặc đứng yên với nét nông. Không lia nhanh, không rung cầm tay, không đổi cỡ cảnh.
- Không tả máy quay như một vật (D8 `camera_object`).

## 5. Prompt video (tiếng Anh, 50–150 từ)
```
References: <tên ảnh bối cảnh> (+ <ảnh chi tiết nếu có>).
Location: the same <bối cảnh> as the reference, during a live <buổi diễn>.
Shot: <cỡ cảnh, góc, ai/cái gì ở tiền cảnh>.
People: <trạng thái của 1–3 người tiền cảnh, ordinary unfamous faces>; the crowd behind stays a soft background.
Camera: one slow continuous <chuyển động> for the whole clip.
Sound: no dialogue, no music.
```
DP viết `style_block` (look chung, ≥60 ký tự, bắt đầu từ `look` của buổi diễn) và `avoid_block` (chữ đọc được, logo,
mặt người biểu diễn, máy nhanh, hành động đột ngột) MỘT lần; pipeline tự nối vào cuối mọi prompt thành "Visual style"
và "Avoid" (như chế độ liền mạch). 50–150 từ là phần riêng của clip, không tính hai khối này.

## 6. Tạo
- Ảnh tham chiếu: **ảnh bối cảnh** (bắt buộc ở mọi clip) + tối đa 1–2 ảnh chi tiết (sân khấu, nhạc cụ). Không ảnh nhân vật.
- Clip r2v **8s**, dùng gần trọn (mẫu cắt mỗi 8.0s).
- Thử thật 24/10 (run c2d82b5b, worship sân vận động, ảnh bối cảnh **ghế trống** theo C3):
  - ✅ Shot `people` (cận khán giả, nền bokeh): Flow tự vẽ khán đài đầy người + đèn điện thoại phía sau → biển người
    làm phông nền **được**.
  - ❌ Shot `wide` từ khán đài cao: khung trùng góc ảnh bối cảnh → Flow **chép lại ảnh**, khán đài trống, gần như đứng yên,
    bỏ qua "thousands of people". Ảnh bối cảnh ở cỡ toàn cảnh hoạt động như ảnh khung đầu.
  - → Ở chế độ này ảnh bối cảnh phải là **buổi diễn đang diễn ra** (khán đài kín người, đèn điện thoại), không phải phông
    trống: đám đông là phông nền chứ không phải hành động, nên C3 không áp dụng. ✅ Thử lại cùng ngày: vẽ lại ảnh bối cảnh "kín khán giả" → shot `wide` ra khán đài
    kín người, đèn điện thoại, sân khấu tím, đúng prompt (lint `amb_venue_crowd`).
  - ⚠️ Dấu ✦ của Flow ở góc dưới phải ảnh asset hiện trong **mọi** clip (07, Old Walt) — người dùng chọn che khi dựng:
    `effects.unmark` (delogo) trong mọi bản dựng, mọi chế độ.

## 7. Dựng (`cut.render_reel` + `cut.loop_reel`, đã làm 24/10)
- `reel.mp4`: mọi clip **dùng nguyên 8s**, nối bằng **cắt thẳng**, không chuyển tiếp, không hiệu ứng, **tắt tiếng clip**,
  che dấu ✦ (`effects.unmark`), 1080p, **nén một lần**.
- `final.mp4`: reel lặp (`-stream_loop`, **chép luồng hình**, không nén lại) tới `loop_s` (chọn trên 💡: 10 / 30 / 60 phút,
  mặc định 30) — hoặc tới độ dài file nhạc nếu ý tưởng có nhạc, khi đó nhạc fade in 3s / fade out 4s. Không nhạc thì
  video không tiếng: người dùng ghép nhạc ngoài (E6).
- Shot cuối của reel nối về shot 1 khi lặp (vì vậy shot cuối không phải `wide`, lint `amb_loop_seam`).

## Tự kiểm trước khi giao danh sách shot
1. Một bối cảnh, một thời điểm, một khối look giống hệt nhau ở mọi prompt?
2. Reel `reel_s / 8` shot (±2), mở bằng `wide`, không hai shot cùng loại liền nhau, tỉ lệ loại gần bảng §3?
3. Mỗi clip đúng một chuyển động máy chậm; người chỉ có trạng thái, không hành động?
4. Không mặt người biểu diễn, không chữ, không logo, không người nổi tiếng?
5. Prompt tiếng Anh 50–150 từ, có ảnh bối cảnh trong References?
