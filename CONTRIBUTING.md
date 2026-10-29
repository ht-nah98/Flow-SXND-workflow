# Góp code và bài học

## Chạy test trước khi đẩy

```bash
cd backend && .venv/bin/python -m pytest tests/unit -q          # ~900 test, ~2 phút
cd canvas && npx tsc --noEmit -p . && npx vitest run            # type check + unit test
```

Test chạy trong thư mục tạm, không đụng `phim/`, `du-lieu/` và **không gọi Flow, không tốn credit**.
`npm run e2e` (canvas) chạy backend giả với worker giả, cũng không tốn credit.

## Quy tắc

- Không commit `.env`, database (`*.db`), ảnh hoặc phim trong `du-lieu/` / `phim/`, email tài khoản Google thật.
  Test dùng email giả (`olya@gmail.com`, `a@gmail.com`…).
- Mỗi commit một việc, mô tả bằng tiếng Việt hoặc tiếng Anh, nói **vì sao** chứ không chỉ cái gì.
- Sửa giao diện → chạy canvas, tự bấm thử, chụp ảnh trước/sau gắn vào PR.
- Thêm luật mà máy kiểm được (độ dài prompt, số hành động, đạo cụ…) → viết vào `backend/agent/director/lint/` (theo chế độ phim)
  kèm test, đừng chỉ viết thành chữ trong sổ tay (Claude có thể quên chữ, không quên lint).

## Góp bài học làm phim

Sổ tay Claude đọc khi làm phim nằm ở `backend/agent/director/knowledge/playbook/`:

| File | Ghi gì |
|------|--------|
| `00-loi-dan-nguoi-dung.md` | Lời dặn của người dùng, kèm nguyên văn và ngày. Quyền cao nhất |
| `01`–`06` | Từng bước: kịch bản, asset, prompt video, dựng, xử lý lỗi, hiệu ứng |
| `07-nhat-ky-bai-hoc.md` | Nhật ký từng phim: hỏng gì, vì sao, sửa thế nào |
| `09`–`11` | Luật riêng của từng chế độ phim |
| `samples/` | Phân tích video mẫu đã học |

Làm xong một phim, có điều đáng nhớ → thêm một dòng vào `07`; nếu thành luật → đưa vào đúng file bước và vào `00`.
Lỗi Flow mới → thêm hàng vào `05-xu-ly-loi.md` (triệu chứng / nguyên nhân / cách xử lý).

Dùng Claude Code trong repo này: skill `flow-video-playbook` (`.claude/skills/`) tự nạp sổ tay khi bạn hỏi về làm phim.

## Nguồn gốc

Backend fork từ [FlowKit](https://github.com/crisng95/flowkit) (MIT). Giữ nguyên `backend/LICENSE` và ghi công khi
dùng lại phần đó.
