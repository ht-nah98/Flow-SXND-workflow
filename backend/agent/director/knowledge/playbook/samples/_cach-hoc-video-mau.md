# Cách học một video mẫu mới

1. Đặt video + prompt/kịch bản gốc (nếu có) vào `samples/<ten-mau>/`.
2. Đo nhịp cắt:
   `ffmpeg -i mau.mp4 -vf "select='gt(scene,0.3)',showinfo" -an -f null - 2>&1 | grep -o 'pts_time:[0-9.]*'`
   → hiệu các mốc = độ dài từng shot.
3. Trích khung đại diện mỗi shot (`-ss <giữa shot> -frames:v 1`) và ghép thành 1 tờ ảnh để xem nhanh.
4. Ghi vào `samples/<ten-mau>.md` theo bảng như [fmv-banh-kem.md](fmv-banh-kem.md):
   asset dùng · từng shot (nội dung, cỡ cảnh, góc máy, chuyển động camera, ánh sáng, độ dài) · chuyển cảnh · màu · âm thanh · cấu trúc câu chuyện.
5. Kỹ thuật MỚI → thêm vào bảng ở `03-prompt-video.md` (góc máy) hoặc `04-dung-phim.md` (dựng), đánh dấu 🧪.
6. Sau khi làm thử ra clip/phim thật → đổi thành ✅ (hoặc ghi vào `05-xu-ly-loi.md` nếu hỏng và vì sao).
