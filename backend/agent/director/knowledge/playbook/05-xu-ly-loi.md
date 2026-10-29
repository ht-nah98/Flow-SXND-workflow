# Bước 5b — Xử lý lỗi kỹ thuật

| Triệu chứng | Nguyên nhân | Cách xử lý |
|------------|-------------|-----------|
| Clip tạo xong rồi biến mất, poll trả `failed: [5]` / NOT_FOUND | Bộ lọc nội dung của Flow xoá clip sau khi tạo | Backend tự đánh dấu `MEDIA_REMOVED` sau 2 lần NOT_FOUND và **gửi lại 1 lần như job mới**. Nếu vẫn bị xoá → viết lại prompt. |
| Bị xoá nhiều lần cùng một cảnh | Nội dung nhạy cảm: dao, vết cắt, máu, thương tích, bạo lực | Đổi hành động sang thứ an toàn tương đương (clip 8: "đứt tay bằng dao" → "giả vờ bỏng khi chạm khuôn bánh ấm"). |
| Request treo mãi ở trạng thái chờ | Retry giữ `request_id` cũ → poll mãi một op đã chết | Đã sửa: retry media_removed tạo request mới (`request_id=None`). Nếu gặp lại: huỷ/đánh FAILED request rồi tạo lại. |
| Canvas báo lỗi cũ trong khi đang chạy lại | Hiển thị lỗi của request cũ | Đã sửa: lỗi lấy theo request mới nhất. |
| Phim xuất ra màn hình đen | yuv444p / xfade | Xem [04](04-dung-phim.md). |
| Nhân vật đổi mặt/trang phục giữa các clip | Thiếu sheet, hoặc tạo ảnh khung đầu riêng từng clip | Dùng đúng character sheet cho mọi clip, r2v, "giữ nguyên đúng như ảnh tham chiếu". |
| Mỗi clip như một nơi khác | Không có ảnh bối cảnh chung | 1 ảnh bối cảnh / địa điểm, đưa vào mọi clip ở đó. |
| Clip lộn xộn, hành động méo | Quá 2 hành động hoặc quá 1 chuyển động camera | Tách thành 2 clip. |
| `NO_MEDIA_CREATED` lặp lại với cùng nhân vật | Flow chặn chính sách. 20–21/10 cảnh 4: **bé gái (ảnh giống người thật) một mình trong khung** bị chặn 3 lần — cả khi prompt đã viết lại ngang tầm mắt, máy tĩnh, đi bộ; các clip có Emma cùng người lớn (Daniel) đều qua | Không gửi lại nguyên prompt, cũng đừng chỉ sửa câu chữ: **trẻ em luôn có người lớn cùng khung** (thêm nhân vật người lớn vào References). Đạo diễn: không chia shot trẻ em một mình. |
| `NO_MEDIA_CREATED` với cảnh **giống bản tin truyền hình thật** (người giống thật ngồi bàn dẫn, chữ ON AIR / LIVE / băng chữ tin, TV đang phát một người) | Flow chặn: "có thể gây rủi ro về danh tiếng hoặc xuyên tạc các sự kiện hiện tại" (chỉ thấy trên thẻ Flow; phía mình chỉ nhận "Media not found"). 22/10 Leo Marsh: 4 cảnh × 3 lần. Không liên quan ảnh do AI tạo, cỡ mặt hay dao cạo | Bỏ dấu hiệu bản tin: phòng thu trắng trơn, màn hình chỉ có hình hoạt hình, không chữ, không biển, không TV chiếu người. Bỏ ảnh tham chiếu bối cảnh nếu chính nó có biển ON AIR. Lint `news_look`. |
| `NO_MEDIA_CREATED` chỉ ở các cảnh **thấy rõ mặt một nhân vật**; cảnh mặt nhỏ, quay lưng hay chỉ có tay thì qua | Ảnh nhân vật **giống người nổi tiếng** (23/10: Elijah giống Morgan Freeman), Flow chặn vì rủi ro danh tiếng | Làm bảng so sánh keyframe cảnh qua và cảnh lỗi. Vẽ lại nhân vật với nét riêng dễ nhận (kiểu đầu, râu, kính, sẹo) và ghi "ordinary unfamous face, not resembling any real person", rồi vẽ lại keyframe có mặt người đó. Đừng gửi lại cùng ảnh |
| `NO_MEDIA_CREATED` ở **mọi** video của một phim, kể cả cảnh không có người; ảnh vẫn tạo được | Project Flow không có trong tài khoản của phim (mở link báo "Không tìm thấy dự án") | `POST /api/flow/projects/{id}/move-account` với `{"account": <tài khoản của phim>, "repair": true}`. Thử 1 video rồi mới chạy tiếp |
| `CAPTCHA_FAILED: Invalid site key or not loaded in api.js` | Tab flow.google.com chưa tải reCAPTCHA (tab cũ / ngủ / lỗi mạng). Gửi lại bao nhiêu cũng hỏng | Từ 16/10: hệ thống **tự tải lại tab Flow một lần**, chờ 30s rồi thử lại. Vẫn lỗi → dừng cả hàng chờ, người dùng tải lại tab (F5), kiểm tra còn đăng nhập, bấm Tiếp tục. Không gửi lặp — Google coi là bot. |
| `FlowBatchError: operation payload carried no record` (Flow từ chối trong 2–4s, worker thử 5 lần đều hỏng) | Chưa rõ; 29/10 xơ dừa TikTok: 3 request trên tài khoản Olya ngay sau khi chuyển tài khoản, cùng prompt đã chạy được lúc khác → không phải nội dung, không phải hết credit (credit không bị trừ) | Tạo **request mới** cho cảnh đó (`POST /api/requests`), không sửa prompt; cả 2 cảnh qua ngay lần đầu. Rồi `shot-failure {"action":"retry"}` để dựng |
| Cần bỏ hẳn một run | — | Nút **🛑 Huỷ toàn bộ run** (node 💡 khi đang viết, node 📜 sau đó): dừng tác vụ + Claude đang chạy, bỏ lệnh chưa gửi Flow; clip Flow đang tạo vẫn hoàn tất. Không chạy tiếp được. |
| Bấm Dừng mà Flow vẫn nhận lượt gửi | (cũ) Dừng chỉ dừng đạo diễn, không huỷ hàng chờ | Đã sửa 16/10: Dừng huỷ mọi request chưa gửi; clip đang tạo vẫn giữ; Tiếp tục tạo lại phần thiếu. |
| Extension mất kết nối | Chrome profile Olya chưa mở/extension ngủ | Kiểm `/health` → `extension_connected: true` trước khi gửi batch. |

## Credit
- Omni Flash 10s ≈ 15 credit/clip. Clip bị xoá + gửi lại vẫn có thể tốn credit (chưa xác minh Flow có hoàn lại không).
- Dự toán = số clip × 15 × ~1.2 (dự phòng gửi lại).

## Biến đổi phi vật lý (mẫu BOTTOMLESS làm thử, 2026-10-16)
Triệu chứng: vật tự hiện ra (vàng trong lưới), lơ lửng (đồng xu quanh mặt), hạt rơi vô lý (lông chim như tuyết),
nhà sập không có lực tác động. Nguyên nhân: prompt tả kết quả "phép màu" thay vì hành động vật lý, và nhồi nhiều sự
kiện vào một clip. Sửa: viết dòng Physics — lực, tiếp xúc, trọng lượng, nước chảy, số lượng cố định; phép màu
= ánh sáng + lộ ra (kéo lưới nặng lên, nước rút, lộ vàng), không biến hình; thảm hoạ đi qua từng vật một.
