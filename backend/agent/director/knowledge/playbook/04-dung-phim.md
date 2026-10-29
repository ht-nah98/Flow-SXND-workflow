# Bước 5a — Dựng phim

> **Chế độ:** người dùng chọn trên 💡 (B13): `cut` (cắt cảnh — các luật của file này) · `continuous` ([09](09-phim-lien-mach.md)) · `keyframe` ([10](10-phim-keyframe.md)) · `ambient` ([11](11-phim-khong-khi.md)).
> Ý tưởng mới mặc định `continuous` (B12, nhắc lại 24/10); phim cũ không ghi chế độ là `cut`. Ở chế độ khác, sổ tay của chế độ đó thắng file này chỗ nào khác nhau; phần ghi "cả hai chế độ" áp cho mọi chế độ có kể chuyện.

## Nhịp cắt (đo từ mẫu FMV, 53s)
Độ dài các shot trong mẫu: 5.1 · 5.0 · 6.1 · 6.0 · 2.9 · 2.6 · 6.5 · [chuỗi chớp 6 × ~0.3s] · 9.5 · 8.2 giây.
- Phần lớn shot 5–6s; nhịp nhanh dần (2.6–2.9s) trước bước ngoặt.
- **Chuỗi chớp**: 6 hình cực ngắn ~0.3s liên tiếp = ký ức lóe lên / thời gian trôi.
- Hai shot cuối (cảm xúc) dài 8–10s, để lắng.
- Chọn đoạn 3–7s đẹp nhất của mỗi clip 10s; bỏ 1–2s đầu (thường đứng yên) và đoạn hỏng.

## Chuyển cảnh, hiệu ứng, màu
Đã có thư viện hiệu ứng kiểu CapCut dựng bằng ffmpeg: xem [06-hieu-ung.md](06-hieu-ung.md). Đạo diễn chọn trong
kịch bản (`film_look`, `edit_transition_out`, `edit_fx`); mặc định là cắt thẳng.

| Kỹ thuật | Trạng thái |
|---------|-----------|
| Cắt thẳng, nháy trắng, bùng sáng vàng (light leak), hòa tan, ấm/lạnh, mất màu, nhòe sáng… | ✅ `effects.py` |
| Chuỗi chớp 0.3s (montage ký ức) | 🧪 chưa làm |
| Cắt theo nhịp nhạc | 🧪 chưa làm (cần phân tích beat) |
| Nhạc nền xuyên suốt | ✅ `music_path` của ý tưởng (add_music) |

## Xuất file (bắt buộc, cả hai chế độ)
- `-pix_fmt yuv420p` (hoặc `format=yuv420p` cuối chuỗi filter), H.264 High, `-movflags +faststart`.
- ⚠️ Bộ lọc màu của ffmpeg có thể đẩy ra yuv444p → nhiều trình phát hiện **màn hình đen**. Luôn ép yuv420p ở cuối.
- ⚠️ `xfade` từng cho ra phim đen sau giây thứ 4 vì các clip khác timebase/SAR. `effects.film_cmd` chuẩn hoá mọi clip
  (`fps=24,setsar=1,settb=AVTB`) trước khi nối; phần lớn chuyển tiếp dùng fade ở mép clip + concat, chỉ vài kiểu dùng xfade.
- Kiểm tra sau khi xuất: `ffprobe` (pix_fmt=yuv420p) + trích vài khung hình xem có đen không.

## Đưa phim lên canvas
Copy phim vào `OUTPUT_DIR` của backend, PATCH video `horizontal_url` (hoặc `vertical_url`) + `duration` → canvas tự hiện node
"🎞 Phim hoàn chỉnh".
