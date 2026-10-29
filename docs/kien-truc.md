# Kiến trúc

## Thành phần

| Thành phần | Ở đâu | Việc |
|---|---|---|
| Canvas | `canvas/` (React, Vite, React Flow) | Hiển thị project dạng node, nhận thao tác và duyệt của người dùng. Hỏi backend mỗi vài giây. |
| Backend | `backend/agent/` (FastAPI, SQLite) | API cho canvas, hàng đợi request gửi Flow, pipeline đạo diễn. |
| Đạo diễn AI | `backend/agent/director/` | Gọi Claude (`claude -p`, headless) theo vai; kiểm tra (lint) mọi câu trả lời; dừng ở các cổng duyệt. |
| Extension | `backend/extension/` | Chạy trong tab Google Flow; nhận lệnh qua WebSocket (cổng 9233), tự giải captcha, gọi RPC của Flow ngay trong trang. |
| Dữ liệu | `../du-lieu/` | `flow_agent.db`, ảnh upload, khung hình QC, log. |
| Đầu ra | `../phim/<project>_<id8>/` | `final.mp4` và `_dung-phim/` (clip gốc, đoạn cắt). |

Đường dẫn dữ liệu/đầu ra lấy từ `FLOWKIT_DATA_DIR` / `FLOWKIT_OUTPUT_DIR` (`.env`, `start.sh` chuyển thành
đường dẫn tuyệt đối). Tên thư mục project do `agent/utils/paths.py:project_folder` tạo, dùng chung cho mọi
tính năng ghi file.

## Pipeline đạo diễn

`agent/director/pipeline.py` là một máy trạng thái (các stage nằm ở `stages_script.py`, `stages_media.py`,
`stages_film.py`, dùng chung `stage_common.py`; thao tác của người dùng ở `actions.py`); mỗi run lưu trong bảng `director_run` (cột `plan` chứa
toàn bộ kịch bản, shotlist, prompt, kết quả QC), mỗi lần gọi Claude lưu trong `director_step`.

| Stage | Vai (file trong `knowledge/roles/`) | Ra |
|---|---|---|
| BRIEF | producer | Hiểu ý tưởng, phân loại ảnh upload, chọn giọng nói |
| STORY | writer | Câu chuyện, nhân vật/bối cảnh/đạo cụ, lời thoại theo beat |
| SHOTLIST | director | Danh sách clip 10s r2v, lệnh máy quay, câu thoại từng clip |
| PROMPTS | dp | Prompt từng clip (tiếng Anh mặc định, khuôn theo chế độ phim) |
| EDIT_REVIEW | editor | Chấm điểm; < 75 thì gửi lại đúng stage cần sửa (tối đa 2 vòng) |
| INGEST | — | Tạo project, nhân vật, cảnh trên canvas |
| REFS | — | Tạo ảnh asset trên Flow (ảnh người dùng upload thì dùng luôn) |
| KEYFRAMES | — | Chỉ chế độ keyframe: ảnh khung mở mỗi shot → cổng duyệt KEYFRAMES |
| VIDEOS | — | Tạo clip (r2v; liền mạch: khung cuối clip trước làm ảnh #1; keyframe: first+last); **chặn** nếu còn asset thiếu ảnh |
| QC | qc | Claude xem khung hình từng clip, chọn đoạn cắt, tạo lại clip hỏng trong ngân sách |
| CUT | — | Cắt + scale 1080p + nén một lần (`cut.py`), ghép, nhạc nếu có |
| PUBLISH / RETRO | coach | Gắn phim vào video trên canvas; rút bài học cho lần sau |

Chế độ phim (`brief.film_mode`: `cut` · `continuous` · `keyframe`; `ambient` đang làm) đổi vai đọc sổ tay nào,
lint nào và cách tạo/dựng. Mỗi câu trả lời của Claude đi qua gói `lint/` (mỗi chế độ một module) (số clip, thời lượng, ≤2 hành động, ≤1 chuyển cảnh, lệnh máy
không xung đột, nhãn prompt, câu thoại có trong prompt…). Sai thì gửi lỗi lại cho Claude sửa.

## Cổng duyệt (không bao giờ tự vượt)

| Cổng | Khi nào | Người dùng làm gì |
|---|---|---|
| IDEA | Ý tưởng vừa tạo | Sửa ý tưởng → *Viết kịch bản* (miễn phí) |
| SCRIPT | Kịch bản xong | Đọc → *Tạo từng bước* hoặc *Chạy toàn bộ* (duyệt credit), hoặc *Yêu cầu sửa* |
| ASSETS | Ảnh asset xong (chế độ từng bước) | Xem ảnh, gen lại ảnh chưa ưng → duyệt tạo video |
| SHOT_FAILED | Clip vẫn hỏng sau khi tạo lại | Bỏ clip đó và dựng tiếp, hoặc dừng |
| BUDGET_EXCEEDED | Hết lượt đã duyệt | Cấp thêm lượt |

Credit chỉ được tiêu trong ngân sách của cổng đã duyệt (`budget` / `spent` trong run).

## Hàng đợi Flow

`agent/worker/processor.py` + `agent/services/flow_client.py`:

- Gửi **từng lệnh một**, cách nhau ≥ `FLOW_GENERATION_MIN_INTERVAL_S` (15s); tối đa 3 lệnh đang render.
- Google trả `PUBLIC_ERROR_UNUSUAL_ACTIVITY` → tạm dừng 120 → 300 → 600s, đưa request về hàng chờ
  (không đánh fail hàng loạt); bị chặn 3 lần mới fail.
- **Không trả tiền hai lần:** mỗi request gửi Flow kèm mã client cố định (`flow_batch.submit_client_ids`).
  Trước khi gửi lại một request đã từng gửi, backend dò mã đó trong danh sách media của project Flow; nếu Flow
  đã tạo clip thì nhận luôn clip đó. Không dò được thì báo lỗi chứ không gửi lại.

## Canvas

- Node: 💡 Ý tưởng → 📜 Kịch bản → asset (nhân vật/bối cảnh/đạo cụ) → cảnh → video → 🎞 Phim hoàn chỉnh.
- `src/graph/mapping.ts` dựng đồ thị từ dữ liệu backend; `src/nodes/RunControls.tsx` chứa mọi nút duyệt.
- Khổ 9:16 hiển thị trong khung 9:16 (không cắt hình).

## Cấu hình (`.env`)

| Biến | Ý nghĩa |
|---|---|
| `FLOWKIT_DATA_DIR` | Thư mục dữ liệu (mặc định `../du-lieu`) |
| `FLOWKIT_OUTPUT_DIR` | Thư mục đầu ra (mặc định `../phim`) |
| `FLOW_PROJECT_ID` | Project Google Flow extension làm việc |
| `FK_EXTENSION_ID` | Extension duy nhất được phép kết nối |
| `API_PORT` / `WS_PORT` / `CANVAS_PORT` | 8110 / 9233 / 5180 |
| `OMNI_FLASH_RESOLUTION` | `720p` (cao nhất Flow cho Omni Flash) |
