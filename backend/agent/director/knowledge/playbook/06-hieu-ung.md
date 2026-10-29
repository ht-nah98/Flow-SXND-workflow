# Bước 5b — Hiệu ứng kiểu CapCut (dựng bằng ffmpeg)

> **Chế độ:** liền mạch là mặc định (lời dặn B12, 21/10) — đọc [09-phim-lien-mach.md](09-phim-lien-mach.md) trước.
> Các luật về chuyển tiếp ffmpeg giữa các clip dưới đây là của chế độ **cắt-ghép** (chỉ khi người dùng chọn), trừ phần ghi rõ "cả hai chế độ".
> Có hiệu lực khi brief ghi `mode: continuous` (code ở bước 2–4 của kế hoạch); run chưa có trường này vẫn theo luật cắt-ghép.

Hiệu ứng được **quan sát** trên CapCut web (2026-10-16, mục Chuyển tiếp / Hiệu ứng / Bộ lọc) rồi **dựng lại bằng
filter ffmpeg** — không tải, không dùng tài sản của CapCut. Code: `agent/director/effects.py`. Danh mục tên đầy đủ đã
quan sát: `luu-tru/demo-hieu-ung/capcut-danh-muc/` (≈300 hiệu ứng, 130 chuyển tiếp, 360 bộ lọc + ảnh chụp chuyển động).

## Dùng thế nào
Đạo diễn ghi trong kịch bản (miễn phí, áp dụng lúc dựng):
- `film_look` — **một** bộ lọc màu cho cả phim.
- `edit_transition_out` trên mỗi shot — cách clip này chuyển sang clip sau.
- `edit_fx` trên mỗi shot — tối đa 2 hiệu ứng trong clip.

Tên viết theo id không dấu (`nhay-trang`), hoặc tên CapCut có dấu ("Nháy trắng"), hoặc tên tiếng Anh quen thuộc
("light leak", "dissolve") — đều hiểu. Tên lạ → cắt thẳng / bỏ qua, phim không bao giờ hỏng vì một tên sai.
Cả phim dựng trong **một lần encode** (filter_complex), nên thêm hiệu ứng không làm giảm chất lượng.

## Nguyên tắc chọn (quan trọng hơn danh sách)
1. **Phần lớn chỗ nối là cắt thẳng.** Mẫu FMV 53s chỉ có ~3 chuyển cảnh có hiệu ứng. Tối đa 1 chuyển tiếp đặc biệt
   trên 3 chỗ nối.
2. Chuyển tiếp **đánh dấu một bước nhảy của câu chuyện**: thời gian (nháy trắng), ký ức (phai xám, nhòe sáng),
   chương mới / đêm xuống (chồng ảnh mờ dần), cảm xúc bừng lên (bùng sáng vàng), cú sốc (rung trắng, động đất).
3. **Một bộ lọc cho cả phim** theo cảm xúc chủ đạo; đổi tông giữa phim chỉ khi câu chuyện đổi hẳn (dùng `mat-mau`,
   `phai-xam` cho ký ức thay vì đổi bộ lọc).
4. Clip có lời thoại: tránh hiệu ứng che mặt (nhòe sáng mạnh, rung) trong lúc nói.
5. Mở phim: `mo-dan` hoặc `mo-tron`; kết phim: `toi-dan`, `trang-dan` hoặc `dong-ngang` ở clip cuối.

## Chuyển tiếp (CapCut "Chuyển tiếp")
| id | Tên CapCut | Trông thế nào (quan sát) | Dùng khi |
|----|-----------|--------------------------|----------|
| cat | — | cắt thẳng | mặc định, cùng nơi đổi góc |
| nhay-trang | Nháy trắng | loé trắng 0.1s → hiện từ trắng 0.25s | nhảy thời gian, đổi không gian |
| chop-cat-roi | Chớp cắt rời | chớp đen rất nhanh | dồn nhịp, căng thẳng |
| bung-sang-vang | Bùng sáng vàng | loé vàng ấm + vệt sáng tràn qua | kỷ niệm đẹp, hạnh phúc, hoàng hôn |
| thu-phong-loe-sang | Thu phóng lóe sáng | cảnh sau bật vào phóng to + loé trắng | bất ngờ, hành động |
| zoom-giat | (zoom punch) | cảnh sau to 130% thu về trong 0.25s | nhịp nhanh, nhạc mạnh |
| rung-trang | Rung trắng | loé trắng + rung mạnh 0.4s | va chạm, tiếng động lớn |
| chop-nhiet | Chớp nhiệt / Quét cắt rời | lệch màu RGB ở chỗ cắt | công nghệ, glitch |
| hoa-tan | (dissolve) | hai cảnh chồng nhau 0.7s | thời gian trôi chậm, lắng |
| chong-anh-mo-dan | Chồng ảnh mờ dần | tối dần rồi hòa sang | chương mới, đêm xuống |
| phai-xam | (fade grays) | phai qua xám | hiện tại → ký ức |
| lot-ngang / lot-doc | Lướt (whip) | lướt nhanh ngang / dọc | nối hai nơi trong một chuyển động |
| nhoe-chuyen | Băng chuyền điện ảnh | nhòe ngang | vội, chuyển động nhanh |
| lam-mo-pixel | Làm mờ pixel | vỡ điểm ảnh | kỹ thuật số, ký ức vỡ vụn |
| mo-tron | (iris) | mở tròn từ tâm | hé lộ, mở chuyện |
| khoet-ngang | Khoét ngang | các dải ngang thay nhau | quảng cáo, nhịp đồ hoạ |

## Hiệu ứng trong clip (CapCut "Hiệu ứng video")
| id | Tên CapCut | Dùng khi |
|----|-----------|----------|
| vien-toi-nhat | Viền tối nhạt | dồn mắt vào giữa; hợp gần như mọi phim |
| hat | Hạt | chất phim, đi cùng phim-co-dien |
| nhoe-sang | Nhòe sáng | glow mơ màng: ký ức, giấc mơ |
| ro-phim | Rò phim 1/2 | vệt sáng ấm quét qua: hoài niệm |
| lay-net-mo | Lấy nét mờ | mở clip từ nhòe sang nét: thức dậy, hồi tưởng |
| ong-kinh-zoom | Ống kính zoom | đẩy máy chậm vào 8%: tăng cảm xúc |
| thu-phong-nho | Thu phóng nhỏ | lùi máy chậm: buông, kết |
| lac-qua-lai | Lắc qua lại | rung nhẹ cầm tay: hồi hộp |
| dong-dat | Động đất / Dư ảnh động đất | rung mạnh 0.6s đầu: va chạm |
| loi-nho | Lỗi nhỏ / Nhiễu nhẹ | glitch RGB định kỳ |
| mat-mau | Mất màu | màu rút dần thành đen trắng: mất mát |
| mo-dan / toi-dan / trang-dan | Phần mở đầu & kết thúc | mở / kết phim |
| dong-ngang | Đóng ngang | hai dải đen khép lại: màn kết |

## Bộ lọc (CapCut "Bộ lọc")
| id | Tên CapCut | Cảm xúc |
|----|-----------|---------|
| goc | — | màu gốc của Flow |
| phim-co-dien | Phim cổ điển | xưa, gia đình, hoài niệm (ấm, bạc màu) |
| mv-co-dien | MV cổ điển | tình cảm, ấm, hơi bạc |
| suong-mo-dien-anh | Sương mờ điện ảnh | mơ màng, buổi sáng |
| hoang-hon-phim-nhua | Hoàng hôn phim nhựa | teal–cam điện ảnh, du lịch |
| be-am-ap | Be ấm áp | ấm cúng, bếp, đồ ăn |
| anh-nen | Ánh nến | đêm ấm, Giáng sinh, lãng mạn |
| cham-tinh-lang | Chàm tĩnh lặng | buồn, cô đơn |
| lanh-vu-tru | Lạnh vũ trụ | đêm xanh, bí ẩn, công nghệ |
| thanh-pho-ve-dem | Thành phố về đêm | đô thị đêm, neon |
| anh-phim-den-trang / noir-co-dien / giay-phai | Ánh phim đen trắng / Noir cổ điển / Giấy phai | hồi tưởng, kịch tính, trinh thám |
| tong-nau-u-toi | Tông nâu u tối | ảnh cũ (sepia), ký ức rất xa |

## Không dựng lại (và vì sao)
- **Hiệu ứng cơ thể / AI** (bám mặt, tách người): cần mô hình AI của CapCut.
- **Sticker, template bản quyền** (B.Duck, Halloween, Minions, Black Friday): tài sản của CapCut.
- **Lật 3D, khối lập phương, đường hầm 3D**: công phu, ít hợp phim kể chuyện.
- **Hạt bay / pháo hoa / cánh hoa trôi**: cần hệ hạt; nếu cần, phủ một video hiệu ứng miễn phí bản quyền lên trên.
- **Cắt theo nhịp nhạc**: cần phân tích beat — 🧪 việc sau.

Trạng thái: ✅ đã kiểm chứng render (độ dài đúng, không khung đen) trên clip thật dự án xơ dừa 2026-10-16;
🧪 chưa dùng trong một phim hoàn chỉnh do đạo diễn chọn.
