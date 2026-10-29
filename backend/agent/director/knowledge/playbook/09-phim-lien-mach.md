# Phim liền mạch (`brief.film_mode = "continuous"`, chế độ mặc định — lời dặn B12)

Học từ phim người dùng tự làm "SIU Phẩm Giáng Sinh 1" (21/10): "Đây mới là kết quả của video tôi mong đợi. Chứ không
phải chỉ các short riêng lẻ rồi bạn lồng ghép vào với nhau." Prompt gốc: [samples/siu-giang-sinh/prompts.md](samples/siu-giang-sinh/prompts.md).
Chế độ cắt-ghép cũ (clip 3–7s, chuyển cảnh ở bàn dựng, luật D3/D8/E1) chỉ dùng khi người dùng chọn.
Sổ này có hiệu lực khi brief ghi `film_mode: continuous` (người dùng chọn trên 💡). Code đã xong (kế hoạch
`flow-canvas/docs/thiet-ke/ke-hoach-phim-lien-mach.md`), ý tưởng mới mặc định `continuous` (người dùng nhắc lại 24/10).

## Mẫu đo được (2 phút đầu)
- 125s ≈ 14 clip 8–10s, **dùng gần trọn**. Chỉ ~4 cú cắt cứng (scdet); còn lại là máy quay đi liên tục.
- Đường đi: phố đông → góc phố yên → Clara vội về → dựa tường thở → cửa sổ nhà ấm → *loá sáng* → ký ức: cây thông →
  chị gái trên chiếu nghỉ → Clara chạy lên nhận quà → *tiếng mẹ gọi* → mẹ trong bếp → bố vào ôm mẹ → *qua khung cửa*
  → bàn tiệc → *tiếng bố gọi* → các con chạy vào → *mâm che ống kính* → cả nhà quanh bàn → *ngọn nến loá* → Clara
  ngoài cửa sổ → quay đi → máy lùi và nâng lên toàn phố.
- Chuyển cảnh thấy được: áo khoác lướt sát ống kính (5.75s), loá trắng vàng vào ký ức (37–38s), khung cửa/tường tối
  (61s, 75s, 81s, 90s), ngọn nến/bokeh về hiện tại (104s), đen ngắn trước toàn cảnh cuối (118s).

## 1. Kịch bản: chuỗi tiếp sức
- Phim chia **chuỗi** (sequence) = một chuyến đi liên tục của máy trong một nơi/một thời. Trong chuỗi **không cắt**.
  Giữa hai chuỗi: cắt hoặc đen ngắn, chỉ khi đổi hẳn nơi/thời mà không có đường máy nào nối được.
- Mỗi shot **nhận gậy** từ khung cuối shot trước và **chuyền gậy** cho người/nơi kế tiếp. Sự chú ý đi: người → người
  (Clara → chị → mẹ → bố → bàn tiệc → cả nhà), không nhảy.
- Mỗi shot ghi: mở từ đâu (khung cuối shot trước) · các nhịp theo giây · **động cơ chuyển** · lúc chuyển (giây 3–5) ·
  **hợp đồng khung cuối** · lời thoại (nếu có).
- Động cơ chuyển (chọn một, phải có lý do trong truyện):
  | Động cơ | Cách máy làm | Mẫu |
  |---|---|---|
  | Giọng nói | có người gọi ngoài khung → máy rời người cũ, đi tới người gọi | mẹ "No running in the house, girls!" |
  | Ánh mắt | người trong khung nhìn về đâu → máy tilt/pan theo | chị gái nhìn xuống Clara |
  | Đi theo người | máy bám người đang đi/chạy sang không gian mới | Clara chạy lên cầu thang |
  | Che tiền cảnh | vật/người lướt sát ống kính che gần kín khung → mở ra chỗ mới | áo khoác, khung cửa, mâm, nến |
  | Loá sáng (nhảy thời gian) | đẩy sát vào một điểm sáng phản chiếu → loá trắng vàng < 1s → hiện thời khác | đèn cây thông trên kính → ký ức; ngọn nến → hiện tại |
- **Người mới phải có lối vào nhìn thấy được** (bố bước qua đúng khung cửa mẹ đang nhìn). Người dùng phải sửa prompt
  vì bố "hiện ra từ hư không".
- Nhảy thời gian luôn qua ánh sáng hoặc vật có ở cả hai phía; không sepia, không đen trắng, không ghosting, không
  chồng hình người lớn và trẻ con, không biến người này thành người kia trong khung.
- Clip mở đầu chuỗi tốn 1–2s thiết lập; các clip giữa chỉ giữ khung kế thừa ~1s rồi đi tiếp ("Hold this only very briefly").

## 2. Nhịp trong một clip 8–10s
```
0 – 1.5s   khung kế thừa: đúng khung cuối clip trước, giữ rất ngắn
1.5 – 3s   hành động / cảm xúc chính của người hiện tại
3 – 5s     chuyển: máy đi theo động cơ (giọng nói, ánh mắt, che tiền cảnh, loá sáng)
5 – 7s     người/nơi mới hiện rõ, hành động của họ
7 – 8(10)s ổn định thành khung cuối = hợp đồng cho clip sau
```
Chuyển **không để tới giây cuối** (người dùng ghi trong Avoid: "end-of-shot transition only at the last second").
Một clip có thể có 5–7 nhịp vì cả clip là một đường máy liên tục; đó không phải "nhiều hành động rời".

### Giới hạn vẫn giữ (đóng gói từ bài học 15–20/10 + prompt của người dùng — máy kiểm)
| Luật | Số | Từ đâu |
|---|---|---|
| Nhịp mở là giữ khung (`hold`) từ 0s | ≥1s khi nối tiếp; ≥2s ở clip mở chuỗi | D3 (2–3s ổn định trước khi chuyển); mẫu "Hold this only very briefly" |
| Hành động vật lý (`action`) mỗi clip | ≤3, mỗi người ≤2 | D3 (≤2 hành động/chủ thể); Cảnh 1 nhồi 5 động tác → hỏng đồ vật |
| Mỗi hành động | MỘT cử chỉ ≤14 từ, không "then" | D8 `action_compound` |
| Nhịp khác (giữ, máy, phản ứng) | ≤30 từ | mẫu người dùng |
| Số nhịp | 3–7 | mẫu: 5–7 |
| Chuyển (handoff) mỗi clip | đúng 1, dài 1–2.5s, bắt đầu sau nhịp giữ, xong trước cuối clip ≥2s | D3 (≤1 chuyển cảnh); mẫu 1.5–2s, ổn định 2.5–3s |
| Trong lúc máy chuyển | không ai làm hành động vật lý, chỉ phản ứng | D3 (chuyển cảnh không kèm chuyển động khác) |
| Loá sáng nhảy thời gian | trắng < 1s | mẫu "less than one second" |
| Ảnh tham chiếu clip nối tiếp | ≤3 tên trong cast (+ khung cuối) | MAX_REFS 4 |
| Tên đạo cụ, đồ vật đôi, máy quay như vật | như D8 | 20/10 Cảnh 1 |
| Độ dài prompt | ≤7.500 ký tự (gồm khối style) | mẫu 550–1.050 từ |

## 3. Ảnh tham chiếu
- r2v (`abra_r2v_8s/10s`), 1–3 ảnh: **#1 = khung cuối thật của clip trước** (cắt từ video đã tạo, không phải ảnh vẽ
  ra), + ảnh nhân vật cần giữ mặt. Clip đầu chuỗi: ảnh bối cảnh + nhân vật như cũ.
- Không trái lời dặn D1: không tạo ảnh khung đầu bằng mô hình ảnh; khung cuối lấy từ video thật nên đã đúng.

## 4. Prompt (tiếng Anh, 500–1.000 từ là bình thường ở chế độ này)
> **Ảnh chụp có người trong cảnh (22/10, Old Walt cảnh 6):** không bao giờ cho mặt ảnh quay về ống kính hay nét — Flow tự vẽ mặt người rõ nét và bộ lọc an toàn xoá clip. Viết "ô xám mờ, không đọc được khuôn mặt" hoặc cho thấy mặt sau / mép ảnh (lint `photo_faces`).

Khung 7 khối, theo mẫu:
```
Use the exact ending frame of the previous shot as the starting point.
Preserve exact continuity: same <người>, same <trang phục, tóc, phụ kiện>, same <nơi, đồ đạc>, same <ánh sáng>.
<1–3 câu: shot này làm gì, chuyển sang đâu, vì sao>
Create one continuous 8-second cinematic shot.

SECOND 0 TO 1.5
<khung kế thừa, giữ ngắn>
SECOND 1.5 TO 3
...
SECOND 7 TO 8
<ổn định thành khung cuối>

FINAL FRAME CONTRACT
<ai ở đâu, nhìn đâu, cầm gì, cỡ cảnh, ánh sáng — đủ để clip sau mở đúng từ đây>
This final frame becomes the starting point for the next shot, where <...>.

Camera language
<một dòng mũi tên: A → B → C> · One continuous movement. No hard cut. No whip pan. No handheld shake.

Performance direction
<từng người: cảm xúc, mức độ; không nhìn camera, không diễn quá>

Sound
<lời thoại trong ngoặc kép, ai nói, giọng gì; tiếng động thật: bước chân, cầu thang kêu, tiếng nói chuyện xa>
No music.

Visual style
<khối style chung — dp viết MỘT lần (`style_block`), pipeline tự chép vào mọi prompt>

Avoid
<`avoid_block` chung của phim (pipeline tự chép) + `avoid` riêng của clip>
```
- Mỗi lần thấy lỗi, thêm câu cấm cụ thể vào chính clip đó ("It is very important that the father does not appear from
  nowhere. He must enter through the exact doorway the mother is looking toward.").
- Vẫn giữ các luật gốc của D8 vì chúng do tên gọi chứ không do độ dài: không tả máy quay như một vật (tripod, "camera
  placed"), vật xuất hiện ở 2+ clip phải có ảnh tham chiếu, gọi đúng nguyên văn tên asset, một ảnh đạo cụ = một vật.

## 5. Âm thanh
- **Nhạc nền người dùng tự ghép ngoài.** Phim của hệ thống không thêm nhạc, không viết nhạc vào prompt ("No music").
- **Giữ nguyên tiếng Flow tạo**: lời thoại, tiếng động, không khí. Khi dựng không tắt, không thay audio của clip.
- Lời thoại: câu ngắn, tự nhiên, ghi trong ngoặc kép, đặt trong một khung giây cụ thể.

## 6. Tạo video
- Trong một chuỗi: tạo **tuần tự**. Clip N xong → kiểm khung cuối có đúng hợp đồng → cắt khung cuối → tải lên làm ảnh
  #1 → tạo clip N+1. Các chuỗi khác nhau chạy song song được.
- **1 bản/clip** (người dùng chọn 21/10); hỏng mới sửa prompt theo lỗi rồi tạo lại.
- Clip hỏng giữa chuỗi chặn các clip sau của chuỗi đó: dừng chuỗi, báo người dùng, không tạo tiếp trên khung sai.

## 7. Dựng
- Nối gần trọn từng clip. Chỉ bỏ: vài khung đầu clip sau nếu lặp lại khung cuối clip trước (~0.2–0.5s), và phần chết
  ở đuôi (nếu có). Không thêm chuyển tiếp ffmpeg bên trong chuỗi — chuyển cảnh đã nằm trong clip.
- Giữa hai chuỗi: cắt thẳng hoặc đen ngắn.
- Kiểm mối nối: khung cuối clip N và khung đầu clip N+1 phải gần như giống nhau (cùng người, cùng chỗ, cùng ánh sáng).

## 8. Bài học phim thử "Old Walt" (22/10 — 6 clip, 14 lần viết lại, điểm đánh giá 5.2–7.9)
Người dùng: "mỗi video bạn viết prompt mà tôi gen ra đều phải feedback và viết lại prompt". Mỗi dòng dưới đây là
lỗi "Claude đánh giá" thấy trong clip thật; cột cuối là luật lint chặn nó từ nay.

| # | Lỗi lặp lại (clip) | Vì sao | Viết thế nào | Lint |
|---|---|---|---|---|
| 1 | Cắt cứng ở đầu clip sau (SH03 giây 2, SH05 giây 1.25, SH06) | Clip trước **kết trên hình trừu tượng** (loé sáng, vải mũ đầy khung, giọt mưa cận cực), clip sau phải kéo máy ra để lộ một cảnh rộng mới → Flow cắt thay vì kéo | Chuyển cảnh bằng ánh sáng/che khung **vào và ra trong cùng một clip** (như phim SIU: loé ≤1s rồi hiện cảnh mới), clip **kết trên khung đọc được**: ai ở đâu, làm gì, ánh sáng nào. Clip sau mở trên chính khung đó | `abstract_final_frame` |
| 2 | Khung cuối không giữ được (SH02 loé tan lại thấy bàn, SH04 vết xước vẫn nét, SH05 thấy cả mũ) | Flow không giữ hình mờ / trừu tượng 2s | Như dòng 1 | `abstract_final_frame` |
| 3 | Vật phẳng không lật / rút được (SH01 ảnh "trượt khỏi túi bìa" thì tự hiện ra, SH02 "lật ngửa" thành nhấc lên rồi đặt lại, SH06 lật thì đổi vật) | Flow không hiểu cơ học lật mặt / rút khỏi túi | Vật **đã ở đúng trạng thái** từ đầu shot; hành động là một tiếp xúc đơn giản: chạm, nhấc, đặt xuống | `flip_action` |
| 4 | Ảnh có người: mặt lính hiện rõ, rồi bị bộ lọc xoá (SH02, SH06) | "Mặt ảnh quay về ống kính / nét" → Flow tự vẽ mặt người thật | Ảnh "ô xám mờ, không đọc được mặt" hoặc thấy mặt sau, **viền trắng răng cưa rõ** để vẫn nhận ra là ảnh (nếu không sẽ thành tờ giấy trắng) | `photo_faces` |
| 5 | Máy quay giật / tự đổi khung (SH03 giây 5.5, SH04 sớm 1s) | Động tác máy quá ngắn (1s) hoặc nhiều động tác máy | Một động tác máy chính mỗi clip, ≥1.5s, đổi cỡ cảnh tối đa một bậc (cận → trung) | `camera_beat_short` |
| 6 | Nhìn thẳng ống kính (SH03, SH04) | "nhìn về người chụp ảnh không thấy" = nhìn ống kính | Hướng nhìn có chỗ trong phòng: "về phía cửa, mép trái khung" | `lens_gaze` |
| 7 | Một vật đổi chất liệu (SH05 mũ vải ↔ vỏ thép; SH01 bìa album thành tấm bìa nhạt) | Prompt tự gọi vật bằng hai cách ("olive canvas cover" và "olive steel rim") | Một cụm tên cố định khớp ảnh tham chiếu, không thêm chất liệu khác | (đọc lại khi viết) |
| 8 | Thời tiết sai (SH01 tuyết thay mưa, SH05 trời âm u thay mưa chạng vạng) | "winter night" → tuyết; thời tiết chỉ nói một lần | Tả thời tiết nhìn thấy được trong **mỗi nhịp** có cửa sổ/trời: "heavy rain streaking the window glass"; tránh chữ kéo sang hướng khác ("winter") | (đọc lại) |
| 9 | Chi tiết trang phục trôi (áo Eddie cài/mở, dây chuyền) | Chi tiết không có trong ảnh nhân vật | Chỉ tả những gì ảnh nhân vật cho thấy | (đọc lại) |
| 10 | Dấu ✦ ở góc video (SH04) | **Mọi ảnh asset Flow tạo đều có dấu ✦ góc dưới phải**; Flow chép theo | Hệ thống: xoá dấu trên ảnh tham chiếu trước khi dùng (việc mở) | — |

### Đánh giá cả phim (Agent Review 22/10: kịch bản 7 · clip 7 · **nối 5** · dựng 7)
| # | Lỗi | Vì sao | Từ nay | Chặn bằng |
|---|---|---|---|---|
| 11 | Cây đèn bão + bàn tay lạ chen giữa hai hình rừng (đầu SH03) | Câu mở SH03 gọi cầu nối là "lamp flare" trong khi khung cuối **thật** của SH02 đã là rừng; chữ "lamp" ở thời 1968 → Flow vẽ đèn bão | Ở cầu nối ánh sáng/chất liệu, **không gọi tên vật nguồn của thời/nơi kia**, chỉ tả ánh sáng; câu mở viết theo khung cuối thật | luật `abstract_final_frame` (khung cuối phải cụ thể) + bài học lưu từ đánh giá |
| 12 | Nối 1→2 và 3→4 nhảy khung: tay chạm ảnh thành lơ lửng, Walt hết cười, bạt mọc trên đầu | Flow vẽ lại khung kế thừa hơi khác; hai khung **tĩnh** cạnh nhau lộ mọi khác biệt | Dựng **cắt theo chuyển động**: clip sau vào từ lúc hết nhịp giữ (động tác đầu tiên); clip trước giữ khung tĩnh cuối ≤2.5s | `cut.chain_trims` (tự động) |
| 13 | Hai đoạn giữ chất liệu ~4s ở mỗi chỗ nối, chết nhịp | Giữ cuối clip trước + giữ đầu clip sau cộng lại | Như dòng 12 | `cut.chain_trims` |
| 14 | Người xem không biết "đây là tấm ảnh" (SH04) | Kịch bản dựa vào tiếng "tách" và nội dung ảnh, mà ảnh đạo cụ phải mờ (`photo_faces`) | Khoảnh khắc chụp ảnh then chốt phải **thấy bằng hình**: đứng hình ngắn rút màu đen trắng ở bản dựng | bài học (biên kịch) |
| 15 | Lựa chọn cuối yếu (SH06) | Chỉ có hành động được chọn, không có lựa chọn bị bỏ | Lựa chọn mang thông điệp phải cho thấy **phương án bị bỏ** một nhịp (bắt đầu giấu, khựng lại) trước hành động chọn | bài học (biên kịch) |
| 16 | Mũ Eddie đổi sang vải rằn ri khi ở xa (SH03) | Đạo cụ nhỏ, xa → Flow kéo về kiểu phổ biến | Mỗi clip có đạo cụ: nhắc tên + 2 nét nhận dạng ("plain olive canvas, rust-brown scratch facing the lens") | đọc lại |
| 17 | Đèn/bàn SH01 khác ảnh bối cảnh; bao cát lúc mưa khác lúc nắng (SH05) | Ảnh bối cảnh thiếu đồ đạc đúng cỡ; clip mở bằng cận cảnh không có toàn cảnh giữ hình học | Ảnh bối cảnh có sẵn đồ đạc dùng trong phim (02); quay lại cùng nơi: chép câu hình học từ ảnh tham chiếu ("the same low single-row curved sandbag ring…") | đọc lại |

## Tự kiểm trước khi giao kịch bản / prompt
1. Có thể kể cả phim như một đường máy đi không? Chỗ nào phải cắt thì đó là ranh giới chuỗi.
2. Mỗi shot có động cơ chuyển và lúc chuyển nằm ở giây 3–5?
3. Mỗi người mới có lối vào nhìn thấy được?
4. Hợp đồng khung cuối của shot N có khớp câu "Begin exactly from…" của shot N+1?
5. Nhảy thời gian đi qua ánh sáng/vật ở cả hai phía?
6. Khối Visual style và Avoid giống hệt nhau ở mọi prompt?
