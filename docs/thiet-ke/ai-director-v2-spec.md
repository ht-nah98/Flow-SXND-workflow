# AI Director v2 — Ý tưởng → Phim (thiết kế)

Ngày: 2026-10-15 · Thay thế các phần tương ứng của `2026-10-15-ai-director-design.md` (v1). Phần nào không nhắc ở đây
giữ nguyên như v1 (brain `claude -p`, lint, budget, lessons, hàng đợi request).
Nguồn kinh nghiệm: `agent/director/knowledge/playbook/` (sổ tay 5 bước, rút từ bản làm lại FMV — đã kiểm chứng).

## 1. Mục tiêu

Người dùng chỉ là **người lên ý tưởng**. Claude làm **biên kịch + đạo diễn + DP + dựng**.

```
💡 Ý tưởng (text, hoặc text + ảnh)
 → 📜 Kịch bản (Claude)                         ✋ Cổng 1: duyệt kịch bản + credit ảnh asset (hoặc góp ý → viết lại)
 → 👤🏠📦 Asset: sheet nhân vật, bối cảnh, đạo cụ ✋ Cổng 2: xem ảnh (tạo lại cái chưa ưng) + duyệt credit video
 → 🎬 Clip r2v 10s → QC → 🎞 Dựng → node Phim hoàn chỉnh
```

### Thành công khi
1. Từ một ý tưởng ~1–3 câu (± ảnh), hệ thống ra kịch bản đọc được trên node 📜 trước khi tốn credit nào.
2. Ảnh người dùng đính kèm được Claude hiểu và dùng đúng: làm asset trực tiếp (không tốn credit) hoặc chỉ làm tham khảo tông/không khí.
3. Mọi clip là **r2v 10s** với 2–3 ảnh asset; không tạo ảnh khung đầu.
4. Người dùng chỉ bấm ở 2 cổng; mọi credit nằm trong ngân sách đã duyệt.
5. Phim cuối hiện trên node 🎞 Phim hoàn chỉnh (video.horizontal_url/vertical_url được set).

### Ngoài phạm vi v2 (để Plan C — hậu kỳ)
Dựng theo EDL đảo thứ tự, chớp trắng/light leak/grade màu, nhạc nền tự chọn, hiệu ứng kiểu CapCut. v2 dựng theo thứ tự
kịch bản, cắt thẳng, dùng trim của QC, xuất yuv420p.

## 2. Đầu vào: Ý tưởng

`POST /api/director/runs`
| Trường | Kiểu | Ghi chú |
|---|---|---|
| `text` | 3–4000 ký tự | ý tưởng |
| `images` | ≤ 6 × `{base64, filename, note?}` | jpg/png/webp, ≤ 10 MB/ảnh; `note` là ghi chú tuỳ chọn của người dùng ("đây là quán cà phê thật của tôi") |
| `orientation` | HORIZONTAL \| VERTICAL | mặc định HORIZONTAL |
| `target_s` | 15–300 | mặc định 60 |
| `style` | material id | mặc định `realistic` |

- Ảnh lưu ở `OUTPUT_DIR/_director/ideas/<run_id>/`.
- **Project được tạo ngay khi tạo run** (tên = 60 ký tự đầu của ý tưởng, sửa được sau), `plan.ids.project_id` set sẵn,
  để canvas mở được ngay và theo dõi tiến độ. `ingest` bỏ qua bước tạo project khi đã có id.
- Response trả `run` kèm `project_id`; canvas chuyển thẳng sang trang canvas của project đó.

## 3. Các công đoạn (thay STAGES của v1)

```
BRIEF → STORY → SHOTLIST → PROMPTS → EDIT_REVIEW → INGEST → [Cổng SCRIPT]
→ REFS → [Cổng ASSETS] → VIDEOS → QC → CUT → PUBLISH → RETRO → DONE
```
Bỏ: `KEYFRAMES`, `ESTIMATE` (gộp vào 2 cổng).

| Stage | Thay đổi so với v1 |
|---|---|
| BRIEF (`producer`) | Nhận thêm danh sách ảnh (Claude được `Read` thư mục ảnh). Trả thêm `images: [{file, use, name?, description}]`, `use ∈ character \| location \| visual_asset \| mood`. Người dùng ghi `note` thì `note` thắng. |
| STORY (`writer`) | Cast có thêm `provided_image: file?` khi lấy từ ảnh người dùng. Nhân vật = character sheet 3 panel (đã có trong writer.md); bối cảnh ghi rõ tỉ lệ theo khổ video. Ảnh `mood` chỉ đưa vào mô tả tông. |
| SHOTLIST (`director`) | Mọi shot `mode = r2v`, `duration_s = 10`. Phủ góc: địa điểm chính có 3–6 shot ở các góc khác nhau (thư viện góc máy của sổ tay). Số shot ≈ `ceil(target_s / 5.5)` (mỗi clip dùng ~5s sau cắt). |
| PROMPTS (`dp`) | Prompt **tiếng Việt** theo khung FMV: `Ảnh tham chiếu / Nhân vật & trang phục / Bối cảnh / Góc quay / Hành động / Chuyển động camera / Ánh sáng & màu sắc / Âm thanh / Thời lượng`. `keyframe_prompt` luôn null. |
| INGEST | Như v1, nhưng project đã có; nhân vật có `provided_image` được upload thay vì chờ gen. Set `scene.prompt` = tiêu đề ngắn của shot (không còn keyframe prompt). |
| Cổng SCRIPT | Đặt **trước** REFS (v1 gen ref trước khi người dùng xem kịch bản). Payload: số clip, số ảnh cần gen (trừ ảnh người dùng đưa), credit ảnh ước tính. Duyệt = cấp ngân sách `refs`. "Yêu cầu sửa" như v1. |
| REFS | Chỉ gen asset chưa có ảnh. Tỉ lệ: nhân vật **16:9** (sheet 3 panel), bối cảnh **theo khổ video**, đạo cụ 9:16. |
| Cổng ASSETS | Người dùng xem ảnh trên các AssetNode, tạo lại ảnh chưa ưng (nút sẵn có, qua hộp duyệt credit sẵn có). Payload: số video + regen + credit ước tính (15/clip 10s). Duyệt = cấp ngân sách `videos` + `regens`. |
| VIDEOS | Chỉ `GENERATE_VIDEO_REFS`. Lỗi `MEDIA_REMOVED` đã tự gửi lại 1 lần ở worker; vẫn hỏng → shot `failed`, sang QC/CUT như v1. |
| CUT | Như v1 + bắt buộc `yuv420p`, `+faststart`. |
| PUBLISH | Copy phim vào `OUTPUT_DIR`, set `video.<orientation>_url = file://…`, `duration`, status COMPLETED → node 🎞 hiện ra. |

### Kiến thức cho các vai
`brain._system_prompt` nối thêm các file sổ tay theo vai:
- `writer`: 01-kich-ban, 02-asset · `director`: 01-kich-ban, 03-prompt-video · `dp`: 03-prompt-video, 05-xu-ly-loi
- `editor`, `qc`: 03-prompt-video, 04-dung-phim

### Lint (sửa `lint.py`)
- Bỏ luật i2v/keyframe; thêm: `mode == r2v`, `duration_s == 10`.
- Kiểm nhãn block theo khung tiếng Việt ở trên (thay cho các nhãn tiếng Anh v1).
- Giữ: ≤2 hành động, ≤1 chuyển cảnh sau ≥2s ổn định, tên cast khớp, mỗi shot có ≥1 ref.
- Tổng nguồn: `shots × 10` trong `[1.5, 2.4] × target_s`.

### Ngân sách
`DIRECTOR_CREDIT_TABLE`: `video` = 15 (Omni Flash 10s), `image` giữ nguyên. Ước tính ở 2 cổng dùng bảng này.

## 4. Canvas

- **Trang danh sách project:** nút **"💡 Ý tưởng mới"** → form: ô ý tưởng, kéo thả/chọn ảnh (xem trước, ô ghi chú từng ảnh),
  khổ 16:9/9:16, thời lượng (mặc định 60s), phong cách. Gửi → chuyển sang canvas project mới.
- **Node 💡 Ý tưởng** (`idea:<run_id>`, cột trái, trên node 📜): ý tưởng + ảnh thu nhỏ (nhãn Claude gán: nhân vật/bối cảnh/đạo cụ/tham khảo),
  thanh tiến độ stage ("Claude đang viết kịch bản…", "Đang tạo ảnh 3/6", "Video 7/12"), lỗi + "Chạy lại bước".
  - Ở Cổng SCRIPT: **"Duyệt kịch bản (≈N credit ảnh)"** và **"Yêu cầu sửa"** (ô góp ý).
  - Ở Cổng ASSETS: **"Ảnh ổn — tạo video (≈N credit)"**.
  - Ở SHOT_FAILED: "Bỏ clip lỗi và dựng" / "Dừng".
  Cạnh nối 💡 → 📜.
- Node 📜 Kịch bản (đã có) là nơi đọc kịch bản; AssetNode, SceneNode, 🎞 tự hiện theo dữ liệu project như hiện nay.
- Canvas nhận sự kiện `director_stage`/`director_gate`/`director_error` qua WS sẵn có để làm mới.
- Backend: `canvas.py` cho phép khoá `idea:`; prune khi run không thuộc project.

## 5. Xử lý lỗi
Như v1 §10, thêm:
| Tình huống | Hành vi |
|---|---|
| Ảnh ý tưởng sai định dạng/quá lớn | 400 trước khi tạo run |
| Claude phân loại ảnh sai | người dùng sửa nhãn trên node 💡 trước Cổng SCRIPT → "Yêu cầu sửa" chạy lại từ STORY |
| Ảnh người dùng upload lên Flow lỗi | asset đó chuyển sang gen bằng prompt (tính vào ngân sách ở Cổng SCRIPT) |
| Clip bị Flow xoá 2 lần | shot `failed`, gợi ý trong lỗi: "viết lại hành động an toàn hơn" (sổ tay 05) |

## 6. Kiểm thử (không tốn credit)
- pytest: tạo run có ảnh (lưu file, giới hạn số/kích thước), project tạo ngay; thứ tự stage mới với FakeBrain tới Cổng SCRIPT
  (chưa có request REFS nào), approve → REFS → Cổng ASSETS → approve → VIDEOS chỉ `GENERATE_VIDEO_REFS` → … → PUBLISH set url.
- pytest ingest: cast `provided_image` → upload, không tạo request gen.
- pytest lint: luật r2v/10s, nhãn block tiếng Việt, tổng nguồn.
- pytest aspect: nhân vật → LANDSCAPE, bối cảnh theo orientation của project/video.
- pytest brain: system prompt chứa đúng file sổ tay theo vai.
- vitest: form Ý tưởng (ảnh + ghi chú), IdeaNode các trạng thái/cổng, cạnh 💡→📜.
- Thật (cần duyệt credit): 1 ý tưởng ~30s (≈6 clip ≈ 90 credit video + ảnh asset), kiểm qua CDP.

## 7. Thứ tự xây dựng
1. Backend: RunCreate có ảnh + tạo project ngay; producer đọc ảnh; schema/stage mới; bỏ KEYFRAMES/ESTIMATE; 2 cổng mới; PUBLISH.
2. Backend: lint v2, aspect asset, sổ tay vào system prompt, cập nhật roles (producer, writer, director, dp).
3. Canvas: form Ý tưởng, IdeaNode, khoá `idea:`, làm mới theo sự kiện director.
4. Chạy thử chỉ Claude (không Flow) với 2–3 ý tưởng để chỉnh roles; rồi 1 phim thật ~30s sau khi người dùng duyệt credit.
