# Kế hoạch tách `pipeline.py` (970 dòng) và `lint.py` (862 dòng) — 23/10

## Mục tiêu
Mỗi file một việc, dễ đọc, dễ test; **chỉ di chuyển code, không đổi hành vi**. Đặc biệt: luật riêng của từng chế độ
phim (cut / continuous / keyframe) nằm ở file riêng — bài học 23/10: chế độ keyframe bị code cũ coi như "cut" vì luật
các chế độ trộn lẫn trong một file.

## Luật khi tách
- Chỉ chuyển code. Không đổi tên hàm, không sửa logic.
- `from agent.director.lint import …` và `pipeline.approve / run_until_blocked / HANDLERS …` giữ nguyên: file cũ
  re-export những tên được dùng ở nơi khác (api, canvas tests, 9 file test).
- Mỗi bước = 1 commit; sau mỗi bước: toàn bộ test unit (873), `ruff check`, khởi động lại backend + gọi thử API.
- Test đang monkeypatch tên trong module (`pipeline._contact_sheets`, `pipeline.QC_BATCH`) → sửa test trỏ tới module
  mới cùng commit (nếu không, patch âm thầm mất tác dụng).

## A. `lint.py` → thư mục `lint/`
| File mới | Nội dung | ~dòng |
|---|---|---|
| `lint/__init__.py` | re-export API công khai (+ `_news_look`, `_photo_faces`, `mentions` mà test dùng) | 30 |
| `lint/common.py` | `LintIssue`, `errors`, hằng số chung, `mentions`, tách khối prompt | 120 |
| `lint/story.py` | `lint_story` | 60 |
| `lint/shotlist.py` | `lint_shotlist` + đạo cụ lặp, liên tục, lệnh, hành động, chuyển cảnh | 230 |
| `lint/prompts_cut.py` | `lint_prompts` chế độ cut + ảnh có mặt người, dáng bản tin | 170 |
| `lint/continuous.py` | `_lint_prompts_cont`, nhịp, chuỗi, `assemble` | 200 |
| `lint/keyframe.py` | `_lint_kf_shot`, `_lint_kf_chain`, `_lint_prompts_kf` | 110 |

## B. `pipeline.py` → 5 file
| File | Nội dung | ~dòng |
|---|---|---|
| `pipeline.py` (giữ) | `STAGES`, `HANDLERS`, `AFTER_GATE`, nhãn tiếng Việt, `run_until_blocked`; re-export | 150 |
| `stage_common.py` | `Gate`, `StageFailed`, `_ask`, `think_with_lint`, `_models`, `agent_on`, `_shot_ctx`, `_gen`, keyframe helpers | 150 |
| `stages_script.py` | BRIEF → STORY → SHOTLIST → PROMPTS → EDIT_REVIEW | 230 |
| `stages_media.py` | INGEST, REFS, KEYFRAMES, VIDEOS (`script_payload`, ghim khung) | 200 |
| `stages_film.py` | QC, CUT, PUBLISH, RETRO, `current_edit` / `save_edit` | 200 |
| `actions.py` | việc người dùng bấm: `approve`, `revise`, `resolve_shot_failure`, `rewrite_shot`, `apply_rewrite`, `recut`, `make_missing_refs`, `clips_missing` | 180 |

## Thứ tự (mỗi dòng 1 commit, báo sau mỗi phần A / B)
1. A: `lint/` (một commit — các hàm lint gọi chéo nhau).
2. B1: `stage_common.py`.
3. B2: `stages_script.py` · B3: `stages_media.py` · B4: `stages_film.py`.
4. B5: `actions.py`.

## Rủi ro
- Import vòng (stages ↔ pipeline): stages chỉ import `stage_common`, không import `pipeline`.
- Patch trong test mất tác dụng: rà `setattr(pipeline, …)` / `setitem(pipeline.HANDLERS, …)` từng bước (đã liệt kê).
- Không chạm dữ liệu, không tốn credit.

## Kết quả (23/10)
- A `62ceec7`: `lint/` 7 file. Lint 12 phim trong DB (401 lỗi) giống hệt bản cũ.
- B `96eb8d9` → `43b3eaf` (5 commit): `pipeline.py` 970 → 162 dòng; `stage_common` 121, `stages_script` 240,
  `stages_media` 153, `stages_film` 234, `actions` 183. Mỗi bước 873 test qua, ruff sạch. `current_edit`,
  `script_payload`, `rewrite_issues` trên 13 phim trong DB giống hệt bản trước khi tách. Backend + canvas chạy bình thường.
- Test patch `_contact_sheets` / `QC_BATCH` giờ trỏ vào `stages_film`.
