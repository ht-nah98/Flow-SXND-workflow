# Canvas

Giao diện node của Flow Canvas: ý tưởng, kịch bản, asset, cảnh, video và phim hoàn chỉnh trên một màn hình.
Cách chạy cả hệ thống: xem [README gốc](../README.md) (`./start.sh`).

## Phát triển

```bash
npm run dev     # http://127.0.0.1:5180, backend mặc định http://127.0.0.1:8110 (VITE_FLOWKIT_URL để đổi)
npm test        # unit test, không cần backend
npm run e2e     # backend riêng với database tạm và worker giả: không gọi Flow, không tốn credit
```

## Cấu trúc

- `src/graph/mapping.ts` — dựng node/cạnh từ dữ liệu backend.
- `src/nodes/` — từng loại node; `RunControls.tsx` chứa mọi nút duyệt của đạo diễn AI.
- `src/api/` — client, kiểu dữ liệu, query.
