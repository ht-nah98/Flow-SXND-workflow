# Flow Canvas

Biến một **ý tưởng** thành **phim ngắn hoàn chỉnh** bằng Google Flow (Omni Flash), trên một canvas dạng node.
Bạn lên ý tưởng; Claude đóng vai biên kịch, đạo diễn, quay phim, biên tập, QC và dựng phim; mọi bước tốn
credit đều chờ bạn duyệt.

![Phim mẫu: TikTok bán hàng viên nén xơ dừa](docs/anh/11-phim-mau-xo-dua.jpg)
*Phim mẫu làm hoàn toàn bằng Flow Canvas: TikTok 9:16, 10 clip, thoại tiếng Việt, ~200 credit.*

```
💡 Ý tưởng ──▶ 📜 Kịch bản ──▶ 🖼 Ảnh nhân vật / bối cảnh / đạo cụ ──▶ 🎬 Clip 10s ──▶ 🎞 Phim hoàn chỉnh
   (bạn)        (Claude viết,     (Flow tạo, từng ảnh một)             (Flow r2v,       (cắt, ghép, 1080p)
                 bạn duyệt)                                             từng clip một)
```

| Viết ý tưởng | Duyệt kịch bản | Canvas: asset → cảnh → phim |
|:---:|:---:|:---:|
| <img src="docs/anh/02-y-tuong-moi.jpg" width="260"> | <img src="docs/anh/03-kich-ban.jpg" width="330"> | <img src="docs/anh/04-canvas-toan-canh.jpg" width="260"> |

## Hướng dẫn

| | Tài liệu | Đọc khi |
|---|----------|---------|
| 1 | [Cài đặt](docs/01-cai-dat.md) | lần đầu, ~30 phút |
| 2 | [Làm phim đầu tiên](docs/02-lam-phim-dau-tien.md) | đi từng bước bằng phim mẫu, có ảnh từng màn hình |
| 3 | [Mẹo làm phim](docs/03-meo-lam-phim.md) | muốn phim đẹp hơn: ý tưởng, ảnh tham chiếu, giới hạn của Flow |
| 4 | [Credit và tài khoản](docs/04-credit-va-tai-khoan.md) | dự toán, nhiều tài khoản Google, hết credit giữa phim |
| 5 | [Xử lý sự cố](docs/05-xu-ly-su-co.md) | gặp lỗi |

## Bắt đầu nhanh

```bash
git clone <link-repo> flow-canvas && cd flow-canvas
cp .env.example .env          # điền FLOW_PROJECT_ID
./start.sh                    # lần đầu tự cài; mở http://127.0.0.1:5180
```

Rồi nạp extension `backend/extension` vào Chrome và mở một tab https://flow.google.com.
Chi tiết: [Cài đặt](docs/01-cai-dat.md).

## Mọi thứ nằm ở đâu

```
<thư-mục-làm-việc>/
├── flow-canvas/            ← repo này (code)
│   ├── backend/            FlowKit + đạo diễn AI (Python, FastAPI) — cổng 8110
│   │   ├── agent/director/ pipeline đạo diễn: kịch bản → ảnh → video → QC → dựng
│   │   │   └── knowledge/  quy tắc + playbook làm phim (Claude đọc khi viết)
│   │   └── extension/      Chrome extension nối backend với Google Flow
│   ├── canvas/             giao diện node (React + Vite) — cổng 5180
│   ├── docs/               kiến trúc, kiến thức làm phim, thiết kế
│   ├── start.sh            chạy cả hệ thống
│   └── .env                cấu hình máy này (không lên git)
├── du-lieu/                ← dữ liệu chạy (không lên git)
│   ├── flow_agent.db       database: project, cảnh, request, run đạo diễn
│   ├── uploads/            ảnh bạn đính kèm ý tưởng, nhạc
│   ├── qc/                 khung hình Claude dùng để chấm clip
│   ├── logs/               log backend
│   └── backup/             bản sao database
└── phim/                   ← ĐẦU RA, mỗi project một thư mục
    └── <ten-project>_<ma>/
        ├── final.mp4       PHIM HOÀN CHỈNH
        └── _dung-phim/     clip gốc tải từ Flow + đoạn đã cắt
```

**Phim cuối của mọi project luôn ở `phim/<ten-project>_<ma>/final.mp4`.** `<ma>` là 8 ký tự đầu của id
project, để hai project trùng tên không đè lên nhau. Trên canvas, node 🎞 *Phim hoàn chỉnh* phát đúng file này.

## Làm một phim (tóm tắt — bản đầy đủ có ảnh: [docs/02](docs/02-lam-phim-dau-tien.md))

1. **💡 Ý tưởng:** nhập ý tưởng, đính kèm ảnh (sản phẩm, người thật, bối cảnh) nếu có, chọn thời lượng,
   khổ (16:9 / 9:16) và **giọng nói** (tự nhận diện / lồng tiếng / nhân vật nói / không lời).
   Chọn **chế độ phim**: liền mạch (mặc định) · cắt cảnh · keyframe · không khí buổi diễn (kịch bản xong, tạo video đang làm) —
   luật từng chế độ ở `playbook/` 09, 10, 11.
   Bấm **✍️ Viết kịch bản** — miễn phí.
2. **📜 Kịch bản:** đọc tóm tắt, từng clip và lời thoại; bấm *Yêu cầu sửa* nếu chưa ưng (miễn phí).
3. Duyệt credit, chọn một trong hai:
   - **▶ Tạo từng bước:** tạo ảnh asset → bạn xem → duyệt tạo video.
   - **⏩ Chạy toàn bộ:** một lần duyệt, hệ thống tự xếp hàng đến phim cuối.
4. Hệ thống gửi Flow **từng lệnh một**, Claude QC từng clip (tạo lại clip hỏng trong ngân sách đã duyệt),
   rồi dựng phim. Không có video nào bắt đầu khi còn thiếu ảnh tham chiếu.
5. Xem phim ở node 🎞 hoặc mở `phim/<ten-project>_<ma>/final.mp4`.

## Công cụ hỗ trợ

- **Đèn hệ thống** (giữa đáy màn hình): bấm để xem từng phần (backend, extension, Claude, ffmpeg, thư mục, ổ đĩa)
  và cách sửa phần đang lỗi.
- **💳 Credit hôm nay:** ước tính từ số lệnh đã gửi Flow (Flow không trả số dư). Bấm để đặt **trần credit
  theo ngày**; chạm trần thì lệnh mới đứng chờ, không bị huỷ.
- **Tiến trình viết kịch bản:** node 💡 hiện từng bước, thời gian, bước đang chạy và thời gian còn lại ước tính.
- **🧩 Canvas / 🎞 Storyboard:** Storyboard là bảng asset × cảnh (chấm màu = cảnh dùng asset) kèm video lớn
  theo thứ tự phim. Canvas có menu Sắp xếp (Hàng ngang / Cột dọc / Theo đồ thị) và chú giải màu asset.
- **✏️ Sửa clip bằng lời:** trên cảnh do đạo diễn tạo; Claude viết lại riêng prompt clip đó, bạn xem chỗ đổi
  rồi mới dùng (miễn phí đến khi bấm Gen lại video).
- **⇔ So sánh phiên bản** của một clip và chọn bản đẹp nhất; **🎬 Dựng lại phim** từ các bản đang chọn (miễn phí).
- **Mẫu ý tưởng:** quảng cáo, review, phim tình cảm, vlog, hướng dẫn.
- **Dùng lại asset:** kéo asset từ Thư viện vào project trước khi viết kịch bản; đạo diễn dùng luôn ảnh đó.
- **🎨 Hiệu ứng kiểu CapCut:** đạo diễn chọn bộ lọc màu cho phim, chuyển tiếp và hiệu ứng trong clip
  (dựng lại bằng ffmpeg, xem `playbook/06-hieu-ung.md`); miễn phí, áp dụng khi dựng.
- **📚 Học từ video mẫu** (`/hoc`): Claude xem từng shot của video bạn thích, đề xuất kỹ thuật; kỹ thuật bạn
  chọn được ghi vào sổ tay và đạo diễn áp dụng từ phim sau.

## Kiểm thử

```bash
cd backend && .venv/bin/python -m pytest tests/unit -q     # ~900 test
cd canvas && npx tsc --noEmit -p . && npx vitest run       # ~116 test
```

Test chạy trong thư mục tạm, không bao giờ ghi vào `phim/` hay `du-lieu/`.

## Tài liệu

- [docs/01–05](docs/) — hướng dẫn sử dụng (xem bảng ở đầu trang)
- [docs/kien-truc.md](docs/kien-truc.md) — hệ thống hoạt động thế nào, các cổng duyệt, hàng đợi Flow
- [docs/kien-thuc-lam-phim.md](docs/kien-thuc-lam-phim.md) — kinh nghiệm đúc kết: prompt, asset, giọng nói, dựng, lỗi Flow
- [backend/agent/director/knowledge/playbook/](backend/agent/director/knowledge/playbook/) — sổ tay làm phim (Claude đọc khi làm)
- [docs/thiet-ke/](docs/thiet-ke/) — đặc tả và kế hoạch thiết kế
- [CONTRIBUTING.md](CONTRIBUTING.md) — góp code, góp bài học vào sổ tay
- [backend/README.md](backend/README.md) — tài liệu gốc của FlowKit

## Nguồn gốc

Backend là bản fork của [FlowKit](https://github.com/crisng95/flowkit) (MIT), đã gia cố bảo mật và thêm
pipeline đạo diễn AI. Xem `backend/LICENSE` và `canvas/NOTICE.md`.
