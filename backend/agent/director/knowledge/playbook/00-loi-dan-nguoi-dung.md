# 00 — Lời dặn của người dùng (ĐỌC TRƯỚC MỌI THỨ)

Đây là nguồn sự thật cao nhất. Mọi vai trò (biên kịch, đạo diễn, DP, dựng, QC) và Claude Code đều phải tuân theo.
Nếu một file khác mâu thuẫn với file này, file này thắng. Mỗi dòng ghi: **quy tắc** — lời gốc (ngày) — nơi được ép
trong code. Lời dặn mới được thêm vào đây NGAY khi người dùng nói, trước khi làm việc khác.

⚠️ = người dùng đã phải nhắc lại vì AI quên. Đọc kỹ những dòng này.

## A. Vai trò và quy trình
- **A1. Người dùng chỉ đưa ý tưởng** (chữ, hoặc chữ + ảnh). Claude là biên kịch, đạo diễn, biên tập, người duyệt;
  Flow vẽ ảnh và quay video. — "Tôi chỉ là người lên ý tưởng thôi. biên kịch, đạo diễn sẽ làm phần còn lại." (15/10)
  ⚠️ Nhắc lại 19/10: "Kịch bản được lên từ ý tưởng. Tôi chỉ cung cấp ý tưởng, bạn dựng kịch bản chứ không phải tôi là
  người đưa kịch bản." → Biên kịch phải tự PHÁT TRIỂN ý tưởng thành truyện đầy đủ (thêm nhân vật, nơi chốn, quá khứ,
  biến cố), không chờ người dùng viết sẵn.
- **A2. Từng bước do người dùng bấm**: 💡 ý tưởng → bấm "Viết kịch bản" → 📜 kịch bản (bản tóm tắt + bản đầy đủ) →
  duyệt Ở NODE KỊCH BẢN → "Tạo từng bước" hoặc "Chạy toàn bộ". Không gì tự chạy. — "từ ý tưởng bụp 1 cái có kịch
  bản luôn xong bắt tôi duyệt kịch bản luôn à" (16/10). Code: cổng IDEA / SCRIPT / ASSETS.
- **A3. Thứ tự bắt buộc**: kịch bản → asset nhân vật → bối cảnh → video → dựng. (15/10)
- **A4. Flow nhận từng request một**, xếp hàng có giãn cách; gửi dồn bị chặn PUBLIC_ERROR_UNUSUAL_ACTIVITY. (16/10)
- **A5. Người dùng chọn agent nào chạy trong luồng** (bật/tắt agent duyệt kịch bản, …). — "cho phép tôi chọn xem có
  nên sử dụng những agent nào trong luồng ý tưởng đó không" (19/10). Code: `brief.agents` {producer, editor, qc,
  coach} (mặc định bật; biên kịch, đạo diễn, DP luôn chạy); `PUT /runs/{id}/agents` đổi lúc nào cũng được;
  khối "🤖 Agent trong luồng" trên 💡 và hộp tạo ý tưởng, kèm số lần gọi AI ước tính.
- **A6. Gọn và hiệu quả**: ít bước AI, ít token, tài liệu không chồng chéo. — "tốn token, tốn thời gian quá trong khâu
  xây kịch bản, viết prompt, làm nội dung mà không hiệu quả gì cả… clean lại tư duy, document, flow, quy trình" (19/10)

## B. Kịch bản
- **B1. ⚠️ Kịch bản là một câu chuyện, không phải cảnh ghép.** Trước khi chia cảnh phải trả lời: 🧵 tuyến truyện
  (ai muốn gì → cản trở → lựa chọn → cái giá, nối bằng "nên/nhưng"), 💬 thông điệp, 🎁 giá trị cho người xem,
  ⚖️ luật & cái giá (khi có phép màu/cám dỗ). — "Mỗi lần lên kịch bản bạn cần xác định: Tuyến câu truyện là gì,
  thông điệp truyền tải qua video là gì? Giá trị mang lại cho người xem là gì?" (16/10). Code: `lint.lint_story`.
- **B2. Tự bóc tách**: từ thời lượng ra số shot, số nhân vật, bối cảnh, asset. Câu chuyện liền mạch, có liên kết. (15/10)
- **B3. ⚠️ Không gian và thời gian liền nhau**: các cảnh nối nhau có lý (cùng nơi thì đúng nơi đó, chuyển nơi thì có
  lý do). — "Ảnh gen ra thì phi logic, không có sự kết nối không gian và thời gian." (15/10)
  ⚠️ KHÔNG có nghĩa là đứng một chỗ: truyện đi qua nhiều nơi thì phim đi theo; quay lại cùng phòng phải có diễn biến
  mới. — "Cứ quay đi quay lại mãi ở chỗ ông thì để làm gì?" (16/10)
- **B3b. ⚠️⚠️ Phim ĐA BỐI CẢNH, luôn sáng tạo.** Nhiều địa điểm, nhiều thời điểm (sáng/tối, mùa, quá khứ/hiện tại),
  nhiều nhân vật khi truyện cần, có chuyển cảnh giữa các đoạn — như mọi video mẫu. Không có quy tắc "một nơi chính".
  — "Tôi không hiểu tại sao tư duy kịch bản của bạn bị fix cứng ở 1 địa điểm???? Tất cả video mẫu tôi gửi bạn đều có
  nhiều bối cảnh, chuyển cảnh các đoạn, đa dạng không gian, thời gian, địa điểm, nhân vật." (19/10).
- **B9. Mức độ sáng tạo chọn trên 💡** (bám sát ý tưởng ↔ tự do phát triển). — "Luôn sáng tạo, hoặc ít nhất cho user
  chỉnh mức độ sáng tạo mỗi khi tạo kịch bản." (19/10) Code: `brief.creativity` = faithful (🎯 Bám sát) | balanced (⚖️ Cân bằng,
  mặc định) | bold (🚀 Bay bổng); chọn trên 💡 và hộp tạo ý tưởng; biên kịch và editor đọc theo mức.
- **B4. ⚠️ Ngôn ngữ chọn trên 💡, mặc định tiếng Anh** (bối cảnh nước ngoài, lời thoại và PROMPT tiếng Anh; mô hình
  hiểu tiếng Anh tốt hơn). Phim bối cảnh Việt → tiếng Việt. (16/10). Code: `language`, mẫu prompt tiếng Anh trong `dp.md`.
  Nhắc lại 19/10: "chúng ta làm nội dung video tiếng anh - default. tiếng việt chỉ khi được yêu cầu thôi". Mọi giá
  trị mặc định trong code là `en` (brief, lint, pipeline). Chữ dành cho người dùng đọc (ý đồ, tóm tắt) vẫn tiếng Việt.
- **B5. ⚠️ Ý tưởng có lồng tiếng thì phim phải có tiếng** (Omni Flash tạo được giọng). Có lựa chọn giọng trên 💡.
  — "Tôi có viết là có lồng tiếng giới thiệu sản phẩm… các prompt viết video của bạn đang không có tạo voice" (16/10).

- **B6. ⚠️⚠️ (Chỉ khi người dùng dán sẵn một truyện đầy đủ) Truyện đó là NGUYÊN TÁC — chuyển thể, không viết lại.** Giữ đủ các hồi, sự kiện then
  chốt, nhân vật (kể cả người đã mất), câu thoại chính, lời kết. Thiếu thời lượng thì NÉN mỗi hồi (montage nhanh),
  không bỏ hồi; bỏ gì phải ghi lý do (`source_map`) và báo người dùng (`notes_for_user`). — "Bạn viết tuyến truyện
  thì cắt ngắn những ý tưởng của tôi… Xem chả hiểu câu chuyện là gì" (16/10). Code: biên kịch, đạo diễn, editor đều
  nhận NGUYÊN VĂN ý tưởng; `lint_story` bắt buộc `source_map`. (Lỗi gốc: biên kịch từng chỉ nhận logline 475 ký tự
  tóm từ truyện 5.500 ký tự.)
- **B7. ⚠️ Cho người xem THẤY quá khứ: flashback.** Truyện về mất mát/thay đổi phải có quá khứ hạnh phúc, biến cố,
  rồi hiện tại; cắt xen quá khứ – hiện tại; chuyển cảnh flashback (lia qua cột: ông già → đứa trẻ; cùng nơi hai thời
  ấm/lạnh; đồ vật nối hai thời). — đã dặn 15/10 ("tạo cảm giác flashback"), nhắc lại 16/10: "không có cảnh quay quá
  khứ? cũng không có các flashback để xem câu chuyện".
  ⚠️⚠️⚠️ Nhắc lần 3 (19/10, Daniel v3): "cảnh 7 đang nhảy múa thì cảnh 8 lại là nghe điện thoại… không có cảnh nối,
  không có cảnh chuyển cảnh từ quá khứ hiện tại". → Từ nay MÁY KIỂM TRA (xem B11), không chỉ lời dặn.
- **B11. ⚠️⚠️ Cảnh sau luôn liền mạch cảnh trước; chuyển thời gian phải có CẦU NỐI.** "Dùng yếu tố nào chuyển cảnh thì
  yếu tố đó là cầu nối. Ví dụ sau khi 2 vợ chồng đang nhảy có cuộc điện thoại, daniel trẻ ra nhấc máy chuyển cảnh sang
  daniel hiện tại nhấc máy để nghe"; "zoom gần vào nhẫn rồi chuyển cảnh daniel trẻ đang cầm trong tay chiếc nhẫn cười
  hạnh phúc và vẫy tay với vợ" (19/10). Code: shot `period` + `bridge` (element/outgoing/incoming); lint `time_bridge`
  (khác thời điểm mà không cầu nối → trả về), `bridge_prompt` (vật cầu nối có trong prompt của CẢ hai shot),
  `place_jump` (đổi nơi không lý do → cảnh báo); vòng sửa có mục tiêu viết lại cả shot đứng trước.
- **B8. Truyện có lời kể/thoại thì nên có tiếng; độ dài phải chứa được truyện.** Chọn "Không lời" hoặc thời lượng quá
  ngắn so với truyện → biên kịch báo trong `notes_for_user` để người dùng quyết trước khi tốn credit. (16/10)

- **B10. Kịch bản như bản giao của SciCloud**: lời đạo diễn (ý đồ, chống sáo rỗng), các màn có mốc giờ, một khoảnh
  khắc giữ chân mỗi 25–30s, nhân vật có tính cách + động tác đặc trưng. — người dùng gửi demo SciCloud: "Cũng là sản
  phẩm đầu ra mà chúng ta hướng đến" (19/10). Code: `Story.director_notes`, `hooks`, `Sequence.start_s/end_s`,
  `CastMember.personality/signature`; `lint_story` đòi ≥2 ý đồ và ≥ target_s/30 − 1 khoảnh khắc. Xem `samples/scicloud-agi-quy-trinh.md`.

- **B12. Phim liền mạch, không phải các short ghép lại**: mỗi clip mở từ khung cuối clip trước, chuyển cảnh do máy quay
  tạo ra giữa clip (che tiền cảnh, loá sáng, đi theo giọng nói/ánh mắt), sự chú ý chuyền từ người này sang người kia. —
  người dùng gửi video tự làm "SIU Phẩm Giáng Sinh 1": "Đây mới là kết quả của video tôi mong đợi. Chứ không phải chỉ các
  short riêng lẻ rồi bạn lồng ghép vào với nhau" (21/10). Kế hoạch: `flow-canvas/docs/thiet-ke/ke-hoach-phim-lien-mach.md`;
  mẫu prompt: `samples/siu-giang-sinh/prompts.md`. Liền mạch là mặc định; 1 bản/clip, hỏng mới tạo lại (21/10). Các ghi chú "↳ Chế độ liền mạch" ở D/E chỉ có hiệu lực khi brief ghi `film_mode: continuous`.
  ⚠️ Nhắc lại 24/10: "Liền mạch là mặc định" → ý tưởng mới mặc định `continuous` (hộp tạo ý tưởng, node 💡, API);
  phim cũ không ghi chế độ vẫn đọc là `cut` (chúng được làm theo luật cắt cảnh). Code: `RunCreate.film_mode`, `IdeaDialog`;
  test `test_playbook_does_not_name_a_default_film_mode_the_code_does_not_use`.
- **B13. Nhiều chế độ phim, người dùng chọn** (22/10): "nên là chọn chế độ. Chúng ta có nhiều chế độ, và với mẫu mới
  này thì bổ sung thêm 1 chế độ chia theo keyframe … hệ thống chỉ nâng cấp, bổ sung các chế độ để đa dạng hơn". Ba chế độ:
  `cut` (cắt cảnh) · `continuous` (liền mạch, 09) · `keyframe` (10, mẫu Kling/Artlist). Không bỏ chế độ nào; luật của
  chế độ nào chỉ áp cho phim chọn chế độ đó.
- **B14. Dạng video mới: KHÔNG kể chuyện — quay không khí một buổi biểu diễn** (24/10). Một bối cảnh, cùng không gian,
  chỉ là các cảnh quay của buổi diễn đang diễn ra, người xem nghe nhạc. — "Video đại khái chỉ giống như các cảnh quay
  trong 1 bối cảnh cụ thể, cùng không gian. Không có câu chuyện nào ở đây cả chỉ là quay lại cảnh quay đang diễn và
  nghe biểu diễn âm nhạc. mình không kể chuyện ở dạng nội dung này." Mẫu: `samples/heaven-sound-worship/phan-tich.md`.
  Với dạng này, B1–B11 (tuyến truyện, đa bối cảnh, flashback, cầu nối) KHÔNG áp dụng.
  Chỉ làm **một vòng 1–2 phút rồi lặp** theo độ dài bản nhạc — "Họ làm video có 1p-2p rồi lặp ấy mà. nên mình cũng chỉ
  cần làm như vậy thôi." (24/10; mẫu đo được vòng 124,75s). **Nhiều loại buổi diễn** (người dùng chọn 24/10), mỗi video
  vẫn một bối cảnh. Code: chưa có (chờ kế hoạch).

## C. Asset (ảnh tham chiếu)
- **C1. Nhân vật = 1 character sheet nhiều góc** (cận mặt, toàn thân trước, nghiêng, sau), dùng lại cho mọi clip. (15/10; thêm góc nghiêng 19/10 theo mẫu SciCloud —
  máy quay ngang/profile giữ đúng dáng)
- **C2. Bối cảnh = 1 ảnh / địa điểm, đúng tỉ lệ phim** (16:9 hoặc 9:16), dùng lại cho mọi clip ở đó. (15/10)
- **C3. Ảnh bối cảnh là phông TRỐNG**: không nhân vật, không hành động, không khoảnh khắc kịch tính. Nếu ảnh bối cảnh
  đã là một cảnh phim thì nó hoạt động như ảnh khung đầu và trói mô hình video (bài học 16/10, xem B-lỗi ở 07).
  ↳ Chế độ ambient (B14, thử thật 24/10): ngược lại — ảnh bối cảnh là **buổi diễn đang diễn ra, khán đài kín khán giả
    vô danh**. Ảnh ghế trống làm shot toàn cảnh chép lại khán đài trống. Đám đông ở đây là phông nền, không phải hành
    động (11 §6). Code: lint `amb_venue_crowd`.

- **C4. Một look cho cả phim: gói phong cách** chọn trên 💡 (quy tắc lõi không đổi, biến số, cách sửa lệch — học thư
  viện skill gonghaosnail, 19/10). Code: `styles.PACKS`, `brief.style_pack`; DP ghi `marker` của gói vào dòng Lighting
  của mọi prompt (lint), ảnh asset viết theo look của gói, `film_look` lấy theo gói. Để trống = đạo diễn tự chọn.

## D. Video (Omni Flash)
- **D1. ⚠️⚠️ Mặc định LUÔN là r2v: prompt + asset tham chiếu. KHÔNG tạo ảnh khung đầu rồi làm video từ ảnh.**
  — "Họ không hề cần tạo ảnh trước rồi mới tạo video. Nếu tạo ảnh trước, ảnh mà sai là video khởi động cũng sai"
  (15/10); "chỉ nhập prompt rồi truyền các bức ảnh asset" (15/10); "Mà bạn không nhớ nguyên tắc à… Chọn chế độ
  default luôn là tạo video từ prompt chỉ lấy tham chiếu là asset" (16/10). Đã nhắc 3 lần.
  ⚠️⚠️⚠️ Nhắc lần 4 (19/10): "Sao vẫn có prompt Ảnh???? Thêm cho tôi option… hoặc bỏ luôn chế độ tạo video từ ảnh
  đi." → Giao diện cảnh của phim đạo diễn KHÔNG có ô "Prompt ảnh"; chế độ ảnh→video chỉ là tuỳ chọn tắt sẵn.
  Code: cột `project.video_mode` (mặc định `refs`); API từ chối request ảnh cảnh khi `refs`; node cảnh chỉ hiện
  "Ý tưởng shot" + "Prompt video"; phim đạo diễn không có công tắc ảnh→video.
  ↳ Chế độ liền mạch (B12, 21/10): ảnh tham chiếu #1 là khung cuối THẬT của clip trước (cắt từ video), vẫn là r2v —
    không trái D1. Xem 09.
- **D2. Clip 8–10 giây**, không viết clip 4s; cắt ở bàn dựng. — "làm 4s quá ngắn" (15/10)
- **D3. Mỗi clip ≤ 2 hành động, ≤ 1 chuyển cảnh; 2–3 giây đầu giữ khung ổn định rồi mới chuyển; mỗi clip một ý.**
  Ví dụ: cận cốc cà phê rồi lùi ra toàn phòng; lia qua cây cột thì ông già thành đứa trẻ (flashback). (15/10). Code: `lint`.
  ↳ Chế độ liền mạch (B12, 21/10): giới hạn vẫn giữ nhưng đếm khác — ≤3 hành động vật lý/clip, ≤2/người, 1 lần
    chuyển dài 1–2.5s sau nhịp giữ khung (≥1s khi nối tiếp, ≥2s ở clip mở chuỗi), ổn định ≥2s trước cuối clip;
    các nhịp giữ/máy/phản ứng không tính là hành động. Bảng đầy đủ: 09 §2 "Giới hạn vẫn giữ". Code: `lint._lint_beats`.
- **D4. ⚠️ Bám vật lý**: không vật nào tự hiện, biến mất, biến dạng, lơ lửng; mỗi hành động có nguyên nhân thấy được;
  phép màu = ánh sáng + lộ ra. — "Các hình ảnh biến đổi phi vật lý quá. Chúng ta cần bám sát vật lý hơn." (16/10).
  Code: dòng Physics bắt buộc.
  Nhắc lại (19/10): "cô vợ đang cầm 2 cốc, xong 1 chiếc cốc biến mất, cốc trắng biến thành cốc xanh phi vật lý… Bạn mô
  tả thì mô tả cảnh cẩn thận, rõ ràng và khoa học chứ?" → shot `props` (số lượng, màu, ai cầm, đầu → cuối clip) +
  clip sau bắt đầu đúng trạng thái clip trước để lại; QC đánh FAIL khi đạo cụ hiện/mất/đổi màu/đổi tay.
  (Dòng Props kê mọi vật trong prompt đã bỏ 20/10 — làm prompt dài thêm và nhiều tên vật hơn, xem D8.)
- **D5. Ra chất phim hoạt hình thật**: ống kính, độ sâu trường ảnh, nguồn sáng, diễn xuất có lấy đà và trọng lượng.
  — "Cảm giác đây chưa ra được chất film hoạt hình gì cả." (16/10)
- **D6. Một prompt = MỘT video** (Flow mặc định 2 → tốn gấp đôi credit). — "một vấn đề siêu cấp to lớn" (16/10).
  Code: f15b93d.
- **D7. Đúng tỉ lệ kịch bản**: kịch bản 9:16 thì video 9:16. (16/10)
- **D8. ⚠️⚠️ Prompt VỪA ĐỦ, không viết lung tung.** — "Sao có hành động đơn giản như vậy mà đã lỗi tùm lum trong 1
  video rồi. Nếu mô hình đều quá, thì viết prompt vừa đủ thôi đừng viết lung tung được không?" (20/10, Cảnh 1: prompt
  2.450 ký tự cho "đặt 2 cốc, rót cà phê" → máy quay + chân máy hiện trong bếp, thành 3 cốc, cốc biến thành ấm).
  Gốc: prompt gấp 4 lần mẫu FMV (~570 ký tự) vì rules.md dạy "900–1800"; "camera placed… on a tripod" bị vẽ ra thật;
  ảnh đạo cụ "Twin Coffee Mugs" là ảnh 2 cốc; ấm không có trong khung đầu nên mô hình biến cốc thành ấm; một clip
  nhồi chuỗi 5 động tác. Code: lint `too_long` (≤1000 ký tự), `camera_object` (cấm tripod/"camera placed"…),
  `action_compound` (mỗi hành động một cử chỉ ≤14 từ, không "then"), `prop_single` (ảnh đạo cụ = một vật);
  dp.md "Just enough": mỗi dòng một câu, mỗi vật nhắc một lần, vật dùng tới phải có trong khung từ giây 0.
  Nhắc thêm (20/10, clip 2): "Sao video thứ 2 từ cái bình lại thành cái nồi nấu cơm thế này?… video thứ 2 có ra được
  nội dung ý tưởng shot không vậy?" Gốc: bình cà phê có ở 4 clip mà không có ảnh tham chiếu, clip 1 gọi "steel coffee
  pot", clip 2 gọi "steel pot" → nồi; "a matching empty mug" cạnh cốc của ông từ ảnh MỘT cốc → chỉ còn một cốc, ý
  tưởng shot (đặt cốc thứ hai trước ghế trống) không ra. Code: lint `recurring_prop` (vật ở 2+ clip phải có ảnh tham
  chiếu), `asset_named` (gọi đúng nguyên văn tên asset), `twin_objects` (hai vật giống hệt từ một ảnh → hai đạo cụ
  khác nhau).
  ↳ Chế độ liền mạch (B12, 21/10): giới hạn 1.000 ký tự không áp dụng — prompt mẫu của người dùng 550–1.050 từ, chạy tốt
    nhờ khung trước làm ảnh #1 + khối "Preserve exact continuity" + FINAL FRAME CONTRACT. Các luật còn lại của D8
    (camera_object, recurring_prop, asset_named, prop_single, twin_objects) VẪN áp dụng. Xem 09 §4.

## E. Dựng phim
- **E1. ⚠️ Chuyển cảnh mỗi 5–8 giây**: ghép các shot, hoặc tạo 2 shot để làm chuyển cảnh. — "nguyên tắc làm film làm
  video là luôn chuyển cảnh mỗi 5 hoặc 8s" (15/10). Code: `cut.plan_trims`.
  ↳ Chế độ liền mạch (B12, 21/10): cảnh vẫn đổi mỗi 5–8s, nhưng bằng chuyển động máy BÊN TRONG clip; clip dùng gần trọn,
    không cắt còn 3–7s. Xem 09 §7.
- **E1b. Thời lượng là ƯỚC LƯỢNG, không cố định.** Chọn 2 phút thì phim có thể dài/ngắn hơn tuỳ cắt dựng ra sao;
  truyện và nhịp quyết định. — "Thời gian không nên cố định, thời gian ưu tiên sự linh hoạt" (19/10)
  Code: `lint` chỉ trả lại khi phim ước tính < 0.5× hoặc > 2× (0.75–1.4× không nhắc gì); `cut.plan_trims` giữ phần
  dùng được của mỗi clip (tối đa 8s/clip không lời), chỉ cắt khi phim vượt 1.4×; giao diện ghi "~2 phút (linh hoạt)".
- **E2. Phim cuối luôn chất lượng cao nhất** (master 1080p, một lần encode, yuv420p). (16/10). Code: ead12d1.
- **E3. Hiệu ứng kiểu CapCut dựng lại bằng ffmpeg**, chỉ quan sát CapCut, không tải tài sản. (16/10). Xem 06.
- **E4. Phim cuối có node xem ngay trên canvas.** (15–16/10)
- **E5. Phim ở đúng một chỗ**: `phim/<dự-án>_<id8>/final.mp4`. — "Lúc thì bạn để folder phim, lúc để folder nào đó" (16/10)
- **E6. Nhạc nền người dùng tự ghép ngoài; giữ tiếng Flow tạo (lời thoại, tiếng động).** — "nhạc nền tôi ghép ngoài,
  giữ tiếng lời thoại do flow tạo ra" (21/10). Phim xuất ra không thêm nhạc; prompt ghi "No music".

## G. Giao diện
- **G1. Box co dãn được** (kéo rộng/dài tuỳ ý), kịch bản đọc được theo chiều NGANG, không ép một cột dọc hẹp.
  — "các box của UI nên có khả năng co dãn, không fix cứng chiều dài, chiều rộng… trải dọc này hơi khó đọc" (19/10)
  Code: `NodeFrame` (NodeResizer) trên mọi ô; kích thước lưu ở `canvas_node.w/h`; ô kịch bản rộng ra thì chia 2–4 cột;
  "Đọc toàn bộ kịch bản" mở bảng ngang (mỗi clip một hàng), có nút "Đọc dọc".
- **G2. Mỗi lựa chọn trên giao diện có lời giải thích tiếng Việt** để người dùng biết chọn gì: chế độ phim làm gì, hợp
  với loại video nào, tốn bao nhiêu. — "Ok thêm chế độ ambient nhé, nhưng phải giải thích tiếng việt để user dùng còn
  biết" (24/10). Code: `FILM_MODE_HINT` + `FILM_MODE_HELP` (`FilmModeSelect.tsx`), test canvas.

## F. Học và sửa lỗi
- **F1. Học từ KẾT QUẢ CUỐI của video mẫu**, hiểu cả câu chuyện (hỏi người dùng nếu chưa chắc), đúc kết thành phiên
  bản của mình, cập nhật sổ tay. (15/10, 16/10). Xem `samples/_cach-hoc-video-mau.md`.
- **F2. Tự review, so với mẫu, rút kinh nghiệm dần dần.** — "Bạn là claude, bạn cũng cần review và học tập lại không
  ngừng" (15/10); "rút kinh nghiệm cải thiện dần dần" (16/10). Mỗi lần làm phim ghi vào [07-nhat-ky-bai-hoc.md](07-nhat-ky-bai-hoc.md).
- **F3. Tự xử lý lỗi kỹ thuật**: bị Flow từ chối/xoá thì viết lại và chạy lại; clip lỗi phải có nút tạo lại; không
  ngồi chờ vòng lặp. (15/10). Xem 05.

## Tự kiểm trước khi giao kịch bản (chế độ `cut`; `continuous`/`keyframe`/`ambient` dùng danh sách tự kiểm ở 09/10/11)
0. Người dùng viết sẵn truyện? Đối chiếu TỪNG hồi/sự kiện/câu thoại với beat; có quá khứ & flashback chưa? (B6, B7)
1. Có đủ tuyến truyện, thông điệp, giá trị, luật & cái giá? Cảnh cuối có trả lời thông điệp bằng hành động? (B1)
2. Nhiều bối cảnh/thời điểm như truyện cần, chuyển cảnh có lý, không lặp một phòng? (B3, B3b)
3. Đúng ngôn ngữ, prompt tiếng Anh nếu `en`? Ý tưởng đòi lồng tiếng thì clip có lời? (B4, B5)
4. Mọi clip r2v, ảnh bối cảnh là phông trống? (D1, C3)
5. Mỗi clip 10s, ≤2 hành động, ≤1 chuyển cảnh sau 2–3s ổn định, không có gì tự hiện/lơ lửng? (D2–D4)
6. Mỗi shot dự kiến giữ 5–8s (cao trào ngắn hơn), tổng ≈ thời lượng chọn (lệch được)? (E1, E1b)
7. Cảnh sau nối liền cảnh trước: đổi thời điểm có cầu nối thấy được ở CẢ hai clip; đạo cụ giữ số lượng, màu, tay
   cầm từ clip trước sang clip sau? (B11, D4)
8. Người xem hiểu chuyện chỉ bằng hình nếu phim không lời; có lời thì câu thoại mang thông điệp? (B5, B8)
9. Prompt vừa đủ (≤150 từ), mỗi hành động một cử chỉ, vật dùng tới có sẵn trong khung đầu, không tả máy quay? (D8)
10. Vật xuất hiện ở 2+ clip có ảnh asset riêng và được gọi đúng nguyên văn tên ở mọi clip; không có hai vật giống hệt; mọi
    clip có ảnh bối cảnh; hành động làm được từ vị trí nhân vật; clip mở đúng trạng thái khung cuối clip trước? (D8)
