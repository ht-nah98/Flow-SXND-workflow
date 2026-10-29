# Bước 4 — Prompt video & kỹ thuật camera

> **Chế độ:** người dùng chọn trên 💡 (B13): `cut` (cắt cảnh — các luật của file này) · `continuous` ([09](09-phim-lien-mach.md)) · `keyframe` ([10](10-phim-keyframe.md)) · `ambient` ([11](11-phim-khong-khi.md)).
> Ý tưởng mới mặc định `continuous` (B12, nhắc lại 24/10); phim cũ không ghi chế độ là `cut`. Ở chế độ khác, sổ tay của chế độ đó thắng file này chỗ nào khác nhau; phần ghi "cả hai chế độ" áp cho mọi chế độ có kể chuyện.

## Chế độ tạo
- **r2v (reference-to-video) cho MỌI clip**: prompt + 2–4 ảnh asset (luôn có ảnh bối cảnh). KHÔNG tạo ảnh khung đầu (i2v/keyframe) —
  ảnh khung đầu sai là video sai, lại tốn thêm credit. ✅ đã kiểm chứng (FMV remake).
- Thời lượng **10s** (Omni Flash ~15 credit/clip). Không dùng 4s: quá ngắn, không có chỗ cắt.
- Video ngang 16:9 hay dọc 9:16 phải khớp tỉ lệ ảnh bối cảnh.

## Giới hạn của Omni Flash (vượt là hỏng clip)
- ≤ **2 hành động** và ≤ **1 chuyển cảnh/chuyển động camera đặc biệt** mỗi clip.
- Chuyển động đặc biệt cần **2–3s khung ổn định trước**, rồi mới di chuyển.
- 1 ý chính / clip. Muốn kể nhiều → nhiều clip, ghép ở bước dựng.
- Tránh: chữ đọc được (biển, màn hình), đám đông, thao tác tay phức tạp, nhiều người di chuyển nhanh,
  dao/máu/thương tích (bị bộ lọc xoá — xem [05](05-xu-ly-loi.md)). Tay cầm tối đa 1 vật; đi xe thì 2 tay trên ghi đông.

## Khung prompt (tiếng Việt, theo mẫu FMV gốc — đã chạy tốt)
> Phim mặc định tiếng Anh (B4): DP dùng khuôn tiếng Anh cùng thứ tự trong `roles/dp.md` (References / … ). Khuôn dưới đây chỉ cho phim tiếng Việt.
```
Ảnh tham chiếu: <tên các asset đính kèm>
Nhân vật & trang phục: Giữ nguyên đúng như ảnh tham chiếu đính kèm (<n> nhân vật, ngoại hình và trang phục không thay đổi).
Bối cảnh: <địa điểm> như ảnh tham chiếu — <ánh sáng, không khí, chi tiết>.
Góc quay: <cỡ cảnh + vị trí máy + bố cục>
Hành động: 0-4s: <hành động 1>. 4-10s: <hành động 2, nếu có>.
Chuyển động camera: Oneshot liền mạch, <kiểu máy>, <một chuyển động chính>.
Ánh sáng & màu sắc: <nguồn sáng, tông màu, hạt bụi/mưa/lens flare>
Âm thanh: <tiếng môi trường, tiếng động thật; không thoại — hoặc nếu clip có lời: Lồng tiếng (voice-over, <giọng cố định>) nói từ giây 1.5 đến 6: "<câu thoại nguyên văn>". Nền: …>
Thời lượng: 10 giây, <nhịp>, không cắt cảnh.
```
Ghi chú: TỐI ĐA 2 mốc giây trong "Hành động" (máy kiểm, lời dặn D3). Mẫu FMV gốc viết 3 mốc nhưng chỉ có 2 hành động
thật — khi chép mẫu, gộp lại thành 2 mốc.

## Thư viện góc máy (từ mẫu FMV) — ✅ tất cả đã ra clip dùng được
| Góc | Cách viết | Dùng khi |
|-----|-----------|----------|
| Oneshot cầm tay | "camera cầm tay rung nhẹ tự nhiên (handheld shake, không giật cục)" | Mặc định cho mọi clip — tạo cảm giác quay thật, MV indie |
| Lia từ tay lên mặt | "lia chậm từ cận cảnh đôi tay … → kéo lên khuôn mặt … → xoay theo nắng tạo lens flare" | Mở đầu, giới thiệu nhân vật + hành động |
| Cận cảnh + rim light | "Cận cảnh, lấy nét vào tay và mặt, nắng chiếu chéo phía sau tạo viền sáng quanh tóc" | Khoảnh khắc thân mật, bất ngờ |
| POV từ trong vật | "Góc máy đặt từ bên trong lò nướng nhìn ra (POV from inside the oven), viền cửa lò tạo vignette" | Góc lạ, vui, phá nhịp |
| Selfie | "Góc selfie chủ quan, như quay từ điện thoại nhân vật cầm, hơi ngước, mặt ở trên, vật ở dưới" | Khoảnh khắc khoe/kỷ niệm |
| Vlog tự quay | "POV vlog-style self-recording, rung theo bước chân, hơi nhòe khi áp sát camera" | Năng lượng cao, hôn/tiến sát ống kính |
| Bám theo xe | "car-mount/dashcam-style, bám theo xe từ phía sau hoặc bên hông, cuối lia mở toàn cảnh" | Di chuyển, chuyển không gian |
| Từ trần nhìn xuống | "top-down bird's-eye view from the ceiling, thấy toàn bàn, vệt nắng có bụi" | Toàn cảnh thiết lập, đẹp để mở phim |
| Từ ngoài cửa sổ | "quay từ ngoài cửa sổ nhìn vào, khung cửa và lá ở tiền cảnh lệch nét, nhân vật mờ sau kính" | Cảm giác lén nhìn / ký ức |
| Sát sàn nhìn lên | "camera đặt ngay trên sàn hướng lên (low angle), nhân vật nhỏ bé trơ trọi" | Cô đơn, buồn, cao trào cuối |
| Toàn cảnh cực rộng, NV tí hon | "extreme wide, thế giới khổng lồ (núi rác/thành phố), nhân vật chỉ là chấm nhỏ ở 1/3 dưới khung, ngược sáng có bụi; máy đứng yên" | Mở phim, thân phận nhỏ bé (mẫu BOTTOMLESS) 🧪 |
| Từ vật mở ra toàn cảnh | "0–3s: cận sát đất một đồ vật (bánh xe gỉ) giữ yên; 3–9s: máy nâng lên và lùi chậm, lộ dần nhân vật đang dùng vật đó" | Giới thiệu nhân vật qua đồ vật 🧪 |
| Cận sát đất bị chà đạp | "máy đặt sát mặt đất ẩm, mặt nhân vật áp xuống bùn ở tiền cảnh, chân kẻ khác giẫm lên đồ vật, nét nông" | Hạ nhục, mất mát 🧪 |
| Dưới lên trước trăng | "worm's-eye, nhân vật thành bóng đen trước vầng trăng tròn khổng lồ, giơ tay lên" | Đỉnh quyền lực, phép màu 🧪 |
| Cận cực sát mắt | "extreme close-up đôi mắt, ánh vàng phản chiếu trong con ngươi, máy đẩy vào rất chậm" | Lòng tham, biến đổi bên trong 🧪 |
| Cận vật + nến | "cận cảnh nghiêng thấp ngang tầm bánh, nét sắc ở tiền cảnh, hậu cảnh mờ ấm; lia chậm dọc cạnh bánh" | Cảnh chèn, motif |

## Ánh sáng & màu (viết trong prompt)
- Ấm: "warm golden hour, nắng xuyên cửa sổ, bụi mịn lấp lánh, tương phản mềm, như MV indie/lofi" (+ "không ngả vàng, giữ màu thật" nếu sợ vàng quá).
- Ngoài trời: "nắng xanh mát xuyên tán lá, trong trẻo, chút lens flare".
- Buồn: "tối, lạnh, xanh xám đêm mưa, chớp trắng lóe đột ngột, mưa lờ mờ qua cửa sổ".
