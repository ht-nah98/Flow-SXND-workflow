# 10 — Chế độ phim KEYFRAME (`brief.film_mode = "keyframe"`, lời dặn B13)

Chỉ áp dụng khi người dùng chọn chế độ keyframe trên node ý tưởng. Hai chế độ kia giữ nguyên: `cut` (01, 03, 04) và
`continuous` (09). Mẫu: [samples/kling-artlist/phan-tich.md](samples/kling-artlist/phan-tich.md) — 15 shot / 47,5s.

## 1. Ý tưởng
Phim là một chuỗi **keyframe** (ảnh tĩnh do mình chốt) và **shot** nối giữa chúng. Mỗi shot có một ảnh keyframe mở.
Khi shot sau **nối** (`join_in` khác `cut`), khung cuối của shot trước **chính là ảnh keyframe của shot sau** (cùng một
ảnh) → Flow (Omni first+last) chỉ lấp chuyển động ở giữa, chỗ nối khớp ngay từ lúc tạo. Shot trước một cú cắt cứng
và shot cuối: chỉ khung đầu.

## 2. Chia shot
- Shot **một việc**: một hành động HOẶC một chuyển động máy, 1–5s trong phim (`use_s`). Video tạo 4/6/8s rồi cắt.
- Nhiều shot ngắn hơn ít shot dài: phim 30s ≈ 8–12 shot.
- Một nhân vật/vật dẫn người xem qua các nơi; giữ một **dấu hiệu nhận biết** rõ (áo, vật cầm, vết trên mặt).
- `join_in` của mỗi shot (cách đi từ shot trước vào shot này):

| join_in | Keyframe của shot này trông thế nào | Shot trước kết thúc bằng | Mẫu |
|---|---|---|---|
| `occlusion` | một vật/người **sát ống kính che gần kín khung** (áo, thân người, cột, cửa) | vật đó lao/kéo tới che ống kính | áo choàng trùm ống kính (shot 10→11) |
| `screen` | **màn hình/khung kính đầy khung** đang chiếu nơi mới | máy đẩy vào một màn hình **có sẵn trong khung** từ đầu shot | TV tiệm cắt tóc → bản tin (2→3→4) |
| `action` | người **đang làm dở** một hành động, đúng tư thế | cùng hành động, cùng tư thế | đưa tiền người ăn xin (11) |
| `whip` | khung **nhoè ngang** theo hướng máy lia | cú lia/chạy nhanh cùng hướng | rời ghế cắt tóc (1→2) |
| `cut` | khung mới bình thường | không nối (cắt cứng; chỉ khi đổi hẳn chuỗi) | — |

- Đổi nơi/thời: chỉ qua `screen`, `occlusion` hoặc `whip` (hoặc `cut` giữa hai chuỗi) — không qua `action`.
- Shot đầu tiên: `join_in = cut`.

## 3. Viết keyframe (`keyframe`, tiếng Anh) = prompt ảnh
Một khung tĩnh cụ thể: ai (tên asset đúng chữ), ở đâu (tên bối cảnh), tư thế/hành động đang dở, cỡ cảnh, góc máy,
ánh sáng, dấu hiệu nhận biết. 25–80 từ. `cast` của shot = mọi người/vật/nơi thấy trong ảnh, **tối đa 6** (ảnh chỉ dùng để vẽ khung tĩnh; cả nhà 4 người + phòng vẫn đủ) và luôn có ảnh bối cảnh (lint `too_many_refs`, `location_ref`). Keyframe nối kiểu `occlusion`/`screen`/`whip` được phép "đầy khung" vì nó là
ảnh ghim, Flow không phải tự giữ.

## 4. Viết video prompt (tiếng Anh, 40–150 từ)
Chỉ tả **chuyển động giữa hai khung**: một hành động hoặc một chuyển động máy, hướng, tốc độ. Khi shot sau nối: kết
bằng "ending exactly on the final frame: <keyframe shot sau, rút gọn>". Không tả lại cả cảnh (ảnh đã có). Luật D8 giữ
nguyên (tên asset, không máy quay như vật, ảnh có người không quay mặt về ống kính).

## 5. Tạo
Ảnh nhân vật/bối cảnh/đạo cụ (như cũ) → **ảnh keyframe mỗi shot** (dùng ảnh tham chiếu, ~1 credit/ảnh) → người dùng
duyệt keyframe (rẻ, sửa từng ảnh) → video i2v: khung đầu = keyframe shot i, khung cuối = keyframe shot i+1 nếu nối.

## 6. Dựng
Cắt mỗi shot theo `use_s`. Shot nối vào dùng từ 0s (bắt đầu đúng keyframe); shot nối ra dùng tới hết clip (kết đúng
keyframe sau). Không thêm hiệu ứng chuyển ở chỗ nối — cú nối đã nằm trong hình.
