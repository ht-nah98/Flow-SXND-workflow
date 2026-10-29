# Kế hoạch: luân chuyển tài khoản Google Flow khi hết credit (19/10)

Lời người dùng: "cho phép user luân chuyển giữa các tài khoản google đăng kí flow khi 1 tài khoản hết token."
(Việc treo từ 16/10: nhận diện tài khoản của từng extension · gắn phim với tài khoản · nút chuyển phim.)

## Hiện trạng (đã khảo sát)
- Mỗi Chrome profile có một extension FlowKit nối vào backend :9233. `flow_client` giữ nhiều kết nối và **tự chuyển
  sang kết nối khác** khi gặp lỗi tab, hoặc lỗi hết quota (`public_error_user_quota_reached`, `…per_model_daily_quota…`).
- Backend **không biết kết nối nào là tài khoản nào**. Dự án = một project Flow; media id (ảnh asset, video) thuộc
  tài khoản đã tạo ra chúng → gửi nhầm sang tài khoản khác thì hỏng (lỗi trộn tài khoản 16/10 với Olya).
- Chưa đọc được số credit còn lại (Flow mới không có rpc credits đã bắt được).

## Các bước (mỗi bước người dùng review; không tốn credit khi thử)
1. ✅ (19/10) **Nhận diện tài khoản**: email đọc từ `WIZ_global_data.oPEP7c` của trang Flow (dự phòng: nhãn
   "Google Account: Tên (email)"); extension 0.6.0 lệnh `get_account`; bảng `flow_account`; `GET/PATCH /api/flow/accounts`;
   nút "👤" ở trang dự án: ai đang kết nối, còn dùng được hay đã hết credit, thứ tự luân chuyển.
2. ✅ (19/10) **Gắn phim ↔ tài khoản**: `CURRENT_ACCOUNT` (contextvar) do worker/đạo diễn đặt theo dự án;
   `_send` chỉ chọn kết nối của tài khoản đó, tài khoản chưa kết nối → lỗi `ACCOUNT_NOT_CONNECTED` rõ ràng; dự án mới ghi
   tài khoản đã tạo nó; dự án cũ gán theo ngày tạo (trước Daniel = Olya). `project.flow_account`; request chỉ đi tới extension của đúng tài khoản; bỏ việc tự
   chuyển sang tài khoản khác (chỉ chuyển giữa các tab của cùng tài khoản). Hết lỗi trộn tài khoản.
3. ✅ (19/10) **Phát hiện hết credit**: lỗi quota (`account_crud.is_quota_error`) → `mark_exhausted` (kèm giờ, lỗi);
   request quay về PENDING không tính lượt; worker giữ mọi request của tài khoản đó (`_account_held`); đạo diễn đang
   chờ request → `production.AccountExhausted` → cổng `ACCOUNT_EXHAUSTED` (payload: account, waiting, stage). Duyệt cổng
   = "tài khoản đã có credit lại" → `reactivate`, chạy tiếp đúng các request cũ (không tạo trùng). Lỗi quota không còn
   chuyển dự phòng sang tab khác (kể cả phim chưa gắn tài khoản). Tài khoản chưa kết nối → request chờ, không tính lượt.
4. ✅ (22/10, Google chặn Hoang "unusual activity" giữa phim) **Chuyển phim sang tài khoản khác** — đã làm: `services/account_move.py`, `POST /api/flow/projects/{pid}/move-account`, nút "đổi tài khoản" cạnh 👤 trên node kịch bản. Id dự án trên máy giữ nguyên; `project.flow_project_alias` + `flow_client.PROJECT_ALIASES` đổi id sang project Flow mới trong mọi lệnh gửi. Ảnh asset tải từ link đã ký (tải hết trước, lỗi thì không đổi gì). Khung cuối nối chuỗi bị xoá (tạo lại khi nối). Khoá "unusual activity" giờ tính riêng từng tài khoản. Thiết kế cũ: (nút trên node kịch bản + gợi ý ở cổng trên): tạo project Flow mới trong
   tài khoản B (qua extension của B), **tải lại ảnh asset từ bản lưu trên máy** (không tạo lại → không tốn credit),
   cập nhật media id; clip đã xong giữ nguyên (đã có file trên máy để dựng); clip chưa xong tạo tiếp ở B.
   Điều kiện: mọi ảnh asset phải có bản lưu trên máy — kiểm tra và bổ sung việc tải về khi ảnh được tạo.
5. **Tự động luân chuyển (tuỳ chọn)**: người dùng xếp thứ tự tài khoản và bật "tự chuyển khi hết credit" → bước 4
   chạy tự động sang tài khoản kế tiếp còn credit, báo người dùng.

## ⏸ Gác lại (19/10, người dùng: "tạm thời gác lại… lưu lại")
- Bước 4, bước 5 chưa làm.
- Tính năng mới người dùng muốn: **chọn tài khoản Google ngay trong canvas** — hoặc chọn tài khoản đang "active" cho
  FlowKit: lúc dùng A, lúc dùng B (extension chạy theo profile Chrome, nên cần bật/chọn đúng profile/tài khoản).
  Ghi chú thiết kế khi quay lại: một phim vẫn phải gắn một tài khoản (media id không dùng chéo được); chọn trong canvas =
  chọn tài khoản cho phim mới / tài khoản ưu tiên, không đổi tài khoản của phim đang làm (việc đó là bước 4).

## Thử nghiệm
Hai profile: Olya và một tài khoản phụ. Thử bằng thao tác miễn phí (tạo project, tải ảnh lên); giả lập
lỗi hết quota trong test, không đốt credit thật.
