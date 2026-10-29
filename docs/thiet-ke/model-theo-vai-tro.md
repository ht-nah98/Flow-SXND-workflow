# Model theo vai trò (đạo diễn AI)

Mỗi bước của đạo diễn AI là một lần gọi `claude -p` riêng. Không phải bước nào cũng cần Opus: dùng Opus ở chỗ
phán đoán quyết định chất lượng phim, Sonnet cho việc theo khuôn mẫu đã có máy kiểm, Haiku cho việc phân loại.
Bảng nằm ở `backend/agent/config.py` (`DIRECTOR_ROLE_MODELS`, `DIRECTOR_ROLE_EFFORT`).

## Số liệu trước khi đổi (58 lần gọi, mọi vai trò đều chạy Opus)
| Bước | Vai trò | TB thời gian | Đầu ra TB | Bị lint trả lại |
|------|---------|-------------|-----------|-----------------|
| PROMPTS | dp | 126s | 23k ký tự | 1/13 |
| SHOTLIST | director | 77s | 8k | 2/15 |
| STORY | writer | 67s | 12k | 0/11 |
| EDIT_REVIEW | editor | 48s | 2.6k | 0/12 |
| BRIEF | producer | 13s | 1.2k | 0/7 |
Giá thử một câu ngắn (16/10): Haiku $0.006 · Sonnet $0.12 · Opus $0.25 (phần lớn là nạp chỉ dẫn hệ thống).

## Bảng hiện tại
| Vai trò | Bước | Model | Effort | Vì sao |
|---------|------|-------|--------|--------|
| producer | BRIEF | Haiku | low | Đọc ý tưởng, điền brief nhỏ (giọng, ngôn ngữ, độ dài); lựa chọn của người dùng luôn thắng |
| writer | STORY | **Opus** | high | Tuyến truyện, thông điệp, nhân vật — chất lượng phim bắt đầu từ đây (lời dặn B1) |
| director | SHOTLIST | **Opus** | high | Chia shot, nhịp, vật lý; bước hay bị lint trả lại nhất |
| dp | PROMPTS | Sonnet | medium | Điền khuôn prompt cố định cho từng shot; đầu ra dài nhất; lint kiểm từng dòng |
| editor | EDIT_REVIEW | **Opus** | high | Cổng chất lượng: người duyệt không được yếu hơn người viết |
| reshoot | viết lại 1 clip lỗi | Sonnet | medium | Sửa một prompt theo lỗi cụ thể |
| qc | QC | Sonnet | medium | Xem ảnh tờ liên tục của clip đã quay |
| coach | RETRO | Sonnet | low | Rút bài học; bài học đi vào mọi prompt sau nên không dùng Haiku |
| analyst | học video mẫu | **Opus** | high | Hiểu câu chuyện + kỹ thuật của phim mẫu |

## Số liệu phim Daniel (16/10, 28 lần gọi, ~$6.4) và đã sửa (19/10)
| Vai | Lần | Chi phí | Ghi chú |
|-----|-----|---------|---------|
| QC (Sonnet) | 19 | $2.08 | Mỗi lần nạp lại ~20–47k token chỉ dẫn → **gộp 4 clip/lần** (`QC_BATCH`) |
| DP | 2 | $1.78 | Sonnet bị trả lại 44/44 vì chương 03 dạy 3 mốc giờ → **sửa khuôn**; lần sau chỉ **viết lại prompt hỏng** (`repair`), vẫn Sonnet trước |
| Đạo diễn (Opus) | 1 | $1.33 | ~5 phút, 36k token ra; giữ nguyên tới khi có thêm số liệu |
| Biên kịch (Opus) | 1 | $0.96 | Giữ nguyên |
| Editor | 3 | $0 | Claude hết lượt, thử lại vô ích → **dừng ngay khi hết lượt** |
Không gộp biên kịch + đạo diễn: hai bước Opus dài nhất, gộp lại một lần lỗi là làm lại cả hai, và chất lượng kịch bản
là điều người dùng phàn nàn nhiều nhất.

## Bật/tắt vai (lời dặn A5, 19/10)
Producer, editor, QC, coach có thể tắt cho từng phim (khối "🤖 Agent trong luồng" trên 💡). Tắt producer → brief lấy
từ lựa chọn trên 💡 (ý tưởng có ảnh thì producer vẫn chạy để phân loại ảnh); tắt editor → không chấm/sửa kịch bản;
tắt QC → mỗi clip lấy đoạn 1–8s, không tự quay lại clip lỗi; tắt coach → không ghi bài học. Biên kịch, đạo diễn,
DP luôn chạy. QC là vai gọi nhiều nhất (một lần mỗi clip).

## Lưới an toàn
- Câu trả lời sai khuôn (schema) ở lần thử cuối, hoặc bị lint trả lại ở bước sau → **tự nâng lên Opus**
  (`DIRECTOR_ESCALATE_MODEL`). Model rẻ chỉ được thử một lần cho mỗi lỗi.
- Đổi không cần sửa code, trong `.env` (có nháy đơn): `DIRECTOR_ROLE_MODELS='{"dp": "opus"}'`, `DIRECTOR_ROLE_EFFORT='{"writer": "max"}'`.

## Đo để chỉnh tiếp
Mỗi lần gọi ghi một dòng vào `du-lieu/logs/brain-usage.jsonl` (vai trò, model, token, chi phí, thời gian). Tổng hợp:
```bash
python3 -c "import json,collections as c;d=c.defaultdict(lambda:[0,0.0,0]);[(d[(r['role'],r['model'])].__setitem__(0,d[(r['role'],r['model'])][0]+1),d[(r['role'],r['model'])].__setitem__(1,d[(r['role'],r['model'])][1]+r['cost_usd']),d[(r['role'],r['model'])].__setitem__(2,d[(r['role'],r['model'])][2]+r['ms'])) for r in map(json.loads,open('du-lieu/logs/brain-usage.jsonl'))];[print(k,n,round(cost,2),'USD',round(ms/n/1000),'s/lần') for k,(n,cost,ms) in sorted(d.items())]"
```
Quy tắc chỉnh: vai trò Sonnet bị nâng lên Opus thường xuyên (>30% lần) → đổi hẳn sang Opus; editor chấm điểm
kịch bản thấp lặp lại sau khi đổi model → trả về Opus. Ghi mỗi lần chỉnh vào bảng trên kèm ngày.
