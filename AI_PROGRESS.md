# AI Progress

## Đợt mới (2026-10-10, auto_pig) - Phối heo: phân tích log THẬT (pig_log.jsonl 3444 dòng + pig_params.json), tắt tự hiệu chỉnh vật lý, thử các đề xuất cấu hình (patch `pig_calib_off.patch`, ÁP SAU `pig_cover_count.patch`; sửa `pig_bot.py`)

Người chơi gửi log thật + pig_params.json kèm 1 bộ đề xuất cấu hình (bật dồn góc `w_corner` 25/`w_inv` 15/`w_buried` 10, tăng `w_bigpair` 20/`w_blocker` 15/`bigpair_min` 4, GIẢM `w_count` 60 và TĂNG `w_cover` 300, `cand_x` bước 2 từ 9 lên 15, `think_s` 2.5-3s).
Phân tích log (file chứa nhiều ván ghi XEN KẼ - chạy nhiều giả lập cùng ghi 1 file; tách bằng cách nối lượt k với k+1 theo `pred_err` đã ghi: 38 chuỗi >= 15 lượt):
- Log do bản code CŨ tạo ra (chạy lại 30 lượt bằng code hiện tại chỉ trùng nước 8/30; mục `top` ghi -33k = phạt cũ, chưa có phạt thua cứng) -> các bản vá 2026-10-09 CHƯA được kiểm trên máy thật.
- Ván thật ~140 lượt còn 11-26 con (TB ~16, giả lập cùng lượt ~12), luôn có nhiều cặp cùng cấp rời nhau (vd 2xL8, 3xL6, 2xL5).
- 16% lượt là "GỘP ẢO": mô phỏng dự đoán gộp mà ảnh thật KHÔNG gộp (462/2916 lượt có khối lượng khớp); 5.6% thật gộp mà mô phỏng không thấy. Khe hở thật giữa 2 con cùng cấp sau gộp ảo: p10 0.28 bán kính, median 2.4 -> phần lớn do con thả lăn/nảy khác dự đoán, một phần là chạm sát chưa tới. Đây là lý do bot xây cặp rời nhau: 1/6 kế hoạch gộp không xảy ra.
- `pig_params.json` của người chơi: gravity 0.8 = CHẠM ĐÁY `CAL_RANGE` (0.8-9), friction 1.185 gần trần 1.3. Trên 2305 cặp lượt liên tiếp (cùng số con): sai số dự đoán tham số mặc định 0.0185 (mẫu 160) so với 0.024 của tham số đã hiệu chỉnh; trên tập kiểm 300 mẫu (hàm mục tiêu = sai số vị trí + 0.1 x lệch số con): mặc định 0.0610, đã hiệu chỉnh 0.0700 -> TỰ HIỆU CHỈNH ĐANG LÀM TỆ. Tìm lại ngẫu nhiên rộng hơn (gravity 0.3-3, friction 0.1-2, merge_eps +-): 2 lần tìm cho kết quả khác nhau (0.0556 và 0.0704 trên tập kiểm), chênh <= 9% -> mặt phẳng phẳng/nhiễu, không có bộ tham số "đúng" rõ; KHÔNG đổi tham số mặc định.
- Sửa: `auto_calib` mặc định true -> FALSE và `_load_params` KHÔNG nạp `debug_dir/pig_params.json` trừ khi `auto_calib: true` hoặc `use_saved_params: true` (cấu hình bước; `gravity/damping/...` ghi đè trong bước vẫn dùng như cũ). Người chơi không cần xoá file cũ.
- `choose_drop` thêm tham số `n_x2` (mặc định 9, đúng như cũ) để chỉnh số vị trí thử cho con kế.
Thử các đề xuất bằng giả lập (chỉ số "con thừa" giữa ván, 8 ván x 170 lượt, seed 41-48, thấp = gọn; bản hiện tại w_count 250 + w_cover 150 = 6.41, SE 0.50): áp TRỌN bộ đề xuất 8.52 (SE 0.85, tệ hơn); chỉ dồn góc/bậc thang/buried 7.71 (tệ hơn); chỉ `w_bigpair` 20/`w_blocker` 15/`bigpair_min` 4: 6.69 (SE 0.55, ngang, không hơn); chỉ `n_x2` 15: 7.48 (SE 0.42, không hơn). => KHÔNG áp các đề xuất này; giữ mặc định hiện tại. Riêng việc giảm `w_count` về 60 là đi ngược kết quả đo (60 -> 250 giảm con thừa 9.73 -> 6.41).
- Nghĩ lâu hơn (`think_s` 2.5-3s) chưa đo được lợi ích riêng (giả lập dùng 0.3s/lượt cho nhanh); lần thử sớm cho thấy ~+11% sống ở 1.2s so với 0.3s nhưng mẫu nhỏ. Có thể đặt `think_s: 2.5` trong bước nếu máy đủ tải.
- Việc nên làm tiếp: chạy bản mới trên máy thật vài chục lượt rồi gửi lại `pig_log.jsonl` (mới, xoá file cũ trước, hoặc chạy 1 giả lập/lần để khỏi ghi xen kẽ) để đo lại tỉ lệ gộp ảo và số con giữa ván.

## Đợt mới (2026-10-09, auto_pig, lần 2) - Phối heo: phạt ĐÈ con to lên con nhỏ + phạt số con mạnh hơn (patch `pig_cover_count.patch`, ÁP SAU `pig_tidy_small.patch`; sửa `pig_bot.py`)

Báo lỗi (2 ảnh: người chơi tự chơi bước 189 chỉ còn ~6 con L10/L7/L5/L4/L2/L1 rất gọn; bot chơi bước 235 có 27-31 con lộn xộn, kẹt): bot không tính cần bao nhiêu con để gộp lên cấp cao mà đè bừa; chỗ có L1/L2 lại thả L3 lên trên -> kẹt.
Chẩn đoán: tổng KHỐI LƯỢNG (2^(cấp-1), bất biến khi gộp) trên bàn ảnh bot ~689 -> biểu diễn nhị phân chỉ cần ~5 con (người chơi: ~6 con), bot giữ 27 con = 22 con "thừa": nhiều cặp cùng cấp nằm RỜI nhau (2xL8, 3xL5, 4xL4, 9xL1) nên không bao giờ chạm nhau (heo không tự di chuyển). Thế cờ ảnh 2 đã gần thua (mọi nước -37k) nên lỗi nằm ở cách xây bàn trước đó, không phải ở lượt cuối. Đo trong giả lập: khi có con cùng cấp và gộp được thì bot gộp 52/64 lần (không tệ) - vấn đề là cấu trúc (vd lượt 61: 2xL7 ở hai đầu bàn).
- `EvalParams` mới: `w_cover`=150 (phạt heo nhỏ bị heo TO HƠN khác cấp nằm ngay trên và chạm: x (1+cấp); thả L3 lên chỗ có L1/L2 bị phạt), `w_far`=0 (phạt cặp cùng cấp nằm xa nhau x 2^cấp - CÓ code nhưng TẮT vì đo không giúp thêm); `w_count` đổi mặc định 60 -> 250. Hàm mới `_cover_far_penalty`, gọi từ `evaluate`. Khoá `w_*` vẫn truyền từ cấu hình bước như cũ nên `w_cover`/`w_far`/`w_count` chỉnh được ngay trong bước.
- Chỉ số mới để đo (ít nhiễu hơn đo lúc chết): "con thừa" = số con trên bàn - popcount(tổng khối lượng), trung bình từ lượt 40 (8 ván x 170 lượt, giả lập). Bộ seed 31-38: bản trước 8.44 (SE 0.42); w_count 250 7.87; w_cover 150 8.51; w_far 8 7.97; w_count 250+w_cover 150+w_far 8 6.39; w_gain 4 7.51; w_gain 10 + w_count 250 7.47; dồn góc (w_corner 60 + w_inv 12) 8.65; w_count 250 + w_far 30 8.47. Bộ seed 41-48 (lặp lại): bản trước 9.73; combo 7.06; w_count 250 + w_cover 150 (BẢN CHỐT) 6.41; w_cover 300 7.02. => phần có ích là w_cover + w_count; w_far, dồn góc, tăng w_gain KHÔNG giúp.
- Sống sót (10 seed mới 51-60, cap 300 lượt, cùng seed, bản trước = commit pig_tidy_small): sống TB 202.7 -> 245.0 lượt (+42.3, SE 11.6), điểm 5588 -> 7817 (+2229, SE 663), số con lúc cuối 25.9 -> 20.5, heo L1-L2 còn lại 11.1 -> 7.7, L10 0.1 -> 0.4/ván; 2 ván sống hết cap 300. Mô phỏng chỉ gần giống game thật (sim bot giữa ván ~13 con, game thật ảnh bot 27 con) - CHƯA test trên LDPlayer thật.
- Vẫn còn khoảng cách với người chơi (~6 con/bước 189 so với ~11-12 con sim bot giữa ván): cần xây theo bậc thang một chỗ để cascade; dồn góc/bậc thang đã thử (w_corner/w_inv) vẫn không giúp trong sim. Hướng chưa thử: nhìn trước sâu hơn (nghĩ lâu hơn: 1.2s/25 vị trí cho thấy ~+11% sống), hiệu chỉnh vật lý bằng log thật.

## Đợt mới (2026-10-09, auto_pig) - Phối heo: phạt THUA cứng, gộp heo nhỏ cho gọn bàn, thả vào chỗ trũng (patch `pig_tidy_small.patch`, áp lên repo GitHub commit 1c02169; sửa `pig_bot.py`)

Báo lỗi (kèm ảnh bàn lúc bước 252, điểm 71026): bàn tự chơi bị KẸT - tháp heo dựng sát tường trái (L8-L7-L5-L3, con trên cùng cách vạch ~10%), 3 con L5 và 2 con L3 nằm rải rác không chạm nhau; yêu cầu tối ưu gộp heo nhỏ (nhất là L1) nhưng vẫn giữ chỗ gộp con to; ưu tiên cao nhất là KHÔNG CHẾT rồi gộp heo cao dần; ví dụ con trên cùng là L3 sát mép thì không gộp L3 nếu L4 nở ra tràn viền = thua.
Chẩn đoán (đo bằng giả lập, 8 ván bản cũ cùng seed): chết ở lượt 189-264 (TB 221); lúc chết trên bàn 23-27 con mà 8-13 con là L1-L2 (có ván 7 con L1, 6 con L2 rải rác), và có tới 4 cặp cùng cấp L4-L7 nằm riêng không chạm nhau. Nguyên nhân trong `evaluate`: gộp heo nhỏ gần như không được thưởng (L1+L1 chỉ +4 điểm, `w_big_low` còn cộng điểm cho MỖI con heo nên gộp lại bị trừ; `w_area`=500 quá nhỏ: 1% diện tích chỉ đáng 5 điểm) nên bot thờ ơ với việc để heo nhỏ rải rác. Thua cũng chỉ bị phạt mềm (`danger_line`), không có phạt thua cứng. Kiểm trên đúng thế cờ trong ảnh: bot (cũ) chọn x~22% (thả L3 lăn vào L3 trên cùng, gộp dây chuyền L4->L5->L6, đỉnh tụt từ 10% lên 21.5% H) - nước này mô phỏng là an toàn, không phải lỗi chọn nước ở khung hình đó; lỗi nằm ở cách bàn bị dồn thành thế kẹt trước đó.
- `EvalParams` mới: `w_lose`=1e6 + `lose_margin`=0.02 (THUA cứng: mép trên heo sau khi gộp nở xong cao hơn 2%H tính từ đỉnh khung -> phạt 1e6, gần như loại nước đó; các phép thử độ bền x/độ rộng/vật lý cũng dùng `evaluate` nên nước nào chỉ cần lệch chút là thua cũng bị trừ rất nặng - đúng ví dụ "L3 sát mép thì không gộp nếu L4 tràn viền"); `next_weighted`=True (nhìn trước con kế: trung bình có TRỌNG SỐ theo tỉ lệ thả thật `LEVEL_PROB` L1 .31/L2 .28/L3 .28/L4 .14 thay vì trung bình đều); `w_count` đổi mặc định 0 -> 60 (mỗi con heo còn trên bàn -60: mỗi lần gộp, kể cả L1+L1, bớt 1 con = +60); `w_skyline`=3000 (phạt chiều cao TRUNG BÌNH mặt đống 24 cột: heo nhỏ chui vào chỗ trũng thay vì chất lên đỉnh); `w_small_cnt` (phạt riêng heo cấp <= `small_max`=3) và `w_tower` (phạt cột cao vọt so với trung vị) có sẵn nhưng mặc định TẮT (0).
- `choose_drop`: thêm 2 tuỳ chọn cuối (mặc định bật, chữ ký cũ vẫn gọi được): `valleys` (thêm tối đa 4 vị trí thả ở tâm các chỗ TRŨNG của mặt đống, hàm `_valley_xs`) và `refine` (thử thêm 2 điểm sát hai bên mỗi nước trong top 3 sau vòng thô, bước ~0.3 x khoảng cách lưới). Hàm mới: `_col_tops`, `_tower_penalty`, `_valley_xs`; hằng `LEVEL_PROB`. `run_auto_pig_step` truyền thêm `lose_margin`/`next_weighted`/`small_max` (vào EvalParams) và `valleys`/`refine` từ cấu hình bước; mọi khoá `w_*` vẫn truyền như cũ. Không đổi tên hàm/biến/tham số cũ.
- Đo bằng giả lập đến khi thua (thua = heo chạm vạch trên, cap 300 lượt, `think` 0.3s, 15 vị trí, topk 4; thế giới dùng vật lý khác mô hình bot): 8 ván/biến thể (seed 1-8) sống TB lượt: bản cũ 221; chỉ thêm phạt thua cứng+nhìn trước có trọng số 214; +`w_count`=60 229; +`w_small_cnt`=150 213; `w_area` 8000+`w_count` 60 223; `w_area` 20000+`w_count` 120 208; +`w_skyline` 3000 +`w_count` 60 237; `w_skyline` 8000 222 -> mọi biến thể quanh 210-237, chênh nhỏ hơn nhiễu (SE ~9-10 lượt). Bản CHỐT (mặc định hiện tại = phạt thua cứng + nhìn trước có trọng số + `w_count` 60 + `w_skyline` 3000 + `valleys` + `refine`) so với bản cũ trên 16 seed MỚI (11-26) xen kẽ cùng seed: sống TB 234.6 so với 216.5 lượt (+18.1, SE 13.3, ~+8%), điểm 6668 so với 5732 (+936, SE 570, ~+16%), heo L1-L2 còn trên bàn lúc chết 9.7 so với 11.1; 2 ván bản mới sống tới hết cap 300 lượt (bản cũ 0 ván). Chưa đạt mức ý nghĩa thống kê (z ~ 1.4) nhưng 3 lần đo độc lập đều cùng chiều và không thấy hại; KHÔNG khẳng định cải thiện chắc chắn. Chạy nghĩ lâu hơn như thật (1.2s, 25 vị trí, topk 6) trên bản cũ, seed 1-4: 256/209/271/269 (TB 251) so với 211/217/264/214 (TB 226.5) ở cấu hình nhẹ - gợi ý thời gian tính có ích (~+11%) nhưng mẫu quá ít.
- Giới hạn lý thuyết (để đặt kỳ vọng): mỗi lượt đổ vào bàn trung bình ~6.2 "khối lượng" (2^cấp); L10 = 1024 và không biến mất nên ~lượt 330 cũng đầy dù xếp hoàn hảo; bot đang chết quanh lượt 220-235 (bàn ~60% diện tích) -> còn dư địa nhưng khó tăng mạnh bằng chỉnh trọng số.
- Chưa test trên LDPlayer thật (chỉ giả lập + ADB giả ở chế độ `test: true`: chạy 2 lượt không lỗi, thả x=21% trên đúng ảnh bàn kẹt). Cách chỉnh nếu thấy bot quá thận trọng/hay bỏ gộp: `w_lose: 0` (tắt phạt thua cứng), `w_count: 0`, `w_skyline: 0`, `valleys: false`, `refine: false`; thử thêm `w_small_cnt: 150` hoặc `w_tower: 3000` (đã đo: không khác biệt).

## Đợt mới (2026-10-08, auto_pig) - Phối heo: thưởng/phạt CẶP LỚN theo cấp số nhân (patch `pig_bigpair.patch`, ÁP SAU `pig_safety_l10.patch`; sửa `pig_bot.py`)

Người chơi nhắc: đã hứa 4 việc cho mục tiêu L10 nhưng mới làm 2 (phạt thua nặng; đo qua nhiều lượt bằng số L10). Còn thiếu: thưởng cấp số nhân khi 2 con L8/L9 sắp chạm nhau, và giữ chỗ cho chúng chạm nhau. Đợt này làm nốt.
- `_bigpair_score` (MỚI) + `EvalParams.w_bigpair=6`, `w_blocker=4`, `bigpair_min=5`: với mỗi cặp CÙNG CẤP >= L5 có khe <= 2r: nếu KHÔNG có con khác chắn giữa (con nào có tâm cách đoạn nối < 0.9 bán kính của nó, nằm giữa) thì thưởng w_bigpair x 2^cấp x (1 - khe/(2r)); nếu CÓ chắn thì phạt w_blocker x 2^cấp. Kiểm tra: 2 L9 gần nhau không chắn +2962; có L5 chắn giữa -2048; ảnh thua Screenshot_20261008-194340 (2 L9 bị L5/heo nhỏ chắn) -2048. Tắt: w_bigpair=0, w_blocker=0.
- Đo (pig_selfplay_survival.py, thua = heo chạm vạch trên, cap 300 lượt, 5 seed/bên, cùng seed): C (patch trước) sống TB 221 lượt, 0 L10, điểm 6184; D (thêm cặp lớn, MẶC ĐỊNH MỚI) 230 lượt, 1 L10 (seed 4, 285 lượt), điểm 6904; E (D + dồn góc/bậc thang w_corner/w_inv/w_buried/w_dup) 204 lượt, 0 L10, điểm 5462 -> dồn góc/bậc thang làm TỆ hơn, giữ TẮT. D hơn C nhưng 5 ván là quá ít, nằm trong nhiễu: KHÔNG khẳng định cải thiện, chỉ là không thấy hại và khớp yêu cầu.
- Việc "giữ chỗ trống để 2 con to chạm nhau" hiện chỉ có qua phạt chắn giữa + `w_flat`; chưa có cơ chế chủ động đẩy 2 con to lại gần nhau. Chưa test trên LDPlayer thật.

## Đợt mới (2026-10-08, auto_pig) - Phối heo: phạt THUA nặng nhất (đỉnh hiệu dụng khi gộp nở ra), thưởng L10, đo bằng giả lập đến khi thua (patch `pig_safety_l10.patch`, áp lên repo GitHub commit 624ad4b trở đi; sửa `pig_bot.py`, thêm `pig_selfplay_survival.py`)

Dữ kiện mới từ người chơi: không giới hạn số lượt (hết thể lực thì tự chơi tiếp sau), L10 là cấp cuối KHÔNG gộp thêm và KHÔNG biến mất khỏi bàn, thua là điều phải phạt nặng nhất. 2 ảnh thua (Screenshot_20261008-192119: bước 261, có L10 + L9; Screenshot_20261008-194340: bước 244, 2 con L9 ở đáy chưa ghép được): nhận diện L10/L9 ĐÚNG (L10 r=183.6 so với danh nghĩa 186.8, điểm 0.98); cả hai thua vì con trên cùng chạm vạch (mép trên -4px và -2px so với đỉnh khung), cả hai nằm trên cột cao dựng sát tường phải.
Phân tích: (1) trước con thả cuối, trạng thái đã nằm TRONG vùng nguy hiểm cũ (đỉnh +68px / +114px; `danger_line` chỉ 79px) nên mọi nước đi đều xấu; (2) ảnh 2: 2 con L9 cùng cấp ở dưới cột L7-L6-L4, nếu gộp thành L10 (bán kính tăng ~46px) sẽ đẩy cả cột lên ~160px => đỉnh hiệu dụng -45px, tức trạng thái đó ĐÃ coi như thua nhưng hàm chấm cũ chỉ nhìn đỉnh hiện tại (+114); (3) hình học: L10 đường kính ~374px > nửa bề ngang bàn (692px): 2 con L10 không thể nằm cạnh nhau trên sàn, con thứ 2 phải nằm cao hơn (đỉnh khoảng +216px), 3 con L10 không vừa => ước lượng tối đa ~2 L10/ván, và sau L10 đầu tiên (chiếm ~20% diện tích, không biến mất) bàn rất chật.
- `effective_top(balls, W)` (MỚI): đỉnh cao nhất tính cả cú đẩy lên khi heo đỡ bên dưới nở ra (con k đỡ con j và k còn gộp được: có >=2 con cùng cấp trên bàn hoặc cấp<=4 -> mép trên j bị đẩy ~2*dr, cộng dồn theo chuỗi đỡ). Ước lượng hình học bảo thủ, KHÔNG phải vật lý thật của game.
- `surface_roughness` (MỚI): độ lệch chuẩn chiều cao 12 cột bề mặt / H (cột cao hẹp sát tường = gồ ghề).
- `EvalParams` mới (mặc định đã bật, tắt = 0/False): `reserve=True` (dùng đỉnh hiệu dụng trong phạt nguy hiểm), `w_safe=30000` + `safe_line=0.25` (phạt mềm bình phương khi đỉnh hiệu dụng còn cách vạch < 25% H), `w_flat=800`, `w_l10=3000` (thưởng mỗi con L10 trên bàn). Có thêm `w_count` (mặc định 0; thử 40/100 không khác biệt).
- Đo bằng `pig_selfplay_survival.py` (thua = heo chạm vạch trên; cap 300 lượt; 4 ván/bên, cùng seed; world dùng tham số vật lý thật từ phiên chơi): ván giả lập thua ở ~200-260 lượt (khớp 2 ván thật 244 và 261). A = mặc định cũ: sống TB 210 lượt, 0 L10; B = reserve+w_safe: 219 lượt, 0 L10; C = B+w_flat+w_l10 (mặc định mới): 228 lượt, 1 L10 (seed 2), maxlv TB 9.2 so với 8.8. MẪU QUÁ NHỎ (4 ván), chênh lệch nằm trong nhiễu - KHÔNG khẳng định cải thiện; chọn C làm mặc định vì khớp yêu cầu "phạt thua nặng nhất" và mục tiêu L10, không vì số liệu đủ mạnh.
- Chưa test trên LDPlayer thật. Chưa thử: tìm kiếm sâu hơn (tăng `think_s`, `n_x`, `topk`; luận văn LIACS cho thấy Monte Carlo/nhìn trước nhiều bước là hướng mạnh nhất), hiệu chỉnh vật lý cho cú đẩy khi gộp nở ra bằng log thật (cần `pig_log.jsonl` của đúng các lượt cuối trước khi thua).

## Đợt mới (2026-10-08, auto_pig) - Phối heo: nghiên cứu thuật toán + tự chơi giả lập A/B + dừng thể lực chính xác (patch `pig_strategy_stamina.patch`, ÁP SAU `pig_physics_fix.patch`; sửa `pig_bot.py`, thêm `pig_selfplay.py`)

Báo lỗi (kèm `debug_pig.rar` 1 ván 13->128 lượt, thể lực 116->26): heo L1 thả linh tinh kẹt nhiều, con to nhất không dồn về góc (ván thật: L8/L9 nằm GIỮA bàn x~280-410, 5-7 con L1 kẹt trong khe, 3 con L4 rời nhau), yêu cầu "dưới 10 thể lực thì dừng" và tìm thuật toán tốt nhất.
Nghiên cứu (luận văn Leiden LIACS 2025 "Creating an AI that plays Suika game" + hướng dẫn người chơi): (1) tự chơi bằng MÔ PHỎNG vật lý rồi chọn nước đi (Monte Carlo, nhìn trước 1-2 lượt) cho điểm trung vị ~6000-7000, hơn người chơi giỏi (~5000) và hơn hẳn RL/Q-learning (~2300-3000) và luật "thả lên con cùng cấp" (~3500-4000) -> bot hiện tại (mô phỏng + chấm điểm + robust) ĐÃ là hướng tốt nhất; (2) chiến thuật người chơi: dồn con to vào 1 góc, xếp cấp giảm dần như bậc thang để thả 1 con gây gộp dây chuyền, tránh thừa heo cùng cấp, đừng để heo nhỏ bị kẹt giữa 2 con to cùng cấp.
Thử nghiệm: thêm `_structure_penalty` (thưởng con to nhất sát góc `w_corner`, phạt đảo thứ tự `w_inv`, phạt heo nhỏ bị chôn `w_buried`, phạt thừa heo cùng cấp `w_dup`, `corner_side`) và A/B bằng `pig_selfplay.py` (130 lượt/ván, con cầm ngẫu nhiên 1-4 theo tỉ lệ log thật, "thế giới" dùng tham số vật lý thật từ phiên chơi còn bot dùng mô hình riêng, nhiễu bấm 3px; cùng seed 1-8): cũ điểm TB 3574 (±217), mới (30/6/3/2) 3506 (±219), v2 (60/12/8/0) 3338 (±162) -> KHÔNG khác biệt có ý nghĩa; con to nhất sát góc hơn chút (khe 0.166 -> 0.123) nhưng heo L1-2 cuối ván nhiều hơn (5.2 -> 6.6). Kết luận: giữ code nhưng mặc định TẮT (`w_corner=w_inv=w_buried=w_dup=0`); bật thử bằng EvalParams. KHÔNG khẳng định cải thiện điểm. Lưu ý: thế giới giả lập chỉ gần giống game thật (điểm giả lập ~3500 chưa so trực tiếp được với "Điểm ván này" của game).
- Dừng thể lực: trước đây đọc OCR mỗi 25 lượt nên có thể tụt xa dưới 10 (ván thật dừng ở lượt 128 khi còn 26 vì hết lượt cấu hình, chưa kiểm tra). Nay `stamina_every` mặc định 5, tự trừ 1/lượt giữa 2 lần đọc, còn <= `min_stamina`+12 thì đọc mỗi lượt; dừng khi < `min_stamina` (mặc định 10). Test ADB giả: dừng ngay khi 9 < 10.
- `pig_selfplay.py` (MỚI): công cụ A/B không cần LDPlayer. Ván 130 lượt ~65s; kết quả dao động mạnh nên cần >= 8 ván/bên (kể cả cùng seed cũng khác nhau vì giới hạn thời gian nghĩ).
- Gợi ý bước tiếp theo (chưa làm): bước nghĩ sâu hơn (nhìn trước 2 lượt với con kế ngẫu nhiên 1-4 đã có ở `next_levels`; thử tăng `n_x`, `topk`, `think_s` và đo bằng selfplay), hiệu chỉnh `damping` (ván này tự hiệu chỉnh chạm sàn 0.3).

## Đợt mới (2026-10-08, auto_pig) - Phối heo: tính đến heo bị NẢY khi chạm vai con khác + chọn nước đi chịu được sai khác vật lý (patch `pig_physics_fix.patch`, ÁP SAU `pig_width_fix.patch`; sửa `pig_bot.py`)

Báo lỗi (kèm `debug_pig.rar`: 2 phiên 165 + 72 lượt, ảnh lượt 58-72): (1) heo thả xuống chạm con nằm phía trên rồi bị nảy ra chỗ khác, không rơi tới con cần gộp; (2) con thả sát mép cũng lăn xuống dưới, không nằm yên sát mép.
Đối chiếu log + ảnh: lượt 64 thả L2 x=372 - mô phỏng cho L2 rơi thẳng xuống gộp L2 (362,540) rồi gộp tiếp L3 (ra L4), nhưng đường rơi chạm VAI L3 (432,480) TRƯỚC (cách tâm 60 < 91) nên L2 thật bị văng trái tới (158,508), không gộp gì. Lượt 65 thả L1 x=79 rơi lên vai L3 rồi lăn: dự đoán dừng (246,477), thật (312,496) - lăn xa hơn dự đoán ~66px.
Số liệu: `pig_params.json` đã lưu có `rad_scale` = 1.03 = CHẠM TRẦN `CAL_RANGE` (heo thật to hơn vòng đo -> hiệu chỉnh bị kẹt). Hiệu chỉnh lại trên 233 cặp lượt liên tiếp của 2 phiên (khoảng thử rộng hơn): sai số TB 0.063 (mặc định cũ) / 0.049 (đã lưu) -> 0.046 với gravity 1.84, damping 0.78, friction 0.81, elasticity 0.097, rad_scale 1.02. Chia 4 nhóm theo độ PHÂN TÁN giữa các bộ tham số vật lý khác nhau: sai số thật tăng 0.034 -> 0.025 -> 0.044 -> 0.085 (nhóm phân tán cao sai gấp ~2.5 lần) => nước đi mà kết quả đổi nhiều theo ma sát/nảy là nước đi dự đoán kém tin cậy.
- `SimParams` mặc định đổi theo số đo trên (gravity 1.84, damping .78, friction .81, elasticity .097, rad_scale 1.02). `CAL_RANGE`: `rad_scale` (0.90, 1.08), `elasticity` (0, 0.8). LƯU Ý: `debug_pig/pig_params.json` trên máy bạn sẽ ghi đè mặc định - xoá file này (hoặc bật reset_params) để dùng số mới; tự hiệu chỉnh (`auto_calib`) vẫn chạy tiếp.
- `first_contact(balls, x, r)` (MỚI): heo rơi thẳng tại x chạm con nào TRƯỚC (tâm lệch dx, điểm chạm). `PHYS_VARIANTS` (MỚI): 4 biến thể vật lý (trơn x0.5, nhám x1.6, nảy x3.5, rơi mạnh).
- `choose_drop`: (d) thử mỗi nước đi với 4 biến thể vật lý, phạt `w_phys` (0.8) x điểm tụt trung bình + `w_phys_gain` (1.5) x điểm gộp biến mất; (e) phạt `w_graze` (0.6) x điểm gộp khi đường rơi chạm vai con KHÁC (không phải con cùng cấp gộp ngay), nặng hơn khi chạm lệch tâm; thưởng `w_direct` giờ chỉ khi chạm ĐẦU TIÊN đúng con cùng cấp (trước đây chỉ xét x gần tâm, bỏ qua con chắn phía trên). Tắt từng phần: `w_phys: 0`, `w_graze: 0`.
- Thử lại trên 2 lượt lỗi: lượt 64 đổi x 362/372 -> 346 (hết chạm sâu vai L3); lượt 65 đổi x 79 -> 292 (không còn thả lên vai L3). 17/32 lượt cuối đổi lựa chọn; thời gian ~1.3s/lượt (trong `think_s`). Vòng lặp ADB giả 3 lượt chạy ổn.
- CHƯA xử lý riêng "thả sát mép": log cho thấy thả x=24.9 (sát tường) dự đoán khá đúng (sai số 0.008-0.010); phần còn lại là lăn xa hơn dự đoán (ví dụ lượt 65). Nếu vẫn thấy lăn khỏi mép: gửi log + ảnh đúng lượt đó (cần lượt có x gần tường) để chỉnh friction/rolling.
- CHƯA test trên LDPlayer thật; các số liệu trên là đối chiếu mô phỏng với log, không phải điểm ván thật.

## Đợt mới (2026-10-08, auto_pig) - Phối heo: đồng nhất ĐỘ RỘNG (bán kính) cùng cấp + chấm điểm chịu sai số độ rộng (patch `pig_width_fix.patch`; sửa `pig_bot.py`)

Báo lỗi (kèm ảnh debug pig_0034/pig_0035): bot thả heo xuống nhưng không chạm được heo cùng cấp (vd thả L1 không chạm L1 kia) - nghi tính sai độ rộng.
Nguyên nhân (đo trên 2 ảnh): (a) con đang CẦM dùng bán kính danh nghĩa `R_FRAC` +-3px (`detect_held` thử dr -3/0/+3) còn heo trên BÀN dùng bán kính Hough đo được - heo cấp 1 trên bàn đo ra ~0.91 x danh nghĩa (r~22.7 vs 24.9), L4 ~0.97 -> cùng cấp nhưng 2 bán kính khác nhau, mô phỏng tưởng chạm/lọt khe trong khi thực tế không; (b) `choose_drop` chỉ kiểm độ bền theo lệch x (+-1.2%), KHÔNG kiểm độ bền theo độ rộng, nên nước đi chỉ đúng khi khe/tiếp tuyến chính xác từng px vẫn được chọn (thử trên trạng thái pig_0034: thả L2 x=293 mô phỏng ra chuỗi gộp 60 điểm ở rad_scale 1.0/1.08 nhưng 0 điểm ở 1.04/1.12/1.16 - kết quả nhảy theo độ rộng, còn ngoài đời con L1 kẹt giữa L4-L3 không tụt xuống); (c) kiểm độ bền x cũ gọi `simulate` thiếu độ cao thả y0 (khác lúc chọn).
- `RadiusBook` (MỚI): nhớ tỉ lệ bán kính thật từng cấp (trung bình trượt từ vòng viền heo trên bàn, bỏ điểm < 0.7 hoặc tỉ lệ ngoài 0.85-1.12); `update(pigs, W)`, `r(lv, W)`, `snap(pigs, W)` (mọi con cùng cấp dùng 1 bán kính, lệch tối đa +-5% so với r đo riêng của con đó). Cấp chưa từng thấy lấy trung bình 2 cấp gần nhất.
- `run_auto_pig_step`: mỗi lượt cập nhật `rbook`, `balls` đã snap, bán kính con cầm (cả khi đọc lại cấp trước lúc thả) đổi sang `rbook.r(cấp, W)` (mép trên con cầm giữ nguyên, tâm dời theo). Tắt bằng `radius_fix: false` trong bước.
- `choose_drop`: thêm bước (c) kiểm độ bền theo ĐỘ RỘNG - mô phỏng lại nước đi với bán kính x(1 +- `rad_jit`) (copy `SimParams.rad_scale`); phạt `w_width` x phần điểm tụt, và phạt thêm `w_width_gain` x phần điểm gộp BIẾN MẤT. Sửa kiểm độ bền x: truyền đủ y0 thả. `EvalParams` thêm `w_width` (0.8), `w_width_gain` (1.5), `rad_jit` (0.04); đặt `w_width: 0` để tắt.
- Test (sandbox, ảnh pig_0034/0035 là ảnh có vẽ chú thích nên nhận diện không hoàn hảo): nhận diện + chọn x chạy được, vòng lặp `run_auto_pig_step` chạy 2 lượt với ADB giả không lỗi. CHƯA test trên LDPlayer thật: chưa kiểm chứng được độ rộng thật của game (collision radius so với vòng viền). Nếu vẫn không chạm: gửi `debug_pig/pig_log.jsonl` + ảnh các lượt; có thể thử `rad_jit` 0.06, `w_width` 1.5, hoặc `rad_scale` 1.03.
- LƯU Ý: mục "pig_l1_direct.patch" (w_travel, info['travel']) ghi bên dưới KHÔNG có trong code repo hiện tại (`grep w_travel pig_bot.py` rỗng) - có thể chưa được đẩy lên; patch này không phụ thuộc nó.

## Đợt mới (2026-10-08, auto_pig) - Phối heo: không đọc nhầm popup điểm thành heo, chờ bàn cờ YÊN mới đọc, thả thẳng tâm, chống kẹt heo nhỏ chen giữa heo to (patch `pig_stable_fix.patch`; sửa `pig_bot.py`)

Báo lỗi (kèm `debug_pig.rar` 19 ảnh + `pig_log.jsonl`): (1) hay thả LỆCH tâm - vd có con L1 nhưng không thả thẳng vào L1 mà thả sang cạnh; (2) đọc ảnh SỚM, đọc nhầm ĐIỂM thành heo; (3) thả L1/L2 lung tung chen vào giữa làm các con to không chạm nhau để gộp được.
Nguyên nhân (đối chiếu ảnh + log): (a) băng điểm nổi "+50 / +6 / +130" (nền xám-nâu mờ, icon xu/hồng + chữ đỏ) hiện ngay sau khi gộp, đúng lúc con kế xuất hiện -> Hough nhận icon/chữ thành heo cấp 1 viền xám (hoặc viền đỏ) ở giữa bàn (log lượt 2,4,5,12,13: `before` có `[1, ~337, ~250, ~25]`), kéo `pred_err` lên 0.13-0.26 và làm mô phỏng sai; (b) `_wait_ready` trả khung ngay khi con kế vừa hiện nhưng heo còn đang gộp/hiệu ứng + con cầm còn đang trượt vào chỗ (lượt 11: nhận con cầm ở sai chỗ, cấp 1 trong khi thực tế đang cầm cấp 3 -> thả sai); (c) ứng viên thả của `choose_drop` gồm cả tâm heo cùng cấp (x = b.x) lẫn cạnh tiếp tuyến (b.x ± (r+r')*0.97) với CÙNG điểm gộp nên hay chọn cạnh tiếp tuyến (mong manh: lệch vài px là không chạm, không gộp); (d) hàm đánh giá chỉ phạt heo nhỏ bị kẹp >= 2 heo to với trọng số nhẹ (`w_trap`) nên L3 nằm giữa 2 L5, L1/L2 kẹt giữa tường và L5 không bị phạt đủ.
- `find_popups(img, box)` (MỚI): tìm băng điểm nổi bằng mặt nạ xám-nâu mờ (V 55-150, S 25-110, H 10-32) + hình thái, lọc theo hình chữ nhật dẹt (w >= 70, h 18-140, w/h >= 1.6). `_in_popup(cx, cy, r, popups)` (MỚI). `detect_pigs(img, box, thr, popups=None)`: thêm tham số `popups` (None = tự tìm), bỏ vòng tròn có TÂM trong băng điểm; heo cấp 1 (viền xám) bắt buộc `_pink_inside` (như con đang cầm). Thử trên 19 ảnh debug: mất đúng các heo giả (lượt 12, 13), không mất heo thật nào.
- `_wait_stable(adb, box, step, should_stop, frame, log)` (MỚI): sau khi con kế hiện, chụp lặp tới khi (1) hết băng điểm (tối đa `popup_max` 3s), (2) ảnh vùng bàn (đã che băng điểm) khác nhau < `stable_diff` 0.7 giữa 2 khung liên tiếp, (3) con cầm cùng cấp và đứng yên (<= 3px) - đủ `stable_need` 2 khung liền; quá `stable_max` 6s thì dùng khung hiện tại + log cảnh báo. Gọi cho khung đầu tiên (không gọi khi `test`) và sau mỗi `_wait_ready`. Tắt bằng `wait_stable: false`. Thời gian suy nghĩ tối thiểu mỗi lượt đổi 0.6s -> `think_min` 1.2s (vì `held_wait` giờ đã bị chờ yên chiếm).
- `EvalParams` thêm `w_block` (2.0), `w_wedge` (4.0), `w_direct` (2.0), `w_robust` (0.6); hàm mới `_block_wedge_penalty(balls, W, ep)` gọi từ cuối `evaluate`: phạt heo nhỏ nằm trên đường nối 2 heo to cùng cấp (>= 3) đang gần nhau (chặn gộp), và heo cấp <= 3 sát tường đang dính một heo to hơn từ 2 cấp trở lên (kẹt giữa tường và heo to).
- `choose_drop`: thưởng nhẹ (`w_direct` x cấp) khi thả THẲNG vào tâm heo cùng cấp (|x - b.x| <= 0.2*(r+r')) và có gộp; kiểm độ bền: mô phỏng lại ở x ± 1.2% chiều rộng khung, nước nào mất điểm nhiều khi lệch (mong manh) bị trừ `w_robust` x phần mất.
- Giữ nguyên tên hàm/biến/tham số cũ; field mới đều tuỳ chọn (có mặc định). Thử mô phỏng tự chơi (Pymunk, 7 ván, 35-45 lượt) cũ vs mới: điểm gộp xấp xỉ nhau (4 ván đầu mới hơn ~7%, 3 ván sau cũ hơn ~9% - trong khoảng nhiễu), nên KHÔNG kết luận được điểm số tốt hơn; phần chắc chắn là sửa nhận diện (popup, chờ yên) vì lỗi nằm ở đọc ảnh chứ không phải ở mô phỏng. So ván thật chưa có.
- CHƯA test trên LDPlayer thật. Nếu vẫn thấy lệch/đọc sớm: gửi lại `debug_pig/` + log; có thể chỉnh `stable_diff` (nhỏ hơn = chờ yên kỹ hơn), `w_block`, `w_robust`.

## Đợt mới (2026-10-07, Dashboard) - Hẹn Giờ: Lặp lại 00:00 = chạy 1 lần rồi xoá + chọn Hoạt Động bằng nút hàng ngang (patch `hen_gio_mot_lan.patch`; sửa `scheduler.py`, `dashboard_schedule.py`, `dashboard_dialogs.py`)

Yêu cầu: (1) Hẹn Giờ chưa có kiểu chạy 1 lần - để ô "Lặp lại" = 00:00 thì chạy đúng 1 lần rồi tự xoá lịch; (2) cửa sổ "Chọn Hoạt Động cho lịch này" hiển thị nút xếp hàng ngang giống "Chọn Hành Động Để Chạy" (Chạy Ngay). Kèm 2 câu hỏi (trả lời trong chat, KHÔNG đổi code): giờ lặp tối đa (code không giới hạn trên - `hhmm_to_hours` chỉ yêu cầu hh >= 0, mm 0-59) và thứ tự của "▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN" (`run_selected_tasks`: sort theo (muc theo BẢNG CHỮ CÁI, thu_tu) - KHÔNG theo thứ tự Mục đã kéo ở "🔀 Sắp Xếp Hành Động" hay thứ tự tick).
- `scheduler.py`: khoá lịch mới `chay_mot_lan` (bool, tuỳ chọn); `is_one_shot(entry)`, `interval_text(entry)` ("00:00" cho lịch 1 lần). Lịch 1 lần vẫn lưu `interval_hours = 24` để toàn bộ phép tính lưới giờ (`is_due`/`next_due_time`/`missed_count`) giữ nguyên; `describe()` hiện "Chạy 1 lần lúc HH:MM rồi tự xoá".
- `dashboard_schedule.py`: `_save_row` dùng `hhmm_to_hours_allow_zero` (ô trống vẫn báo lỗi) - 00:00 -> `chay_mot_lan = True` + `interval_hours = 24`, giá trị khác -> bỏ cờ; đổi cờ cũng tính là "đổi giờ" (gọi `mark_triggered` để không chạy ngay sau khi lưu). Ô Lặp lại hiện "00:00" cho lịch 1 lần; cột sắp xếp "Lặp lại" coi 1 lần = 0. `_trigger_schedule` giờ trả `True/False` (False = bỏ qua vì thiếu Hoạt Động/Giả Lập; nơi gọi cũ không dùng giá trị trả về nên không ảnh hưởng). Hàm mới `_remove_one_shot_schedules(entries, reason)`: xoá lịch 1 lần khỏi `self.schedules` + `schedules.json`, gọi từ `_check_schedules` (sau khi trigger thành công) và `_handle_missed_schedules` (chạy bù xong thì xoá; chọn KHÔNG chạy bù cũng xoá vì mốc duy nhất đã qua). Nút "▶" Chạy Ngay thủ công KHÔNG xoá lịch (chỉ chạy thử). Trigger thất bại (False) thì GIỮ lịch lại. Lượt đã xếp hàng chờ giả lập bận vẫn chạy bình thường (job trong hàng chờ tự chứa đủ dữ liệu).
- `dashboard_dialogs.py::_open_multi_select_dialog`: tham số mới `button_mode=False` (mặc định giữ checklist cũ cho Tài Khoản/Hành Động Cuối/...). `button_mode=True`: cột trái là các `RoundedButton` trong `FlowBar` theo từng Mục (`📁 Mục`), bấm = chọn/bỏ chọn (nút xanh + số thứ tự, vd `2. Tên`), CHUỘT PHẢI = thêm lại 1 lần nữa khi `allow_duplicates` (nút hiện `1,4. Tên`); vẫn tạo BooleanVar ẩn nên Tất cả/Bỏ chọn/chọn nhanh theo nhóm/✕ cột phải chạy như cũ. Chỉ `_pick_activities` trong `dashboard_schedule.py` truyền `button_mode=True`.
- Test (sandbox, Xvfb): dialog button_mode chọn/bỏ chọn/chuột phải/Lưu ra đúng `['t2','t2']`, chế độ checkbox cũ vẫn mở được; `scheduler`: lịch 1 lần mô tả đúng, lưu lúc 06:00 -> chưa đến hạn 06:30, đến hạn 07:00; `_remove_one_shot_schedules` chỉ xoá lịch 1 lần. Chưa test trên Windows thật. Lưu ý: nếu cửa sổ Hẹn Giờ đang MỞ đúng lúc lịch 1 lần tự xoá thì dòng đó vẫn còn trên màn hình tới khi mở lại cửa sổ (đừng bấm 💾 dòng đó - sẽ tạo lại lịch).

## Đợt mới (2026-10-07, Dashboard) - Đưa Lên Trên + Chọn nhiều Hành Động + bảng Hẹn Giờ thẳng cột (patch `dashboard_ui_fixes.patch`; sửa `dashboard_emulators.py`, `dashboard_tasks.py`, `dashboard_schedule.py`)

Yêu cầu: (1) nút "⬆ Đưa Lên Trên" không có tác dụng (ô 📌 ghim thì ổn); (2) "Chọn Hành Động Để Chạy" chọn được NHIỀU hành động, chạy theo thứ tự chọn, thêm list chạy + nút xếp hàng ngang ở dưới; (3) cửa sổ Hẹn Giờ Tự Động: tiêu đề lệch nội dung, cột "🎯 HĐ / 🔗 GL-TK" và "Tên GL/TK/HĐ" dính nhau không kéo được, thêm nút chọn tất cả / bỏ chọn tất cả.
- `dashboard_emulators.py::bring_selected_emulators_to_front`: trước đây chỉ `SetWindowPos(HWND_TOP, ..., SWP_NOACTIVATE)` - Windows bỏ qua khi tiến trình gọi không phải cửa sổ đang focus. Giờ đặt HWND_TOPMOST rồi trả HWND_NOTOPMOST ngay (nhảy lên đầu thứ tự xếp lớp thường, KHÔNG ghim) + `BringWindowToTop`; giả lập đang ghim 📌 (`_topmost_emu_indexes`) thì giữ TOPMOST.
- `dashboard_tasks.py::_open_task_picker`: bấm nút = chọn/bỏ chọn (nút hiện số thứ tự + màu xanh, Nhóm Hành Động chọn xen kẽ được); dưới cùng có "📋 Danh sách chạy" (các chip xếp hàng ngang, bấm chip = bỏ) + hàng nút "▶ Chạy (N)", "☐ Bỏ Chọn Tất Cả", "✖ Đóng". Chạy: 1 Hoạt Động / toàn Hoạt Động thường -> `_start_run`/`_start_run_with_accounts` theo ĐÚNG thứ tự chọn (giữ Tự Login/Xoay Vòng như cũ, helper `_start_tasks`); 1 Nhóm -> `_run_group_from_ui` như cũ; có Nhóm trong danh sách nhiều mục -> gộp thành chuỗi id (`id` / `GROUP:<id>`) chạy như 1 Nhóm (lúc này KHÔNG chạy Tự Login riêng trước từng Hoạt Động, giống chạy Nhóm). Nhóm chưa soạn bước thì báo và không chạy.
- `dashboard_schedule.py::_open_schedule_manager`: độ rộng cột đổi từ "số ký tự" sang PIXEL (`col_width`, `COL_MIN_PX`, `ROW_CELL_H`, `HEADER_CELL_H`); header và MỌI dòng lịch dựng từ các ô Frame cố định (`pack_propagate(False)`, hàm `_mk_cell` trong `_add_row`) nên luôn thẳng hàng; mọi cột (kể cả "gan" và "smart") đều có thanh kéo bên phải tiêu đề (đồng thời là vạch phân tách), kéo là đổi width cả header + mọi dòng; ô "gan" chứa các nút 🎯/🔗/🏁/🧩 + ⏱ + biểu tượng chế độ (cần ~320px, mặc định 340). Thêm "☑ Chọn Tất Cả" / "☐ Bỏ Chọn Tất Cả" ở thanh dưới: tick/bỏ tick ô "Bật" của mọi lịch ĐANG HIỂN THỊ (lịch bị ẩn do lọc giả lập không đổi); `row_record["bat_var"]`; vẫn phải bấm "💾 Lưu Tất Cả" để lưu.
- Test (sandbox, Xvfb + stub win32): header/dòng khớp từng pixel, kéo cột cập nhật đồng loạt, 2 nút chọn tất cả đúng; popup chọn nhiều ra đúng thứ tự `['t3','t6']`, trộn Nhóm ra `['t5','GROUP:nhom_1','t2']`. Chưa test trên Windows thật: nút Đưa Lên Trên (cần thử với LDPlayer thật).

## Đợt mới (2026-10-07, Bot) - 🐷 Auto Lợn Giống (game ghép heo kiểu Suika) (patch `pig_bot.patch`; file MỚI `pig_bot.py`; sửa `logic_engine.py`, `gui_manual_steps.py`, `gui_canvas.py`, `gui_ui_build.py`, `gui_steplist_ops.py`, `gui_step_edit.py`, `build_portable.py`)

Yêu cầu: bot tự chơi game "Lợn giống" (thả heo, 2 con cùng cấp CHẠM THẬT thì gộp, 10 cấp, heo đỏ cấp 10 không gộp, con thả ngẫu nhiên cấp 1-4), mục tiêu ghép được nhiều heo cấp cao nhất; thể lực tối đa 300 tự hồi, dưới 10 thì dừng. Tích hợp như 2048/Ngưu Ma Vương.
- `pig_bot.py` (mới): `run_auto_pig_step(adb, step, should_stop, log)`. Mỗi lượt: chụp -> `detect_pigs` (Hough theo bán kính từng cấp từ lớn xuống nhỏ + kiểm tra vòng viền theo cửa sổ hue từng nhóm: ngọc/xanh/tím/vàng/đỏ, heo cấp 1 viền xám; con nhỏ nằm trong tâm con lớn bị loại; cấp chốt theo bán kính gần nhất trong nhóm màu) -> `detect_held` (con đang cầm, cấp 1-4) -> `choose_drop` (mô phỏng Pymunk ~25 vị trí thả + vị trí kề heo cùng cấp, giữ top 6 rồi thử tiếp con kế ngẫu nhiên 1-4, chấm bằng `evaluate`: điểm gộp 2^cấp, phạt đống cao/diện tích/heo nhỏ bị kẹp, thưởng cặp cùng cấp sát nhau + heo lớn nằm thấp + cấp cao nhất) -> bấm `adb.tap_px` (hoặc `swipe_hold_px` khi `drop_mode=swipe`) -> `_wait_settle` (so khung bàn liên tiếp) -> lặp.
- Luật mô phỏng: gộp khi khoảng cách tâm <= r1+r2 (+`merge_eps`); đỏ không gộp; con mới ở trung điểm. Pymunk 6.x/7.x đều chạy (không dùng collision handler). ~4ms/lần mô phỏng, ~1-3s/lượt cả nhận diện.
- Dừng khi: thể lực (OCR `n/300` ở `stamina_box`) < `min_stamina` (mặc định 10; đọc lúc đầu + mỗi `stamina_every`=25 lượt), hết `max_turns`/`max_seconds`, Dừng, không đọc được con cầm 6 lần liền, hoặc màn hình không đổi sau 4 lần thả. `test: true` = chỉ tính + lưu ảnh kế hoạch `debug_pig/pig_NNNN.png`; mọi lượt ghi `debug_pig/pig_log.jsonl` (trạng thái trước, dự đoán, vị trí thả) để hiệu chỉnh mô phỏng sau này; log in "sai số dự đoán" giữa mô phỏng và ảnh thật.
- GUI: nút "🐷 Auto Lợn Giống" + menu chuột phải; kéo khung bao đúng KHUNG NÉT ĐỨT của bàn trên Preview (`board_from/board_to`); chuột phải bước: đổi TEST/THẬT, chọn lại khung. Cần `pip install pymunk` (đã thêm vào `build_portable.REQUIREMENTS`); thiếu Pymunk thì bước báo lỗi rõ và dừng.
- Test (sandbox, headless): nhận diện đúng 16/17, 14, 11 heo trên 3 ảnh máy 946x2048 (thiếu tối đa 1 heo cấp 1); mô phỏng: thả L3 lên L3 -> L4, đỏ+đỏ không gộp, L2 cạnh L2 có hở không gộp; vòng lặp `run_auto_pig_step` chạy với ADB giả (bấm đúng toạ độ trong khung, dừng khi thể lực 5 < 10, chế độ test không bấm). CHƯA chạy trên LDPlayer thật: chưa kiểm chứng (1) điểm bấm `tap_y`/chế độ `tap` có thả đúng x không, (2) tham số vật lý mặc định (gravity/damping/friction/elasticity) so với game thật, (3) ngưỡng nhận diện ở độ phân giải giả lập, (4) vị trí `stamina_box`, (5) điều kiện thua thật của game.

## Đợt mới (2026-10-05, GUI) - "🧪 Test Quét Ảnh": thêm chọn VÙNG QUÉT (áp SAU `popup_footer.patch`; patch `image_test_region.patch`; sửa `gui_image_test.py`, `gui_capture.py`)

Yêu cầu: test quét ảnh có thêm chọn vùng quét.
- Cửa sổ test có thêm dòng "Vùng quét: toàn màn hình / x%,y% → x%,y%" + nút "🖼️ Chọn Vùng..." (mở `RegionPickerDialog` của `gui_dialogs_ifgroup.py` trên ảnh `current_screen_cv`, chưa có thì tự chụp; chưa kết nối thì báo lưu ý) + nút "🖥️ Toàn Màn" (bỏ vùng). Các hàng lưới phía dưới dời 4->5, 5->6, 6->7.
- Vùng lưu ở `self._img_test_region` (None hoặc [x1,y1,x2,y2] tỉ lệ 0..1 - CÙNG định dạng `step["region"]`, nên test xong đặt y hệt cho bước ảnh). Mỗi lần mở cửa sổ reset về toàn màn hình (giống ảnh mẫu).
- `_img_test_worker` đọc lại `self._img_test_region` MỖI vòng nên đổi vùng khi đang quét có hiệu lực ngay (log "đổi vùng quét"), truyền `region=` vào `find_image_on_screen`/`find_image_all_modes` (2 hàm này vốn đã hỗ trợ region, toạ độ trả về vẫn là toạ độ TOÀN màn hình). Log "bắt đầu quét" in thêm vùng. Vùng nhỏ hơn ảnh mẫu (px) -> cảnh báo 1 lần/vùng vì khi đó điểm luôn 0.000.
- Preview: khung vùng quét màu vàng + chữ "SCAN AREA" vẽ ở `gui_capture.render_preview` (thuộc tính `_img_test_region_ov`, vẽ TRƯỚC khung FOUND); tắt khi đóng cửa sổ test.
- Test (sandbox, headless): ảnh mẫu nằm ở (0.825, 0.775): quét toàn màn và vùng chứa ảnh đều ra đúng toạ độ toàn màn hình; vùng loại trừ ảnh -> không thấy (0.09); vùng nhỏ hơn mẫu -> (None, 0.0); `find_image_all_modes` tương tự. CHƯA chạy giao diện Tk thật (bố cục, hộp chọn vùng, khung vàng) trên Windows.

## Đợt mới (2026-10-05, Dashboard) - popup "Điều khiển": thêm chân popup "⏰ Lịch kế tiếp" luôn hiện (áp SAU `chain_schedule.patch`; patch `popup_footer.patch`; chỉ sửa `dashboard_popup_ctl.py`)

Vấn đề: dòng "⏰ Tiếp: ..." chỉ nằm trong từng dòng giả lập ĐANG CHẠY, nên khi không có giả lập nào chạy (popup chỉ hiện "Không có giả lập nào đang chạy") thì popup không cho thấy lịch hẹn giờ kế tiếp.
- Thêm chân popup (có đường kẻ ngăn) với nhãn `self._ctl_footer_next`: "⏰ Lịch kế tiếp: <tên lịch> lúc hh:mm (còn ...)" = lịch BẬT sớm nhất của mọi giả lập (`_next_schedule_text(None)`), hoặc "chưa có lịch hẹn giờ nào đang BẬT". Tự cập nhật theo nhịp 0,4s của `_ctl_refresh_rows` (chỉ `config` khi chữ đổi). Hàm mới `_ctl_footer_text()`. Dòng "⏰ Tiếp:" trong từng dòng giả lập giữ nguyên.
- CHƯA chạy giao diện Tk thật (chỉ biên dịch).

## Đợt mới (2026-10-04, Dashboard) - Hẹn Giờ: tuỳ chọn "⏱ tính từ lúc chạy thật" cho từng lịch (áp SAU `next_schedule.patch`; patch `chain_schedule.patch`; sửa `scheduler.py`, `dashboard_schedule.py`, `dashboard_theme.py`)

Yêu cầu: mặc định lịch là LƯỚI GIỜ CỐ ĐỊNH (3:30 lặp 4h -> 3:30, 7:30, 11:30... dù lượt trước chạy trễ); thêm TUỲ CHỌN để mốc kế tiếp tính từ lúc chạy thật (tới 4:00 mới chạy được -> lần sau 8:00).
- Khoá lịch MỚI (tuỳ chọn, không có = như cũ, KHÔNG cần migrate): `tinh_tu_luc_chay` (bool) và `lan_chay_that_luc` (ISO, lúc 1 giả lập của lịch THỰC SỰ bắt đầu chạy; khác `lan_chay_luc` = lúc trigger, có thể sớm hơn nếu giả lập bận phải xếp hàng chờ).
- `scheduler.py`: hàm `_chain_due_time(entry)` = (`lan_chay_that_luc`, hoặc `lan_chay_luc` nếu lượt trigger mới hơn mà chưa kịp bắt đầu - tạm tính để không trigger chồng) + `interval_hours`. Trả về None (-> lưới cố định như cũ) khi không bật chế độ, hoặc lịch CHƯA TỪNG thực sự chạy (lượt đầu vẫn theo Giờ hẹn). `_is_due_ignoring_bat`, `last_due_time` (None nếu chưa tới hạn), `next_due_time` (đã quá hạn thì trả về bây giờ), `missed_count`, `describe` (thêm "(⏱ tính từ lúc chạy thật)") đều rẽ nhánh theo hàm này; các nơi gọi khác không đổi.
- `dashboard_schedule.py`: `_start_schedule_worker(..., schedule_id=None)` gọi `_note_schedule_actual_start(schedule_id)` (ghi `lan_chay_that_luc` + lưu file, điều phối qua `root.after` vì có thể gọi từ luồng nền); job hàng chờ `kind=="schedule"` mang thêm `schedule_id` (job cũ không có khoá này vẫn chạy bình thường). Dòng lịch có ô tick "⏱" (sau nút 🧩, có tooltip); `_save_row` lưu/xoá `tinh_tu_luc_chay`, đổi ô này tính là "đổi lịch" (đặt `lan_chay_luc` = bây giờ như đổi giờ/lặp lại, tránh tự chạy ngay), và CHẶN lưu nếu bật ⏱ mà ô Giờ hẹn có NHIỀU mốc (sau lần chạy thật đầu tiên mốc phụ sẽ bị bỏ qua nên báo lỗi rõ ràng).
- `dashboard_theme.py`: HELP_TEXT mục 7 thêm ý g) giải thích ô ⏱.
- Hành vi cần biết: nhiều giả lập trong 1 lịch -> tính từ giả lập bắt đầu chạy SAU CÙNG; "▶ Chạy Ngay" và "bỏ qua lịch đã lỡ" (đặt "vừa chạy xong") ở chế độ ⏱ cũng dời mốc kế = lúc đó + Lặp lại; xoá job khỏi Hàng Chờ thì mốc kế tạm tính từ lúc trigger.
- Test (sandbox): tắt ⏱ -> so với `scheduler.py` bản cũ trên 4000 lịch ngẫu nhiên x 6 hàm (24000 phép so), 0 khác biệt; bật ⏱ nhưng chưa chạy thật = y hệt lưới; ví dụ 3:30 lặp 4h trigger 3:30:05, chạy thật 4:00:10 -> mốc 7:30 KHÔNG còn đến hạn, kế tiếp 8:00:10, đúng cả trường hợp đang xếp hàng chờ/đổi cờ/ISO hỏng; hook ghi `lan_chay_that_luc` chỉ với lịch bật ⏱ và chỉ lưu 1 lần. CHƯA chạy giao diện Tk thật (ô tick ⏱, Tooltip, hộp thoại lỗi nhiều mốc) trên Windows.

## Đợt mới (2026-10-04, Dashboard) - thêm "⏰ hành động hẹn giờ kế tiếp" vào popup Dừng/Tạm Dừng + Nhật Ký thời gian thực (patch `next_schedule.patch`, áp lên bản repo gốc; sửa `dashboard_schedule.py`, `dashboard_popup_ctl.py`, `dashboard_ui.py`, `dashboard_log.py`)

Yêu cầu: popup tạm dừng và nhật ký thời gian thực thêm phần "hành động tiếp theo (hẹn giờ)".
- `dashboard_schedule.py` (ScheduleMixin): thêm `_next_schedule_for_emulator(idx|None)` (lịch Hẹn Giờ BẬT + đã có Hoạt Động + có giả lập đó trong `gan_may_tk`, lấy mốc sớm nhất qua `scheduler.next_due_time`), `_next_schedule_text(idx|None)` (chuỗi "Tên lịch lúc hh:mm (còn 1g05p)", cache 10s vì popup vẽ lại mỗi 0,4s), `_fmt_countdown`. Không đổi hàm cũ.
- `dashboard_popup_ctl.py`: mỗi dòng giả lập có thêm dòng nhỏ màu teal "⏰ Tiếp: ..." (dưới dòng trạng thái Hoạt Động, TK i/n), tự cập nhật; không có lịch thì "⏰ Tiếp: chưa có lịch hẹn giờ"; cắt tối đa 46 ký tự để popup không bị giãn rộng (`_CTL_NEXT_MAX_CHARS`).
- `dashboard_ui.py` + `dashboard_log.py`: thêm dòng "⏰ Kế tiếp (hẹn giờ):" (`self.lbl_next_action`) ngay dưới dòng "⏳ Đang chạy" ở thanh Nhật Ký; mỗi giả lập đang bận 1 đoạn "[tên] lịch lúc hh:mm (còn ...)", không giả lập nào bận thì hiện lịch sớm nhất toàn danh sách. Làm mới khi trạng thái "Đang chạy" đổi (`_set_current_task_status`) và mỗi 5s (`_next_action_tick`).
- Hiểu "hành động tiếp theo (hẹn giờ)" = LỊCH HẸN GIỜ sắp chạy (không phải Hoạt Động kế trong cùng phiên). Nếu muốn hiện thêm tên các Hoạt Động trong lịch đó thì báo để thêm.
- Test (sandbox, không có tkinter nên stub): helper trả đúng lịch sớm nhất theo từng giả lập, bỏ lịch TẮT/chưa gán Hoạt Động, giả lập không có lịch -> rỗng, đếm ngược đúng. CHƯA chạy giao diện Tk thật trên Windows.

## Đợt mới (2026-10-04, Ngưu Ma Vương #16) - NỘ dùng như bình thường khi có nhện + log quái bị bỏ (áp SAU #15 / `thtg_spider.patch`, chỉ sửa `thtg_bot.py`; patch `thtg_spider_fix.patch`)

Người dùng: "vẫn dùng nộ như bình thường, không dùng được cũng không ảnh hưởng gì, chỉ ưu tiên diệt hết nhện" + "thỉnh thoảng bot bỏ qua không ăn quái to mặc dù ăn được".
- `spider_lock_rage` mặc định ĐỔI true -> false: bot vẫn đọc/bấm nộ như cũ kể cả khi có nhện (đặt true mới bỏ qua nộ). Khi false không tốn công đếm nhện/dò ổ khoá ở `run()`. `_battle_gone` vẫn coi ổ khoá là còn trong trận (vô hại).
- KIỂM TRA BỎ QUÁI (sandbox): bộ giải so với bản tham chiếu (tắt phạt vị trí cuối, 3 triệu nút) trên ~3800 bàn giống thật (3 màu, 4 ô gỗ, 2-4 quái, có/không nhện) + 62 bàn có lồng màu/kim cương/gỗ mở/`turns_left`: 0 bàn bỏ sót quái ăn được (4/62 chỉ là chưa chứng minh tối ưu nhưng vẫn đủ quái). => khi bot bỏ quái, nguyên nhân gần như chắc chắn nằm ở ĐỌC ẢNH (số bước đọc cao hơn thật nên bot tưởng không đủ bước; hoặc quái bị nhận thành thú thường), KHÔNG ở bộ giải.
- Trọng số nhện: đo 28 bàn có nhện: w_spider 500/2000/3000/5000 diệt nhện 14/18/21/21, tổng quái 57/57/56/56 -> ưu tiên nhện chỉ làm mất 1 quái ở 1/28 bàn (khi nhện xung đột với 2 quái khác); giữ 5000.
- Log MỚI mỗi lượt: "quái BỎ lại lượt này: (r,c) cần N [NHỆN] [đọc số CHƯA chắc] [bộ giải đã chứng minh không ăn thêm được | chưa chứng minh tối ưu]" -> thấy ngay quái nào bị bỏ và vì sao. Gặp lại lỗi thì gửi dòng log này + ảnh `*_ke_hoach.png`/`*_truoc_chien.png` của lượt đó.
- CHƯA XÁC NHẬN: chưa có ảnh/log thật của lượt bị bỏ quái; chưa rõ luật thật là bước >= N hay bước+1 >= N (field `count_step_first`): nếu bot bỏ quái khi số bước gom được đúng bằng N-1 thì thử `count_step_first` = true.

## Đợt mới (2026-10-04, Ngưu Ma Vương #15) - NHỆN: khoá nộ + ưu tiên diệt hết nhện + sửa lệch khung bàn cờ map mới (áp SAU #14 / `thtg_ocr_speed.patch`, chỉ sửa `thtg_bot.py`; patch `thtg_spider.patch`)

Yêu cầu: map mới có thêm con NHỆN; còn nhện thì thanh nộ bị khoá (không dùng được nộ) nên phải ưu tiên tiêu diệt toàn bộ nhện.
Ảnh người dùng gửi: nhện ở ô (0,0) (mạng nhện ở nền ô, tóc/cánh tím đen, chỉ có số bước "5" ở góc, KHÔNG có đồng hồ cát), thanh nộ hiện ổ khoá + "0/1000".
- NHẬN DIỆN NHỆN (`Cell.mtype == "spider"`): trong `BoardDetector.classify`, ô đã là quái to thì xét thêm khớp mẫu `templates/thtg_spider_*.png` (`tpl_spiders`, ngưỡng `spider_thr` 0.6; tuỳ chọn) HOẶC tỉ lệ pixel tím-đen ở nửa trên ô >= `SPIDER_PURPLE_MIN` 0.12 (`_spider_purple`; đo trên ảnh: nhện 0.291, thỏ 0.024, chuột 0.001, thú thường <= 0.05). Nhện không có đồng hồ cát nên `detect`/`_vote_monsters` KHÔNG đọc lượt đếm ngược của nhện (turns = 0) -> đỡ đọc nhầm, nhanh hơn. Thêm mẫu: `python thtg_bot.py --add-spider anh.png HÀNG CỘT` (`add_spider_template`, dùng chung `add_monster_template(prefix=...)`).
- ƯU TIÊN DIỆT NHỆN: `SolverParams.monster_weights` thêm `"spider": 5000.0` (nhện = w_kill 1000 + 5000 = 6000 điểm, hơn 3 quái thường không khẩn cấp cộng lại 3x1500; quái thường đếm ngược 1 lượt vẫn ~5500). Dùng chung hàm `monster_extra` nên cả bộ giải chính xác `thtg_solver.py` (không sửa) lẫn beam đều theo. Field bước: `w_spider` (5000).
- KHOÁ NỘ: `run()` mỗi lượt đếm nhện (`_count_spiders`, chỉ phân loại 49 ô, không OCR) + dò ổ khoá ở thanh nộ (`_rage_lock_visible`, đĩa xám sáng tại (0.270w, 0.938h), đo 0.82 so với 0.2 xung quanh, ngưỡng 0.6). Còn nhện HOẶC thấy ổ khoá -> BỎ QUA đọc/bấm nộ (trước đây nộ đầy mà bị khoá thì bot bấm ảnh nhân vật + Chiến phí lượt, và OCR thanh nộ bị ổ khoá che gây cảnh báo). Log khi ĐỔI trạng thái: "nộ đang bị KHOÁ (N nhện...)" / "hết nhện -> nộ đã mở khoá". Field bước: `spider_lock_rage` (true; false = bỏ qua luật khoá nộ).
- `_battle_gone`: thấy ổ khoá cũng coi là còn trong trận (OCR không đọc được thanh nộ khi bị khoá, tránh kết luận nhầm đã thoát bàn cờ).
- `play_turn`: log số nhện + "kế hoạch diệt HẾT x/y nhện" (cảnh báo nếu chưa hết); ghi chú ảnh kế hoạch có dòng "Nhện (hàng, cột, số bước cần)". `draw_plan`: nhãn "NHEN n" + "NHEN DIET/BO", tiêu đề có "NHEN a/b (no bi khoa)". `board_from_strings`/`Board.pretty`: ký hiệu `S` = nhện (số bước lấy từ monsters[(r,c)], mặc định 5).
- SỬA LỆCH KHUNG BÀN CỜ map mới: `find_board_rect` đo bàn cờ cao 745px (thật 700) do nền trời be sát trên bàn (cách 1 vạch khung 2px) mà vẫn lọt ngưỡng 12% -> `top` = 355 thay vì 392 (hàng 0 lệch gần nửa ô, bấm trượt). Nay lệch > 3% thì thử cách dự phòng (lấy cụm be CUỐI = bàn cờ) trước, cách cũ giữ làm phương án cuối (`cand`). Ảnh người dùng: top 355 -> 392, pitch 100.14.
- Test (sandbox, ảnh người dùng; không có thư mục templates/ trong repo nên đặt `find_geometry` tay): nhận ra nhện (0,0) cần 5 (đọc số đúng), thỏ (0,6) 6/đếm ngược 3, chuột (5,3) 7/đếm ngược 2, 4 ô gỗ đóng, mèo trong mây (3,3) là thú thường; kế hoạch 24 bước diệt đủ 3/3 quái (kể cả nhện); 150 bàn ngẫu nhiên có 1-2 nhện + 1-3 quái: 0 bàn diệt ít nhện hơn mức tối đa khả dĩ, 20 bàn nhờ ưu tiên mà diệt thêm nhện so với trọng số ngang quái thường; 60 bàn KHÔNG nhện: đường đi y hệt bản trước (60/60); chạy `run()` với adb giả: có nhện + nộ "đầy" -> 0 lần đọc nộ, KHÔNG bấm ảnh nhân vật (25 lần bấm = 24 ô + Chiến); `spider_lock_rage=false` -> bấm nộ như cũ; ảnh đã xoá nhện + xoá ổ khoá -> đếm 0 nhện, không thấy khoá.
- CHƯA XÁC NHẬN trên máy thật: (1) chỉ có 1 ảnh nhện (kiểu nhận bằng màu tím-đen dựa trên ảnh này; nếu có loại nhện khác màu, dùng `--add-spider` để thêm mẫu); (2) ổ khoá chưa có ảnh lúc MỞ khoá để so (nên nhận nhện là căn cứ chính, ổ khoá chỉ phụ; nếu ổ khoá nhận nhầm khiến bot không bao giờ dùng nộ thì đặt `spider_lock_rage` = false hoặc báo để chỉnh ngưỡng 0.6); (3) giả định nhện có số bước ở góc như quái thường (đã đọc đúng "5" trên ảnh); (4) khoá nộ hết ngay khi diệt xong nhện (bot lượt sau tự thấy 0 nhện và dùng nộ lại).

## Đợt mới (2026-10-04, Ngưu Ma Vương #14) - LƯỢT MẤT 50-125s: do GỌI TESSERACT QUÁ NHIỀU LẦN (áp SAU #13 / `thtg_cage_exit.patch`, chỉ sửa `thtg_bot.py`; patch `thtg_ocr_speed.patch`)

Người dùng gửi log 1 trận (lượt 3-8): bấm Chiến xong rất lâu sau mới đánh tiếp. Phân tích mốc giờ trong log: chờ bàn cờ sẵn sàng chỉ 7-20s (hoạt ảnh chạy, bình thường) nhưng từ lúc bàn cờ sẵn sàng tới dòng "quái to/lồng" mất 49-94s, đọc "Hiệp còn lại" 3-5s, bấm ô + lưu ảnh 1-11s. => nút cổ chai là OCR sau khi bàn cờ yên, KHÔNG phải thời gian chờ.
- NGUYÊN NHÂN: mỗi `pytesseract.image_to_string` là 1 tiến trình tesseract.exe mới (Windows ~0.3-1s). `_turns_votes` (đếm ngược trên đồng hồ cát) gọi tới 24 lần cho MỖI quái (4 ngưỡng x 2 độ mỏng x 3 psm), `_number_votes` fallback 12 lần, `read_turns_left` 24 lần, `read_rage` 5 lần/hộp (dựng hết rồi mới parse). Đo sandbox trên 49 ô: 502 lần chạy tesseract.
- `_tess_batch`/`_tess_digits` (MỚI): OCR cả LÔ ảnh bằng 1 lần chạy tesseract (danh sách ảnh, trang cách nhau bằng \f); lô lỗi thì rơi về từng ảnh một như cũ. `_turns_votes`: lần 1 chạy psm 10 cho 8 biến thể, >=3 phiếu cùng số thì dừng; không thì chạy thêm psm 8 và 13 (tối đa 3 tiến trình thay vì 24). `_number_votes` fallback 12 -> 4; `read_turns_left` 24 -> 4; `_rage_white_ocr` 3 -> 1.
- `read_rage`: đọc lười - parse từng nguồn OCR (chữ trắng -> adb OCR -> OCR thường), đọc được là dừng (trước: chạy hết 5 nguồn rồi mới parse).
- Đọc số/lượt các quái SONG SONG (`_pmap`, `OCR_WORKERS`=3, `BoardDetector.ocr_workers`) trong `detect` và `_vote_monsters`.
- Log MỚI mỗi lượt: `thời gian lượt N: chờ bàn cờ, đọc nộ, nhận diện+đọc số quái, bỏ phiếu quái, đọc hiệp, giải, bấm ô (cộng ...)` -> thấy ngay lượt mất ở đâu.
- Test (sandbox, ảnh lượt 2): kết quả đọc số/lượt GIỐNG HỆT bản cũ trên 49 ô (0 khác); tesseract 502 -> 66 lần (`_turns_votes`), 24 -> 8 (`_number_votes`); chạy trọn 1 lượt 8-10s -> 2.3s; ép lô lỗi thì kết quả vẫn y hệt; solver vẫn tối ưu 90/90.
- CHƯA XÁC NHẬN trên Windows thật: chế độ danh sách ảnh của tesseract.exe (đã thử 5.3.4 Linux; nếu lỗi sẽ tự rơi về cách cũ = chậm như trước, không sai kết quả). Cần xem dòng `thời gian lượt` trên máy thật.
- Ý "nghỉ 1s/bước rồi đợi đủ 49 ô": không cần sửa code, đặt `attack_wait_per_step`=1.0, `attack_wait_base`=0, `attack_wait_per_kill`=0 là được; nhưng không nhanh hơn vì `_settle` đã đợi đủ 49 ô đứng yên 3 khung (thích nghi theo hoạt ảnh).

## Đợt mới (2026-10-04, Ngưu Ma Vương #13) - LỒNG XANH LÁ bị nhận nhầm thành quái + ảnh kiểm tra ghi màu lồng + THOÁT NGAY khi ra khỏi bàn cờ (áp SAU #12 / `thtg_cage5.patch`, chỉ sửa `thtg_bot.py`; patch `thtg_cage_exit.patch`)

Người dùng báo: (1) "vẫn nhận diện ô lồng sai, có 4 loại lồng xanh lá / xanh lục / nâu (cam) / đỏ; trên ảnh lồng cam thành xanh lục, xanh lá thành cam, cam lại thành xanh lục"; (2) 21 bước di chuyển tính từ lúc bấm Chiến mất tối đa ~20s (nên thời gian chờ là bình thường); (3) "không thấy ô nộ hoặc nhân vật chính thì là đã thoát bàn cờ, kết thúc luôn".
- NGUYÊN NHÂN (1), đo trên ảnh `113721_luot2_truoc_chien.png`: ảnh kế hoạch vẽ MỌI lồng viền cyan ("LONG") bất kể màu -> cyan chỉ nghĩa là "nhận ra là lồng", KHÔNG phải màu; viền CAM + chữ "BO" là ô bị nhận là QUÁI. Lồng xanh lá (3,3) bị nhận thành quái "5 BO" vì mặt nạ xanh lục trong `_cage_info` quá chặt (s>=90, v>=150, h>=35: chỉ 5 cột, cần >=12) trong khi thanh lồng xanh lá NHẠT. Lồng cam (1,5) nhận đúng cam (bò).
- `_cage_info`: mặt nạ xanh lá nới thành h 30-80, s>=50, v>=140 -> lồng (3,3) đo 0.92 + 24 cột (nhận ra, màu ếch); quái có hào quang xanh chỉ 0.2 + 6 cột, không nhầm.
- `draw_plan`: ô lồng giờ ghi MÀU bot nhận được ở góc dưới trái (`_CAGE_COLOR_LABEL`: XANH LA / CAM / XANH DG / DO / MAU ?), viền cyan vẫn chỉ báo "là lồng".
- THOÁT NGAY: `_battle_gone` + `_settle`: khi không thấy nhân vật (`find_geometry`), không thấy khung bàn cờ (`find_board_rect`), không thấy nút Chiến (`_attack_button_visible`, cam bão hoà >= 0.20 ở góc dưới phải) và không đọc được thanh nộ (`read_rage`) trong `gone_frames` (3) khung liên tiếp thì `_left_board = True`, `run` kết thúc trả True. Cố ý chặt hơn "không thấy nhân vật" vì lúc bấm Chiến nhân vật chạy đi (vắng tới ~20s) mà vẫn còn trong trận. Field mới của bước: `exit_when_gone` (true), `gone_frames` (3). Tắt = hành vi cũ (chờ hết `settle_max`).
- Test (sandbox): màn đen -> thoát sau 0.3s thay vì chờ 20s; khung còn nút Chiến nhưng vắng nhân vật -> KHÔNG thoát; thanh nộ đọc được -> không thoát; `exit_when_gone=false` -> không thoát; 90 bàn ngẫu nhiên solve vẫn tối ưu (0.01-0.03s TB).
- CHƯA XÁC NHẬN: màu lồng cam/đỏ/xanh dương trên ảnh thật khác (ảnh kiểm tra bị chữ vẽ đè nên chỉ đo được lồng xanh lá + cam); ngưỡng nút Chiến chưa thử trên màn hình NGOÀI trận (an toàn: nếu không nhận ra thì chỉ chờ `settle_max` như cũ). Nếu lồng đỏ/xanh dương vẫn sai, gửi ảnh GỐC (không vẽ đè) của lượt đó.

## Đợt mới (2026-10-04, Ngưu Ma Vương #12) - LỒNG CÓ MÀU: nhận ra lồng xanh dương + lồng chỉ đi qua khi cùng màu con đang nối (áp SAU #11 / `thtg_cage5.patch`, sửa `thtg_bot.py` + `thtg_solver.py`)

Người dùng báo bot "toàn đổi màu qua lồng" (ảnh lượt 6: mèo -> lồng -> heo, heo -> lồng -> mèo). Luật thật: lồng CÓ MÀU, đang nối con đỏ thì chỉ đi qua lồng đỏ, đi qua xong vẫn nối tiếp đỏ.
- NGUYÊN NHÂN thật của việc "đổi màu": `_is_cage` chỉ dò khung HỒNG/CAM nên lồng XANH DƯƠNG bị nhận nhầm thành QUÁI TO (ảnh kế hoạch ghi "5 DIET" ở các lồng xanh, "diệt 4/8 quái to" tính cả lồng) -> diệt "quái" được đổi màu tự do. Luật giữ màu của #6 vốn đúng, chỉ áp cho lồng nhận ra được.
- `_cage_info` (mới, `_is_cage` giữ tên cũ gọi vào): thêm dò khung xanh dương (đo: 0.80-0.91 thanh trên + 29-34 cột), xanh lục (CHƯA có ảnh để kiểm), và trả MÀU lồng theo màu khung: xanh dương = mèo(2), hồng/đỏ = heo(3), cam = bò(1), lục = ếch(0). Màu lưu ở `Cell.color` của ô lồng (-1 = không rõ -> qua được mọi màu). `classify` chỉ cần dấu hiệu số >= 25 (trước 60) khi khung lồng đã rõ.
- `_step`: đi qua lồng khi đang nối màu X mà lồng màu Y != X (cả hai đã biết) -> KHÔNG đi được; qua xong giữ màu X. `_to_exact_grid` gửi màu lồng cho `thtg_solver.py` (kind "L" tuple[1]); `solve_exact`: thêm mảng `lcol`, ô lồng khác màu bị loại khỏi ứng viên (cận trên vẫn coi lồng là cầu nối - nới lỏng, vẫn hợp lệ). `board_from_strings`: `LF/LO/LC/LP` = lồng màu ếch/bò/mèo/heo, `L` = không rõ.
- Test (sandbox, 2 ảnh người dùng gửi, khung đặt tay vì ảnh bị tối/vẽ đè): ảnh lượt 2 nhận đủ 4 lồng (3 mèo, 1 heo) thay vì chỉ 1; ảnh lượt 6 nhận lồng mèo (4,3) + heo (3,5), lồng (3,1) bị nhãn vẽ đè che số nên không nhận (chỉ do ảnh vẽ đè; ảnh gốc không bị). validate: mèo->lồng mèo->mèo OK, mèo->lồng heo X, mèo->lồng không rõ->mèo OK, mèo->lồng mèo->heo X. 80 bàn ngẫu nhiên có lồng nhiều màu: 0 đường sai luật (133 lần đi qua lồng hợp lệ). Hồi quy ô gỗ/xen kẽ vẫn đạt.
- GIẢ ĐỊNH chưa xác nhận: màu lồng = màu khung (không phải màu viên ngọc bên trong); lồng cam=bò, lục=ếch suy từ quy ước màu thú, chưa có ảnh thật. Ô lồng ĐẦU đường (chưa có màu đang nối) qua được mọi màu rồi đặt màu nối tiếp = màu lồng? - hiện giữ -1 (không ép màu), cần xác nhận.

## Đợt mới (2026-10-04, Ngưu Ma Vương #11) - số bước của LỒNG cố định = 5, không đọc OCR (áp SAU #10 / `thtg_box_alternate.patch`, chỉ sửa `thtg_bot.py`)

Yêu cầu: bot hay đọc sai số của lồng (ảnh người dùng gửi: lồng bị đọc "7?") -> đặt mặc định 5, game không có số khác.
- MỚI hằng số `CAGE_STEPS = 5`. `classify` trả lồng với `n = CAGE_STEPS`; `BoardDetector.detect` với ô lồng gán `n = 5`, `turns = 0`, `last_raw = (5, 0, True)` (coi là đọc chắc) rồi BỎ QUA đọc số/lượt; `THTGBot._vote_monsters` ép mọi lồng về 5, không đưa lồng vào danh sách vote/chụp thêm khung (đỡ tốn thời gian), log thêm "N lồng (luôn cần 5 bước)". Quái to vẫn đọc OCR như cũ. Không đổi tên hàm/field nào.
- Test (sandbox, ảnh người dùng gửi + hình học đặt tay vì ảnh bị làm tối khi đang nối đường nên `find_board_rect` không dò ra - ảnh chụp bình thường trước khi nối thì dò được như trước): lồng nhận ra có `n = 5`; giả vờ lồng bị đọc 9 -> `_vote_monsters` ép lại 5; `solve` chạy bình thường. Do ảnh bị tối/vẽ đè nên chỉ nhận ra 1/3 lồng và (3,2) đọc mặc định 7 - không liên quan đợt này.
- LƯU Ý: `board_from_strings` ký hiệu `L` vẫn nhận số tuỳ ý từ `monsters` (chỉ để test), mặc định 5.

## Đợt mới (2026-10-04, Ngưu Ma Vương #10) - ô gỗ ĐỔI XEN KẼ mỗi lượt (đóng -> mở -> đóng) (áp SAU #9 / `thtg_box.patch`, chỉ sửa `thtg_bot.py`)

Người dùng xác nhận: ô gỗ mở xen kẽ mỗi lượt, đóng rồi mở rồi đóng.
- Lượt đang chơi: vẫn đọc trạng thái từ ảnh (đóng = đá, mở = thú thường) nên đường đi lượt này luôn đúng.
- MỚI `SolverParams.box_alternate` (mặc định true; field bước `box_alternate`): `_EndEval` (phạt vị trí kết thúc - nhân vật đứng lại ở ô cuối, lượt sau bắt đầu từ đó) tính ô gỗ theo trạng thái LƯỢT SAU: ô gỗ đang ĐÓNG sẽ MỞ (đi vào được), ô gỗ đang MỞ sẽ ĐÓNG (không vào được, như đá). Trước đây ô gỗ đóng bị tính là không vào được và ô mở là vào được cả lượt sau -> có thể kết thúc cạnh toàn ô gỗ đang mở rồi lượt sau bị kẹt. `false` = coi ô gỗ giữ nguyên như #9.
- Test (sandbox): ô cuối ở góc kề 3 ô gỗ MỞ: phạt 25 -> 2500 (lượt sau đóng hết = kẹt); kề 3 ô gỗ ĐÓNG: 2500 -> 25 (lượt sau mở hết); 25 bàn không có ô gỗ: đường đi giống hệt bật/tắt; ảnh thật vẫn 24 bước diệt 2; 60 bàn ngẫu nhiên có ô gỗ: 0 đường sai luật.
- GIẢ ĐỊNH chưa xác nhận: (1) đổi trạng thái xảy ra đúng 1 lần mỗi lượt (sau khi bấm Chiến); (2) ô gỗ đứng yên tại chỗ hay rơi xuống cùng các ô khác khi ô phía dưới biến mất - hiện coi như các ô thường (rơi theo cột, `fall_down`); nếu thực tế ô gỗ cố định như đá thì báo để chỉnh; (3) ô gỗ vừa bị nối (đang mở) thì thú trong hộp biến mất như thú thường.

## Đợt mới (2026-10-04, Ngưu Ma Vương #9) - Ô GỖ đóng/mở (map mới) + sửa dò khung bàn cờ nền sa mạc + sửa nhận nhầm quái (áp SAU đợt #8, chỉ sửa `thtg_bot.py`)

Yêu cầu: map mới có ô GỖ với 2 trạng thái: ĐÓNG = như đá, không đi được; MỞ = như ô thú con bình thường.
- Quan sát trên ảnh người dùng gửi (723x1276, map Phàn Đầu): ô gỗ ĐÓNG = hộp CAO che gần hết con thú (chỉ lòi cái đầu; ảnh ở (3,2) và (3,4)); ô gỗ MỞ = hộp THẤP ở đáy ô, con thú lộ rõ (ảnh ở (3,3)).
- `Cell` thêm field `box` ("closed" | "open" | ""). Đóng -> `Cell("stone", box="closed")` (bộ giải/`_EndEval`/`_to_exact_grid`/`validate_path` vốn đã chặn đá nên KHÔNG phải sửa gì thêm, `thtg_solver.py` không đổi). Mở -> `Cell("animal", color=<thú trong hộp>, box="open")` đi như thú thường (vẫn phải cùng loại thú mới nối được).
- `_box_bands` + `_box_state` (mới): đo tỉ lệ điểm màu gỗ/be (cùng ngưỡng HSV với ô đá) theo 10 dải ngang của ô. Dải 5-8 trung bình >= 0.65 -> đóng (đo: đóng 0.83-0.87, mở 0.35, thú thường <= 0.30); mở = dải 8 >= 0.80 và dải 5, 6 <= 0.30. Chịu lệch hình học +-1 dải. `classify` gọi sau bước quái to/kim cương (không đổi hành vi cũ). Ô ĐÁ thật cũng ra "closed" (không sao: cùng không đi được). "open" chỉ để log/vẽ debug nên nhận sai không làm đổi đường đi.
- `Board.pretty`: ô gỗ đóng in ` B `, ô gỗ mở in `F_`/`O_`/`C_`/`P_`. `board_from_strings`: `B` = ô gỗ đóng, hậu tố `_` sau chữ thú = ô gỗ mở (vd `F_`, `P*_`).
- `play_turn` log "ô gỗ ĐÓNG n (...), ô gỗ MỞ m (...)"; file debug .txt thêm dòng ô gỗ; `draw_plan` vẽ khung đỏ "GO DONG" / xanh "GO MO".
- SỬA LỖI 1 (ảnh map mới): `find_board_rect` đo bàn cờ cao gấp đôi (trên = 3, vì trời/nền sa mạc màu be phía trên bàn cờ bị coi là ô) nên cả hàng/cột lệch, và nhận ra bàn cờ sai. Giờ: dò cách cũ, nếu khung KHÔNG gần hình vuông (sai > 12%) thì dò lại: lấy cụm hàng be CUỐI CÙNG (bàn cờ nằm dưới trời) rồi mới dò cột. Ảnh cũ vẫn đi đường cũ (không đổi kết quả). Thêm `_segs`.
- SỬA LỖI 2: `_num_glyph` nhận số LƯỢT (đồng hồ cát, đỏ) của quái ở ô bên PHẢI làm "số bước" của ô bên trái -> con ếch (5,2) bị nhận nhầm là quái to. Giờ bỏ chữ số có tâm nằm ngoài mép phải ô (`cx + 0.5*pitch`). Chữ số bước thật (đo: +0.38p) không bị ảnh hưởng.
- Test (sandbox): ảnh thật: 49 ô nhận đúng (ô gỗ đóng (3,2) (3,4), mở (3,3) = heo; quái số 6, 7, 5; không còn quái giả ở (5,2)); kế hoạch 24 bước diệt 2/3 quái, đi qua ô gỗ mở (3,3), không đi vào ô đóng (đã vẽ ảnh kiểm tra). 80 bàn ngẫu nhiên có ô gỗ đóng/mở/đá/quái/kim cương: 0 đường sai luật, 0 lần đi vào ô gỗ đóng, 133 lần đi qua ô gỗ mở; luật đóng = đá, mở = thú thường, mở nhưng khác loại thú thì không nối được.
- GIẢ ĐỊNH chưa xác nhận (cần người dùng xem game thật): (1) game đổi trạng thái đóng/mở lúc nào chưa biết (theo lượt? sau khi đi qua?) nên bot KHÔNG dự đoán, chỉ đọc lại trạng thái ở đầu MỖI lượt; chưa mô hình hoá việc ô gỗ đổi trạng thái ngay sau lượt đang đi (ảnh hưởng `_EndEval` - vị trí kết thúc); (2) đứng/kết thúc ở ô gỗ mở rồi hộp đóng lại thì sao chưa rõ; (3) ngưỡng màu đo trên 1 ảnh (hộp màu be); ô gỗ màu khác cần ảnh mẫu. Nếu game có quy luật đóng/mở thì báo để thêm vào mô hình.
- CHƯA SỬA (đã có từ trước): số LƯỢT đếm ngược của quái ở (5,3) đọc ra 7 (thật là 3) - ảnh hưởng điểm khẩn cấp `urgency`; repo không có `templates/` nên chưa chạy được `find_geometry` đầy đủ (dò nhân vật) ở sandbox, nhân vật được đặt tay ở (6,3). CHƯA thử trên LDPlayer thật.

## Đợt mới (2026-10-03, Ngưu Ma Vương #8) - đọc "Hiệp còn lại" + lượt cuối + kiểm tra số bước ở nút Chiến + log thưởng kim cương (áp SAU đợt #7, chỉ sửa `thtg_bot.py`)

Yêu cầu: hoàn thiện chế độ Ngưu Ma Vương theo luật: đủ bước thì thưởng kim cương (ảnh: 23 bước = 2 viên, hiện cạnh nút Chiến); bấm Chiến, đánh xong thì LƯỢT SAU 2 ô quái con ngẫu nhiên biến thành kim cương; "Hiệp còn lại" = số lượt đi còn lại, hết (ảnh: còn 9) là thua.
- Đã có từ #7 (giữ nguyên): thưởng `steps // reward_every` (w_reward) trong điểm đường đi. Vị trí kim cương thưởng là ngẫu nhiên nên KHÔNG mô hình hoá; lượt sau nhận diện lại bàn cờ là thấy.
- MỚI `read_turns_left(frame)`: đọc số trong vòng tròn "Hiệp còn lại" (vùng `TURNS_BOX`, theo tỉ lệ ảnh). Chữ số vàng sáng cách điệu (tách bằng HSV `_glow_glyphs`); Tesseract không đọc ra chữ 9 này (đã thử nhiều kiểu tiền xử lý trên ảnh thật) nên ưu tiên KHỚP MẪU (IoU, ngưỡng 0.78) với `templates/thtg_turns_<chữ số>.png`, không có mẫu thì mới OCR bỏ phiếu, không chắc thì trả None (bot chơi như cũ). Lưu mẫu: `python thtg_bot.py --add-turns-template anh.png N` (ảnh chụp lúc còn đúng N hiệp, 1 chữ số). Đã tạo sẵn `thtg_turns_9.png` từ ảnh người dùng gửi; các chữ số khác cần chụp thêm khi chơi tới (mỗi số 1 lần).
- MỚI `read_step_counter(frame)`: đọc số bước ở nút Chiến (vùng `STEPS_BOX`), OCR bỏ phiếu; ảnh thật đọc đúng 23. Cũng có `--add-steps-template` nếu OCR sai.
- `THTGBot._params_for_turn`: còn đúng 1 hiệp (lượt cuối) thì `w_reward=0`, `w_diamond=0`, `end_safety=False` (thưởng kim cương chỉ có ở lượt SAU nên vô nghĩa; dùng kim cương không bị trừ; không cần tránh kẹt) -> chỉ còn ưu tiên diệt quái. Các lượt khác giữ nguyên tham số.
- `THTGBot._verify_steps` (field `verify_steps`, mặc định true): nối xong đọc số ở nút Chiến. Đường chỉ gồm thú/kim cương thì số phải bằng số ô nối; thiếu (bấm hụt) thì bấm bù phần còn lại 1 lần rồi đọc lại; nhiều hơn thì cảnh báo. Đường có quái/lồng chỉ GHI LOG số hiển thị cạnh số dư dự kiến vì chưa biết nút Chiến hiện tổng bước hay số dư sau khi trừ quái - cần người dùng xem log rồi báo lại để chỉnh.
- `play_turn`: log "hiệp còn lại N" mỗi lượt; sau khi bấm Chiến ghi nhớ `plan.reward` (trừ lượt cuối) và đầu lượt sau log "lượt trước thưởng X kim cương, trên bàn có Y" để đối chiếu luật. File debug .txt thêm dòng Hiệp còn lại. Field mới: `verify_steps` (true), `read_turns` (true; false = không đọc hiệp, chơi như #7). `python thtg_bot.py anh.png` in thêm hiệp còn lại + số bước.
- Test (sandbox): ảnh người dùng gửi: số bước = 23 (OCR), hiệp còn lại = 9 (khớp mẫu; không có mẫu thì None, không đoán bừa); `_params_for_turn` đúng; bàn thử: lượt thường 40 bước dùng 1 viên, lượt cuối 41 bước dùng 3 viên; `_verify_steps` giả lập: khớp / thiếu -> bấm bù 2 ô / thừa -> cảnh báo / không đọc được -> bỏ qua. CHƯA chạy trên LDPlayer thật; repo không có `templates/` nên không chạy được nhận diện bàn cờ đầy đủ ở sandbox.
- GIẢ ĐỊNH chưa xác nhận: (1) vùng `TURNS_BOX`/`STEPS_BOX` đúng cho màn hình dọc như ảnh (tỉ lệ theo ảnh); (2) hết hiệp mà chưa thắng là thua nên lượt cuối chỉ lo diệt quái.

## Đợt mới (2026-10-03, Ngưu Ma Vương #7) - luật kim cương (thưởng mỗi 10 bước) + tránh KẸT/góc ở bước cuối + sửa lỗi bộ giải chính xác với ô lồng (áp SAU `thtg_cage.patch` / đợt #6)

Yêu cầu: (1) hạn chế bước cuối đi vào góc / chỗ dễ kẹt (lượt sau quái chặn hết, không còn đường); lồng nếu dư nước thì đi mở (làm trống đường + lấy kim cương); (2) kim cương chỉ để tạo lối đi, không cần ăn hết: đi 10 bước thưởng 1 viên ngẫu nhiên, 20 -> 2, 30 -> 3...; nên tròn mốc, vd 33 bước dùng 3 viên là hợp lý còn 31 bước chỉ cần 2 viên thì dùng 2 viên, chừa 1; (3) mục tiêu vẫn là diệt hết quái to trước.
- `thtg_bot.py::SolverParams`: `w_diamond` ĐỔI NGHĨA + giá trị: từ +15 (thưởng khi ăn) thành -40 (TRỪ mỗi viên dùng); thêm `w_reward=60` (cộng cho mỗi viên thưởng) + `reward_every=10` (thưởng = số bước // 10). Điểm 1 đường = quái + `w_step*bước` + `w_diamond*viên dùng` + `w_reward*(bước//10)` + cage - phạt vị trí cuối. Đo: tối đa 49 bước*10 + 4 mốc*60 = 730 < `w_kill` 1000 nên diệt quái vẫn luôn ưu tiên số 1. Lồng vẫn `w_cage=200` (chỉ đi lồng khi còn dư bước sau khi đã diệt được quái vì diệt quái lớn hơn nhiều).
- `thtg_bot.py::_EndEval` (mới) + field `end_safety`, `fall_down`, `open_pen=(2500,400,150,50)`, `w_corner=150`, `w_edge=40`, `reach_min=8`, `w_reach=25`: phạt VỊ TRÍ CUỐI. Mô phỏng sau lượt: các ô đã đi (và ô xuất phát của nhân vật) biến mất, ô còn lại rơi xuống theo cột, ô mới phía trên chưa biết coi là đi được; nhân vật đứng ở ô cuối. Đầu lượt sau chưa có bước nên chỉ vào được thú/kim cương (quái to, lồng, đá không vào được). Phạt theo số ô kề đi vào được (0 = kẹt hẳn 2500, 1 = 400, 2 = 150, 3 = 50) + góc 150 / mép 40 + vùng đi vào được liền nhau quanh nhân vật < 8 ô thì 25/ô thiếu. KHÔNG phạt khi đường đi diệt nốt quái to cuối (thắng). Beam và `evaluate_path`/`_plan_from_path` dùng cùng hàm này; bộ giải chính xác nhận qua `end_fn(tip, mask)` (phạt <= 0 nên cận trên vẫn hợp lệ). `Plan` thêm `reward`, `end_pen`. Điểm có thể ÂM nên khởi tạo best = -1e18 (trước là 0 -> nếu mọi đường đều âm thì trả "không có đường"); `solve()` coi đường vi phạm luật là -1e18 thay vì 0.
- `thtg_solver.py::solve_exact`: thêm tham số `w_reward=0.0, reward_every=10, end_fn=None` (mặc định = hành vi cũ); cận trên cộng `w_reward*((bước+bs)//reward_every)`, kim cương `dv` chỉ cộng vào cận khi `w_diamond > 0`; phạt vị trí cuối chỉ tính khi điểm gốc đã vượt best.
- SỬA LỖI CÓ SẴN (quan trọng): `bound()` trong `thtg_solver.py` bị `ValueError: negative shift count` khi tip là ÔLỒNG đang giữ loại thú (`comp_of[tip] == -1` nhưng color >= 0). `solve()` bắt `except Exception` nên bộ giải chính xác bị bỏ lặng lẽ và bàn có lồng chỉ còn chạy beam. Sửa: tip là lồng -> dùng nhánh nới lỏng (vẫn là cận hợp lệ). Sau sửa, 14 bàn nhiều chướng ngại có lồng: chứng minh tối ưu 12/14 (trước 1/14).
- Field bước mới (đều tuỳ chọn): `diamond_cost` (40), `diamond_reward` (60), `reward_every` (10), `end_safety` (true), `fall_down` (true), `w_corner` (150), `w_edge` (40). Log mỗi lượt thêm "dùng N kim cương, thưởng M (ròng ±k)" và dòng nhân vật sẽ đứng ở đâu / bị phạt bao nhiêu; file debug .txt thêm phạt vị trí cuối.
- Test (sandbox, mỗi phiên bản chạy tiến trình riêng vì `solve()` import `thtg_solver` lúc gọi): 150 bàn ngẫu nhiên nhiều chướng ngại (3-5 quái, 1-3 lồng, 4-8 đá) cũ -> mới: quái diệt 339 -> 352; kết thúc gần như kẹt (<= 1 ô đi tiếp) 5 -> 0 (3 ca cũ kẹt hẳn, phạt 2650 mỗi ca); kết thúc ở góc 21 -> 3 (còn lại là không tránh được); tổng phạt 16720 -> 2580; kim cương dùng 209 -> 187 trong khi thưởng 194 -> 213. 16 bàn nhẹ: thưởng 30 -> 33, dùng 31 -> 27. Bàn toàn mèo + 3 kim cương: đi 45 bước dùng 0 viên (vẫn đủ 4 viên thưởng); kiểu cũ đi 48 bước ăn cả 3 viên. Hồi quy (tham số kiểu cũ `w_diamond=15, w_reward=0, end_safety=False`): 6 bàn tốt hơn, 10 bằng, 0 kém. Ảnh người dùng gửi (9 quái + 2 lồng): 39 bước, diệt 6 quái, dùng 3 viên, thưởng 3, mở 1 lồng, nhân vật đứng ở (1,6) mép phải (phạt 40, còn nhiều ô đi tiếp).
- GIẢ ĐỊNH chưa xác nhận trên game thật (cần người dùng kiểm khi chạy): (1) ô rơi xuống theo cột và nhân vật đứng yên ở ô cuối; nếu thực tế khác thì đặt `fall_down: false` hoặc chỉnh `open_pen`; (2) thưởng kim cương = bước // 10 xuất hiện ở ô ngẫu nhiên (không mô hình hoá vị trí); (3) `w_diamond=-40`, `w_reward=60`, các mức phạt chỉ là ước lượng. Muốn quay về kiểu cũ (ăn kim cương, không phạt cuối): `diamond_cost: 0, diamond_reward: 0, end_safety: false`.
- LƯU Ý tốc độ: bàn khó nhất (9 quái + 2 lồng) tính khoảng 25-30s trong sandbox (beam ~17s + 2 lần exact ~5s, trước đây ~15s vì exact bị lỗi lồng bỏ qua). Giảm bằng `exact_nodes` (vd 150000); beam có mức tối thiểu 5000 do `run_auto_thtg_step`. Chưa thử LDPlayer thật.

## Đợt mới (2026-10-03, Ngưu Ma Vương #6) - sửa luật ô lồng: đi qua lồng KHÔNG đổi loại (áp SAU `thtg_cage.patch`)

Người dùng đính chính: đi qua lồng thì không được đổi loại thú; phá lồng xong nó thành kim cương thường thì mới đổi loại được (từ lượt sau).
- `thtg_bot.py::_step`: nhánh `mtype == "cage"` trả `color` (GIỮ loại đang nối) thay vì -1; vẫn cần bal >= N, trừ N, +1 bước, không tính diệt, điểm `w_cage`. `_to_exact_grid` gửi lồng sang bộ giải chính xác bằng kind mới `"L"` (quái vẫn là `"M"`).
- `thtg_solver.py`: hỗ trợ kind `"L"` - như `"M"` về số bước/điểm nhưng KHÔNG đặt lại loại (`dfs(j, nm, color, ...)`). Khoá nhớ `seen` thêm loại hiện tại cho ô L (vì qua lồng giữ loại nên loại tại ô L phụ thuộc đường đi). CẬN TRÊN (`bound`) tính L như cầu nối (cho phép đổi loại = nới lỏng hơn thực tế) nên vẫn là cận hợp lệ, không cắt nhầm đường tối ưu, chỉ cắt kém hơn chút.
- Test (sandbox): F-lồng-F hợp lệ, F-lồng-O (đổi loại qua lồng) KHÔNG hợp lệ, F-kim cương-O hợp lệ; 40 bàn nhiều đá so với VÉT CẠN: lệch 0/40 (15 đường có đi qua lồng); 40 bàn đầy có lồng: 0 đường sai luật, solve không thua beam, không bàn nào chậm quá 3s; ảnh thật người dùng gửi: 32 bước, diệt 3 chuột, mở 2/3 lồng, 0.64s (dùng beam vì exact hết số nút, nên "tối ưu" = False).
- LƯU Ý: lồng giờ không còn là cầu nối đổi màu nên kế hoạch trên ảnh thật ngắn hơn (40 -> 32 bước); và bộ giải exact với lồng khó chứng minh tối ưu hơn (cận lỏng) nên thường rơi về beam + exact. Chưa thử LDPlayer thật. Giả định còn lại: đi qua lồng bị trừ N bước; `w_cage` = 200 là ước lượng.

## Đợt mới (2026-10-03, Ngưu Ma Vương #5) - ô LỒNG (thêm vào thtg_bot.py, áp SAU patch `thtg_rage_wait_fix_v2`)

Yêu cầu: ô lồng (khung đỏ/cam nhốt viên ngọc, số N ở góc) giống quái to ở chỗ cần đủ bước mới đi qua được, nhưng đi qua thì lồng KHÔNG mất mà mở khoá thành kim cương thường. Trước đây lồng bị nhận nhầm là quái to (huy hiệu số) nên bị tính là "diệt quái" (+1000 +500 điểm) và bot dồn đường đi vào lồng.
- Nhận diện: `_is_cage()` - lồng có thanh khung hồng/cam chạy ngang gần hết ô + nhiều thanh dọc (đo trên ảnh người dùng gửi: lồng thanh trên 0.90-0.93, 24-27 cột; chuột 0.00 và 0 cột). Chỉ xét ô đã có huy hiệu số. `classify` trả `Cell("monster", mtype="cage")` TRƯỚC khi xét mẫu quái. Không đọc đồng hồ cát cho lồng (trước đây ra số lượt rác, vd lồng đọc ra 7).
- Luật trong solver (`_step`): lồng cần bal >= N như quái, trừ N, +1 bước, đổi loại tự do (-1); KHÔNG tính kill; điểm cộng `SolverParams.w_cage` (mặc định 200: thấp hơn diệt quái 1000, cao hơn kim cương 15; 0 = chỉ qua khi làm cầu nối). Lồng không nằm trong danh sách mục tiêu của beam nhắm quái (`monsters`) nhưng vẫn là cầu nối (`mon_mask`). `_to_exact_grid` truyền `w_cage` cho thtg_solver (không sửa thtg_solver.py). `Plan.killed` không gồm lồng.
- Tiện ích: `board_from_strings` nhận `L` (lồng), `Board.pretty` in `L5`, log "đường đi mở khoá N ô lồng", `_vote_monsters` ghi "LỒNG cần N", file debug .txt thêm dòng "Lồng (hàng, cột, số bước cần)".
- Test (sandbox, ảnh thật người dùng gửi, dựng ô bằng `classify` vì repo không có templates/): 3 lồng (2,3) (4,1) (4,5) số 5 nhận ĐÚNG là lồng, 3 chuột (2,1)=5 (2,5)=6 (4,3)=7 nhận đúng là quái; kế hoạch 40 bước diệt cả 3 chuột và mở cả 3 lồng; 60 bàn ngẫu nhiên có lồng: 0 đường vi phạm luật, exact và beam khớp.
- GIẢ ĐỊNH chưa xác nhận (cần người dùng kiểm khi chạy thật): (1) đi qua lồng cũng bị TRỪ N bước như quái; (2) đi qua lồng thì được đổi loại thú như kim cương; (3) giá trị w_cage = 200 chỉ là ước lượng. Lồng màu khác ngoài hồng/cam chưa có mẫu để thử.
- PHÁT HIỆN CHƯA SỬA: đọc số LƯỢT đếm ngược của chuột trên ảnh này sai (chuột (2,1) thật là 2 nhưng đọc ra 7, chuột (4,3) đọc ra 4 không chắc; thật là 2) - ảnh hưởng điểm khẩn cấp `urgency`. Cần ảnh gốc/ô cắt để chỉnh `_turns_votes`.

## Đợt mới (2026-10-03, Ngưu Ma Vương #4) - chỉnh lại patch `thtg_rage_wait_fix.patch` cho khớp repo (chỉ `thtg_bot.py`)

Patch gốc không áp được (`git apply --check` báo lỗi ở hunk 1) vì repo đã chứa SẴN một phần nội dung của nó. Đã tách từng hunk và đối chiếu:
- ĐÃ CÓ trong repo (giữ nguyên, không áp lại): `SolverParams.target_beams/w_target/w_need` + beam nhắm quái (`run_beam(..., target, bal_need)`), `BoardDetector.signature`, `_settle` dùng chữ ký bàn cờ, `rage_portrait=True` + `rage_delay` + `ready_first_wait`, `_press_skill` mới (TEST chỉ ghi log), lưu ảnh khi kế hoạch <= 4 bước, vòng `rage_tries` trong `run()`, docstring/`run_auto_thtg_step` của `rage_delay`/`ready_first_wait`.
- ĐÃ THÊM (phần còn thiếu): `BoardDetector.last_raw`; `_turns_votes` / `_number_votes` (OCR nhiều kiểu nhị phân hoá + bỏ phiếu, trả `(giá trị, đọc_chắc)`; chỉ nhận lượt 1-9) - `read_monster_turns` / `read_monster_number` giữ nguyên tên và chữ ký, chỉ còn là lớp bọc; `THTGBot._vote_monsters` (chụp thêm tới `vote_frames` khung cho quái đọc chưa chắc, log số đã dùng) gọi trong `play_turn`; `_parse_rage` + `_rage_white_ocr` + `read_rage` mới (tách chữ TRẮNG trên nền cam, 2 vùng đọc, nhận x >= 1000); log + lưu ảnh `*_khong_doc_duoc_no` (tối đa 3 lần) khi không đọc được thanh nộ; field bước mới `vote_frames` (3; 1 = tắt).
- Không đổi tên hàm/lớp/field có sẵn. Test sandbox (Tesseract thật, ảnh giả): `_parse_rage` 7/7, `read_rage` đọc đúng 2685/1000, 1000/1000, 350/1000, `_number_votes` đúng 3/5/6/8/12, `run()` với adb giả không lỗi. CHƯA thử trên LDPlayer thật (số 30/30 trong patch gốc đo trên ảnh thật của người dùng, chưa kiểm lại được ở đây).
- LƯU Ý (giữ đúng thiết kế patch gốc, chưa sửa): `_vote_monsters` khi hoà phiếu thì giữ số của khung đầu, nên nếu khung đầu đọc sai (chưa chắc) và khung thứ 2 đọc đúng (chắc) thì vẫn ra số khung đầu; nên cho số đọc "chắc" thắng nếu người dùng đồng ý.

## Đợt mới (2026-10-02, Telegram #1) - tin "xong" nêu TÊN cái đã chạy + tin tổng kết cho Lịch Hẹn Giờ

Yêu cầu người dùng: tin "🏁 Xong toàn bộ phiên" phải gọi đúng tên (xong phiên Thư ký / xong nhóm X / xong lịch hẹn giờ Y); lịch hẹn giờ trước đây KHÔNG có tin tổng kết.
- `session_report.py`: thêm nhãn theo giả lập - `REPORT.set_label(idx, "phiên A, B +N" | "nhóm X" | "lịch hẹn giờ Y")`, mỗi dòng ghi nhận mang field `label`; `short_names(names, limit=3)`; `REPORT.take(idx)` lấy+xoá riêng dòng của 1 giả lập; `close/discard/take` xoá nhãn. `format_report(rows, t_finish=None, title=None)`: title=None -> tự ghép từ nhãn các dòng ("🏁 Xong phiên Thư ký · nhóm X"), không có nhãn -> "🏁 Xong toàn bộ phiên" như cũ.
- `dashboard_run.py`: `_worker_run_emulator` đặt nhãn "phiên <tên các tác vụ đã tick>"; `_worker_run_group` đặt "nhóm <tên nhóm>". `dashboard_accounts.py::_worker_run_emulator_with_accounts`: "phiên <tên> (xoay vòng tài khoản)". Tin tổng kết vẫn gửi ở `_on_finish_all` (sự kiện `all_done`, mặc định TẮT).
- `dashboard_schedule.py`: `_worker_run_schedule` đặt nhãn "lịch hẹn giờ <tên lịch>", ghi `add_note` khi không bật được giả lập / không thấy adb; `_on_schedule_thread_done(emulator_index, schedule_name=None)` lấy `REPORT.take(idx)` rồi gửi tin RIÊNG "🏁 Xong lịch hẹn giờ <tên>" (kèm giờ, số lượt ✅/⚠️/⏹, từng Hoạt Động) - mỗi LƯỢT lịch trên mỗi giả lập 1 tin. Import thêm `notifier`.
- `notifier.py`: sự kiện mới `schedule_done` ("Xong lịch hẹn giờ ...", mặc định BẬT; config cũ thiếu key sẽ nhận mặc định BẬT; hiện tự động ở Cài Đặt Telegram vì UI lặp theo EVENTS).
- Lưu ý: các tin riêng từng Hoạt Động của lịch (▶️ Bắt đầu / ✅ Hoàn thành) đã có từ trước (notify_run=True) và phụ thuộc 2 ô task_start/task_done ở Cài Đặt Telegram. Chưa có tin "BẮT ĐẦU lịch" riêng. Test bằng mô phỏng (không gửi Telegram thật).

## Đợt mới (2026-10-02, Tự Login sau khi mở lại game #1) - game văng/đơ được mở lại nhưng KHÔNG đăng nhập lại

Lỗi người dùng báo: chương trình (game) bị tắt đột ngột -> bot chỉ mở lại, không chạy `auto_login` nên không vào được game.
- NGUYÊN NHÂN: trong `dashboard_run.py::_exec_entry`, sau khi `_recover_hung_emulator` mở lại game (`_soft_recover_game`: force-stop + monkey) hoặc khởi động lại giả lập, code chỉ chạy lại Tự Login khi `self._login_by_emu[emulator.index]` có giá trị - mà dict này CHỈ được ghi ở `_worker_run_emulator` (nút CHẠY tay). Mọi luồng khác (Hẹn Giờ, Xoay Vòng Tài Khoản, Nhóm Hành Động, Hành Động Cuối, 🎁 Sự Kiện) gọi thẳng `_exec_entry` nên `login_entry = None` -> chạy lại tác vụ ngay từ đầu khi game đang ở màn hình đăng nhập/chờ. (`_soft_recover_game` / `_recover_hung_emulator` chỉ chờ "Chờ boot" chứ không đăng nhập, đúng thiết kế.)
- SỬA (`dashboard_run.py::_exec_entry`, vòng phục hồi treo): nếu `_login_by_emu` không có mà ô "Tự Login" (`auto_login_var`) đang bật và tác vụ đang chạy không phải chính `auto_login` -> tự `task_registry.find_task(self.tasks, "auto_login")` rồi chạy nó (truyền `context_label`/`event` của luồng hiện tại) TRƯỚC khi chạy lại tác vụ. Chưa soạn `auto_login` thì ghi cảnh báo. `auto_login` thất bại (không treo) chỉ cảnh báo rồi vẫn chạy lại tác vụ như hành vi cũ của luồng CHẠY tay. Luồng CHẠY tay không đổi.
- LƯU Ý: điều kiện là ô "Tự Login" phải được TICK. Nếu bỏ tick thì mọi luồng vẫn không đăng nhập lại (như thiết kế cũ). Chưa thử trên LDPlayer thật.

## Đợt mới (2026-10-02, OCR #2) - OCR nhận số ÂM / số LẺ + ô "Ký tự chấp nhận thêm"

Lỗi người dùng báo: bước `ocr_text` chỉ có "Cả chữ và số" / "Chỉ số" / "Chỉ chữ". Chọn "Chỉ số" thì `-100` thành `100` (lớn hơn 90 -> IF Biến `<= 90` sai), `90.8` thành `908`, vì `filter_ocr_charset` + whitelist Tesseract chỉ giữ 0-9, làm rơi dấu `-` và `.`. (Tái hiện được bằng Tesseract thật ở sandbox: `-100` -> `100`, `90.8` -> `908`.)
- `adb_helper.py`: kiểu ký tự mới `charset: "number"` = SỐ có thể âm/lẻ. `_normalize_ocr_number()`: giữ chữ số, đúng 1 dấu `-` ĐỨNG ĐẦU (gộp các dấu gạch lạ − – — ~ về `-`, `-` ở giữa là nhiễu -> bỏ), dấu thập phân `.`; `,` coi là thập phân nếu chỉ có 1 dấu phẩy với 1-2 chữ số sau (`90,8` -> `90.8`), còn lại coi là ngăn cách hàng nghìn (`1,000` -> `1000`); nhiều dấu `.` -> bỏ hết (`1.000.000` -> `1000000`). `ocr_text_in_box(..., extra_chars="")` thêm tham số; whitelist Tesseract của 'number' = `0123456789-.,` + extra. Chọn kết quả: với 'number' ưu tiên các bản đọc LÀ SỐ HỢP LỆ (`ocr_looks_like_number`) rồi mới lấy bản dài nhất (tránh nhiễu như `-.`). `filter_ocr_charset(text, charset, extra_chars="")`.
- Ô "Ký tự chấp nhận thêm" (field mới `extra_chars` của bước `ocr_text` / `if_ocr` / lá `ocr` của `if_group`; thiếu field = rỗng = như cũ): các ký tự này luôn được giữ lại và đưa vào whitelist ở 'digits'/'number', và ở 'letters' (kể cả chữ số được liệt kê thì không còn bị blacklist). 'all' vốn giữ hết nên không ảnh hưởng. Ký tự trắng, `'`, `"`, `\` bị bỏ khỏi ô (làm hỏng chuỗi cấu hình Tesseract).
- `logic_engine.py`: 3 chỗ gọi `ocr_text_in_box` (lá 'ocr' của if_group, `if_ocr`, `ocr_text`) truyền thêm `extra_chars`; `_OCR_CHARSET_VN` thêm "number"; log OCR hiện thêm `+ '<ký tự>'`.
- GUI: `gui_dialogs.py` (`OCR_CHARSET_LABELS` thêm "number": "Chỉ nhận SỐ có thể ÂM / LẺ (-100, 90.8)", `OCR_EXTRA_HINT`, `ocr_charset_tag()`, thêm ô nhập vào `IfOcrDialog` và `OcrVarDialog`, result có `extra_chars`), `gui_dialogs_ifgroup.py` (ô nhập ở `IfGroupOcrLeafDialog`, nhãn nút lá dùng `ocr_charset_tag`), `gui_canvas.py` (ghi `extra_chars` khi thêm bước mới), `gui_step_edit.py` (sửa bước: nạp/ghi `extra_chars`, rỗng thì xoá field), `gui_steplist_ops.py` (danh sách bước hiện `[số âm/lẻ]` và `[+ký tự: ...]`).
- Kịch bản cũ (`charset: "digits"`) giữ nguyên hành vi. Muốn kịch bản cũ nhận số âm/lẻ: sửa bước Quét OCR đổi kiểu sang "Chỉ nhận SỐ có thể ÂM / LẺ" (hoặc giữ "Chỉ số" và gõ `-.` vào ô ký tự thêm).
- Test (sandbox, Tesseract thật + font TrueType): `-100`, `90.8`, `-5.5`, `120.25`, `-0.75` đọc đúng ở chế độ 'number' (nền tối/sáng); 'digits' cũ vẫn ra `100`, `908`. Dựng 3 hộp thoại dưới xvfb: kết quả có `charset` + `extra_chars` đúng. CHƯA thử trên LDPlayer thật.
- LƯU Ý (chưa sửa, theo quy tắc không đổi hành vi cũ): `LogicEngine._compare_values` khi biến RỖNG (OCR không đọc ra gì) và toán tử `<`/`<=` thì so sánh CHUỖI nên `"" <= 90` ra ĐÚNG -> IF "nhỏ hơn" có thể chạy nhánh mua khi OCR thất bại. Nên chặn nếu người dùng đồng ý.

## Đợt mới (2026-10-02, Ngưu Ma Vương #3) - đổi tên game, nước đi ổn định + ưu tiên diệt hết quái to

Yêu cầu: đổi tên game thành Ngưu Ma Vương; nước đi chưa tối ưu (ảnh 1 bot đi 13 bước, diệt 1 gấu; ảnh 2 người đi 16 bước, diệt cả 2 gấu); mỗi lần chạy đi một kiểu.
- NGUYÊN NHÂN tái hiện được: dựng lại bàn cờ từ ảnh (nhân vật (4,4), gấu số 6 ở (2,3) và (3,1), kim cương (2,4)). `solve()` cũ có `time_limit=3.0` rồi `break` giữa chừng: máy chậm/đang bận (ADB, chụp màn hình, nhiều giả lập) thì beam bị cắt sớm. Cùng bàn cờ, giả lập time_limit 3s/0.2s/0.1s/0.05s cho 24/24/13/11 bước, diệt 2/2/2/1 quái -> đúng kiểu "13 bước, 1 gấu" của ảnh 1, và mỗi lần một khác.
- `solve()`: bỏ cắt theo giờ (`SolverParams.time_limit` mặc định 0 = không giới hạn; >0 chỉ để test), xếp hạng beam có khoá phụ cố định (hoà điểm vẫn ra cùng 1 đường), chạy beam 3 bộ trọng số phụ `variants` (w_region, w_pull) rồi lấy đường tốt nhất. Beam mặc định 2000 -> 5000 (40 bàn ngẫu nhiên: beam 2000 thua beam 12000 ở 5/40 bàn, 5000 là 0/40; ~0.12s/bàn). `run_auto_thtg_step` coi 5000 là tối thiểu (kịch bản cũ lưu beam=2000 vẫn được hưởng); `gui_manual_steps.py` bước mới ghi beam 5000.
- Ưu tiên quái to: giữ thứ tự diệt quái > số bước > kim cương (w_kill=1000 luôn lớn hơn 49 bước x 10). Thêm `Cell.mtype` (mặc định "boss") + `SolverParams.monster_weights` (điểm cộng theo loại) + `monster_extra()`: sau này có loại quái mới chỉ cần detector gán `mtype` và thêm 1 dòng trọng số. `_step` trả điểm cộng thay vì cờ 0/1 (chỉ dùng nội bộ).
- `read_monster_number`: trước đây mặt nạ "màu đỏ" lẫn hào quang hồng/móng quái nên Tesseract hay trả 0 -> rơi về `monster_default` 7 (trên 2 ảnh: đọc đúng 1/4 ô). Nay tìm huy hiệu màu KEM, lấp đầy rồi chỉ lấy chữ đỏ nằm TRONG huy hiệu: 4/4 ô đọc đúng số 6.
- Đổi tên hiển thị "Thất Thánh" -> "Ngưu Ma Vương": nút/menu/ghi chú bước (`gui_ui_build.py`, `gui_manual_steps.py`, `gui_steplist_ops.py`), comment `logic_engine.py`, tiền tố log trong `thtg_bot.py`. KHÔNG đổi tên hàm/lớp/field/action (`auto_thtg`, `THTGBot`, `run_auto_thtg_step`, `thtg_*.png`) theo quy tắc dự án.
- Test (sandbox): bàn cờ dựng từ ảnh -> 25 bước diệt cả 2 gấu, `validate_path` hợp lệ; chạy 5 lần + khi 8 luồng ăn CPU: luôn đúng 1 đường. CHƯA thử trên LDPlayer thật; mô hình giả định nhiều bước hơn = sát thương cao hơn (ảnh: 13 bước 381, 16 bước 714).
- LƯU Ý: repo không có `templates/` nên không chạy được nhận diện đầy đủ ở sandbox; `find_board_rect` trả None trên 2 ảnh này (ô nền xanh rêu, không phải màu be) - cần xem log/ảnh `debug_thtg/` nếu bot báo không thấy bàn cờ.

## Đợt mới (2026-10-02, Thất Thánh #2) - sửa auto_thtg: nhân vật ở ô bất kỳ, heo đỏ, ăn hết cụm cuối, lưu ảnh TEST

Lỗi người dùng báo: (1) map mới báo "không thấy nhân vật/bàn cờ"; (2) bot không ăn hết các con cùng màu ở cuối đường đi; (3) chế độ TEST cần lưu lại đường đi thử.
- (1) Nhân vật KHÔNG cố định ở hàng 0: đầu trận có map đứng hàng dưới (hàng 6, cột 3) và sau mỗi lượt đứng ở cuối đường đi. Trước đây chỉ tìm mẫu ở 25-50% chiều cao ảnh + giả định (0,3). Nay `find_board_rect` dò khung 7x7 theo màu nền ô be (chịu được cửa sổ LDPlayer bị cắt/tỉ lệ khác), `find_geometry` tìm mẫu nhân vật trên TOÀN BỘ bàn cờ rồi suy ra (hàng, cột) -> trả `(Geometry, hero)`; `Board.hero` đã có sẵn và solver vốn xuất phát từ `board.hero`. `Geometry.cx0/cy0` giờ là TÂM Ô (bấm đúng giữa ô).
- Map mới có THÊM con HEO đỏ/hồng (loại thứ 4, ký hiệu `P`): `ANIMALS` có 4 loại, `classify` tách bò (hue 5-16) và heo (hue >=165 hoặc <=4); `board_from_strings` nhận `P`.
- Số trên quái to (vd 8): `read_monster_number` đọc chữ số ĐỎ trên huy hiệu (mặt nạ màu đỏ, bỏ chấm nhiễu, Tesseract 3 chế độ rồi bỏ phiếu); không đọc được thì dùng `monster_default`.
- (2) Beam search trước đây xếp hạng theo "số ô đi tiếp" nên hay bỏ sót cụm cùng loại ở cuối. Nay `solve` dùng bitboard (lưới bit rộng 8) + flood-fill: điểm phụ `w_region` = số ô cùng loại (kim cương/quái làm cầu nối) còn nối liền được từ đầu đường -> đường đi ưu tiên ăn hết cụm. Mặc định beam 2000. Thử 150 bàn ngẫu nhiên: trung bình 14,1 bước (cũ 13,0), diệt 77 quái (cũ 67), chỉ 5/150 bàn ngắn hơn bản cũ.
- (3) `THTGBot` có `save_debug` (mặc định = chế độ test) + `debug_dir` (mặc định `debug_thtg/`): mỗi lượt lưu `HHMMSS_luotN.png` (đường đi vẽ lên ảnh, đánh số bước) + `.txt` (ma trận bàn cờ, vị trí nhân vật, đường đi, số quái). Không thấy bàn cờ thì lưu `HHMMSS_khong_thay_ban_co.png` để chẩn đoán. Field bước mới: `save_debug`, `debug_dir`.
- Ngưỡng khớp nhân vật hạ 0,40 -> 0,33 (khung hình đang hoạt ảnh vẫn nhận ra).
- Test (sandbox): ảnh map mới (nhân vật hàng 6) nhận diện đúng 49/49 ô gồm heo, lửa, quái số 8, đường đi 17 bước diệt quái rồi ăn tiếp ếch; ảnh map cũ vẫn đúng; 300 bàn ngẫu nhiên (nhân vật ở ô bất kỳ, 3-4 loại, đá, kim cương, quái) không có đường vi phạm luật.
  CHƯA thử trên LDPlayer thật. Chưa làm: quái nhỏ có lửa đứng cạnh mất máu, phạt quái to có skill không diệt hết lượt, nhận diện đá bằng ảnh, đọc "Hiệp còn lại".

## Đợt mới (2026-10-02, Thất Thánh) - ⚔️ Auto Thất Thánh - Phàn Đầu (bước `auto_thtg`)

Yêu cầu: auto mini game lưới 7x7 (Ngưu Ma Vương): nối các con CÙNG LOẠI (ếch/bò/mèo) thành đường đi 8 HƯỚNG, mỗi ô +1 bước, quái to số N cần đủ N bước (10 bước, quái 7 -> 3, +1 bước vừa đi = 4), kim cương / diệt quái to thì được đổi loại; mỗi lượt ô đã đi biến mất, quái mới rơi từ trên xuống; bấm lần lượt từng ô là nối được; nộ đầy bấm "Chiến".
- `thtg_bot.py` (mới, không import tkinter): `Board/Cell`, `solve()` = beam search (mặc định beam 2000, ~0.3s) tối ưu 1 lượt: diệt quái to (ưu tiên quái có skill) > số bước (nạp nộ) > kim cương; `validate_path()` mô phỏng lại luật; `BoardDetector` (nhận diện: nhân vật bằng `templates/thtg_hero.png` -> suy ra lưới; thú theo màu HSV; kim cương/quái to bằng template; lửa bằng điểm vàng trên đầu; số quái đọc bằng OCR của adb, không được thì dùng `monster_default`); `THTGBot` (chụp -> tính -> bấm từng ô bằng `tap_px` -> chờ hoạt ảnh xong -> lặp; đọc nộ x/1000 bằng OCR, đủ thì bấm Chiến); `run_auto_thtg_step` (điểm nối). Chạy riêng: `python thtg_bot.py anh.png [beam]` -> in bàn cờ + đường đi, lưu `thtg_debug.png`.
- Field bước: `test` (true = chỉ tính, KHÔNG bấm), `max_turns` (50), `beam` (2000), `tap_delay` (0.12), `use_skill` (true), `monster_default` (7), `count_step_first` (false: cần bước >= N; true: cần bước+1 >= N).
- `logic_engine.py`: import + nhánh `act == "auto_thtg"`. `gui_manual_steps.py`: `add_manual_auto_thtg`, `_toggle_auto_thtg_test`. `gui_ui_build.py`: nút "⚔️ Auto Thất Thánh", mục menu chuột phải, menu đổi TEST/thật. `gui_steplist_ops.py`: hiển thị bước. `templates/`: `thtg_hero.png`, `thtg_diamond.png`, `thtg_bigmonster.png`.
- Test (sandbox): nhận diện đúng 49/49 ô loại thú + kim cương + quái to trên ảnh thật 671x1183 (cờ lửa còn sót 1 ô hàng 0, chưa dùng trong điểm); 200 bàn ngẫu nhiên (có đá, nhiều quái, kim cương) không có đường vi phạm luật; chạy qua adb giả: bấm đúng tâm ô, TEST không bấm.
  CHƯA thử trên LDPlayer thật. Chưa làm: quái nhỏ có lửa (đứng cạnh mất máu), quái to có skill phạt khi không diệt hết lượt, ô đá nhận diện bằng ảnh (solver đã chặn đá), đọc "Hiệp còn lại". Cần xác nhận: số 50 cạnh thanh kiếm, ý nghĩa ngọn lửa trên thú, đi vào quái cần bước >= N hay bước+1 >= N.

## Đợt mới (2026-10-02, chụp ảnh) - 📸 Auto Chụp Ảnh (bước `auto_photo`)

Yêu cầu: auto cho game chụp ảnh tiệm ảnh, 25 mức khách (PhotoQuestionDB.csv: 5 phong cách x 5 mức). Chọn 1 Nền (bắt buộc, 12 hình) + 1 Trang Trí (tuỳ chọn, 12 hình), 2 dải kéo ngang; vạch chỉ phải vào vùng vàng trên thanh đo.
- Phân tích 54 ảnh chụp màn hình (720x1280): thanh đo thang 0-20 điểm (~24,65 px/điểm, x=112 là 0); vùng vàng = cột `score` của CSV (2|5, 6|9, 10|13, 14|17, 17|20), sáng lên khi vạch nằm trong; điểm mỗi hình KHÁC nhau theo khách nên bot ĐO trực tiếp bằng cách bấm từng hình rồi đọc vạch.
- `photo_bot.py` (mới, không import tkinter): `detect_bar` (đọc vùng vàng + vạch + trạng thái sáng từ pixel), `PhotoBot` (duyệt Nền -> nền đơn lẻ vào vùng vàng thì chụp; không thì giữ 1 nền duyệt Trang Trí, điểm trang trí = vạch - điểm nền, dự đoán tổ hợp nền+trang trí rồi kiểm lại bằng vạch thật; dự phòng thử vài cặp gần nhất), cuộn dải bằng `estimate_shift` (so ảnh trước/sau mỗi lần kéo, mất mốc thì kéo về đầu đồng bộ lại), `bracket_score` (nhận khung chọn để bấm lại nếu bấm hụt), `run_auto_photo_step` (điểm nối). Ghi bảng điểm đo được vào `photo_scores_log.jsonl`. Chạy riêng: `python photo_bot.py anh.png`.
- Field bước: `shoot` (mặc định true; false = TEST không bấm Chụp ảnh), `max_seconds` (180), `n_bg`/`n_deco` (12), `log_path`, `csv_path`, `shoot_anyway`.
- `logic_engine.py`: import + nhánh `act == "auto_photo"`. `gui_manual_steps.py`: `add_manual_auto_photo` (hỏi chạy thật/TEST), `_toggle_auto_photo_shoot`. `gui_ui_build.py`: nút "📸 Auto Chụp Ảnh", mục menu chuột phải, menu đổi chế độ TEST/thật. `gui_steplist_ops.py`: hiển thị bước.
- Test (sandbox, game giả): detect_bar đúng 54/54 ảnh thật; 120 khách mô phỏng (cuộn đều/lệch ngẫu nhiên/chính xác) đều đúng (kể cả báo lỗi khi vô nghiệm); chạy qua LogicEngine, Dừng, hết giờ, không thấy thanh đo, TEST mode đều đúng.
  CHƯA thử trên LDPlayer thật (cuộn dải bằng adb swipe, quán tính thật) và Tkinter thật. Giả định điểm nền + trang trí CỘNG DỒN là suy ra, bot luôn kiểm lại bằng vạch thật. Màn hình phải dọc 720x1280 (tự co giãn theo ảnh chụp). Nên chạy ở chế độ TEST trước.

## Đợt mới (2026-10-02, bổ sung) - 🛠 Setup LDPlayer: chọn ldconsole + màn hình 1280x720 + bật Gỡ lỗi ADB

Yêu cầu: ở khu Setup cho người/máy mới, có công cụ chọn ldconsole, tự chỉnh màn hình LD về 1280x720, bật gỡ lỗi ADB.
- Nút '🛠 Setup LDPlayer' (nhóm TÁC VỤ NHANH, cạnh '🆕 Setup Người Mới' - nút cũ vẫn chạy kịch bản `setup_nguoi_moi` y như trước).
- `ld_setup.py` (mới, không import tkinter): `set_resolution` = `ldconsole modify --index N --resolution 1280,720,240` rồi ĐỌC LẠI `vms/config/leidianN.config` để xác nhận;
  `set_adb_debug` = ghi khoá `basicSettings.adbDebug`=1 (bật local) vào file đó (sao lưu 1 lần `.bak_ldsetup`, ghi tạm rồi đổi tên, đọc lại xác nhận); `read_settings`/`describe_settings` hiển thị hiện trạng.
- `dashboard_ld_setup.py` (mới, `LdSetupMixin`, thêm vào `DashboardApp`): cửa sổ chọn/dò ldconsole (dùng lại `choose_ldconsole_path`/`_detect_ldconsole`), tick giả lập + tuỳ chọn;
  giả lập đang chạy được TẮT (`quit_and_wait_stopped`) rồi áp dụng, tuỳ chọn bật lại; bỏ qua/chặn giả lập đang bận (`_busy_emulator_indexes`).
- Test (sandbox, ldconsole giả + file cấu hình giả): đổi 960x540/160 + ADB tắt -> 1280x720/240 + ADB local, giữ nguyên khoá khác, chạy lại idempotent, index không có file -> báo lỗi.
  CHƯA thử trên LDPlayer 9 thật: tên khoá `basicSettings.adbDebug`/`basicSettings.resolution(Dpi)` và lệnh `modify --resolution` lấy theo hiểu biết về LDPlayer 9, chương trình tự đọc lại để báo nếu không khớp.
  CHƯA thử Tkinter thật: mở cửa sổ, Áp Dụng trên 1 giả lập thử trước khi dùng cho tất cả.

## Đợt mới (2026-10-02) - 🔀 Sắp Xếp Hành Động: đổi tên Hoạt Động đổi LUÔN tên file .json + cập nhật mọi nơi dùng

Yêu cầu: đổi tên ở '🔀 Sắp Xếp Hành Động' trước chỉ đổi Tên hiển thị, file ngoài `tasks/` giữ nguyên.
- ID Hoạt Động = tên file (không đuôi) nên đổi tên file = đổi ID. Khi bấm '💾 Lưu', Hoạt Động nào có Tên hiển thị khác lúc mở cửa sổ
  sẽ được đổi file thành `<tên mới>.json` (cùng thư mục; bỏ ký tự cấm của Windows, khoảng trắng -> `_`, giữ chữ có dấu) rồi cập nhật ID cũ -> mới ở:
  Lịch Hẹn Giờ (`hoat_dong_ids` + `hanh_dong_cuoi_ids`, lưu `schedules.json`), Nhóm Hành Động (`activity_groups.json`),
  Hành Động Cuối + Sự Kiện theo giả lập (`dashboard_settings.json`), `run_state_today.json` (mọi ngày), `task_registry.json`.
  Kịch bản trong `tasks/` KHÔNG tham chiếu chéo Hoạt Động khác (chỉ tham chiếu `groups/` + ảnh) nên không cần sửa.
- `task_registry.py`: thêm `RESERVED_TASK_IDS` (auto_login, account_login, account_logout, cai_dat_shop, setup_nguoi_moi, quet_xe, uid_like -
  code tìm theo tên file nên CHỈ đổi tên hiển thị, giữ file), `slugify_task_stem`, `rename_task_file` (chịu được đổi HOA/thường trên Windows), `replace_ids`.
- `run_state.py::rename_task_ids`, `activity_groups.py::rename_task_ids`: đổi khoá/id ở file dữ liệu tương ứng.
- `dashboard_tasks.py`: `_task_rename_blocker` + `_apply_task_file_renames`; `_save_and_close` chốt tên các ô đang gõ dở trước khi lưu rồi áp đổi tên file.
  Từ chối đổi (hoàn tác tên hiển thị, báo lý do) nếu đang chạy/giả lập bận/Sự Kiện chạy nền/Hàng Chờ còn job. Trùng tên Hoạt Động khác hoặc lỗi đổi file -> báo, giữ tên file cũ.
- Test (sandbox, stub tkinter): đổi tên có dấu + nằm trong thư mục con, trùng tên, ID hệ thống, đổi HOA/thường, giả lập bận; kiểm tra schedules/nhóm/post-run/event/run_state đổi đúng.
  CHƯA thử Tkinter thật trên Windows: mở '🔀 Sắp Xếp Hành Động' -> đổi tên -> Lưu -> xem thông báo + file trong tasks/.
- Lưu ý: nếu LD Macro Studio đang mở đúng kịch bản vừa đổi tên, Lưu lại sẽ tạo lại file tên cũ - đóng/mở lại bằng tên mới. Tên Mục (thư mục con) vẫn chỉ là tên hiển thị.

## Đợt mới (2026-10-02) - Quét OCR: thêm tuỳ chọn kiểu ký tự nhận (cả chữ và số / chỉ số / chỉ chữ)

Yêu cầu: bước quét OCR có thêm lựa chọn chỉ nhận số, chỉ nhận chữ, hoặc cả 2.
- Field mới `charset` ("all" | "digits" | "letters"; THIẾU field = "all" = hành vi cũ, kịch bản cũ chạy y nguyên) trên bước `ocr_text`, `if_ocr` và lá `ocr` của `if_group`.
- `adb_helper.py`: hàm module `filter_ocr_charset(text, charset)`; `ocr_text_in_box(..., charset="all")` (tham số mới đặt CUỐI, mặc định giữ nguyên chữ ký cũ).
  digits -> Tesseract `tessedit_char_whitelist=0123456789` + lọc lại chỉ giữ 0-9 (ghép liền, bỏ dấu phẩy/chấm/khoảng trắng);
  letters -> `tessedit_char_blacklist=0123456789` + lọc lại chỉ giữ chữ cái (có dấu tiếng Việt) và khoảng trắng. Lọc áp dụng cho TỪNG biến thể ảnh trước khi chọn kết quả dài nhất.
- `logic_engine.py`: 3 chỗ gọi OCR (`_eval_condition_node` lá ocr, `if_ocr`, `ocr_text`) truyền `charset`; log `OCR: cắt vùng...` ghi thêm kiểu nhận (`_OCR_CHARSET_VN`).
- `gui_dialogs.py`: `OCR_CHARSET_LABELS`/`ocr_charset_label`/`ocr_charset_key`; `IfOcrDialog` thêm ô chọn kiểu ký tự (tham số `initial_charset`, `result["charset"]`);
  thêm `OcrVarDialog` (tên biến + kiểu ký tự) thay `simpledialog.askstring` cho bước Quét OCR.
- `gui_canvas.py`: thêm bước `ocr_text`/`if_ocr` mới lưu `charset`. `gui_step_edit.py`: sửa `ocr_var` (nay mở `OcrVarDialog`) và `if_ocr_config` đọc/ghi `charset`.
- `gui_dialogs_ifgroup.py`: `IfGroupOcrLeafDialog` thêm ô chọn + mô tả lá hiện `, chỉ số`/`, chỉ chữ`. `gui_steplist_ops.py`: dòng bước hiện `[chỉ số]`/`[chỉ chữ]`. `gui_ui_build.py`: đổi nhãn menu chuột phải thành "Sửa Tên Biến / Kiểu Ký Tự OCR".
- Test (sandbox Linux, Tesseract 5.3 thật): ảnh "Gold 12345 Mana" -> all `Gold 12545 Ma` / digits `12545` / letters `Gold Z Ma`; test `filter_ocr_charset` các ca dấu phẩy, tiếng Việt, xuống dòng, rỗng, giá trị lạ. `py_compile` 8 file OK.
  CHƯA thử Tkinter thật trên Windows: mở hộp thoại Quét OCR / IF OCR / lá OCR của IF Nhóm, kiểm tra combobox + bước lưu ra .json.
- Lưu ý: chế độ "chỉ chữ" dùng blacklist số nên chữ số trong vùng đôi khi bị Tesseract đọc thành chữ giống hình (vd `5` -> `S`); vùng quét nên chỉ chứa phần cần đọc.

## Đợt mới (2026-10-01, sửa lại) - Gọn bộ lọc dòng `list2`, cửa sổ chẩn đoán đúng theme, kiểm tra máy mới chọn ldconsole

- `emulator_manager.py`: `_parse_list2_line` viết lại gọn, đọc cột số từ PHẢI (8/5/4 cột cuối, `android_started` chỉ 0/1) nên tên có dấu phẩy kể cả dạng `Nick A,5` không còn
  bị tách sai cột (trước đây báo sai hwnd/pid -> sai trạng thái chạy); dòng rác toàn số (`1,2,3,4,5,6`) bị loại. Thêm `_parse_list2_output` (dùng trong `query_list2`, bỏ dòng trùng index).
  Thêm `_dedupe_names`: 2 giả lập trùng tên -> thêm ` (#index)` (trước đây `emu_vars` đánh khoá theo tên nên 2 ô tick dùng chung 1 biến, thiếu/lệch chọn); tên không trùng giữ nguyên.
  Thêm `EmulatorManager.set_console_path(path)`: đặt ldconsole + trỏ adb.exe về cùng thư mục LDPlayer.
- `adb_helper.py`: thêm `ADBHelper.adb_dir_hint`; `detect_adb()` ưu tiên adb.exe ở thư mục đó (sau bản portable, trước dò tiến trình). Máy mới chưa mở giả lập / không cài C:,D:\leidian trước đây rơi về `adb` trần
  (không thấy serial thật, mọi `ADBHelper()` tạo riêng ở từng luồng cũng vậy).
- `dashboard_emulators.py`: `choose_ldconsole_path` gọi `set_console_path`; lỗi list2 hiện bằng cửa sổ chẩn đoán mới `_show_console_diag` (ThemedToplevel, nền COL_PANEL, ô nội dung COL_ENTRY,
  nút Sao chép/Đóng, KHÔNG tự tắt) thay cho thông báo tự tắt 5s. `dashboard.py`: nạp `ldconsole_path` từ cài đặt cũng qua `set_console_path`.
- Test (ldconsole giả trên sandbox, KHÔNG phải Windows thật): 10 cột/tên có phẩy/`pid -1`/dòng rác/tên trùng/list2 rỗng + `vms/config`/adb cạnh ldconsole. CHƯA thử Tkinter thật: mở cửa sổ chẩn đoán.
- Chưa sửa (ghi nhận): `kill_emulator_process` vẫn tự tách `list2` theo cột cố định (sai nếu tên có dấu phẩy).

## Đợt mới (2026-10-01, bổ sung) - Nhóm Hành Động + Xoay Vòng Tài Khoản; giả lập hiện đủ + có tên khi list2 hỏng

- **Xoay Vòng Tài Khoản không cho chọn tài khoản khi bấm Nhóm**: nút Nhóm ở 'Chọn Hành Động Để Chạy' (và ▶ Chạy ở
  cửa sổ Nhóm) gọi thẳng `_start_run_group`, bỏ qua ô 'Xoay Vòng Tài Khoản'. Nay qua `dashboard_run._run_group_from_ui`:
  đang tick xoay vòng -> popup chọn Tài khoản từng giả lập, Nhóm được bọc thành entry ảo (`__group_ids__`) đi qua
  luồng xoay vòng sẵn có (đăng xuất -> đăng nhập -> chạy Nhóm với `tk_user`/`tk_pass`/biến preset). Không tick ->
  chạy thẳng như cũ. Hàng chờ/Hẹn Giờ vẫn gọi `_start_run_group` (không bật lại popup). `_run_post_run_steps` có
  thêm tham số tuỳ chọn `preset_vars`/`context_label` (mặc định giữ nguyên hành vi cũ). Entry ảo không vào bảng
  tiến độ (`dashboard_accounts._launch_run_with_accounts`, `dashboard_schedule._run_queued_manual_accounts_job`).
- **Danh sách giả lập không đủ/không tên khi `ldconsole list2` không dùng được** (`emulator_manager.py`): fallback
  nay GHÉP tên + cả giả lập đang tắt từ file cấu hình LDPlayer (`vms/config/leidianN.config`, khoá
  `statusSettings.playerName`) với trạng thái từ `adb devices`; `refresh()` vẫn chỉ trả giả lập đang chạy.
  `query_list2` thử thêm cách gọi chạy trong thư mục LDPlayer, nhận UTF-16/BOM, diag kèm byte thô để chẩn đoán.

## Đợt mới (2026-10-01) - Sửa: chọn đường dẫn ldconsole nhưng Dashboard vẫn không nhận giả lập (Macro Studio nhận)

Nguyên nhân: Macro Studio lấy thiết bị thẳng từ `adb devices`; Dashboard lấy TOÀN BỘ từ `ldconsole list2`
(`list_configured`) và khi `list2` không ra dòng hợp lệ (sai file/bản LDPlayer khác/định dạng lạ) thì trả về
DANH SÁCH RỖNG, không fallback sang adb như `refresh()`.
- `emulator_manager.py`: `query_list2()` (chạy list2, trả (rows, lý do) và lưu `last_console_diag`);
  `list_configured()` giờ fallback sang `adb devices` khi list2 không dùng được; `_parse_list2_line` chịu được
  tên giả lập có dấu phẩy + giải mã UTF-8/code page/GBK; coi giả lập là ĐANG CHẠY nếu pid>0 HOẶC serial của nó
  có trong `adb devices` (list2 báo pid -1 trên 1 số máy); dò thêm `dnconsole.exe`; `normalize_console_path()`
  (chọn nhầm dnplayer.exe/thư mục -> tự quy về ldconsole.exe/dnconsole.exe cùng chỗ).
- `dashboard_emulators.py`: '📁 Chọn ldconsole.exe' chạy thử `list2` NGAY và báo kết quả thật (thấy N giả lập
  / hộp thoại nêu lý do + nội dung list2 nhận được); `refresh_emulators` ghi lý do khi đang dùng tạm adb.
- Đã test bằng ldconsole giả: 10 cột/7 cột, tên có phẩy, list2 rỗng/in rác, pid -1, GBK, file không tồn tại.

## Đợt mới (2026-10-01) - Làm nốt "đổi ảnh nhiều nơi": sửa ảnh ở LÁ ẢNH trong IF Nhóm Điều Kiện (if_group) cũng hỏi đổi hàng loạt

Yêu cầu: pack "đổi ảnh nhiều nơi" trước còn sót phần IF ảnh / IF nhóm ảnh chưa đổi theo; kiểm tra lại và làm nốt.
Kiểm tra lại: `template_replace.py` đã QUÉT/ĐỔI đủ mọi chỗ lưu tên ảnh (`template`, `templates`, lá `image` trong cây `tree` của if_group, cả tasks/ + groups/ + kịch bản đang mở);
các đường đổi ảnh của bước thường đã có hỏi (🔄 Đổi Ảnh Khác, chụp lại ảnh, Quản Lý Ảnh Trong Nhóm). Chỗ còn thiếu duy nhất đúng như ghi chú "Chưa phủ" bên dưới:
sửa lá Ảnh trong hộp thoại cây điều kiện (`IfGroupDialog` -> `IfGroupImageLeafDialog`) thì chỉ đổi lá đó, không hỏi.
- `gui_dialogs_ifgroup.py`: `IfGroupDialog.image_changes` ({ảnh gốc: ảnh cuối}) + `_note_image_change(old, new)`; `_on_edit_selected` gọi khi sửa lá Ảnh đổi sang ảnh khác
  (A->B rồi B->C gộp thành A->C; đổi về lại A thì bỏ). Xoá lá rồi thêm lá mới KHÔNG tính là đổi ảnh.
- `gui_manual_steps.py` (`_arm_if_group_recapture`): SAU khi cây được lưu vào bước, với từng cặp trong `dlg.image_changes` gọi `_offer_replace_image_everywhere(cũ, mới)`;
  bỏ qua ảnh cũ vẫn còn ở lá khác trong chính cây này; bấm Hủy hộp thoại thì không hỏi. Thêm `import template_replace`.
- Lưu ý còn tồn tại từ trước (chưa đổi): `IfGroupDialog` sửa TRỰC TIẾP lên cây của bước, nên bấm Hủy sau khi đã sửa lá thì thay đổi vẫn còn trong bộ nhớ (chưa Lưu file). Nếu muốn Hủy là hoàn tác hẳn thì báo để bọc `copy.deepcopy(initial_tree)`.
- Test (tkinter/win32 giả): chuỗi đổi A->B->C/A->B->A, luồng `_arm_if_group_recapture` (hỏi / bỏ qua khi ảnh cũ còn trong cây / Hủy), quét+đổi cả task, nhóm ngoài, lá trong cây if_group và bước đang mở.
  CHƯA thử Tkinter thật trên Windows: mở IF Nhóm -> sửa 1 lá Ảnh -> chọn ảnh khác -> Lưu -> xem hộp Có/Không.

## Đợt mới (2026-10-01) - Tin Telegram "Xong toàn bộ phiên" nêu rõ chạy gì / giả lập nào / tài khoản nào / mất bao lâu

Yêu cầu: tin "🏁 Đã chạy xong toàn bộ phiên." trống trơn; cần hiển thị rõ phiên đó chạy cái gì, tài khoản nào, chạy bao lâu.
- `session_report.py` (MỚI): `REPORT` (SessionReport) ghi từng lượt chạy {giả lập, tài khoản, tên Hoạt Động, giờ bắt đầu/xong, trạng thái done/error/stopped, ghi chú};
  `format_report(rows)` dựng tin: tổng giờ + số lượt ✅/⚠️/⏹, rồi nhóm 🖥 giả lập -> 👤 tài khoản -> từng lượt (giờ, thời lượng, ghi chú treo/lỗi/bị dừng).
  Tin dài quá 3500 ký tự thì rút gọn (mỗi tài khoản 1 dòng tổng, chỉ liệt kê lượt lỗi/dừng). Phiên không chạy được gì -> tin giải thích thay vì chỉ 1 dòng.
  Tên tài khoản lấy theo thứ tự: `account_label` (nơi gọi truyền) > `context_label` ("... Tài khoản thứ i/n - Tên") > tài khoản app đăng nhập THÀNH CÔNG gần nhất trên giả lập đó
  (ghi chú "đăng nhập gần nhất qua app" vì app không đọc được tài khoản thật trong game).
- `dashboard_run.py`: `_exec_entry` thêm tham số tuỳ chọn cuối `account_label=None`; ghi nhận kết quả ở MỌI lối ra (xong/lỗi/không thấy file/bỏ cuộc vì treo/bị dừng/break-continue),
  KHÔNG ghi khi `event=True` (🎁 Sự Kiện chạy lặp suốt ngày). Tin "Bắt đầu"/"Hoàn thành" thêm dòng "👤 Tài khoản: ..." khi không có context_label mà biết tài khoản.
  `_on_emulator_thread_done` -> `REPORT.close(idx)`; `_on_finish_all` gửi `format_report(REPORT.drain())` với `force=True` (trước đây 2 phiên sát nhau bị chống-ngập nuốt mất tin).
  `_worker_run_emulator`/`_worker_run_group`: ghi chú lý do khi giả lập không bật được / không thấy trong adb devices.
- `dashboard_schedule.py` (`_on_schedule_thread_done`) và `dashboard_accounts.py` (`_finish_quick_login`): `REPORT.discard(idx)` - Hẹn Giờ/Log Nhanh có tin riêng, không lẫn vào tin phiên chạy tay.
  `dashboard_accounts.py`: Log Nhanh truyền `account_label=ten` cho Tự Login/Đăng Xuất/Đăng Nhập; luồng Xoay Vòng khi giả lập không bật được cũng ghi chú.
- `notifier.py`: chỉ đổi nhãn sự kiện `all_done` ở màn hình Cài Đặt Telegram (logic giữ nguyên). Sự kiện này vẫn MẶC ĐỊNH TẮT như cũ.
- Lưu ý: Hẹn Giờ không gọi `_on_finish_all` nên vẫn KHÔNG có tin "xong phiên" riêng (chỉ có tin từng Hoạt Động) - giữ nguyên hành vi cũ.
- Test (sandbox, tkinter/win32 giả): `session_report` (nhóm, rút gọn khi dài, phiên rỗng, discard/close) + `_exec_entry` thật với engine giả (xong/lỗi/mất file/event/tài khoản gần nhất).
  CHƯA thử trên Windows thật với LDPlayer - cần chạy 1 phiên tay vài Hoạt Động + 1 phiên Xoay Vòng và xem tin Telegram.

## Đợt mới (2026-10-01) - Đổi ảnh mẫu: ảnh cũ còn dùng ở nơi khác thì HỎI có đổi luôn không (cả tasks/ lẫn groups/)

Yêu cầu: khi thay ảnh ở 1 hành động mà ảnh cũ còn dùng nhiều nơi thì hỏi có đổi tất cả không, gồm cả Nhóm Ngoài trong `groups/`.
Trước đây mỗi bước chỉ lưu TÊN file ảnh nên đổi 1 bước không kéo theo các bước/task/nhóm khác.
- `template_replace.py` (MỚI): `find_usages(old, current_steps, current_path)` quét `tasks/*.json` + `groups/*.json` + kịch bản đang mở (bản trong bộ nhớ) và đếm số chỗ dùng ảnh cũ
  (field `template`, danh sách `templates`, lá `image` trong cây `tree` của if_group); `apply_replace(old, new, usages, current_steps)` thay tên ảnh. File khác ghi bằng `paths.save_json` (có .bak);
  kịch bản ĐANG MỞ chỉ sửa trong bộ nhớ (không ghi đè file, người dùng tự Lưu - tránh lưu luôn phần đang sửa dở). Comment dạng "Ảnh: <cũ>" tự đổi theo, comment tuỳ chỉnh giữ nguyên.
  File JSON hỏng/không phải list bị bỏ qua, lỗi ghi từng file được gom lại báo cho người dùng.
- `gui_inspector.py`: `_offer_replace_image_everywhere(old, new, parent=None)` - nếu ảnh cũ còn dùng nơi khác thì hiện hộp Có/Không liệt kê nơi dùng (📋 Task / 📦 Nhóm) rồi đổi hàng loạt,
  sau đó báo kết quả; không còn nơi nào dùng thì im lặng. `change_step_image` ("🔄 Đổi Ảnh Khác") nhớ ảnh cũ (kể cả ảnh đang xem trong nhóm ◀/▶) rồi gọi hàm này.
  `_compute_template_usage` nay quét CẢ `groups/` và ảnh trong cây if_group (trước đây bỏ sót -> "Xoá ảnh chưa dùng" ở Thư Viện Ảnh có thể xoá nhầm ảnh chỉ dùng trong Nhóm Ngoài).
- `gui_canvas.py` (`_do_crop`, `_do_crop_custom`, nhánh chọn lại ảnh cho bước đã có - `edit_idx`): gọi hàm trên sau khi gán ảnh mới.
- `gui_step_edit.py` (`manage_group_templates`, "Quản Lý Ảnh Trong Nhóm"): ghi nhận các lần "🔄 Đổi" (A->B rồi B->C gộp thành A->C), SAU khi bấm Xong mới hỏi; bỏ qua ảnh cũ vẫn còn trong nhóm.
- (Đã làm nốt ở đợt 2026-10-01 phía trên) đổi ảnh lá trong cây if_group ở `gui_dialogs_ifgroup.py` nay đã hỏi đổi hàng loạt.
- Test (tkinter giả, thư mục tạm): quét/đổi tasks + groups + cây if_group + kịch bản đang mở, file đang mở không bị ghi đè, comment, file hỏng bị bỏ qua; luồng hỏi Không/Có/hết chỗ dùng.
  CHƯA thử Tkinter thật trên Windows (cần xem hộp Có/Không hiển thị đủ dòng, đổi ảnh bằng 🔄, chụp lại ảnh, Quản Lý Ảnh Trong Nhóm).

## Đợt mới (2026-10-01) - Sửa lăn chuột giữa không dùng được ở nhiều cửa sổ (Quản Lý Biến, Quản Lý Tài Khoản...)

Lỗi: một số cửa sổ (Quản Lý Biến, Quản Lý Tài Khoản, Quản Lý Ảnh Trong Nhóm...) không lăn chuột giữa được.
Nguyên nhân: (1) các file `dashboard_misc.py`, `dashboard_accounts.py` (3 cửa sổ), `gui_inspector.py` có Canvas + Scrollbar nhưng KHÔNG bind `<MouseWheel>`;
(2) 6 chỗ khác dùng `canvas.bind_all("<MouseWheel>")` + `unbind_all("<MouseWheel>")` khi đóng - bind_all chỉ giữ được 1 hàm cho cả chương trình nên cửa sổ mở sau đè cửa sổ trước,
đóng 1 cửa sổ là gỡ luôn lăn chuột của cửa sổ chính/cửa sổ còn lại; (3) trên Windows Tk 8.6 sự kiện lăn chuột gửi tới widget đang có FOCUS chứ không phải widget dưới con trỏ.
- `wheel_scroll.py` (MỚI): `install_wheel_scroll(root)` đăng ký `bind_class(..., "<MouseWheel>", add="+")` cho các lớp widget phổ biến (Toplevel/Frame/Label/Canvas/Button/... + bản ttk) nên
  KHÔNG bị bind_all/unbind_all của cửa sổ nào đè. Handler lấy widget DƯỚI CON TRỎ (`winfo_containing`), đi ngược lên cha tới widget cuộn được gần nhất (Canvas/Listbox/Text/Treeview có
  `yscrollcommand` và nội dung dài hơn vùng nhìn) rồi `yview_scroll`, trả "break" để handler bind_all cũ không cuộn đôi. Bỏ qua khi giữ Shift/Ctrl, khi widget nhận sự kiện đã tự có binding
  `<MouseWheel>` riêng, hoặc không tìm thấy widget cuộn được (handler cũ vẫn chạy như trước). Không bind Combobox/Spinbox (có binding đổi giá trị riêng của ttk).
- `dashboard_widgets.py`: `apply_global_theme()` gọi `install_wheel_scroll(root)` ở cuối (hàm này chạy 1 lần ở cả Dashboard và LD Macro Studio nên cả 2 chương trình được áp dụng).
- Các `bind_all/unbind_all` cũ ở từng cửa sổ GIỮ NGUYÊN (không xoá chức năng) - vẫn là phương án dự phòng khi handler mới không tìm thấy gì để cuộn.
- Test (widget giả, sandbox không có tkinter): cuộn qua label/nút nằm trong canvas, nội dung ngắn không cuộn, widget có binding riêng bị bỏ qua, Ctrl/Shift bỏ qua, canvas lồng nhau
  cuộn canvas ngoài, Treeview, delta nhỏ của touchpad, cài đặt đúng 1 lần. CHƯA thử Tkinter thật trên Windows - cần thử lăn chuột ở Quản Lý Biến, Quản Lý Tài Khoản, Quản Lý Ảnh Trong
  Nhóm (Studio), Hẹn Giờ, Chọn Hành Động; và xem cửa sổ nào vẫn không cuộn (nếu có thì báo tên cửa sổ).

## Đợt mới (2026-10-01) - Popup nhỏ "🪟 Popup Dừng/Tạm Dừng" theo từng giả lập

Yêu cầu: nút mở 1 popup tối giản, mỗi giả lập đang chạy 1 dòng (chỉ tên giả lập) + nút Tạm dừng/Tiếp tục + nút Dừng; có 1 ô tích nhỏ luôn hiện trên đầu.
- `dashboard_popup_ctl.py` (MỚI): `RunControlPopupMixin` - `open_run_control_popup()`. Popup `ThemedToplevel` nhỏ, không co giãn; hàng đầu là ô tích
  "📌 Luôn trên cùng" (mặc định BẬT, bỏ tích = hết `-topmost`). Mỗi giả lập trong `_busy_emulator_indexes` có 1 dòng: tên + "⏸ Tạm dừng"
  (bấm xong đổi thành "▶ Tiếp tục", màu xanh) + "⏹ Dừng". Tự cập nhật mỗi 400ms (dòng tự thêm/bớt khi giả lập bận/rảnh; không có gì chạy -> hiện "Không có giả lập nào đang chạy").
  Nhớ VỊ TRÍ popup (không ép kích thước) qua `window_geometry` (tên `run_control_popup`).
- KHÔNG tạo cơ chế dừng mới: dùng lại đúng cờ cũ ở `dashboard_run.py` - giả lập chạy tay/Hẹn Giờ/Nhóm/Xoay Vòng/Log Nhanh -> `stop_flags[idx]`/`pause_flags[idx]`
  (= chọn "Áp dụng cho" 1 giả lập rồi bấm Dừng/Tạm Dừng); giả lập đang chạy 1 lượt 🎁 Sự Kiện -> cờ RIÊNG `_event_stop_flags`/`_event_pause_flags` (dòng có biểu tượng 🎁;
  lưu ý Dừng ở dòng này = dừng hẳn Sự Kiện của giả lập đó giống nút "Dừng Sự Kiện").
- Đang "Tạm Dừng TẤT CẢ" (cờ tổng `pause_flag`) mà bấm "Tiếp tục" ở 1 dòng -> gỡ cờ tổng, các giả lập còn lại GIỮ tạm dừng (đặt `pause_flags` riêng), chỉ giả lập đó chạy tiếp.
  Sau mỗi lần bấm popup, nút "Tạm Dừng" ở thanh chính được đồng bộ lại nhãn (`_ctl_sync_main_pause_button`).
- `dashboard.py`: import + thêm `RunControlPopupMixin` vào bases `DashboardApp`; khởi tạo `self._event_cycle_indexes = set()`; cập nhật docstring.
- `dashboard_event.py` (`_worker_event_action`): thêm/bỏ idx vào `_event_cycle_indexes` quanh `_run_one_event_cycle` (cùng chỗ add/discard `_busy_emulator_indexes`).
- `dashboard_ui.py`: nút "🪟 Popup Dừng/Tạm Dừng" ở hàng 2 của thanh điều khiển, ngay sau ô "Áp dụng cho".
- Test (stub tkinter/widget giả, sandbox không có tkinter): tạm dừng/tiếp tục/dừng riêng 1 giả lập, tạm dừng tất cả rồi tiếp tục riêng 1 giả lập, dòng biến mất khi giả lập rảnh, dòng Sự Kiện
  dùng cờ riêng (không đụng `stop_flags`), đổi loại dòng thường <-> Sự Kiện. CHƯA thử giao diện Tkinter thật trên Windows (cần xem: popup nổi trên cùng, ô tích, kích thước dòng).

## Đợt mới (2026-10-01) - Watchdog: đứng hình / văng khỏi game / ANR -> tự mở lại game hoặc khởi động lại giả lập

Yêu cầu: game thỉnh thoảng văng ra ngoài, thỉnh thoảng đứng hình im (adb vẫn trả lời nên cơ chế timeout adb không bắt được).
- `health_watchdog.py` (MỚI): luồng nền `HealthWatchdog` chạy song song kịch bản. (1) `frozen`: khung hình thu nhỏ y hệt nhau liên tục `freeze_seconds`
  (180s) - sai khác TB <= `STILL_DIFF`=0.8/255; (2) `left_game`: `dumpsys window` -> `mCurrentFocus` là launcher suốt `left_game_seconds` (25s);
  (3) `anr`: hộp thoại "Application Not Responding/Error" suốt `anr_seconds` (15s). Phát hiện -> `adb.mark_hung(lý_do, kind)`. Tự học package game
  (app foreground không phải launcher/hệ thống, thấy 2 mẫu liên tiếp). Không bao giờ ném lỗi; có `pause()/resume()/reset()`, bỏ qua khi người dùng Tạm Dừng.
- `adb_helper.py`: thêm `hung_kind` ("adb"/"dead"/"frozen"/"left_game"/"anr"); `mark_hung(reason, kind="dead")`; `reset_health()` xoá cả `hung_kind`.
- `dashboard_run.py`: `_exec_entry()` tạo watchdog cho mỗi Hoạt Động (KHÔNG cho id `auto_login`/`account_login`/`account_logout` - ở launcher là bình thường; khi
  chạy lồng trong Hoạt Động khác thì chỉ `pause()` watchdog đang có) và tạm ngưng nó trong lúc phục hồi. Thêm `_watchdog_cfg()`, `_game_pkg_for()`, `_learn_game_pkg()`,
  `_soft_recover_game()` (adb còn sống -> `am force-stop` + `monkey -p <pkg>` mở lại game, KHÔNG khởi động lại giả lập). `_recover_hung_emulator()`: lỗi phía game ở
  lần 1 thử soft trước; soft thất bại (không biết package / adb chết / mở game lỗi) hoặc từ lần 2 -> tắt hẳn + bật lại giả lập.
- `emulator_manager.py`: `quit_and_wait_stopped()` nếu `ldconsole quit` không tắt nổi giả lập đơ -> `kill_emulator_process()` GIẾT CỨNG (psutil: pid + vbox_pid từ list2, kèm tiến trình con).
- `dashboard.py`: `_save_settings()` ghi thêm khoá `"watchdog"` (hàm dựng lại cả dict nên khoá lạ sẽ mất). Chỉnh ngưỡng/`game_package` bằng cách sửa
  `data/dashboard_settings.json` -> `watchdog` KHI ĐÃ ĐÓNG Dashboard; `"enabled": false` để tắt hẳn.
- Lưu ý: watchdog chỉ giám sát trong `_exec_entry` (không phủ Macro Studio). Kịch bản có `sleep`/chờ tĩnh > `freeze_seconds` sẽ bị báo đứng hình oan -> tăng `freeze_seconds`.
- Đã test bằng adb/giả lập GIẢ (parse focus, 7 ca phát hiện, 6 ca quyết định soft/hard); CHƯA thử trên LDPlayer thật.

## Đợt mới (2026-10-01) - Giả lập bị TẮT giữa lúc chạy -> tự bật lại + chạy lại tác vụ

Lỗi: đang chạy mà giả lập bị tắt/đóng thì tác vụ dừng luôn (thậm chí báo "Hoàn thành"), không bật lại. Nguyên nhân: cờ `hung` chỉ bật sau >=4 lần
adb lỗi LIÊN TIẾP và >=30s; trong lúc đó `wait_image` chỉ báo "không thấy ảnh" rồi kịch bản chạy hết bình thường.
- `logic_engine.py`: thêm `alive_checker` (mặc định None = Macro Studio không đổi) + `ALIVE_CHECK_INTERVAL`=4s; `_should_stop()` định kỳ gọi nó, nếu False
  -> `adb.mark_hung(...)` ngay rồi đi tiếp nhánh `hung` cũ.
- `adb_helper.py`: thêm `mark_hung(reason)` (đặt cờ treo ngay, không chờ ngưỡng).
- `dashboard_run.py`: `_exec_entry()` gắn `engine.alive_checker` (hỏi `_emulator_process_alive(index)` = ldconsole list2 báo pid<=0; không có ldconsole/lỗi/không tra được
  -> coi như còn sống) và kiểm tra lại ngay sau `execute_steps` (giả lập tắt đúng lúc cuối kịch bản thì không báo "Hoàn thành" oan) -> dùng lại toàn bộ luồng
  `_recover_hung_emulator` (bật lại -> Tự Login -> chạy lại từ đầu, tối đa `MAX_HANG_RETRIES`=2).
- `dashboard_run.py::_recover_hung_emulator`: `reset_health()` đặt TRƯỚC `turbo_reset()` và mỗi bước gắn lại ADB bọc `try` riêng (trước đây 1 bước lỗi làm `hung` còn True -> chạy lại dừng ngay).
- Lưu ý: kịch bản CỐ TÌNH tắt giả lập ở cuối (vd shell poweroff) sẽ bị coi là bị tắt giữa chừng và chạy lại tối đa 2 lần; "Hành Động Cuối"/hệ thống tắt giả lập thì KHÔNG ảnh hưởng (chạy ngoài engine).
- Chưa làm: giết cứng `dnplayer.exe` khi `ldconsole quit` không tắt nổi giả lập đơ (chưa test được ca treo thật); Macro Studio vẫn chưa tự phục hồi.

## Đợt mới (2026-10-01) - Timeout ADB + tự phục hồi giả lập treo + thông báo Telegram

- `adb_helper.py`: `run_cmd`/`run_cmd_full`/`screencap_fast` có TIMEOUT (`ADB_CMD_TIMEOUT`=20s, `ADB_SCREENCAP_TIMEOUT`=15s; vuốt cộng thêm `duration_ms`).
  Trước đây adb kẹt là luồng đứng vĩnh viễn. Thêm theo dõi sức khoẻ: `_note_ok/_note_fail/reset_health`, cờ `hung` đặt khi `HUNG_FAIL_LIMIT`=4 lần thất bại
  LIÊN TIẾP (timeout, chụp rỗng/giải mã lỗi, adb báo device offline/not found) VÀ >= `HUNG_MIN_SECONDS`=30s chưa có lần thành công. Các đường Siêu Tốc
  (`_turbo_transact`, `screencap_turbo`, `tap_turbo_px`, `turbo_poll_*` khi tìm thấy) gọi `_note_ok` để không báo treo oan. Thêm `turbo_reset()`.
- `logic_engine.py`: `_should_stop()` trả True khi `adb.hung` (log 1 lần) -> kịch bản dừng ngay thay vì quét ảnh vô ích.
- `dashboard_run.py`: `_exec_entry()` (lõi dùng chung chạy tay/hẹn giờ/xoay vòng/hành động cuối) nay lặp: chạy -> nếu `hung` thì
  `_recover_hung_emulator()` (lần 1: nếu adb còn trả lời chỉ thử lại; từ lần 2 hoặc adb không trả lời: tắt hẳn + `ensure_running`, gắn lại adb, `turbo_reset`,
  `reset_health`) -> chạy lại Tự Login (nếu có, nhớ qua `_login_by_emu`) -> chạy lại Hoạt Động TỪ ĐẦU. Tối đa `MAX_HANG_RETRIES`=2 lần rồi bỏ cuộc (tác vụ = error).
- `notifier.py` (MỚI) + `dashboard_telegram.py` (MỚI, nút "📨 Telegram" cạnh nút Reset Bộ Nhớ ở `dashboard_ui.py`, ghép vào `DashboardApp`): sự kiện
  `task_error` (kèm ảnh chụp màn hình nếu bật), `emu_hung`, `emu_restarted`, `emu_recover_failed`, `all_done`. Chống ngập: cùng `key` tối đa 1 tin/`min_interval_sec`.
- Telegram bổ sung: sự kiện `task_start` ("▶️ Bắt đầu 'A' trên giả lập 'B' - lúc HH:MM:SS dd/mm") và `task_done` ("✅ Hoàn thành ... Bắt đầu/Xong/Mất"); tin lỗi
  `task_error` nay có giờ + thời gian đã chạy. `notifier.notify(..., force=True)` bỏ qua chống ngập cho tin bắt đầu/hoàn thành; thêm `fmt_time`/`fmt_duration`.
  `_exec_entry()` có tham số `notify_run` (mặc định = `tracked`); `dashboard_schedule.py` truyền `notify_run=True` cho Hoạt Động trong Hẹn Giờ. Tự Login/đăng nhập/đăng xuất KHÔNG gửi.
- `.gitignore` (MỚI): loại `data/telegram_config.json*` (chứa Bot Token), `__pycache__/`.
- Chưa phủ: Macro Studio (`gui_run.py`) vẫn chưa tự phục hồi giả lập treo; chưa gửi Telegram cho "lịch hẹn giờ bỏ lỡ".

## Đợt mới (2026-10-01) - Vá 2 lỗi từ đợt rà soát: thiếu hàm vị trí popup + race condition `run_state`

- `gui_manual_steps.py`: THÊM `_arm_popup_pos(idx)` và `_clear_popup_pos(idx)` - menu chuột phải của bước popup
  ("📍 Chọn Vị Trí Hiển Thị" / "↩️ Bỏ Vị Trí Tuỳ Chỉnh") gọi 2 hàm này (gui_ui_build.py) nhưng trước đây KHÔNG tồn tại -> bấm vào
  là `AttributeError`. `_arm_popup_pos` đặt `_popup_pos_edit_idx` rồi `_arm_capture("popup_pos")` (nhánh lưu `pos_box` đã có
  sẵn ở gui_canvas.py); `_clear_popup_pos` xoá `pos_box` về mặc định (dải trên).
- `gui_step_edit.py`: `_CAPTURE_HINTS` thêm dòng hướng dẫn cho "popup_pos"; `_is_editing_existing_step` nhận biết popup_pos;
  `_cancel_pending_action` nay reset cả `_popup_pos_edit_idx` (trước đây bấm ESC rồi kéo khung lần sau có thể ghi nhầm vào bước cũ).
- `run_state.py`: thêm `_state_lock` (RLock) bọc `mark_done()` và `reset_today()` (đọc-sửa-ghi cả file). Trước đây nhiều luồng giả
  lập xong cùng lúc ghi đè nhau làm mất bản ghi "đã chạy hôm nay" (thử 40 luồng: bản cũ còn 1/40, bản mới 40/40).
- Chưa sửa (đã ghi trong báo cáo rà soát): tên file tạm cố định `.tmp` ở `paths.save_json`, `run_state._load_raw` nuốt lỗi JSON.

## Đợt mới (2026-09-30) - Hẹn Giờ: sửa hộp thoại "🧩 Biến riêng của lịch" + Cài Đặt Shop THEO GIẢ LẬP

Yêu cầu: (1) hộp thoại biến riêng của lịch bị lỗi - không kéo/không có thanh trượt -> sửa dễ nhìn hơn, thêm nút chỉ hiện
biến theo hành động đã chọn. (2) Cài Đặt Shop khi hẹn giờ: hiện bảng giống Cài Đặt Shop để đặt số lượng mua cho TỪNG giả lập.
- `dashboard_schedule.py` (`_open_schedule_vars_dialog` viết lại): danh sách biến nằm trong Canvas + Scrollbar (lăn chuột được,
  cửa sổ co giãn), thanh nút Lưu/Đóng pack TRƯỚC nên luôn ở đáy không bị cắt; thanh công cụ dùng FlowBar tự xuống dòng khi hẹp;
  dòng thông tin "Đang hiện X/Y". Nút MỚI "🎯 Chỉ hiện biến của hành động đã chọn" (bật/tắt): lọc theo Hoạt Động + Hành Động
  Cuối đang chọn của lịch (kể cả trong Nhóm Hành Động); khi lọc bật thì "📥 Nạp Từ Quản Lý Biến" chỉ nạp biến liên quan.
  Thêm nút "Đóng". Tham số mới đều TUỲ CHỌN (`get_activity_ids`, `emulators`, `per_emu_vars`, `on_save_emu`) nên chỗ gọi cũ vẫn chạy.
  Hàm mới `_expand_activity_ids` (bung GROUP:<id> đệ quy, chống lặp vòng).
- Nút MỚI "🛍 Cài Đặt Shop Theo Giả Lập" trong hộp thoại đó (mở bảng ở `dashboard_shop.py`); nếu lịch chưa chọn Hoạt Động
  `cai_dat_shop` (kể cả trong Nhóm) thì hỏi xác nhận trước khi mở. Dòng lịch: nút 🧩 hiện "🧩N+🛍M" (M = số giả lập có số riêng),
  tooltip liệt kê biến riêng từng giả lập.
- `dashboard_shop.py`: `_open_shop_qty_per_emulator(parent, emulators, base_vars, per_emu, on_save)` - cùng giao diện Cài Đặt
  Shop (tab Shop, +/−, Tất cả=0/1) + hàng tab GIẢ LẬP; tab giả lập hiện "(N riêng)". Nút "↩ Giả lập này = giá trị chung",
  "📋 Chép sang mọi giả lập". Lưu CHỈ các biến KHÁC giá trị chung của lịch (chung = biến riêng của lịch đè Quản Lý Biến).
  Cài Đặt Shop gốc (`_open_shop_qty_settings`) KHÔNG đổi.
- `scheduler.py`: khoá dữ liệu MỚI tuỳ chọn `bien_theo_gia_lap` = {"<index giả lập>": {biến: số}}; hàm `get_emulator_vars(entry, idx)`
  (lịch cũ/dữ liệu hỏng -> {}). Lịch cũ không cần migrate.
- `dashboard_schedule.py::_trigger_schedule`: với mỗi giả lập, biến chạy = biến chung của lịch + `get_emulator_vars` (riêng
  giả lập đè lên), truyền cho cả luồng chạy ngay lẫn job xếp hàng chờ; có log "🛍 biến RIÊNG giả lập". Lưu vào entry ở `_save_row`
  (khoá `bien_theo_gia_lap`), lịch mới có sẵn khoá rỗng. Thứ tự ưu tiên: biến riêng giả lập > biến riêng lịch > Quản Lý Biến.
- `dashboard_misc.py`: `_scan_variables_for_activity_ids(ids)` - quét {biến} trong file Hoạt Động (+ Nhóm Ngoài trong groups/,
  + Nhóm Hành Động đệ quy); bỏ `{rand:a-b}`. Chỉ để lọc hiển thị.
- Test (stub tkinter/widget giả): quét biến (đệ quy nhóm, chống lặp vòng, nhóm ngoài), merge riêng giả lập > riêng lịch, bảng Shop
  (giá trị khởi tạo, chỉ lưu biến khác chung, số sai không lưu), hộp thoại (bật/tắt lọc, mở shop truyền đúng base + trạng thái,
  Lưu gọi cả 2 callback). Test bắt được 1 lỗi thoát ký tự `\t` (tên biến chứa chữ "t" bị báo sai) - đã sửa.
  CHƯA thử giao diện Tkinter thật (sandbox không có tkinter) - cần mở thử trên Windows: cuộn danh sách biến, nút 🎯, nút 🛍,
  bố cục hai hàng tab giả lập/shop.

## Đợt mới (2026-09-30) - Studio: sửa HÀNG LOẠT nhiều bước + Ctrl+Z hoàn tác

Yêu cầu: ở trình tạo macro, chọn nhiều hành động rồi sửa delay / timeout / số lần lặp... thì sửa hết các hành động đó;
thêm Ctrl+Z hoàn tác.
- `gui_ui_build.py` (`open_step_edit_menu_at`): trước đây menu chuột phải luôn `selection_set` về 1 dòng nên mất vùng
  bôi đen -> nay chỉ chọn lại khi dòng đó CHƯA nằm trong vùng bôi đen; nhiều dòng thì menu có dòng tiêu đề xám
  "Đang chọn N bước ... áp cho TẤT CẢ". Thêm mục "↩️ Hoàn Tác (Ctrl+Z)" (+ "Làm Lại") vào menu chuột phải.
  `bind_all` Ctrl+Z / Ctrl+Y (và Ctrl+Shift+Z = làm lại), cả chữ hoa/thường.
- `gui_step_edit.py`: bảng `_BULK_FIELD_ACTIONS` + hàm `_bulk_targets(idx, field_type)`. `_edit_step_field` áp giá trị
  mới cho MỌI bước đang bôi đen mà field đó áp dụng được (bước không hỗ trợ field bị BỎ QUA, không bị thêm field thừa;
  vd chọn lẫn tap + wait_image rồi sửa Timeout thì chỉ wait_image đổi). Field hỗ trợ: repeat, delay (kể cả khoảng
  10-30), timeout, conf, scan_interval, on_fail_config, click/turbo/click_all/wait_for (các nút bật-tắt: đặt TẤT CẢ theo
  giá trị MỚI của bước vừa chuột phải), click_offset, click_delay_after_found, click_jitter, tap_hold_ms, swipe_duration,
  swipe_hold_ms, popup_duration. Field riêng từng bước (ghi chú, gõ chữ, biến, nhãn...) vẫn sửa 1 bước như cũ.
  Tiêu đề hộp thoại thêm "[áp cho N bước]"; sau khi sửa GIỮ NGUYÊN vùng bôi đen (trước đây thu về 1 dòng).
- `gui_steplist_ops.py`: Hoàn tác/Làm lại dựa trên bản chụp: `refresh_tree()` gọi `_undo_track_changes()` đầu tiên,
  so `self.steps` với bản chụp lần trước, khác thì đẩy bản cũ vào ngăn xếp (tối đa `_UNDO_MAX` = 100). Nhờ vậy MỌI thao
  tác (thêm/xoá/dán/kéo-thả/sửa hàng loạt/áp cài đặt ảnh...) tự hoàn tác được mà không phải rải code từng chỗ. Hàm mới:
  `undo_steps`, `redo_steps`, `_undo_reset`, `_undo_track_changes`, `_undo_restore` (sửa TẠI CHỖ `self.steps[:]`, bôi đen
  đúng đoạn vừa khôi phục), `_can_undo/_can_redo`, `_undo_key_allowed`, `_on_undo_key`, `_on_redo_key`.
  Ctrl+Z bị BỎ QUA khi focus ở ô nhập chữ (Entry/Text/Spinbox/Combobox) hoặc hộp thoại con; bị chặn khi đang chạy thử
  (`is_playing`). Nạp file (`load_macro_file`) / khôi phục bản nháp (`gui.py`) gọi `_undo_reset()` để Ctrl+Z không
  quay về kịch bản trước.
- Test (stub tkinter): sửa hàng loạt timeout/delay 10-30/lặp/conf đúng bước, bước không hỗ trợ không bị thêm field, hủy
  hộp thoại không đổi gì, không chọn nhiều = chỉ 1 bước; undo 5 bước rồi hết lịch sử, redo, thao tác mới xoá redo, giữ
  nguyên đối tượng list, chặn khi đang chạy, phím ở Entry/hộp thoại con bị bỏ qua, Ctrl+Shift+Z = redo. CHƯA thử giao diện
  Tkinter thật (sandbox không có tkinter) - cần thử trên Windows: bôi đen nhiều dòng (Ctrl/Shift+click) -> chuột phải ->
  Sửa Delay/Timeout/Lặp, rồi Ctrl+Z.
- Lưu ý: bước nằm trong khối IF/Nhóm đang THU GỌN không hiện trên cây nên không được bôi đen -> không bị sửa hàng loạt.
  Menu chuột phải vẫn dựng theo LOẠI của dòng vừa bấm chuột phải (chọn lẫn nhiều loại thì bấm vào dòng loại có mục cần sửa).

## Đợt mới (2026-09-30) - Bước "⏭ Nhảy Tới Nhãn (Skip to Label)" (goto_label)

Yêu cầu: nhãn (label) hiện chỉ dùng được khi KHÔNG thấy ảnh (on_fail=skip_to_label); thêm hành động
"skip to label" để chuyển thẳng tới nhãn đó.
- `logic_engine.py`: action MỚI `goto_label` (tên nhãn ở field `skip_to_label_name`, dùng chung tên với on_fail).
  Nhảy VÔ ĐIỀU KIỆN tới bước `label` cùng tên (`find_label_index`); nhảy ngược = tạo vòng lặp (nghỉ 0.05s/lượt
  chống ngốn CPU, vẫn Dừng được). Bước nhảy đặt TRONG Nhóm mà nhãn ở NGOÀI Nhóm: class MỚI `GotoLabelSignal`
  thoát Nhóm, cấp ngoài tìm nhãn (nhiều cấp lồng cũng được; nhóm ngoài file `action="group"` cũng cho tín hiệu đi qua).
  Không thấy nhãn / chưa chọn nhãn -> log lỗi, chạy tiếp bước kế tiếp (không dừng kịch bản).
- `gui_dialogs.py`: `GotoLabelDialog` MỚI - chọn nhãn từ DANH SÁCH nhãn đã có (vẫn gõ tay được).
- `gui_manual_steps.py`: `add_manual_goto_label`, `_get_existing_label_names`.
- `gui_ui_build.py`: nút "⏭ Nhảy Tới Nhãn (Skip to Label)" cạnh "🏷️ Thêm Nhãn"; menu chuột phải thêm "Thêm Nhãn" +
  "Thêm Nhảy Tới Nhãn"; menu bước goto_label có "⏭ Đổi Nhãn Đích".
- `gui_step_edit.py`: field `goto_label_name`; ô nhãn của on_fail=skip_to_label giờ CHỌN từ danh sách (thay vì gõ);
  ĐỔI TÊN nhãn tự cập nhật các bước goto_label / on_fail đang trỏ tới tên cũ.
- `gui_steplist_ops.py`: dòng `label` / `goto_label` hiển thị gọn trên cây (trước đây label rơi vào nhánh in dict thô).
- `script_validator.py`: "Kiểm Tra Kịch Bản" cũng báo thiếu nhãn cho bước goto_label.
- Test (LogicEngine + adb giả): nhảy xuôi, vòng lặp ngược đếm tới 5, thoát Nhóm, thoát 2 cấp Nhóm lồng, nhãn nằm
  trong cùng Nhóm, nhãn không tồn tại, tên rỗng - đều đúng. py_compile/pyflakes sạch lỗi mới.
  CHƯA thử giao diện Tkinter thật (sandbox không có tkinter) - cần mở thử hộp "Nhảy Tới Nhãn" trên Windows.
- Lưu ý: nhãn tìm trong danh sách bước phẳng của cấp đang chạy (hành vi cũ của `find_label_index`), nên nhảy từ
  ngoài vào giữa thân 1 Nhóm sẽ chạy thân Nhóm đúng 1 lần, không lặp.

## Đợt mới (2026-09-30) - Sửa: lưu Hẹn Giờ (💾) xong lịch tự chạy ngay

Yêu cầu: kiểm tra lại, hình như lưu hành động hẹn giờ thì nó tự chạy luôn, mở lại chương trình cũng vậy.
- Nguyên nhân: `_save_row` (dashboard_schedule.py) khi đổi Giờ hẹn / Lặp lại (hoặc tick Bật lại lịch
  đã tắt lâu) KHÔNG cập nhật `lan_chay_luc`. Lưới giờ mới có mốc đã qua mà mới hơn `lan_chay_luc`
  -> `scheduler.is_due()` = True -> `_check_schedules` (20s/lần) tự chạy; app tắt/mở lại thì lịch còn
  nợ mốc đó nên bị coi là bỏ lỡ / chạy lại. (`_add_new` đã có xử lý này từ trước, `_save_row` thì chưa.)
- Sửa: `_save_row` nhớ `bat/gio_hen/interval_hours` cũ; nếu giờ hẹn hoặc chu kỳ đổi, hoặc Bật từ tắt
  sang bật -> `scheduler.mark_triggered(entry)` (chỉ ghi `lan_chay_luc` = bây giờ, KHÔNG chạy) rồi
  mới lưu; lịch chỉ chạy ở mốc lưới TIẾP THEO. Chỉ đổi Hoạt Động / Gán GL/TK / biến thì không đụng
  `lan_chay_luc`. Không đổi tên hàm/biến nào; `scheduler.py` không đổi.
- Test (mô phỏng scheduler): 07:00 -> đổi 14:00 lúc 15:00: trước sửa is_due=True, sau sửa False,
  mốc kế 01/10 14:00. py_compile OK. CHƯA thử giao diện Tkinter thật trên Windows.

## Đợt mới (2026-09-30) - Hành Động Sự Kiện: ô NGHỈ RIÊNG theo từng giả lập (ưu tiên)

Yêu cầu: "hành động theo sự kiện thêm ô nghỉ theo từng giả lập (ưu tiên)".
- `dashboard_event.py`:
  - Trong "🎁 Soạn Hành Động Sự Kiện Theo Giả Lập": mỗi dòng giả lập thêm ô "Nghỉ (p)" (phút, cho
    phép thập phân, kẹp 0.5-240; sai -> chữ đỏ, không lưu). Thanh mới "⏱ Nghỉ riêng (phút)" + nút
    "Áp Cho Đã Tick" đặt cùng lúc cho các giả lập đã tick ở cột ☑ (để trống = xoá nghỉ riêng).
    Tự lưu khi gõ/Enter/rời ô/đóng cửa sổ.
  - `_get_event_interval_seconds(emulator_index=None)`: THÊM tham số tuỳ chọn; giả lập có nghỉ RIÊNG
    -> dùng số riêng (ƯU TIÊN), không có -> dùng ô "Nghỉ chung" như cũ. Gọi không tham số = y hệt cũ.
    Hàm mới: `_parse_event_rest_text`, `_get_event_rest_override_minutes`, `_event_rest_text`.
  - `_worker_event_action` dùng nghỉ riêng của đúng giả lập (log "nghỉ X phút (nghỉ RIÊNG...)").
  - XEM LẠI nghỉ riêng: dòng tóm tắt màu cam trong cửa sổ soạn ("Nghỉ riêng: LD1 2p, LD3 0.5p · còn lại
    dùng nghỉ chung 5p", tự cập nhật mỗi khi gõ/áp), hộp thông báo sau "Áp Cho Đã Tick", và nhãn chính
    ở thanh Hành Động Sự Kiện thêm "- nghỉ riêng N giả lập" (hàm `_event_rest_summary_text`).
- `dashboard.py` lưu / `dashboard_ui.py` nạp key MỚI `event_interval_by_emulator` ({"<index>": phút});
  ô ở thanh chính đổi nhãn "Nghỉ (phút)" -> "Nghỉ chung (phút)" (biến `event_interval_var` giữ nguyên).
- Test (stub tkinter): parse "", "2", "2,5", "0.1"->0.5, "999"->240, sai/0/âm/nan bị từ chối; riêng thắng
  chung, trống/sai -> chung; worker chạy 1 lượt rồi nghỉ đúng số riêng, Dừng giữa lúc nghỉ thoát ngay.
  pyflakes sạch lỗi mới. CHƯA thử giao diện Tkinter thật (sandbox không có tkinter) - cần mở thử
  cửa sổ "Soạn Hành Động Sự Kiện" trên Windows để kiểm tra bố cục ô Nghỉ/thanh Nghỉ riêng.

## Đợt mới (2026-09-30) - Cập nhật File Map đầy đủ trong PROJECT_CONTEXT.md
- Bổ sung 28 file trước đây chưa có trong File Map (gui_*.py, dashboard_groups, activity_groups, variables_registry, paths, file_logger, auto_notify, popup_widget, turbo_engine, merge2048_bot, window_geometry, script_validator, data_groups, các công cụ phụ...), thêm mục tài liệu .md + danh sách Mixin của DashboardApp/MacroStudioApp. Chỉ sửa tài liệu, không đụng code.

## Đợt mới (2026-09-30) - Delay/Sleep NGẪU NHIÊN + biến random `{rand:a-b}`

Yêu cầu: thêm chức năng biến random, vd sleep hoặc delay sau hành động random trong khoảng 10-30s.
- `logic_engine.py`:
  - Field MỚI tuỳ chọn `delay_max` trên MỌI bước: `delay_max > delay` -> chờ ngẫu nhiên
    `uniform(delay, delay_max)` mỗi lần (log "🎲 Chờ ngẫu nhiên Xs"). Không có `delay_max` = y hệt cũ.
    Hàm mới `_get_step_delay(step)` thay cho `delay` cố định ở cuối vòng lặp repeat (vẫn ngắt được
    khi Dừng). `delay` giờ cũng có thể là chuỗi (vd `{rand:10-30}`, `{cho}*2`) qua `_resolve_step_number`.
  - Token BIẾN RANDOM `{rand:10-30}` (hoặc `{random:..}`) trong `_interpolate_vars`: 2 đầu nguyên ->
    số nguyên, có thập phân -> số thực 2 chữ số; đảo đầu tự sửa; nếu có biến trùng tên thì biến thắng.
    Dùng được ở mọi ô hỗ trợ biến (Sửa Lặp, Gõ Chữ, Popup, Sửa Delay...).
  - `set_var`: value chuỗi có `{..}` -> thay biến/random rồi ép số (vd biến `cho` = `{rand:10-30}`).
- `gui_manual_steps.py`: hàm mới `_format_delay_display`, `_parse_delay_input` ("2", "10-30", "10~30",
  "{rand:10-30}"); "⏳ Chờ (Sleep)" nay nhập được khoảng (vd 10-30).
- `gui_step_edit.py`: "⏱ Sửa Delay" đổi askfloat -> askstring (nhập 2 hoặc 10-30).
- `gui_steplist_ops.py`: cột Delay + dòng sleep hiện "10-30" (sleep thêm 🎲); "Áp dụng hàng loạt"
  cho bước ảnh xoá `delay_max` cũ. `gui_ui_build.py`: nhãn menu chuột phải hiện khoảng.
- Test (adb giả): 300 lần `{rand:10-30}` trong 10..30; delay 10-30 ra 10..30; delay_max<=delay = cố
  định; sleep 0.2-0.5 chạy thật ~0.3s; Dừng giữa lúc chờ 10-30s thoát sau 0.3s; parse/format GUI OK.
  pyflakes: không thêm cảnh báo. CHƯA thử giao diện Tkinter thật trên Windows.

## Đợt mới (2026-09-30) - Đếm ảnh -> biến (`count_var`) cho Quét Đa Ảnh

Yêu cầu: tìm nhóm ảnh, đếm được bao nhiêu thì lặp nhóm hành động từng ấy lần.
- `logic_engine.py` (multi_image, nhánh click_all): field MỚI tuỳ chọn `count_var`
  -> lưu số vị trí khớp vào biến (không thấy = 0). Không đổi tên/hành vi cũ.
- `gui_step_edit.py` (field_type `count_var`) + `gui_ui_build.py` (menu chuột phải
  "🔢 Đếm Ảnh -> Biến") để đặt tên biến.
- Dùng: Quét Đa Ảnh (Click Tất Cả, tắt Click nếu chỉ đếm, count_var=so_anh)
  -> IF biến so_anh > 0 -> Nhóm Sửa Lặp = {so_anh} -> ... (IF để chặn trường hợp 0
  vì Nhóm luôn chạy tối thiểu 1 lượt: `max(1, ...)`).
- Đã test bằng adb giả: 0/1/3/5 ảnh -> lặp 0/1/3/5 lần.

## Current Task (2026-09-30, đợt 20 - LD Macro Studio (gui*.py): đồng bộ theme tối 3D với Dashboard)

Yêu cầu: "làm tương tự với gui, tôi muốn tất cả đồng bộ".

- Dùng CHUNG theme với Dashboard (import từ `dashboard_widgets.py` / `dashboard_theme.py`):
  - `gui_ui_build.py::_setup_styles` gọi `apply_global_theme(root)` + `install_themed_simpledialog()`
    (thay theme sáng "clam" cũ); Treeview giữ font Consolas, rowheight 26, chọn dòng = `COL_SELECT`.
  - 22 class dialog `(tk.Toplevel)` -> `(ThemedToplevel)` + 5 chỗ `tk.Toplevel(` (gui_dialogs*.py,
    gui_image_test.py, gui_inspector.py, gui_step_edit.py). `super().__init__(parent)` giữ nguyên.
  - 86 `ttk.Button(` + 3 `tk.Button(` -> `Btn3D(` (MỚI trong dashboard_widgets.py, kế thừa
    RoundedButton, API tương thích ttk/tk Button: text/command/width/state, `.config(text=/state=/
    bg=/command=)`, `.invoke()`, `.state([...])`; màu tự chọn theo nhãn: Xoá/Dừng đỏ, Chạy xanh lá,
    Lưu/Thêm/Chọn xanh dương, còn lại xám - hoặc truyền `bg=`). Nút LIVE / GHI LD đổi màu bằng
    `config(bg=...)` vẫn chạy.
  - Màu loại bước (STEP_BTN_COLORS + tree.tag_configure + chú thích) đổi từ pastel sáng sang
    nền tối + chữ sáng cùng tông (vẫn TRÙNG nhau giữa nút thêm bước, dòng danh sách, chú thích).
    Màu chữ đơn lẻ (gray/red/green/#555...) đổi sang màu sáng hợp nền tối.
  - Hàng nút "Thêm Bước Thủ Công" / "Biến Số" dùng `FlowBar` -> tự xuống dòng, không còn bị cắt
    nút ở panel hẹp (trước đây thanh trượt/khuất "Nhãn", "Khung IF/ELSE"...).
- `simpledialog.askstring/askinteger/askfloat` -> hộp nhập cùng theme (Enter=OK, Esc=Huỷ, số sai/
  ngoài min-max báo ngay dưới ô nhập; KHÔNG grab - giống auto_notify.py). Áp dụng cho cả 2 app.
- `auto_notify.py`: đổi giao diện sang theme tối 3D (dải màu theo loại, huy hiệu tròn 3D, nút
  RoundedButton). GIỮ NGUYÊN hành vi: thông báo tự tắt sau 5s + không chặn, câu hỏi không grab,
  thread nền -> root.after, lỗi -> rơi về hộp thoại gốc. (Import `dashboard_theme`/`dashboard_widgets`.)
- `RoundedButton` vẽ theo kích thước thật khi bị kéo giãn (pack fill/grid sticky) - cần cho nút
  "Lên/Xuống/Xoá bước/Clear" full-width của Macro Studio.
- `apply_global_theme` thêm style TCheckbutton/TRadiobutton (ô chọn tối), Sash, Scale, LabelFrame.
- Đã test trên Xvfb (mock win32*/pynput): dựng MacroStudioApp + DashboardApp thật, mở dialog
  (SetVar, IfVar, MatchMode, DataGroupManager), simpledialog (OK/sai số/min-max), showinfo tự tắt,
  gọi từ luồng nền, askyesno; pyflakes sạch lỗi mới. CHƯA thử trên Windows thật; các dialog gui_*
  còn lại (IfGroup, RegionPicker, ZoomStep...) chỉ kiểm tra qua import + cùng lớp ThemedToplevel.
- Còn lại (chưa đổi, có chủ ý): filedialog (hộp chọn file gốc của Windows), vùng Canvas xem trước
  màn hình LDPlayer (#181818), màu vẽ chọn vùng trên ảnh (#ba00ff, #00ff00) vì cần nổi trên ảnh.

---

## Current Task (2026-09-30, đợt 19 - Dashboard: giao diện 3D + gom nút + đồng bộ theme)

Yêu cầu người dùng: "Sắp xếp lại các nút ấn cho hợp lý, dễ nhìn, dễ thao tác; đồng bộ
lại theme tất cả các cửa sổ, popup, làm cho nó 3D hoặc đẹp, chuyên nghiệp hơn".

### Đã làm (đợt 19)

- `dashboard_theme.py`: THÊM màu `COL_ENTRY`, `COL_SHADOW`, `COL_HIGHLIGHT`, `COL_SELECT`
  (không đổi màu cũ).
- `dashboard_widgets.py` (viết lại, GIỮ NGUYÊN tên/API cũ của RoundedButton, FlowBar,
  DarkCheck, CategorySection, Tooltip, _bind_esc_close, _set_dpi_awareness):
  - `RoundedButton` thành nút 3D: nền chuyển màu dọc, viền, vệt sáng, "gờ" bóng dưới;
    rê chuột sáng lên; GIỮ chuột thì nút lún xuống; lệnh chạy khi NHẢ chuột trong nút
    (kéo ra ngoài rồi nhả = huỷ). `bg_color`/`_redraw()`/`set_text()`/`set_state()` vẫn
    dùng như cũ (dashboard_accounts.py đang đổi `bg_color` rồi `_redraw()`).
  - MỚI `ThemedToplevel` (thay `tk.Toplevel` ở MỌI popup dashboard_*.py): nền + viền theo
    theme, thanh tiêu đề tối (DWM, Windows 10/11; lỗi thì bỏ qua).
  - MỚI `apply_global_theme(root)`: style ttk (Scrollbar, Combobox, Spinbox, Entry,
    Treeview, Notebook, Progressbar...) + `option_add` mặc định cho Entry/Text/Listbox/
    Menu/Button... -> ô nhập, danh sách xổ xuống, thanh cuộn ở mọi popup ra đúng tông tối.
  - Hộp thoại thông báo/xác nhận (messagebox) do `auto_notify.py` đảm nhận (tự tắt 5s, không
    chặn cửa sổ khác) - đợt 20 đã đổi giao diện auto_notify sang theme tối 3D, GIỮ NGUYÊN
    hành vi. KHÔNG thêm lớp thay messagebox thứ hai (sẽ ghi đè auto_notify).
  - MỚI `ToolGroup` (khối gom nút có tiêu đề + màu nhấn + bóng đổ) và `make_separator`.
  - `DarkCheck` ô bo góc; `CategorySection` thêm dải màu nhấn; `Tooltip` đổi màu theo theme.
- `dashboard.py`: gọi `apply_global_theme(self.root)` + `install_themed_simpledialog()` ngay
  sau `root.configure(bg=COL_BG)`.
- 12 file `dashboard_*.py` có popup: `tk.Toplevel(` -> `ThemedToplevel(` (+ import).
- `dashboard_ui.py` sắp xếp lại nút (TÊN biến giữ nguyên: btn_create_activity, btn_queue,
  btn_view_errors, auto_login_var, boot_wait_var, account_rotate_var, lbl_post_run_action,
  lbl_event_action, event_interval_var, btn_event_pause, btn_run/btn_stop/btn_pause,
  stop_target_var, combo_stop_target, lbl_status...):
  - Hàng 1 theo nhóm: 🚀 TÁC VỤ NHANH (Mở Bảng Giả Lập, Setup Người Mới, Quét Xe, UID Like,
    Cài Đặt Shop) | 👤 TÀI KHOẢN (Quản Lý TK, Quản Lý Biến, Log Nhanh, Đăng Nhập 1 Acc,
    Xoay Vòng TK) | ⏰ LỊCH & HÀNG CHỜ (Hẹn Giờ, Nhóm Hành Động, Hàng Chờ, Xem Lỗi).
    "📖 Hướng Dẫn" chuyển lên cạnh "➕ Tạo Hoạt Động".
  - Hàng 2: 🏁 HÀNH ĐỘNG CUỐI | 🎁 HÀNH ĐỘNG SỰ KIỆN (gọn 2 dòng).
  - Thanh Giả lập: nút gom theo cụm (Bật/Tắt/Ghim/Thu nhỏ | Chọn/Bỏ chọn | Quét/Quét lại/
    Sắp xếp) có vạch ngăn; "📁 Chọn ldconsole.exe" đưa lên hàng nhãn "Giả lập:".
  - Thanh điều khiển dưới thành khối riêng, 2 hàng: CHẠY / Chọn Hành Động / DỪNG / Tạm Dừng
    và (hàng 2) 🔐 Tự Login + Chờ boot, Áp dụng cho, Reset Bộ Nhớ.
  - Nhật Ký + thanh điều khiển pack `side="bottom"` TRƯỚC vùng danh sách -> cửa sổ thấp
    thì DANH SÁCH co lại, Nhật Ký/nút điều khiển không còn bị đẩy khỏi màn hình.
- Đã kiểm tra: `pyflakes`; chạy DashboardApp THẬT trên Xvfb (mock win32*): dựng giao diện,
  chụp ảnh, hộp thoại themed (Enter/Esc/kết quả), nút 3D (click, kéo ra ngoài = huỷ,
  disabled), mở 12 popup (Hàng Chờ, Nhóm, Tài Khoản, Hẹn Giờ, Biến, Sắp Xếp, Chọn Hành
  Động, Hành Động Cuối/Sự Kiện, Lỗi, Log Nhanh, Đăng Nhập 1 Acc) không lỗi.
- Đợt 20 (bên dưới) đã làm nốt LD Macro Studio. Chưa thử trên Windows thật (thanh tiêu đề tối cần Windows 10 1809+/11).

---

## Current Task (2026-09-29, đợt 17)

Yêu cầu người dùng: "Log Nhanh khi giả lập bận báo 'đang bận' mà không xếp vào
hàng chờ - thêm vào hàng chờ, thêm quản lý hàng chờ (hiển thị hàng chờ và xoá,
thay đổi thứ tự được)".

### Đã làm (đợt 17)

- Nguyên nhân: `_start_quick_login()` (dashboard_accounts.py) cố ý KHÔNG xếp
  hàng (chỉ báo bận rồi huỷ) và `_after_emulator_freed()` không có nhánh cho
  Log Nhanh. Cả "⚡ Log Nhanh" lẫn "🔑 Đăng Nhập 1 Acc" đều đi qua hàm này.
- File MỚI `dashboard_queue.py` (QueueMixin, ghép vào DashboardApp ở
  dashboard.py):
  - `_enqueue_job(emulator_index, job)`: cách DUY NHẤT nên dùng để thêm job
    vào `_emulator_job_queue` - giữ `self._queue_lock`, đóng dấu
    `job["queued_at"]` (chỉ để hiển thị), trả về vị trí trong hàng, báo giao
    diện cập nhật (`_notify_queue_changed`, an toàn gọi từ luồng nền).
  - Nút MỚI "⏳ Hàng Chờ (N)" ở thanh nút chính (dashboard_ui.py,
    `self.btn_queue`, N tự cập nhật) mở cửa sổ QUẢN LÝ HÀNG CHỜ: liệt kê job
    theo từng giả lập (kèm việc giả lập đó đang chạy), chọn dòng (Ctrl/Shift
    chọn nhiều), nút ⬆ Lên / ⬇ Xuống / ⤒ Lên đầu / ⤓ Xuống cuối / 🗑 Xoá Đã
    Chọn (phím Delete) / 🧹 Xoá Tất Cả (có hỏi xác nhận). Tự làm mới mỗi 1s
    (chỉ dựng lại khi có thay đổi, giữ vị trí cuộn + lựa chọn). Đổi thứ tự
    chỉ trong PHẠM VI 1 giả lập (job không chuyển sang giả lập khác được).
  - `_queue_remove_jobs()` / `_queue_move_jobs()`: nhận diện job bằng `id()`
    của dict (không bằng chỉ số) nên job vừa bị lấy ra chạy giữa chừng tự bị
    bỏ qua, không nhầm sang job khác; xoá job ghi 1 dòng vào Nhật Ký.
- Job MỚI kind `"quick_login"` ({"account": <dict tài khoản>}):
  - `_start_quick_login()` giờ trả về `"started"` / `"queued"`; giả lập bận
    -> `_queue_job()` xếp hàng (KHÔNG xếp trùng nếu đã có lượt Log Nhanh cùng
    tài khoản đang chờ trên giả lập đó); phần chạy thật tách thành
    `_begin_quick_login()` (nội dung y như cũ, không đổi tên hàm cũ).
  - `_after_emulator_freed()` (dashboard_schedule.py) thêm nhánh `quick_login`
    -> `_run_queued_quick_login_job()`: giữ chỗ giả lập (bận) NGAY rồi bắt đầu
    ở luồng chính qua `root.after` (hàm này có thể được gọi từ luồng nền).
  - 2 nơi gọi (popup Log Nhanh nhiều giả lập + popup Đăng Nhập 1 Acc) đổi
    dòng trạng thái: "🕒 ... đã XẾP HÀNG CHỜ ..." thay vì "Đã bắt đầu ...".
- Thay đổi khác: `_queue_job()` (dashboard_run.py) và `_trigger_schedule()`
  (dashboard_schedule.py) dùng `_enqueue_job()` thay vì tự `append`;
  `_after_emulator_freed()` lấy job đầu hàng trong `self._queue_lock` (khoá
  `threading.RLock`, khởi tạo ở `dashboard.py`) vì hàm này chạy được ở luồng
  nền (luồng Sự Kiện, luồng bật giả lập) trong khi cửa sổ Hàng Chờ sửa hàng ở
  luồng giao diện. Hàng chờ vẫn CHỈ nằm trong bộ nhớ (tắt app là mất).
- LƯU Ý HÀNH VI:
  - Xoá job Hẹn Giờ khỏi hàng chờ chỉ bỏ lượt đó: lịch đã `mark_triggered` từ
    lúc tới giờ nên KHÔNG tự xếp lại, lần chạy kế tiếp theo mốc giờ như bình
    thường. Nếu lịch dùng "Chu kỳ xoay tài khoản" thì tài khoản xoay tới lượt
    đã được tính là dùng rồi, lượt bị xoá không được bù lại.
  - Nút "⏹ Dừng" KHÔNG xoá hàng chờ (như trước): job đang chờ vẫn tự chạy khi
    giả lập rảnh - muốn huỷ hẳn thì xoá ở '⏳ Hàng Chờ'.
  - Log Nhanh xếp hàng sau 1 lịch dài có thể đợi rất lâu mới đăng nhập; xem
    "xếp lúc" ở cửa sổ Hàng Chờ, xoá nếu không còn cần.
- Đã kiểm tra: `pyflakes`; test tự động trên DashboardApp THẬT (Xvfb, mock
  win32*): xếp hàng đủ 5 loại job, chống trùng Log Nhanh, đổi thứ tự (up/down/
  top/bottom, chọn nhiều), xoá, chạy đúng thứ tự khi giả lập rảnh, cửa sổ
  (chọn Ctrl/Shift, nút, tự làm mới, ca job bị chạy mất khi đang chọn, Xoá Tất
  Cả), stress đa luồng ~180k job (bảo toàn số lượng, không lỗi; tắt khoá thì
  test báo hỏng).

---

## Task song song (2026-09-29, đợt 18 - LD Macro Studio)

Yêu cầu người dùng (LD Macro Studio): (1) 🧪 Test Quét Ảnh mở chọn ảnh mặc định ở
thư mục `templates` (vẫn chuyển sang thư mục khác được); (2) phần test ảnh hiện VỊ
TRÍ tìm thấy ảnh trên Preview; (3) các thông số mặc định (Timeout, Độ khớp, Tốc độ
quét...) tắt chương trình vẫn lưu lại; (4) các ô tạo hành động thêm màu như hiển thị
các bước; (5) list hành động thêm thanh cuộn.

### Đã làm (đợt 18)

- `gui_image_test.py`: `filedialog.askopenfilename(initialdir=abspath("templates"),
  parent=win)` (không có thư mục -> thư mục hiện tại). Worker chụp 1 LẦN
  (`adb.screencap_fast()`) rồi quét trên đúng khung đó (truyền `screen=`), gọi hàm
  MỚI `_img_test_push_preview()` (root.after, chỉ giữ payload mới nhất) để vẽ lại
  Preview + khung vị trí tìm thấy; `_img_test_clear_overlay()` xoá khung khi dừng.
  Log "Tìm thấy" thêm toạ độ px. Cửa sổ Test đặt lệch sang PHẢI để không che Preview.
- `adb_helper.py`: `find_image_on_screen()` / `find_image_all_modes()` thêm tham số
  CUỐI `screen=None` (ảnh chụp sẵn; không truyền = tự chụp như cũ).
- `gui_capture.py::render_preview()`: vẽ `self._img_test_overlay` (khung trắng+đỏ,
  dấu cộng ở tâm, chữ "FOUND 0.87" - ASCII vì cv2.putText không có dấu tiếng Việt).
  Toạ độ 0..1 nên vẫn đúng khi zoom/đổi cỡ Preview, và không mất khi bật LIVE.
- `gui.py`: `_apply_saved_batch_defaults()` nạp `batch_timeout/batch_conf/batch_scan/
  default_delay` từ `data/config.json` sau `_build_ui()`; tự lưu (debounce 0.6s,
  `_save_config_soon`) khi đổi ô (▲▼/Enter/rời ô) + vẫn lưu khi đóng; ô gõ dở/hỏng
  thì giữ giá trị đã lưu. `_save_config()` vẫn ghi geometry/sash như cũ.
- `gui_ui_build.py`: bảng `STEP_BTN_COLORS` (trùng màu `tag_*` của danh sách bước) +
  `_step_btn()` (tk.Button có màu, viền cùng tông, hover đậm hơn) thay cho ttk.Button ở
  3 hàng "Thêm Bước Thủ Công", "Thêm Logic", "Biến Số & Điều Kiện" (27 nút, TÊN HÀM
  command giữ nguyên). Danh sách bước `self.tree` thêm `self.tree_vscroll` (thanh cuộn
  dọc).
- GIẢ ĐỊNH: "ô tạo hành động" = các nút Thêm Bước ở panel phải Macro Studio; "list
  hành động" = danh sách bước (`self.tree`, trước đây KHÔNG có thanh cuộn). Popup soạn
  "Hành Động Cuối/Sự Kiện" của Dashboard đã có thanh cuộn nên KHÔNG đụng tới.
- Lưu ý còn tồn: `gui_image_test.py` gọi `self._panel_match_mode()` nhưng hàm này
  không tồn tại ở đâu (được bọc try/except nên rơi về kiểu mặc định) - chưa sửa.
- Đã kiểm tra (Xvfb, stub win32): py_compile + pyflakes (không có tên undefined);
  nạp/lưu thông số config.json; thanh cuộn + 27 nút màu; Test Quét Ảnh: initialdir đúng,
  khung overlay khớp đúng vị trí ảnh mẫu (kể cả pixel viền đỏ), xoá khi Dừng.
  CHƯA test trên Windows + LDPlayer thật.

---

---

## Task trước (2026-09-28, đợt 16)

Yêu cầu người dùng: "thêm cài đặt biến cho từng hẹn giờ. sẽ ưu tiên dùng biến
cài đặt trong hẹn giờ trước".

### Đã làm (đợt 16b) - Sửa Lặp hỗ trợ phép tính với biến (vd `{sach}-1`)

- Lỗi: `{sach}-1` không dùng được vì (1) `_parse_repeat_input` (gui_manual_steps.py)
  chỉ nhận đúng `{biến}` hoặc `{biến}s/p/ms`, (2) `_resolve_step_number`
  (logic_engine.py) chỉ hiểu duy nhất 1 dấu `*`.
- File MỚI `safe_calc.py`: `safe_calc(text)` tính + - * / ( ) bằng `ast` (KHÔNG
  eval), từ chối mọi thứ khác (ValueError; chia 0 -> ZeroDivisionError).
- `logic_engine.py`: `_resolve_step_number` thử `float()` trước, không được thì
  `safe_calc()`; kiểu cũ `{so_phut}*60000` cho kết quả y hệt. Lỗi -> log + dùng
  default như cũ. Áp dụng cho repeat / repeat_ms / repeat_seconds / lặp nhóm.
- `gui_manual_steps.py`: `_parse_repeat_input` nhận biểu thức chứa `{biến}` +
  phép tính (kiểm tra cú pháp bằng cách thay mỗi `{biến}` = 1), hậu tố ms/s/p/m
  áp cho cả biểu thức (`{a}-1s` -> `({a}-1)*1000`). Các dạng cũ giữ nguyên.
- Lưu ý: lặp theo số lần luôn tối thiểu 1 (`max(1, ...)`), nên `{sach}-1` khi
  sach=1 vẫn chạy 1 lần chứ không 0.
- Chưa đổi: Gõ Chữ/Popup vẫn chỉ THAY biến thành chữ (`{sach}-1` -> `5-1`),
  set_var/inc_var/if_var chưa nội suy biến.
- Đã kiểm tra: pyflakes, test safe_calc (kể cả chuỗi độc hại), engine, parse.

### Đã làm (đợt 16)

- `scheduler.py`: thêm khoá tuỳ chọn `bien_cai_dat` ({tên biến: giá trị}) cho
  mỗi lịch + 2 hàm mới `get_schedule_vars(entry)` / `merge_preset_vars(base,
  entry)` (biến riêng của lịch GHI ĐÈ lên nền). Lịch cũ không có khoá này vẫn
  chạy bình thường, không cần migrate `schedules.json`.
- `dashboard_schedule.py`:
  - Hàm mới `_get_schedule_preset_vars(entry)` = giá trị "🧩 Quản Lý Biến"
    (`_get_registry_preset_vars()`) làm nền, biến riêng của lịch ưu tiên đè lên.
    `_trigger_schedule()` tính 1 lần lúc trigger, log các biến riêng (nếu có),
    và lưu vào job hàng chờ (`"schedule_vars"`) để lượt xếp hàng chờ giả lập
    cũng dùng đúng giá trị.
  - `_start_schedule_worker()` / `_worker_run_schedule()` thêm tham số CUỐI
    `schedule_vars=None` (mặc định = hành vi cũ, không đổi chữ ký gọi cũ).
    Nhánh chạy thẳng: truyền `schedule_vars` cho Hoạt Động. Nhánh xoay vòng
    tài khoản: Hoạt Động nhận `{schedule_vars, tk_user, tk_pass}` (tk_* luôn
    đè cuối); bước Đăng Nhập vẫn CHỈ nhận tk_user/tk_pass như cũ.
  - UI: mỗi dòng lịch có nút "🧩N" (N = số biến riêng, rê chuột xem chi tiết)
    mở hộp thoại `_open_schedule_vars_dialog()` (chọn tên biến từ Quản Lý Biến
    hoặc tự gõ, cột bên phải hiện giá trị chung để đối chiếu, nút "📥 Nạp Từ
    Quản Lý Biến", ép kiểu theo `var_type` của Quản Lý Biến, báo lỗi sai kiểu/
    trùng tên). `_save_row()` ghi `entry["bien_cai_dat"]`; lịch mới có sẵn
    `"bien_cai_dat": {}`. Thêm 1 câu hướng dẫn ở đầu cửa sổ Hẹn Giờ.
- LƯU Ý HÀNH VI: trước đây lượt chạy Hẹn Giờ KHÔNG áp dụng giá trị ở Quản Lý
  Biến (preset_vars = None / chỉ tk_user, tk_pass -> input_var dùng default
  của bước). Nay mọi lượt hẹn giờ dùng Quản Lý Biến làm nền + biến riêng đè
  lên. Muốn lịch không có biến riêng giữ hành vi cũ tuyệt đối: đổi
  `_get_schedule_preset_vars` chỉ trả `scheduler.get_schedule_vars(entry)`.
- Đã kiểm tra: `py_compile` + `pyflakes`; test không-GUI cho helper, trigger,
  hàng chờ, cả 2 nhánh worker; test GUI (Xvfb) cho hộp thoại và dòng lịch.

---

## Task trước (2026-09-27, đợt 15)

Yêu cầu người dùng: thêm "🎁 Hành Động Sự Kiện" - 1 hành động cho sự kiện
trong game chỉ diễn ra vài ngày (thỉnh thoảng hiện quà để nhận): tích chọn
thì chạy SUỐT CẢ NGÀY (lặp lại liên tục), nhưng nếu có hành động khác (chạy
tay hoặc hẹn giờ) thì phải DỪNG LẠI nhường ưu tiên cho hành động khác chạy
trước, xong lại tự chạy tiếp; có thể Dừng hoặc Tạm Dừng riêng hành động này.

### Đã làm (đợt 15)

- File MỚI `dashboard_event.py` (EventActionMixin, ghép vào DashboardApp ở
  dashboard.py):
  - Soạn 1 CHUỖI BƯỚC riêng theo TỪNG GIẢ LẬP (`_pick_event_actions`/
    `self._event_action_steps_by_emulator`) - TÁI DÙNG NGUYÊN XI popup
    `self._open_steps_editor()` đã có sẵn (y hệt cách soạn "🏁 Hành Động
    Cuối"), không viết lại UI chọn Hoạt Động/Hành động hệ thống.
  - `start_event_action()`: mở 1 luồng nền RIÊNG (`_worker_event_action`)
    cho MỖI giả lập đang được TICK ở thanh Giả Lập mà ĐÃ soạn chuỗi bước -
    luồng này tự LẶP LẠI vô hạn (chạy 1 lượt -> nghỉ N phút -> chạy lượt
    kế) tới khi bấm `stop_event_action()`.
  - `stop_event_action()`/`toggle_pause_event_action()`: áp dụng cho các
    giả lập đang TICK (nếu trùng với giả lập đang chạy Sự Kiện) hoặc TẤT CẢ
    giả lập đang chạy Sự Kiện (nếu không tick trúng cái nào) - dùng cờ
    RIÊNG `self._event_stop_flags`/`self._event_pause_flags` (theo
    emulator_index), HOÀN TOÀN ĐỘC LẬP với `self.stop_flag(s)`/
    `pause_flag(s)` của Chạy tay/Hẹn Giờ (bấm Dừng/Tạm Dừng bên nào không
    ảnh hưởng bên kia).
  - CƠ CHẾ NHƯỜNG ƯU TIÊN (phần quan trọng nhất, KHÔNG viết cơ chế mới mà
    tái dùng hàng chờ `self._emulator_job_queue`/`self._busy_emulator_indexes`
    đã có sẵn cho Chạy tay/Hẹn Giờ):
    - Trước khi chạy 1 lượt, `_worker_event_action` tự kiểm tra
      `emulator.index in self._busy_emulator_indexes` - nếu bận thì ĐỨNG
      CHỜ (không tự xếp hàng qua `_queue_job` vì Sự Kiện không phải job
      "phải chạy đúng 1 lần"), thử lại mỗi 2s.
    - Khi giả lập rảnh, tự nhận `_busy_emulator_indexes` rồi chạy 1 lượt
      qua `self._run_post_run_steps(engine, emulator, ids, tag="🎁 Sự
      Kiện", event=True)` (hàm LÕI dùng chung với "🏁 Hành Động Cuối",
      KHÔNG viết lại phần thực thi bước).
    - **Sửa `dashboard_run.py`**: `_is_stop_requested`/`_is_pause_requested`
      /`_make_stop_checker`/`_exec_entry`/`_run_post_run_steps`/
      `_wait_after_boot_for_autologin`/`_autologin_after_boot`/
      `_autologin_before_step` đều thêm tham số MỚI `event=False` (mặc
      định GIỮ NGUYÊN hành vi cũ, không đổi chữ ký gọi cũ ở bất kỳ đâu
      khác trong code - đúng quy tắc "không tự ý đổi tên biến/hàm/tham số
      đã có"). Khi `event=True`: `_is_stop_requested` chuyển sang đọc
      `self._event_stop_flags` THAY VÌ `self.stop_flag(s)`, VÀ coi như
      "cần dừng" NGAY nếu `self._emulator_job_queue` đang có job khác chờ
      đúng giả lập đó - đây chính là điểm mấu chốt khiến Sự Kiện tự NGẮT
      NGANG (không đợi hết cả chuỗi bước, chỉ tới điểm dừng an toàn kế
      tiếp - giữa 2 bước hoặc giữa 1 vòng lặp chờ ảnh, y hệt độ trễ của
      nút "⏸ Tạm Dừng" thường) ngay khi có Chạy tay/Hẹn Giờ/Nhóm Hành Động
      khác vừa bấm/vừa tới giờ nhưng bị chặn vì Sự Kiện đang giữ giả lập.
    - **Sửa `dashboard_schedule.py`**: `_exec_system_action` cũng thêm
      `event=False` và truyền xuyên suốt xuống các lời gọi
      `_exec_entry`/`_autologin_before_step`/`_autologin_after_boot` bên
      trong (để bước hệ thống Đăng Xuất/Đăng Nhập trong chuỗi Sự Kiện cũng
      nhường được, không chỉ Hoạt Động thường).
    - Sau khi 1 lượt Sự Kiện kết thúc (dù chạy xong hẳn hay bị ngắt ngang
      để nhường) -> `_busy_emulator_indexes.discard()` +
      `self._after_emulator_freed(idx)` NGAY LẬP TỨC - job đang xếp hàng
      chờ (nếu có) được chạy tiếp NGAY, không cần đợi vòng kiểm tra kế
      tiếp - rồi Sự Kiện tự lặp lại vòng ngoài để chờ giả lập rảnh lại.
  - Tự BẬT giả lập nếu đang tắt trước mỗi lượt (dùng `emu_manager.
    ensure_running`, giống Chạy tay/Xoay Vòng/Hẹn Giờ).
- `dashboard_ui.py`: thêm hàng nút MỚI "🎁 Hành Động Sự Kiện" (dưới hàng
  "🏁 Hành Động Cuối") - nút "🎁 Soạn Hành Động Sự Kiện Theo Giả Lập", ô
  "Nghỉ giữa lượt (phút)" (`event_interval_var`, mặc định 5 phút), nút
  "▶ Bắt Đầu Sự Kiện (Giả Lập Đã Tick)"/"⏸ Tạm Dừng Sự Kiện"/"⏹ Dừng Sự
  Kiện". Load `self._event_action_steps_by_emulator` từ settings ở đây,
  giống hệt cách `_post_run_steps_by_emulator` đang được load.
- `dashboard.py`: import + ghép `EventActionMixin` vào `DashboardApp`; khởi
  tạo `self._event_stop_flags`/`self._event_pause_flags`/
  `self._event_active_indexes` trong `__init__`; `_save_settings()` lưu
  thêm `event_action_steps_by_emulator` + `event_interval_minutes` (KHÔNG
  lưu trạng thái đang chạy/đang tạm dừng - mở lại app luôn coi Sự Kiện
  đang TẮT, người dùng tự bấm "▶ Bắt Đầu Sự Kiện" lại nếu muốn, tránh tự ý
  chạy nền ngay khi vừa mở app).
- Đã kiểm tra cú pháp (`py_compile` toàn bộ `*.py` + `pyflakes`) - không
  lỗi (các cảnh báo "may be undefined from star imports" của pyflakes là
  false-positive do `from dashboard_theme import *`, giống y hệt mọi file
  khác trong dự án, không phải lỗi mới).

### Cần người dùng tự kiểm tra trên máy thật

- Bấm "🎁 Soạn Hành Động Sự Kiện Theo Giả Lập" soạn 1 chuỗi bước ngắn (vd
  1 Hoạt Động "Nhận Quà Sự Kiện") cho 1 giả lập, tick giả lập đó, bấm
  "▶ Bắt Đầu Sự Kiện" - kiểm tra chuỗi bước tự chạy lặp lại đúng khoảng nghỉ
  đã đặt.
- Trong lúc Sự Kiện đang chạy 1 lượt, bấm "▶ CHẠY" (chạy tay 1 Hoạt Động
  khác) trên ĐÚNG giả lập đó - kiểm tra Sự Kiện có NGẮT NGANG NHANH (trong
  vòng vài giây, không phải đợi hết cả chuỗi bước) để nhường không, và sau
  khi lượt chạy tay xong, Sự Kiện có tự chạy lại không.
- Tương tự với 1 lịch "⏰ Hẹn Giờ" vừa tới giờ trong lúc Sự Kiện đang chạy.
- Bấm "⏸ Tạm Dừng Sự Kiện"/"⏹ Dừng Sự Kiện" - kiểm tra KHÔNG ảnh hưởng tới
  1 phiên Chạy tay khác đang chạy song song trên giả lập khác, và ngược lại
  bấm "⏹ DỪNG" ở thanh Chạy tay chính không làm tắt luôn Sự Kiện.
- Trường hợp giả lập đang TẮT lúc bấm "▶ Bắt Đầu Sự Kiện" - kiểm tra Sự
  Kiện có tự bật giả lập lên được không (timeout đang đặt 120s).

### Next Steps

- Nếu người dùng muốn Sự Kiện tự BẬT LẠI khi mở app (nhớ trạng thái đang
  chạy giữa các lần mở app) thay vì phải tự bấm lại mỗi lần, có thể thêm
  tuỳ chọn lưu `_event_active_indexes` vào settings và tự `start_event_action()`
  lại ở cuối `__init__` - hiện đang CỐ Ý không làm vậy để tránh tự ý chạy
  nền ngoài ý muốn người dùng.
- Cân nhắc thêm ngày hết hạn sự kiện (vd nhập "hết hạn 30/09") để tự động
  Dừng khi qua ngày đó, thay vì người dùng phải tự nhớ bấm "⏹ Dừng Sự
  Kiện" khi sự kiện trong game kết thúc - CHƯA làm ở đợt này vì người dùng
  chưa yêu cầu rõ, có thể hỏi lại nếu cần.

---

## Current Task (2026-09-26, đợt 14)

Yêu cầu người dùng: (1) thêm tuỳ chọn nhập biến TRƯỚC KHI CHẠY (vd số lượng
mua Shop) thay vì phải sửa cứng trong kịch bản; (2) thêm "ô lặp theo thời
gian" (chạy 1 hành động lặp đi lặp lại tới khi hết thời gian đã đặt).

### Đã làm (đợt 14)

- (2) **Lặp theo thời gian**: tính năng này ĐÃ CÓ SẴN trong code từ trước
  (`repeat_mode="time"` + `repeat_ms`, xem `_get_repeat_ms()` và vòng lặp
  action trong `logic_engine.py`, áp dụng cho MỌI bước kể cả `group_start`)
  - chỉ cần double-click "🔁 Sửa Lặp" trên 1 bước rồi gõ `30s`/`2p`/`500ms`
    thay vì số lần (xem `_parse_repeat_input`/`_format_repeat_display` trong
    `gui_manual_steps.py`). Không cần sửa gì thêm cho mục này.
- (1) **Biến Nhập Trước Khi Chạy** (action mới `input_var`):
  - `logic_engine.py`: xử lý `input_var` - nếu biến đã có sẵn trong
    `self.variables` (do Dashboard hỏi trước) thì giữ nguyên, chưa có thì
    dùng `default`.
  - `gui_dialogs.py`: thêm `InputVarDialog` (tên biến, câu hỏi hiển thị,
    kiểu dữ liệu int/float/text, giá trị mặc định).
  - `gui_manual_steps.py`/`gui_ui_build.py`/`gui_step_edit.py`: thêm nút
    "🧩 Biến Nhập Trước Khi Chạy" (Macro Studio) để thêm/sửa bước này, cùng
    menu chuột phải tương ứng.
  - `gui_steplist_ops.py`: hiển thị bước này trong cây danh sách bước.
  - `dashboard_misc.py`: thêm `_scan_input_vars_for_entries()` (quét PHẲNG
    file .json của các Hoạt Động sắp chạy để tìm bước `input_var`) và
    `_prompt_input_vars_for_entries()` (hộp thoại GỘP hỏi tất cả biến 1 lần,
    trả về `{}` nếu không có biến nào, `None` nếu bấm Hủy).
  - `dashboard_run.py`: `_start_run`/`_worker_run_emulator` nhận thêm tham
    số `preset_vars` (mặc định `None`, không phá vỡ chỗ gọi cũ); nối vào
    `_exec_entry(..., preset_vars=preset_vars, ...)`. `run_selected_tasks()`
    gọi `_prompt_input_vars_for_entries` trước khi chạy (hủy chạy nếu bấm
    Hủy) - CHỈ áp dụng nhánh KHÔNG Xoay Vòng Tài Khoản (Xoay Vòng không có
    người túc trực nên cứ để dùng giá trị mặc định).
  - `dashboard_tasks.py`: cả 2 nút chạy nhanh 1 Hoạt Động ("⚡ Nút Chức Năng
    Nhanh" và "Chọn Hành Động Để Chạy") cũng hỏi biến trước khi chạy.
  - `dashboard_schedule.py::_run_queued_manual_job`: giữ nguyên `preset_vars`
    đã hỏi khi job "manual_run" phải XẾP HÀNG CHỜ (giả lập đang bận) rồi mới
    chạy lại lúc giả lập rảnh.

### Đã làm thêm - Biến dùng cho SỐ LẦN/THỜI GIAN LẶP (đợt 14b, cùng ngày)

Người dùng hỏi: biến có điền được vào ô "số lần lặp"/"thời gian lặp" không -
TRƯỚC ĐÓ chưa được ("repeat"/"repeat_ms"/"repeat_seconds" luôn đọc như số cố
định qua `int()`/`float()` trực tiếp). Đã bổ sung để dùng được:

- `logic_engine.py`: thêm `_resolve_step_number(raw, default)` - đọc 1 giá
  trị số CÓ THỂ là biểu thức chứa biến `{ten_bien}` (dùng lại
  `_interpolate_vars`), hỗ trợ thêm 1 dấu `*` đơn giản (KHÔNG dùng eval())
  vd `{so_phut}*60000` để lặp theo phút. `_get_repeat_ms` đổi từ hàm rời
  thành METHOD của `LogicEngine` (dùng `self._resolve_step_number`) - đã sửa
  cả 2 chỗ gọi (`group_start` lặp theo Nhóm, và vòng lặp repeat của từng
  bước). Chỗ đọc `repeat` (số lần) ở cả bước thường và `group_start` cũng
  đổi qua `_resolve_step_number`.
- `gui_manual_steps.py`: `_parse_repeat_input` nhận thêm cú pháp gõ trực
  tiếp `{ten_bien}` (số lần), `{ten_bien}s`/`{ten_bien}p`/`{ten_bien}ms`
  (thời gian) ở hộp thoại "🔁 Sửa Lặp" - giữ NGUYÊN dạng chuỗi trong JSON,
  không ép về số ngay lúc soạn. `_format_repeat_display` hiện lại đúng
  chuỗi biểu thức nếu có, không còn crash khi giá trị là chuỗi.
- Đã tự viết script test độc lập (mock LogicEngine + test parse) xác nhận:
  số cố định cũ (`30s`, `5`...) vẫn hoạt động y hệt trước; cú pháp biến mới
  (`{so_luong}`, `{so_phut}p`...) parse/resolve đúng; biến chưa tồn tại thì
  fallback về default + log lỗi thay vì crash.

### Chưa làm / giới hạn phạm vi (đợt 14)

- KHÔNG hỏi biến ở: Xoay Vòng Tài Khoản, Hẹn Giờ Tự Động, "📦 Nhóm Hành Động"
  (`_start_run_group`), "🏁 Hành Động Cuối" (`_run_post_run_steps`) - các luồng
  này chạy không người túc trực nên cứ để `input_var` tự dùng `default` (đúng
  như thiết kế, xem comment trong `logic_engine.py`). Muốn mở rộng thêm thì
  làm tương tự `_prompt_input_vars_for_entries` ở các điểm gọi tương ứng.
- Chỉ quét `input_var` ở CẤP FILE CHÍNH của Hoạt Động, không đệ quy vào Nhóm
  Ngoài (`action="group"`, `group_file=...`).
- Chưa test trên Windows/LDPlayer thật (chỉ compile-check bằng `py_compile`
  trên Linux, không có Tkinter display để chạy GUI thật).

## Current Task (2026-09-24, đợt 13)

Yêu cầu người dùng: (1) bước hệ thống "Đăng Xuất"/"Đăng Nhập" (trong "🏁 Hành
Động Cuối" hoặc Hẹn Giờ) phải chạy `auto_login` ngay trước bước đó - trước đây
xếp "Bật giả lập" rồi "Đăng Xuất" liền nhau thì Đăng Xuất chạy khi chưa vào game
nên hỏng; (2) mỗi khi giả lập được KHỞI ĐỘNG (ở bất kỳ đâu, kể cả tắt rồi bật lại
giữa chuỗi bước) phải chờ boot xong hẳn (+ tuỳ chọn thời gian chờ) rồi chạy
`auto_login`; bình thường vẫn chạy `auto_login` trước khi chạy thao tác.

### Đã làm (đợt 13)

- `dashboard_run.py`: thêm `_get_boot_wait_seconds`, `_wait_after_boot_for_autologin`,
  `_autologin_after_boot`, `_autologin_before_step`. `_exec_entry` xoá cờ
  `_prev_sys_loai[emulator.index]` (bước liền trước là Đăng Xuất). `_worker_run_emulator`:
  vừa tự bật -> chờ boot-wait rồi vòng lặp sẵn có chạy auto_login.
- `dashboard_schedule.py` `_exec_system_action`: `dang_xuat` chạy auto_login trước;
  `dang_nhap` chạy auto_login trước, TRỪ khi ngay sau 1 bước Đăng Xuất (tránh vào lại
  game bằng TK cũ); `bat_gia_lap` dùng `find_by_index` mới, nếu THẬT SỰ vừa khởi động
  (`ensure_running` trả True) -> chờ boot-wait + auto_login, cập nhật hwnd/serial;
  `tat_gia_lap` chờ tắt hẳn (`wait_until_stopped`, tối đa 30s) để "tắt rồi bật" không
  bị coi là đã bật sẵn. `_worker_run_schedule`: vừa tự bật -> chờ boot-wait.
- `dashboard_emulators.py`: nút Bật giả lập chờ boot-wait trước Tự Login.
- `dashboard_accounts.py`: Xoay Vòng + Log Nhanh chờ boot-wait khi vừa tự bật.
- `emulator_manager.py`: thêm `wait_until_stopped()`.
- `dashboard_ui.py` + `dashboard.py`: ô "Chờ boot (s)" cạnh "Tự Login", lưu
  `boot_wait_seconds` (mặc định 10, 0-600) trong dashboard_settings.json.

### Lưu ý (đợt 13)

- Chỉ chờ boot-wait khi "Tự Login" đang bật.
- Chưa test trên Windows/LDPlayer thật (chỉ test giả lập bằng mock trên Linux).
- WindowFinder (chỉ dùng cho popup trong game) không tự gắn lại hwnd mới sau khi tắt-bật.

## Current Task (2026-09-21, đợt 12)

Yêu cầu người dùng: khi tắt Dashboard rồi bật lại, nó tự chạy bù các lịch hẹn
giờ đã bỏ lỡ. Thêm BẢNG liệt kê các lịch đã bỏ lỡ + tuỳ chọn chạy hay không
(nhiều lịch thì tick chọn lịch nào chạy, vẫn theo thứ tự); nếu chọn không chạy
thì đặt hết thành "vừa chạy xong".

### Đã làm (đợt 12)

- `scheduler.py`: thêm `last_due_time()` (mốc lưới giờ gần nhất đã qua),
  `next_due_time()` (mốc kế tiếp, chỉ để ghi log) và `missed_count()` (đã lỡ
  bao nhiêu mốc kể từ `lan_chay_luc`). KHÔNG đổi `is_due()`/`mark_triggered()`.
- `dashboard_missed.py` (FILE MỚI): `MissedSchedulesDialog` - bảng tối màu, mỗi
  dòng 1 lịch bị lỡ (tick chạy, tên, mốc bị lỡ + "cách đây", Hoạt Động theo thứ
  tự chạy, giả lập gán). Tick sẵn TẤT CẢ (giữ hành vi cũ nếu chỉ bấm Chạy).
  Nút: Tick/Bỏ tick tất cả, "Không chạy gì (coi như vừa chạy xong)", "Chạy N lịch
  đã tick". Nút X và ESC = "Không chạy". Chỉ lo giao diện, trả `result` (list
  chỉ số dòng tick theo thứ tự bảng / [] / None nếu cửa sổ bị huỷ khi app tắt).
- `dashboard.py`: thêm `self._app_start_time` (mốc mở app) và
  `self._missed_startup_checked` (+ `from datetime import datetime`).
- `dashboard_schedule.py`: `_check_schedules` - Ở LẦN KIỂM TRA ĐẦU TIÊN sau khi
  mở app, lịch đến hạn mà `last_due_time` < lúc mở app = "bỏ lỡ" -> KHÔNG tự
  chạy nữa mà đưa vào `_handle_missed_schedules`; lịch vừa tới giờ khi app đang
  mở (và mọi lần kiểm tra sau) chạy y như cũ. `_handle_missed_schedules`: sắp
  theo mốc lỡ (sớm chạy trước, bằng nhau theo thứ tự file), mở bảng chờ chọn,
  rồi `mark_triggered` cho TẤT CẢ lịch trong bảng + lưu TRƯỚC khi chạy, sau đó
  `_trigger_schedule` lần lượt các lịch được tick (giả lập bận vẫn tự xếp hàng
  chờ như mọi lượt lịch). Lịch không tick chỉ ghi log + đặt "vừa chạy xong".
  Bảng lỗi không mở được -> chạy bù TẤT CẢ như cũ; cửa sổ bị đóng do app tắt ->
  không đánh dấu gì (lần mở sau hỏi lại).
- `dashboard_theme.py` HELP_TEXT: thêm mục 7f giải thích bảng lịch bỏ lỡ.

### Kiểm tra (đợt 12)

- Dựng DashboardApp thật dưới Xvfb (stub win32*): tick 1 phần (chỉ lịch được tick
  chạy, đúng thứ tự, lịch bỏ tick được `lan_chay_luc` mới và không còn `is_due`);
  chạy tất cả; "Không chạy gì"; ESC; kiểm tra lần 2 không chạy/hỏi lại; lịch
  vừa tới giờ khi app mở (sau `_app_start_time`) vẫn tự chạy không qua bảng;
  không có lịch bỏ lỡ -> không mở bảng; bảng lỗi -> chạy bù tất cả; huỷ không
  chọn -> giữ nguyên. Bảng 8 dòng: cuộn, wrap, nút Chạy khoá khi 0 tick.

### Lưu ý / hạn chế

- Bảng chờ người dùng bấm: máy chạy không người trông (tự bật khi khởi động)
  sẽ KHÔNG tự chạy bù cho tới khi có người chọn (trước đây tự chạy hết). Muốn
  có thể thêm đếm ngược tự chạy sau N giây.
- Chỉ áp cho lịch bỏ lỡ LÚC MỞ APP; lịch trễ do máy ngủ/treo khi app vẫn mở vẫn
  tự chạy bù như cũ.
- Lịch lặp lại lỡ nhiều mốc vẫn chỉ chạy bù 1 lượt (như cũ) - bảng chỉ hiện số mốc lỡ.
- Chưa test trên Windows thật (chỉ Linux + Xvfb).

## Current Task (2026-09-21, đợt 11)

Yêu cầu người dùng: `dong_goi_dong_bo.py` thêm TUỲ CHỌN ĐỒNG BỘ GÌ (vd chỉ cần
đồng bộ Hoạt Động + Kịch bản, không cần đồng bộ Giờ Hẹn và Tài khoản).

### Đã làm (đợt 11)

- `dong_goi_dong_bo.py`: chia dữ liệu thành 7 NHÓM chọn được (`NHOM_DONG_BO`):
  `kich_ban` (tasks/*.json), `hoat_dong` (task_registry.json), `anh_mau`
  (templates/), `nhom_du_lieu` (data_groups.json), `tai_khoan` (accounts +
  account_groups + quick_login_groups), `lich_hen_gio` (schedules.json),
  `cai_dat_dashboard` (dashboard_settings.json). Map file: `DATA_FILES_BY_NHOM`.
- Chạy không tham số -> hộp thoại Tkinter (`HopThoaiChon`) tick chọn + 3 nút
  chọn nhanh (`PRESETS`: `day_du`, `hoat_dong_kich_ban`, `chi_kich_ban`). Không
  mở được Tkinter/không có màn hình -> tự chuyển sang menu chữ
  (`_hoi_chon_console`). Dòng lệnh không hỏi: `--chon a,b,c`, `--preset x`,
  `--console`, `--liet-ke`.
- `build_package(chon=None)`: `chon=None` = ĐÚNG hành vi cũ (`NHOM_MAC_DINH`).
  Giữ nguyên tên `PROJECT_ROOT/TASKS_DIR/TEMPLATES_DIR/DATA_DIR/OUTPUT_DIR/
  DATA_FILES_TO_INCLUDE/INCLUDE_DASHBOARD_SETTINGS/IMAGE_EXTS/SKIP_*/
  _iter_files/_build_readme` (`_build_readme` thêm 2 tham số cuối tuỳ chọn).
- Gói chọn một phần đặt tên `dong_bo_mot_phan_<ngày_giờ>.zip` (gói đầy đủ vẫn
  `dong_bo_<ngày_giờ>.zip`). README trong gói liệt kê nhóm đã/không đồng bộ.
- `_canh_bao_chon()` nhắc khi chọn tổ hợp dễ sai (Tuỳ chỉnh Hoạt Động không kèm
  Kịch bản; Kịch bản không kèm Ảnh mẫu; có Cài đặt Dashboard).

### Kiểm tra (đợt 11)

- Preset `day_du` cho danh sách file trong .zip GIỐNG HỆT bản cũ (so sánh trên
  dự án giả có .bak/__pycache__/file lạ/window_geometry/run_state).
- Từng preset và `--chon` tuỳ ý cho đúng file; nhóm sai/rỗng báo lỗi, exit 1.
- Hộp thoại dựng thật dưới Xvfb: preset, tick tay, bỏ hết -> cảnh báo không
  đóng, Huỷ -> None. Menu chữ và fallback khi không có DISPLAY chạy đúng.

### Lưu ý

- `data_groups.json` (Nhóm Dữ Liệu, bước "Lấy Dữ Liệu (Nhóm)") TRƯỚC ĐÂY chưa
  từng được đóng gói; nay có nhóm riêng nhưng để KHÔNG tick sẵn (giữ nguyên
  hành vi gói đầy đủ cũ). Kịch bản dùng bước đó nên tick kèm.
- Chưa test trên Windows thật (chỉ Linux + Xvfb).

## Current Task (2026-09-20, đợt 10)

Yêu cầu người dùng: thêm TUỲ CHỌN KIỂU QUÉT ẢNH ở MỌI chỗ tìm ảnh (kể cả 🧪 Test
Quét Ảnh), mỗi ảnh/bước chọn được 1 kiểu phù hợp, MẶC ĐỊNH vẫn là `_to_gray`
như cũ. Nguyên nhân gốc: `TM_CCOEFF_NORMED` trên ảnh xám bỏ qua độ sáng/tương
phản nên 2 ảnh cùng hình chỉ khác sáng/màu vẫn ra ~0.998 (log `.2f` làm tròn
thành "1.00").

### Đã làm (đợt 10)

- `adb_helper.py`: thêm `DEFAULT_MATCH_MODE`, `MATCH_MODES` (5 kiểu: `gray`
  mặc định = cách cũ, `color`, `gray_sqdiff`, `color_sqdiff`, `edge`),
  `normalize_match_mode`, `match_mode_label/short/from_label`,
  `_prep_for_mode`, `_match_map` (module-level). Điểm LUÔN "càng cao càng
  khớp" 0..1 (kiểu SQDIFF đảo thành 1 - sai_khác). `find_image_on_screen`,
  `find_any_image_on_screen`, `find_all_images_on_screen`,
  `find_all_matches_on_screen` thêm tham số CUỐI `mode=` (và `modes=` dict
  tên_ảnh->kiểu cho hàm nhiều ảnh) - KHÔNG đổi tên/thứ tự tham số cũ. Thêm
  `find_image_all_modes()` (1 lần chụp, điểm của mọi kiểu - cho Test Quét Ảnh).
- Dữ liệu bước: `step["match_mode"]` (str) + `step["template_modes"]`
  ({tên_file: kiểu}, chỉ bước nhiều ảnh). KHÔNG có field = "gray" => kịch bản
  cũ chạy y hệt. Chọn lại mặc định thì XOÁ key cho file JSON gọn.
- `logic_engine.py`: `_poll_single_template`/`_poll_any_template` thêm tham số
  cuối `mode`/`modes` (mặc định None); `check_condition` (if_image), `wait_image`,
  `wait_vanish`, `multi_image` (cả click_all) đều đọc và truyền kiểu quét.
- GUI: `gui_dialogs.MatchModeDialog` (kiểu chung + kiểu riêng từng ảnh);
  `gui_step_edit` nhánh `_edit_step_field(..., "match_mode")`, `_panel_match_mode`,
  và `_insert_step` áp kiểu đang chọn ở panel cho bước ảnh MỚI;
  `gui_ui_build` menu chuột phải "🧠 Sửa Kiểu Quét Ảnh" (kể cả wait_vanish),
  dòng riêng "🧠 Kiểu quét ảnh" dưới khung hàng loạt (hàng trên đã kín 1440px),
  cột Độ khớp rộng 100 và hiện nhãn kiểu khi khác mặc định (`*` = có ảnh dùng
  kiểu riêng); `gui_steplist_ops` áp hàng loạt ("Giữ nguyên" KHÔNG đụng kiểu
  đã đặt); `gui_image_test` thêm ô Kiểu quét + tick "So sánh điểm của MỌI kiểu",
  điểm log đổi `.2f` -> `.3f`.

### Kiểm tra (đợt 10)

- Kiểu mặc định so với bản cũ: 25 trial ngẫu nhiên x 8 phép gọi (4 hàm find_*,
  có/không region, mode=None/lạ) cho kết quả GIỐNG HỆT (repr bằng nhau).
- Ảnh thật icon_78x86_73490/73510 (cùng hình, khác sáng): gray 0.998, color
  0.993 (nhận nhầm) - gray_sqdiff 0.764, color_sqdiff 0.704, edge 0.488 (phân biệt).
- E2E qua LogicEngine (màn hình giả): wait_image/if_image/multi_image click_all/
  wait_vanish đều dùng đúng kiểu; click_all gray = 4 click (nhận nhầm), color_sqdiff = 3.
- GUI dựng thật dưới Xvfb: dialog, menu, cột conf, áp hàng loạt, cửa sổ Test.

### Lưu ý / hạn chế

- SQDIFF chuẩn hoá có thể vẫn cho điểm cao khi ảnh mẫu và nền cùng rất sáng;
  `edge` cần hạ Độ khớp (~0.6-0.75). Nên dùng 🧪 Test + "So sánh mọi kiểu" để chọn.
- Áp hàng loạt với kiểu cụ thể sẽ xoá `template_modes` của các bước nhiều ảnh.

## Current Task (2026-09-15, đợt 9)

Yêu cầu người dùng: "file dashboard đang dài quá, chia nhỏ ra để dễ chỉnh
sửa và quản lý" (dashboard.py đã tới 3020 dòng, 1 class DashboardApp với
~90 phương thức).

### Đã làm (đợt 9)

- CHỈ tổ chức lại code, KHÔNG đổi bất kỳ hành vi/logic nào (đã kiểm tra kỹ
  - xem bên dưới). Tách `dashboard.py` (3020 dòng) thành 12 file nhỏ hơn,
  dùng mô hình MIXIN (nhiều class kế thừa cùng lúc) để mọi phương thức vẫn
  thuộc về ĐÚNG 1 class/instance `DashboardApp` như trước - chỉ khác là
  ĐỊNH NGHĨA rải ở nhiều file:
    - `dashboard_theme.py`      - bảng màu COL_* + HELP_TEXT
    - `dashboard_widgets.py`    - RoundedButton/FlowBar/DarkCheck/
      CategorySection + `_set_dpi_awareness`/`_bind_esc_close`
    - `dashboard_ui.py`         - `UIBuildMixin` (dựng khung giao diện)
    - `dashboard_emulators.py`  - `EmulatorMixin` (quét/bật/tắt giả lập,
      Bảng Giả Lập, Chụp Thử)
    - `dashboard_tasks.py`      - `TaskMixin` (danh mục Hoạt Động, nút
      chức năng nhanh, Chọn Hành Động Để Chạy)
    - `dashboard_run.py`        - `RunMixin` (CHẠY tay/hàng chờ/tạm dừng/
      `_exec_entry`/2 tuỳ chọn hậu kỳ)
    - `dashboard_accounts.py`   - `AccountsMixin` (Xoay Vòng Tài Khoản,
      Quản Lý Tài Khoản)
    - `dashboard_schedule.py`   - `ScheduleMixin` (Hẹn Giờ Tự Động, Gán
      GL/TK)
    - `dashboard_dialogs.py`    - `DialogsMixin` (popup multi-select dùng
      chung giữa Task/Run/Schedule)
    - `dashboard_progress.py`   - `ProgressMixin` (tiến độ + Lỗi/Chưa
      Xong)
    - `dashboard_misc.py`       - `MiscMixin` (popup trong-game, Hướng
      Dẫn, Cài Đặt Shop, Reset Bộ Nhớ Task)
    - `dashboard_log.py`        - `LogMixin` (Nhật Ký)
  `dashboard.py` giờ chỉ còn ~185 dòng: docstring giải thích cách tổ chức
  mới, imports, `SETTINGS_PATH`, và `class DashboardApp(UIBuildMixin,
  EmulatorMixin, TaskMixin, RunMixin, AccountsMixin, ScheduleMixin,
  DialogsMixin, ProgressMixin, MiscMixin, LogMixin)` chứa `__init__` +
  `_load_settings`/`_save_settings`/`_on_close` + khối `if __name__`.
- QUY TRÌNH KIỂM TRA KHÔNG MẤT/ĐỔI CODE (làm bằng script, không gõ tay
  từng dòng để tránh sai sót khi di chuyển ~2550 dòng):
  1. Dò toàn bộ ranh giới `def` bằng `grep -n` để xác định chính xác từng
     phương thức bắt đầu ở dòng nào.
  2. Cắt file gốc thành các đoạn theo đúng ranh giới đó (script Python),
     kiểm chứng bằng cách cộng dồn số dòng của mọi đoạn = đúng số dòng gốc
     và mỗi dòng gốc (469-3014, toàn bộ thân class) xuất hiện ĐÚNG 1 LẦN
     duy nhất trong tổng các đoạn (không trùng, không thiếu).
  3. Đếm tên từng `def` ở gốc vs. tổng các file mới - khớp 100/100 (kể cả
     các `__init__` trùng tên của nhiều class khác nhau).
  4. So sánh nội dung ở mức "mỗi dòng code sau khi bỏ dòng trắng" giữa bản
     gốc và tổng các file mới - phần khác biệt DUY NHẤT là docstring đầu
     file, các dòng import được viết lại (gộp/tách `from tkinter import
     ...`), các dòng comment phân cách, và khai báo `class DashboardApp:`
     đổi thành `class DashboardApp(...Mixin...):` - không có dòng logic
     nào bị mất/đổi.
  5. `ast.parse` + `py_compile` toàn bộ 13 file - không lỗi cú pháp.
  6. Kiểm tra tĩnh (tự viết bằng `ast`) mọi tên được dùng (Name-Load) ở
     từng file đều được import/định nghĩa/là tham số hàm - phát hiện đủ
     import còn thiếu (vd `ADBHelper`, `WindowFinder`, `LogicEngine`,
     `datetime`, `run_state`, `scheduler`...) và đã thêm đủ vào từng file
     theo đúng nhu cầu thực tế của file đó (không import thừa tràn lan).
  7. Riêng bảng màu COL_*/HELP_TEXT: dùng `from dashboard_theme import *`
     ở các file cần nhiều màu (đây là theme module nội bộ, star-import ở
     đây chấp nhận được) - đã đối chiếu mọi `COL_*`/`HELP_TEXT` được dùng
     ở bất kỳ file nào đều có định nghĩa trong `dashboard_theme.py`.
- CHƯA thể `import` thật với `tkinter` để chạy GUI thử (môi trường code
  hiện tại không có `tkinter`/Windows/LDPlayer) - đã kiểm tra tĩnh kỹ như
  trên nhưng người dùng NÊN tự mở thử `python dashboard.py` trên máy thật
  trước khi dùng để chạy các tác vụ quan trọng, phòng trường hợp hiếm gặp
  ngoài phạm vi kiểm tra tĩnh (vd lỗi thứ tự khởi tạo MRO - dù đã xem qua
  và không thấy phương thức nào bị gọi đè lẫn nhau giữa các Mixin).

### Cần người dùng tự kiểm tra trên máy thật

- Mở `python dashboard.py`, xác nhận giao diện hiện lên y hệt trước đây
  (không thiếu nút/khung nào), thử qua các tính năng chính 1 lượt: CHẠY
  tay, Xoay Vòng Tài Khoản, Hẹn Giờ, Bảng Giả Lập, Hướng Dẫn, Nhật Ký.
- Nếu về sau cần SỬA 1 tính năng cụ thể, chỉ cần mở đúng file
  `dashboard_xxx.py` tương ứng (xem bảng trong docstring đầu
  `dashboard.py`) - không cần mở lại `dashboard.py` gốc nữa.

---

## Current Task (2026-09-14, đợt 8)

Theo yêu cầu người dùng (4 ý):
1. "Chạy ngay" (chạy tay/Chạy Ngay/Xoay Vòng Tài Khoản) cũng phải XẾP HÀNG
   CHỜ khi giả lập bận, giống lịch hẹn giờ (đợt 7 mới chỉ làm cho lịch hẹn
   giờ, chưa áp dụng cho các lượt CHẠY do người dùng bấm tay).
2. Danh sách lịch trong '⏰ Hẹn Giờ' sắp xếp theo THỜI GIAN CHẠY (giờ hẹn).
3. Nút 'Tự Login' (Hoạt Động 'auto_login') phải là 1 hành động RIÊNG (khác
   'account_login') để đưa giả lập vào game (script tự kiểm tra đã vào
   game chưa) - CHỈ SAU KHI thành công mới bắt đầu chạy kịch bản đã chọn
   (trước đây chạy nối tiếp vô điều kiện, không gate theo kết quả).
4. Thêm 2 tuỳ chọn HẬU KỲ: (a) tự TẮT GIẢ LẬP sau khi chạy xong, (b) tự
   ĐĂNG NHẬP vào 1 TÀI KHOẢN CHỈ ĐỊNH sau khi chạy xong.

### Đã làm (đợt 8)

- `dashboard.py`:
  - Đổi tên `self._emulator_schedule_queue` -> `self._emulator_job_queue`
    (dict `{emulator_index: [job, ...]}`), mỗi job có khoá `"kind"`:
    `"schedule"` (như đợt 7), `"manual_run"` (CHẠY tay/Chạy Ngay 1 tác vụ/
    Tự Login), `"manual_accounts"` (Xoay Vòng Tài Khoản).
  - Thêm `_split_busy_emulators()` (tách available/busy) và `_queue_job()`
    (đẩy 1 job vào hàng chờ + log rõ vị trí) dùng chung - thay thế hẳn
    `_filter_busy_emulators()` cũ (đã xoá, trước đây chỉ log cảnh báo rồi
    BỎ QUA giả lập bận).
  - `_start_run()`: giả lập bận -> `_queue_job(kind="manual_run")` thay vì
    bỏ qua; giả lập rảnh chạy như cũ.
  - `_start_run_with_accounts()` / `_launch_run_with_accounts()`: KHÔNG
    lọc bận trước khi mở popup gán Tài khoản nữa (vẫn cho gán Tài khoản
    cho MỌI giả lập đã tick kể cả đang bận) - tách available/busy SAU khi
    đã có `assignment`, giả lập bận -> `_queue_job(kind="manual_accounts")`
    kèm đúng `account_ids` đã gán cho giả lập đó.
  - `_trigger_schedule()`: đẩy job qua `_queue_job`/`_emulator_job_queue`
    chung (job `kind="schedule"`) thay vì hàng chờ riêng như đợt 7 - nhờ
    vậy "▶ Chạy Ngay" của 1 lịch (vốn gọi thẳng `_trigger_schedule`) TỰ
    ĐỘNG được xếp hàng chờ đúng như lịch tự động, không cần sửa thêm gì ở
    nút "▶ Chạy Ngay".
  - `_after_emulator_freed()`: đọc `kind` của job đầu hàng để dispatch đúng
    chỗ - `"schedule"` -> `_start_schedule_worker()` (như cũ); `"manual_run"`
    -> `_run_queued_manual_job()` (mới); `"manual_accounts"` ->
    `_run_queued_manual_accounts_job()` (mới). 2 hàm mới lấy lại
    `EmulatorInfo` MỚI NHẤT qua `emu_manager.find_by_index()` (phòng
    trường hợp giả lập vừa khởi động lại đổi hwnd/serial), rồi tăng
    `self.active_threads` + `task_progress[...]["total"]` THEO KIỂU CỘNG
    DỒN (không reset) qua `_begin_queue_replay_session()` - tránh phá vỡ
    đếm luồng/tiến độ của các giả lập khác đang chạy song song.
  - `scheduler.py`: thêm `sort_key(entry)` (khoá sắp xếp theo `gio_hen`
    tăng dần trong ngày). `_open_schedule_manager()` giờ hiển thị danh
    sách lịch theo `sorted(self.schedules, key=scheduler.sort_key)` thay
    vì đúng thứ tự lưu trong file - KHÔNG đổi thứ tự lưu trong
    `schedules.json`, chỉ đổi thứ tự HIỂN THỊ.
  - `_worker_run_emulator()` (lượt CHẠY tay thường, không xoay vòng): viết
    lại để dùng `_exec_entry()` thay vì code lặp riêng (giảm trùng lặp,
    đồng bộ với 2 worker kia). Nếu có `login_entry` ('Tự Login'): chạy
    TRƯỚC, lấy kết quả `ok_login` - THẤT BẠI (không vào được game) thì BỎ
    QUA hẳn các tác vụ đã chọn trên giả lập đó (log lỗi rõ ràng), KHÔNG
    còn chạy tiếp vô điều kiện như trước. Không gate trong trường hợp bấm
    DỪNG giữa chừng (kiểm tra `self.stop_flag` riêng để không log nhầm
    "thất bại" khi thực ra là do người dùng dừng).
  - Thêm `_apply_post_run_options(engine, emulator)`: áp dụng 2 tuỳ chọn
    HẬU KỲ mới sau khi 1 giả lập chạy xong hết việc của lượt hiện tại,
    dùng chung cho cả 3 worker (`_worker_run_emulator`,
    `_worker_run_emulator_with_accounts`, `_worker_run_schedule`) - BỎ
    QUA nếu `self.stop_flag` (đang dừng dở dang). Nếu bật CẢ 2 tuỳ chọn,
    ưu tiên TẮT GIẢ LẬP (log cảnh báo, bỏ qua đăng nhập).
  - Thêm `self.shutdown_after_var` (checkbox "🔌 Tắt Giả Lập Sau Khi Chạy
    Xong") và `self.post_login_after_var` (checkbox "🔑 Đăng Nhập TK Chỉ
    Định Sau Khi Chạy Xong") ở dòng `actions_bar2` mới (bên dưới dòng nút
    cũ, tránh chật). Thêm `_pick_post_login_account()` (popup chọn ĐÚNG 1
    Tài khoản, khác popup multi-select cũ) + `_get_post_run_account()` +
    `_post_login_account_label_text()`. Lưu `shutdown_after`,
    `post_login_after`, `post_login_account_id` vào `dashboard_settings.json`
    qua `_save_settings()` (đã có sẵn cơ chế persist từ trước) - tự nạp
    lại đúng lựa chọn cũ mỗi khi mở lại app.
  - `HELP_TEXT`: thêm mục 8 (Tự Login là hành động riêng, có gate theo kết
    quả), mục 9 (Chạy tay/Chạy Ngay cũng xếp hàng chờ), mục 10 (2 tuỳ chọn
    hậu kỳ mới).
- Đã `py_compile` + `ast.parse` cả `dashboard.py` + `scheduler.py` - không
  lỗi cú pháp. CHƯA test thật trên Windows/LDPlayer (môi trường code hiện
  tại không có Windows/LDPlayer).

### Cần người dùng tự kiểm tra trên máy thật

- Cho 2 giả lập CÙNG chạy 1 lượt tay dài, trong lúc đó bấm CHẠY thêm cho
  1 trong 2 giả lập đó (hoặc bấm "▶ Chạy Ngay" 1 lịch gán đúng giả lập
  đó) - xác nhận lượt mới XẾP HÀNG CHỜ (có log rõ) thay vì bị bỏ qua, và
  tự chạy tiếp đúng lúc giả lập đó rảnh, KHÔNG làm rối tiến độ (%) của
  giả lập kia đang chạy song song.
- Test 'Tự Login' với 1 `tasks/auto_login.json` cố tình cho THẤT BẠI (vd
  chờ 1 ảnh không tồn tại) - xác nhận các tác vụ đã tick trên giả lập đó
  bị BỎ QUA hẳn (không chạy nhầm khi màn hình chưa đúng), có log lỗi rõ.
  Sau đó test lại với `auto_login.json` chạy THÀNH CÔNG - xác nhận các
  tác vụ đã tick chạy bình thường như trước.
- Mở '⏰ Hẹn Giờ' với nhiều lịch có `gio_hen` khác nhau - xác nhận danh
  sách hiển thị đúng thứ tự giờ tăng dần.
- Bật '🔌 Tắt Giả Lập Sau Khi Chạy Xong', chạy xong 1 lượt - xác nhận giả
  lập tự tắt. Tắt tuỳ chọn đó, bật '🔑 Đăng Nhập TK Chỉ Định Sau Khi Chạy
  Xong', bấm '🎯 Chọn TK' chọn 1 tài khoản, chạy xong 1 lượt - xác nhận tự
  đăng nhập đúng tài khoản đã chọn (cần có sẵn Hoạt Động 'account_login').
  Bật cả 2 cùng lúc - xác nhận chỉ tắt giả lập, có log cảnh báo bỏ qua
  đăng nhập.
- Đóng/mở lại app - xác nhận 2 tuỳ chọn hậu kỳ + tài khoản đã chọn vẫn giữ
  nguyên (đọc từ `dashboard_settings.json`).

---

## Current Task (2026-09-13, đợt 7)

Báo lỗi: Hoạt Động A đang chạy dở trên 1 giả lập, tới giờ Hoạt Động B (1
lịch khác, hoặc cùng lịch tới kỳ lặp tiếp theo) cần chạy trên CÙNG giả lập
đó thì bị BỎ QUA LUÔN (chỉ ghi log cảnh báo rồi thôi) thay vì chờ A chạy
xong rồi chạy tiếp B.

### Đã làm (đợt 7)

- `dashboard.py`:
  - Thêm `self._emulator_schedule_queue` (dict `{emulator_index: [job, ...]}`)
    trong `__init__`.
  - `_trigger_schedule()`: khi giả lập đích đang có trong
    `_busy_emulator_indexes`, KHÔNG còn bỏ qua nữa - đẩy job (tên lịch +
    danh sách tài khoản + danh sách Hoạt Động) vào hàng chờ của đúng giả
    lập đó, log rõ "đã XẾP HÀNG CHỜ (vị trí N)".
  - Tách phần khởi chạy luồng ra hàm riêng `_start_schedule_worker(name,
    idx, accs, activities)` - dùng chung cho cả lượt chạy NGAY (giả lập
    đang rảnh) và lượt LẤY TỪ HÀNG CHỜ.
  - Thêm `_after_emulator_freed(emulator_index)`: gọi ngay khi 1 giả lập
    vừa hết bận (dù do chạy tay xong hay 1 lượt lịch chạy xong) - nếu hàng
    chờ của giả lập đó còn job, lấy job ĐẦU HÀNG ra chạy tiếp ngay lập tức
    (không cần đợi chu kỳ `_check_schedules()` 20s kế tiếp).
  - Gọi `_after_emulator_freed()` ở CẢ 2 nơi giải phóng "bận":
    `_on_emulator_thread_done()` (chạy tay/xoay vòng tài khoản xong) và
    `_on_schedule_thread_done()` (1 lượt lịch hẹn giờ xong).
  - Nút "▶ Chạy Ngay" (test thủ công 1 lịch) gọi thẳng `_trigger_schedule()`
    nên tự động thừa hưởng cơ chế hàng chờ này, không cần sửa riêng.
  - Cập nhật HELP_TEXT mục 7.e mô tả đúng hành vi mới (xếp hàng chờ thay vì
    bỏ qua).
  - **Lưu ý phạm vi sửa**: hàng chờ chỉ áp dụng cho LỊCH HẸN GIỜ khi gặp
    giả lập bận (dù bận do chạy tay hay do lịch khác). Nút CHẠY thủ công
    ('▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN' / xoay vòng tài khoản) vẫn giữ hành
    vi CŨ (bỏ qua giả lập đang bận + cảnh báo, không tự xếp hàng) vì đó là
    hành động người dùng chủ động bấm ngay lúc đó, xếp hàng ngầm có thể gây
    hiểu nhầm "đã bấm mà không thấy chạy gì".
- Đã kiểm tra cú pháp (`py_compile`) - không lỗi. CHƯA test thật trên
  Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Đặt 2 lịch trên CÙNG 1 giả lập, giờ hẹn gần nhau (vd cách 2-3 phút, Hoạt
  Động A cố tình dài) - xác nhận lịch B bị "XẾP HÀNG CHỜ" (log), rồi tự
  chạy ngay khi A xong (không cần đợi tới chu kỳ 20s kế tiếp).
  Chờ nhiều Hoạt Động B, C cùng xếp hàng cho 1 giả lập - xác nhận chạy
  đúng thứ tự (FIFO) từng cái một, không chạy chồng lên nhau.
- Bấm DỪNG LẠI trong lúc có job đang nằm trong hàng chờ (chưa tới lượt
  chạy) - xác nhận job đó có bị bỏ dở giữa chừng đúng không, hay vẫn tự
  chạy sau đó (hiện tại: `_worker_run_schedule` tự kiểm tra `stop_flag`
  qua từng bước nên vẫn sẽ CHẠY nhưng dừng giữa chừng ngay khi
  `stop_flag` bật - nếu người dùng muốn hàng chờ cũng bị HUỶ HẲN khi bấm
  DỪNG thì cần báo lại để bổ sung).

---

## Current Task (2026-09-13, đợt 6)

Người dùng báo cáo 3 việc:
1. Hẹn Giờ đang THIẾU cách chọn thẳng Giả lập để chạy - lịch chỉ chạy được
   khi có gán Tài khoản (vì giả lập được suy ra từ `emulator_index` của
   tài khoản). Yêu cầu: nếu KHÔNG chọn Tài khoản nào thì chạy thẳng kịch
   bản trên giả lập đã chọn, không cần đổi tài khoản.
2. Thêm phân loại Nhóm tài khoản (vd "Clone", "Acc chính") để lọc/chọn
   nhanh.
3. Ở cửa sổ Hẹn Giờ, các nút (Hoạt Động/Tài khoản/Chạy Ngay/💾/🗑) nằm
   ngoài vùng nhìn thấy, phải kéo rộng cửa sổ mới thấy được.

### Đã làm (đợt 6)

- `scheduler.py`: KHÔNG đổi cấu trúc bắt buộc - lịch giờ có thêm field tuỳ
  chọn mới `may_ids` (list index giả lập chọn THẲNG cho lịch, độc lập với
  tài khoản). Không cần migrate vì field cũ dùng `.get(..., [])`.
- `dashboard.py`:
  - `_trigger_schedule`: tách 2 CHẾ ĐỘ rõ ràng - (a) CÓ `tai_khoan_ids`:
    xoay vòng như cũ (nhóm theo `emulator_index` của tài khoản); (b)
    KHÔNG có `tai_khoan_ids` nhưng CÓ `may_ids`: chạy thẳng trên đúng các
    giả lập đó, không đăng xuất/đăng nhập. Thiếu cả 2 -> log lỗi rõ ràng,
    bỏ qua lượt đó (trước đây bị "im lặng" nếu tài khoản rỗng vì vòng lặp
    for không chạy).
  - `_worker_run_schedule`: thêm nhánh `if not accounts:` chạy thẳng các
    Hoạt Động 1 lần trên giả lập (dùng đúng phiên đăng nhập sẵn có), y hệt
    kiểu fallback đã có sẵn ở `_worker_run_emulator_with_accounts`.
  - `_open_schedule_manager`: thêm nút chọn "🖥 GL (n)" (giả lập trực tiếp,
    dùng lại `_open_multi_select_dialog`), nhãn chế độ tự động (
    "→ xoay vòng tài khoản" / "→ chạy thẳng, không đổi tài khoản" /
    "→ chưa chọn..."). Sửa layout: mỗi dòng lịch tách thành 2 dòng con
    (line1: Bật/Tên/Giờ hẹn/Lặp lại/Chạy cuối; line2: 🎯 HĐ / 👤 TK / 🖥 GL
    + Chạy Ngay/💾/🗑) thay vì nhồi hết vào 1 dòng ngang - khắc phục lỗi
    phải kéo rộng cửa sổ mới thấy hết nút (line 2 tự đủ chỗ ở khổ cửa sổ
    bình thường, không phụ thuộc độ rộng cửa sổ). Cũng tăng kích thước cửa
    sổ mặc định lên 1150x620 (trước 1080x580) và thêm `minsize` để tránh
    thu quá nhỏ làm vỡ layout lần nữa.
  - `_open_multi_select_dialog`: thêm tham số tuỳ chọn `group_of` (dict
    item_id -> tên nhóm) - nếu có, hiện thêm hàng nút "chọn nhanh theo
    nhóm" phía trên danh sách checkbox (bấm 1 nút là tick hết các mục cùng
    nhóm). Dùng khi mở dialog chọn Tài khoản cho 1 lịch (group theo `nhom`
    của account_manager); không ảnh hưởng dialog chọn Hoạt Động (không
    truyền `group_of`).
  - `_open_account_manager`: thêm cột "Nhóm" (combobox gõ tự do, gợi ý sẵn
    "Acc chính"/"Clone" + các nhóm đã có), lưu vào field `nhom`. Thêm hàng
    "Lọc nhanh theo Nhóm" phía trên bảng - bấm 1 nút ẩn/hiện các dòng tài
    khoản theo đúng nhóm đó (ẩn bằng `pack_forget`, không xoá dữ liệu).
    Tăng kích thước cửa sổ mặc định lên 1060x560 (trước 920x520) + thêm
    `minsize` cho cùng lý do layout ở trên.
- `account_manager.py`: thêm field tài liệu hoá `"nhom"` (chuỗi tự do,
  mặc định rỗng, KHÔNG ảnh hưởng logic xoay vòng) vào docstring đầu file,
  và hàm tiện ích `list_groups(entries)`.
- Đã kiểm tra `py_compile` + `ast.parse` trên `dashboard.py`,
  `account_manager.py`, `scheduler.py` - không lỗi cú pháp. CHƯA test thật
  trên Windows/LDPlayer (môi trường code hiện tại không có Tkinter thật
  chạy giao diện lẫn LDPlayer) - cần người dùng tự mở app và xác nhận:
  1) 1 lịch không chọn Tài khoản, chỉ chọn Giả lập, chạy đúng giờ không
     đăng xuất/đăng nhập gì.
  2) Cột "Nhóm" gõ/lưu/tải lại đúng, nút lọc nhanh hoạt động, và nút
     "chọn nhanh theo nhóm" trong dialog chọn Tài khoản khi soạn lịch tick
     đúng các tài khoản cùng nhóm.
  3) Cửa sổ "Hẹn Giờ Tự Động" và "Quản Lý Tài Khoản" mở ra ở kích thước
     mặc định đã thấy đủ hết các nút mà không cần kéo giãn cửa sổ.

### Cần người dùng tự kiểm tra trên máy thật

- Test đầy đủ như 3 mục ở trên trên máy Windows thật với LDPlayer.
- Nếu màn hình nhỏ hơn 1150px chiều ngang, xác nhận cửa sổ Hẹn Giờ vẫn co
  giãn hợp lý nhờ `minsize` + layout 2 dòng (không còn phụ thuộc độ rộng
  cửa sổ như trước).

---

## Current Task (2026-09-13, đợt 5)

Người dùng báo cáo: lịch đang Bật, "▶ Chạy Ngay" chạy được, nhưng đến đúng
giờ hẹn thì Hoạt Động không tự chạy và KHÔNG có bất kỳ dòng log nào giải
thích. Kèm yêu cầu đổi ô "Lặp lại" từ số giờ thập phân sang định dạng hh:mm.

### Nguyên nhân (đợt 5)

`is_due()` (viết lại ở đợt 4) chỉ neo theo `gio_hen` (giờ hẹn) cho tới
TRƯỚC lần trigger đầu tiên. Ngay khi lịch trigger LẦN ĐẦU - kể cả chỉ do
bấm "▶ Chạy Ngay" để test - `lan_chay_luc` được ghi lại đúng giờ:phút bấm
nút đó, và mọi lần tính "đến giờ chưa" SAU ĐÓ chuyển hẳn sang công thức
`lan_chay_luc + interval_hours`, không còn dùng `gio_hen` nữa. Hậu quả:
bấm "Chạy Ngay" thử lúc 14:00 khiến lịch "hằng ngày lúc 07:00" âm thầm trôi
thành "hằng ngày lúc 14:00" mãi mãi - đúng 07:00 hôm sau `is_due()` trả về
False (chưa 24h kể từ 14:00 hôm trước) nên không chạy, không có gì để log
vì đơn giản là "chưa đến hạn" theo cách tính (sai) đó.

### Đã làm (đợt 5)

- `scheduler.py`:
  - Viết lại `is_due()`/`would_be_due_if_enabled()` theo **lưới giờ cố
    định** neo tại `gio_hen`, dùng mốc gốc cố định 2020-01-01 (không phụ
    thuộc ngày hôm nay hay lần trigger gần nhất) + bội số của
    `interval_hours` - nhờ vậy giờ hẹn hh:mm luôn được tôn trọng vĩnh viễn,
    kể cả sau khi bấm "▶ Chạy Ngay" test ở bất kỳ giờ nào. `lan_chay_luc`
    giờ CHỈ dùng để biết mốc lưới gần nhất đã xử lý hay chưa (chống trigger
    lặp lại nhiều lần cho cùng 1 mốc do Dashboard kiểm tra mỗi ~20s), không
    còn dùng để TÍNH mốc kế tiếp.
  - Thêm `hours_to_hhmm()` / `hhmm_to_hours()` để ô "Lặp lại" nhập/hiển thị
    theo định dạng hh:mm (vd `04:00` = mỗi 4 tiếng, `00:30` = mỗi 30 phút)
    thay vì số giờ thập phân (`4`, `0.5`) - `interval_hours` vẫn lưu nội bộ
    dạng giờ float như cũ (không vỡ `schedules.json` đã lưu). `describe()`
    cập nhật hiển thị theo hh:mm.
- `dashboard.py` (`_open_schedule_manager`): đổi nhãn cột "Lặp lại (giờ)"
  -> "Lặp lại (hh:mm)", ô nhập dùng `scheduler.hours_to_hhmm`/`hhmm_to_hours`
  để đọc/ghi, thông báo lỗi khi nhập sai định dạng cập nhật theo hh:mm.
- Đã viết test thủ công mô phỏng đúng kịch bản báo lỗi (Chạy Ngay lúc 14:00
  ngày 1, kiểm tra 07:00 ngày 2) - xác nhận `is_due()` mới trả về True đúng
  giờ hẹn, không còn bị trôi theo giờ Chạy Ngay. Đã `ast.parse` cả 2 file -
  không lỗi cú pháp. CHƯA test thật trên Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Mở lại app với `schedules.json` cũ - các lịch đã lưu trước đó (đợt 4) vẫn
  đọc được bình thường (không cần migrate gì thêm, chỉ đổi cách TÍNH đến
  hạn, không đổi định dạng file). Ô "Lặp lại" nay hiển thị hh:mm (vd lịch cũ
  `interval_hours: 24` sẽ hiện `24:00`) - bấm 💾 lại 1 lần để chắc chắn.
- Bấm "▶ Chạy Ngay" thử ở 1 giờ bất kỳ khác xa `gio_hen`, sau đó xác nhận
  lịch VẪN tự chạy đúng vào đúng `gio_hen` đã đặt ở lần kế tiếp (không bị
  trôi theo giờ vừa bấm Chạy Ngay như trước).
- Nhập thử ô "Lặp lại" sai định dạng (vd `4` thay vì `04:00`) - xác nhận có
  `messagebox` báo lỗi rõ ràng thay vì âm thầm nhận giá trị sai.

---

## Current Task (2026-09-13, đợt 4)

Sửa 4 vấn đề người dùng báo cáo về tính năng HẸN GIỜ TỰ ĐỘNG (đợt 3):
1. Popup "Chọn Hoạt Động" / "Chọn Tài Khoản" chọn không được / không có
   xác nhận.
2. Chưa chỉnh được giờ tuỳ chọn - chỉ cần "giờ hẹn" + "giờ lặp lại"
   (hằng ngày = 24h).
3. Thêm nút "Chạy Ngay" để test lịch mà không cần chờ tới giờ.
4. Các popup cần bấm ESC để tắt nhanh.

### Đã làm (đợt 4)

- `scheduler.py`: **Gộp mô hình lịch** - bỏ 2 loại "daily"/"interval"
  riêng biệt, thay bằng 2 trường duy nhất: `gio_hen` (hh:mm - mốc chạy LẦN
  ĐẦU) + `interval_hours` (lặp lại mỗi N giờ; hằng ngày = 24, mỗi 4 tiếng =
  4, có thể để số lẻ như 0.5 để test nhanh). `is_due()` viết lại theo mô
  hình mới: nếu chưa từng trigger thì so với mốc `gio_hen` hôm nay; nếu đã
  từng trigger thì so `now - lan_chay_luc >= interval_hours`. Thêm
  `_migrate_entry()` tự động chuyển các lịch đã lưu ở định dạng CŨ
  (`loai`/`gio`) sang định dạng mới ngay khi `load_schedules()` - lịch cũ
  không bị mất khi mở lại app với bản này. `describe()` cập nhật theo mô
  hình mới.
- `dashboard.py` (`_open_schedule_manager`):
  - Bảng lịch đổi cột "Loại" + "Giờ (hh:mm)" + "Mỗi (giờ)" thành 2 cột
    "Giờ hẹn (hh:mm)" + "Lặp lại (giờ)", có validate rõ ràng (báo lỗi bằng
    `messagebox` nếu nhập sai định dạng giờ hoặc số giờ lặp <= 0) thay vì
    âm thầm dùng giá trị mặc định như trước.
  - Thêm nút "▶ Chạy Ngay" ở mỗi dòng lịch: tự lưu lịch trước, kiểm tra đã
    chọn đủ Hoạt Động + Tài khoản chưa (báo rõ nếu thiếu), rồi gọi thẳng
    `mark_triggered()` + `_trigger_schedule()` để chạy thử ngay không cần
    chờ đến giờ hẹn - tiện để test mà không phải chỉnh giờ hệ thống.
  - `_open_multi_select_dialog` (popup chọn Hoạt Động / Tài khoản): thêm
    cuộn bằng con lăn chuột (`<MouseWheel>`) - trước đây chỉ kéo được
    thanh cuộn hẹp bên phải, khiến các mục nằm khuất bên dưới trông như
    "không chọn được". Thêm nhãn đếm "Đã chọn X/Y mục" cập nhật realtime
    khi tick, và sau khi bấm "💾 Lưu" hiện `messagebox` xác nhận đã chọn
    bao nhiêu mục (kèm nhắc bấm 💾 ở dòng lịch để lưu hẳn) - trước đây bấm
    Lưu xong đóng popup im lặng, không rõ đã ăn hay chưa.
  - Thêm hàm dùng chung `_bind_esc_close(win)`: gán phím ESC để đóng ngay
    1 cửa sổ Toplevel. Áp dụng cho TẤT CẢ popup cài đặt/chọn lựa: Chọn
    Hành Động Để Chạy, Hẹn Giờ Tự Động, popup Chọn Hoạt Động/Tài Khoản,
    Lỗi/Chưa Xong, Quản Lý Tài Khoản, Bảng Giả Lập, Hướng Dẫn, Cài Đặt Mua
    Shop. KHÔNG áp dụng cho overlay thông báo trong game (`_show_ingame_popup`)
    vì đó là cửa sổ `overrideredirect` đè lên giả lập, không phải dialog
    cài đặt.
- `gui.py`: thêm cùng hàm `_bind_esc_close()` và áp dụng cho 2 popup thật
  sự là dialog ("Quản Lý Ảnh Trong Nhóm", xem ảnh phóng to) - bỏ qua popup
  overlay trong game (giống dashboard.py, lý do tương tự).
- Đã kiểm tra cú pháp (`py_compile`) trên cả 3 file - không lỗi. CHƯA test
  thật trên Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Mở lại app với `schedules.json` cũ (định dạng "loai"/"gio") - xác nhận
  các lịch cũ vẫn hiện đúng tên/hoạt động/tài khoản và tự chuyển sang hiện
  "Giờ hẹn"/"Lặp lại (giờ)" hợp lý (lịch "daily" cũ -> lặp lại 24; lịch
  "interval" cũ giữ nguyên số giờ lặp).
  Bấm 💾 lại 1 lần cho từng lịch cũ để chốt định dạng mới vào file.
- Bấm "▶ Chạy Ngay" thử với 1 lịch đã chọn đủ Hoạt Động + Tài khoản, xác
  nhận chạy đúng luồng (đăng xuất - đăng nhập - chạy Hoạt Động) giống hệt
  khi tự động đến giờ, và giờ hẹn/lặp lại được tính lại từ mốc vừa chạy
  (không bị lịch tự trigger lại ngay lập tức ở lần kiểm tra 20s kế tiếp).
- Test popup Chọn Hoạt Động / Chọn Tài khoản với danh sách dài (nhiều hơn
  1 màn hình) - xác nhận cuộn được bằng con lăn chuột và tick chọn được
  mọi mục kể cả mục nằm khuất bên dưới.
- Bấm ESC ở từng popup xem có đóng đúng không (đặc biệt popup chọn nhiều -
  ESC sẽ đóng mà KHÔNG lưu lựa chọn, đúng ý nghĩa "huỷ/đóng nhanh").

---

## Current Task (2026-09-13, đợt 3)

Thêm tính năng HẸN GIỜ TỰ ĐỘNG theo yêu cầu người dùng: hẹn chạy 1 (hoặc
nhiều) Hoạt Động cho 1 nhóm Tài Khoản vào giờ cố định hằng ngày, hoặc lặp
lại mỗi N giờ - không cần bấm CHẠY thủ công. Ví dụ đúng use-case người
dùng nêu: "7h hằng ngày chạy HĐ A cho tài khoản 1,2,3", "mỗi 4 tiếng chạy
HĐ B cho tài khoản 4,5,6", "8h hằng ngày chạy A,B,C cho tài khoản 6,7,8" -
đều là 3 lịch riêng biệt, mỗi lịch có danh sách Hoạt Động + danh sách Tài
Khoản + kiểu lặp riêng.

### Đã làm (đợt 3)

- `scheduler.py` (MỚI): lưu/đọc `schedules.json` (danh sách lịch), mỗi lịch
  gồm `loai` ("daily" giờ cố định `gio` hh:mm, hoặc "interval" lặp mỗi
  `interval_hours` giờ), `hoat_dong_ids` (list id Hoạt Động), `tai_khoan_ids`
  (list id Tài Khoản), `bat` (bật/tắt lịch). `is_due(entry, now)` tính đã
  đến giờ chưa; `mark_triggered()` ghi lại NGAY KHI quyết định trigger
  (không chờ chạy xong) để tránh bị kích hoạt lặp lại nhiều lần trong lúc
  1 lượt chạy còn đang dở (có thể mất vài phút - vài chục phút).
- `dashboard.py`:
  - Nút "⏰ Hẹn Giờ" mở dialog `_open_schedule_manager()`: mỗi dòng = 1
    lịch, sửa tên/loại/giờ/số giờ trực tiếp, bấm "🎯 HĐ (n)" / "👤 TK (n)"
    mở popup checkbox multi-select (`_open_multi_select_dialog`) để chọn
    Hoạt Động / Tài khoản áp dụng, bấm 💾 lưu từng dòng, 🗑 xoá, "➕ Thêm
    Lịch Mới" thêm dòng trống.
  - `self.root.after(20000, self._check_schedules)` (đặt trong `__init__`,
    tự lặp lại) - mỗi 20s kiểm tra `scheduler.is_due()` cho từng lịch, nếu
    đến giờ thì `mark_triggered()` + lưu file NGAY rồi mới `_trigger_schedule()`.
  - `_trigger_schedule()`: nhóm các Tài khoản của lịch theo `emulator_index`
    được gán (xem account_manager.py) - mỗi giả lập 1 luồng riêng
    (`_worker_run_schedule`), y hệt cơ chế đa luồng của nút CHẠY thủ công.
    Bỏ qua (log warn) nếu giả lập đó ĐANG BẬN.
  - `_worker_run_schedule()`: `ensure_running()` (tự bật giả lập nếu tắt,
    tái dùng từ đợt 1) -> với từng tài khoản: Đăng Xuất (nếu có
    `account_logout`) -> Đăng Nhập (`account_login`, bơm `{tk_user}`/
    `{tk_pass}`) -> chạy đúng các Hoạt Động đã hẹn của lịch này (dùng lại
    `_exec_entry()` có sẵn, `tracked=False` vì không phải tick trong danh
    sách tác vụ chính) - logic giống hệt `_worker_run_emulator_with_accounts`
    nhưng scope theo TỪNG LỊCH thay vì "mọi tài khoản gán cho giả lập".
  - **Chống xung đột thủ công/lịch trên CÙNG 1 giả lập**: thêm
    `self._busy_emulator_indexes` (set index đang bận) - CHẠY THỦ CÔNG
    (`_start_run`/`_start_run_with_accounts`) giờ cũng đánh dấu bận/gỡ bận
    qua `_filter_busy_emulators()` (bỏ qua + log warn nếu giả lập đã bận do
    1 lịch đang chạy) và `_on_emulator_thread_done(emulator_index)`.
  - **Nút DỪNG / Tạm Dừng dùng chung cho cả lịch tự động**: thêm
    `_any_active_work()` (đang chạy tay HOẶC có lịch đang chạy nền) +
    `_refresh_run_control_buttons()` để bật/tắt 2 nút này đúng lúc kể cả
    khi việc đang chạy là do lịch tự kích hoạt (người dùng không bấm CHẠY).
    **Sửa 1 lỗi tiềm ẩn**: trước đây `stop_flag` chỉ được reset về False ở
    đầu `_start_run`/`_start_run_with_accounts` - nếu người dùng bấm DỪNG
    trong lúc CHỈ có lịch hẹn giờ đang chạy (không bấm CHẠY tay lần nào),
    `stop_flag` sẽ bị kẹt ở True mãi mãi và MỌI lịch sau đó sẽ tự thoát
    ngay lập tức mà không chạy gì (im lặng, khó phát hiện). Đã sửa:
    `_refresh_run_control_buttons()` tự reset `stop_flag`/`pause_flag` về
    False ngay khi không còn việc gì đang chạy (`_any_active_work()` ==
    False) - đảm bảo lượt lịch tiếp theo luôn bắt đầu "sạch".
  - Trạng thái (`_update_status_label`) hiển thị thêm số lịch đang chạy
    nền. HELP_TEXT thêm mục 7 hướng dẫn Hẹn Giờ.
- Đã kiểm tra cú pháp (`py_compile`) trên `dashboard.py` + `scheduler.py` -
  không lỗi. CHƯA test thật trên Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Đặt 1 lịch "Mỗi N giờ" nhỏ (vd 0.05 giờ ~ 3 phút) để xem có tự trigger
  đúng hạn không, và log ra đúng như mô tả.
- Đặt 2 lịch có tài khoản CÙNG gán 1 giả lập nhưng khác giờ chạy gần nhau,
  kiểm tra 1 lịch có bị bỏ qua đúng (do giả lập bận) và có log rõ ràng.
- Bấm DỪNG trong lúc 1 lịch đang chạy (không có phiên chạy tay nào), sau
  đó chờ lịch tiếp theo (hoặc lịch khác) tự trigger - xác nhận KHÔNG bị
  kẹt (đây là lỗi tiềm ẩn đã fix ở bản này, cần xác nhận lại trên máy
  thật vì môi trường code hiện tại không mô phỏng được đa luồng thật với
  Tkinter mainloop).
- Đóng/mở lại Dashboard giữa chừng: lịch "Hằng ngày" đã lỡ giờ trong lúc
  tắt app sẽ tự chạy ngay khi mở lại (vì `is_due()` chỉ so `lan_chay_ngay
  != hôm nay`, không quan tâm đã trễ bao lâu) - xác nhận đây là hành vi
  mong muốn (chạy bù) chứ không phải bug.

---



Theo yêu cầu người dùng:
1. Thêm nút "⏸ Tạm Dừng" khi đang chạy (bên cạnh nút DỪNG).
2. Dashboard trước đây chỉ quét được giả lập ĐANG CHẠY (dùng
   emu_manager.refresh()) - không nhận diện được giả lập đã tắt. Cần: (a)
   nút tự chọn đường dẫn ldconsole.exe thủ công, (b) quét đầy đủ danh sách
   giả lập kể cả đang tắt, (c) nút khởi động/tắt các giả lập đang được tick
   chọn.

### Đã làm (đợt 2)

- `dashboard.py`:
  - Thêm `self.pause_flag`, nút `self.btn_pause` ("⏸ Tạm Dừng" / "▶ Tiếp
    Tục") cạnh nút DỪNG, chỉ bật khi `is_running`.
  - `toggle_pause()` bật/tắt `pause_flag`. `_make_stop_checker()` trả về 1
    hàm `stop_checker` RIÊNG cho mỗi luồng giả lập: hàm này BUSY-WAIT (sleep
    0.15s) khi `pause_flag` đang bật (vẫn thoát ngay nếu `stop_flag` bật, để
    nút DỪNG luôn hoạt động kể cả đang tạm dừng), rồi trả về `stop_flag` như
    cũ. Tận dụng LUÔN các điểm gọi `stop_checker()` có sẵn trong
    `logic_engine.py` (giữa mỗi bước, trong vòng lặp chờ ảnh...) làm điểm
    tạm dừng -> **KHÔNG cần sửa gì trong `logic_engine.py`**, không đổi
    hành vi cũ khi không tạm dừng.
  - `_start_run()` / `_start_run_with_accounts()` reset `pause_flag=False`,
    bật nút Tạm Dừng; `stop_run()` và `_on_finish_all()` reset lại
    `pause_flag`/text nút.
  - `refresh_emulators()` đổi từ `emu_manager.refresh()` (chỉ thấy giả lập
    ĐANG CHẠY) sang `emu_manager.list_configured()` (thấy TẤT CẢ giả lập đã
    tạo trong LDPlayer, kể cả đang tắt - hàm này đã có sẵn từ đợt 1, dùng
    cho "Quản Lý Tài Khoản"). Giả lập đang tắt hiển thị mờ + nhãn "(đang
    tắt)", KHÔNG tự tick khi bấm "Tất cả giả lập" (tránh chạy nhầm ngay khi
    chưa bật) nhưng vẫn tick tay được để dùng với nút Bật Đã Chọn.
  - Thêm nút "📁 Chọn ldconsole.exe" (`choose_ldconsole_path`): mở hộp
    thoại chọn file, gán thẳng `self.emu_manager.ldconsole_path`, lưu vào
    `dashboard_settings.json` (key `ldconsole_path`) để không phải chọn lại
    mỗi lần mở app - áp dụng lại ở `__init__`.
  - Thêm nút "🟢 Bật Đã Chọn" / "🔴 Tắt Đã Chọn" (`launch_selected_emulators`
    / `quit_selected_emulators`): chạy trên thread nền, gọi
    `emu_manager.launch(index)` / `quit_emulator(index)` (đã có sẵn từ đợt
    1) cho từng giả lập ĐANG ĐƯỢC TICK, log kết quả, rồi tự `refresh_emulators()`
    lại sau 1.5s (giả lập vừa bật cần thêm 30-60s mới thấy "đang chạy" -
    người dùng cần tự bấm Quét Giả Lập lại sau khi Android boot xong, có
    ghi rõ trong log).
  - `emulator_manager.py`: KHÔNG cần sửa - `list_configured()`, `launch()`,
    `quit_emulator()`, thuộc tính public `ldconsole_path` đã có sẵn từ đợt
    1, chỉ cần gọi/gán từ dashboard.py.
- Đã kiểm tra cú pháp (`py_compile`) trên `dashboard.py` - không lỗi. CHƯA
  test thật trên Windows/LDPlayer (môi trường code hiện tại không có
  Windows/LDPlayer).

### Cần người dùng tự kiểm tra trên máy thật

- Tạm dừng/tiếp tục giữa 1 bước wait_image / swipe thật.
- Chọn tay đường dẫn ldconsole.exe khi máy không có sẵn giả lập nào đang
  bật (test trường hợp tự dò thất bại).
- Bật/Tắt giả lập qua nút mới, đối chiếu với `ldconsole.exe list2` xem
  index có đúng không sau khi bật lại.

---

## Current Task (đợt 1)

Thêm tính năng: tự nhận diện giả lập bật/tắt (tự khởi động nếu tắt) +
xoay vòng nhiều tài khoản trên cùng 1 giả lập (đăng xuất - đổi - đăng
nhập), theo yêu cầu người dùng ngày 2026-09-13.

## Completed

- Git repository initialized.
- `emulator_manager.py`: thêm `EmulatorInfo.running`, `list_configured()`
  (liệt kê TẤT CẢ giả lập kể cả đang tắt), `find_by_index()`, `launch()`,
  `quit_emulator()`, `reboot()`, `_boot_completed()`, `wait_until_ready()`,
  `ensure_running()` (tự kiểm tra bật/tắt, tự khởi động nếu tắt, chờ tới
  khi Android boot xong mới coi là sẵn sàng). Không đổi hành vi cũ của
  `refresh()`.
- `account_manager.py` (MỚI): quản lý `accounts.json` - danh sách tài
  khoản (username/password/ghi_chú), gán theo `emulator_index`, bật/tắt,
  `accounts_for_emulator()` để lấy hàng chờ xoay vòng của 1 giả lập.
- `dashboard.py`:
  - Nút "👥 Quản Lý Tài Khoản" (thêm/sửa/xoá tài khoản, gán giả lập, lưu
    vào accounts.json).
  - Tick "Xoay Vòng Tài Khoản" cạnh "Tự Login".
  - Khi bật tick này và bấm CHẠY: mỗi giả lập chạy trên 1 luồng riêng như
    cũ, nhưng qua `_worker_run_emulator_with_accounts()`: tự
    `ensure_running()` giả lập, rồi lặp qua từng tài khoản đã gán (đang
    bật): chạy Hoạt Động id `account_logout` (nếu có) -> `account_login`
    (bơm biến `{tk_user}`/`{tk_pass}`) -> các tác vụ đã tick -> tài khoản
    kế tiếp. Không có tài khoản nào gán cho giả lập -> fallback chạy 1 lần
    bình thường (không vỡ luồng chạy cũ).
  - Cập nhật HELP_TEXT (mục 6) hướng dẫn quy ước 2 Hoạt Động bắt buộc
    `account_login` / `account_logout`.
- Đã kiểm tra cú pháp (`py_compile`) và `pyflakes` trên cả 3 file - không
  lỗi. CHƯA kiểm thử thật trên Windows/LDPlayer thật (môi trường code hiện
  tại không có Windows/LDPlayer) - cần người dùng tự test lại trên máy
  thật, đặc biệt bước `ldconsole launch` + thời gian chờ boot.

## In Progress

- Chờ người dùng tự soạn 2 kịch bản `tasks/account_login.json` và
  `tasks/account_logout.json` (dùng {tk_user}/{tk_pass}) rồi test thực tế
  trên LDPlayer.

## Problems

- Chưa xác nhận được thời gian LDPlayer thật sự cần để khởi động xong
  (mặc định timeout 120s trong `ensure_running`) - có thể cần chỉnh tuỳ
  cấu hình máy.

## Next Steps

- Test `ldconsole launch/quit/reboot` thật trên máy Windows của người
  dùng, tinh chỉnh timeout nếu cần.
- Soạn `tasks/account_login.json` / `tasks/account_logout.json` mẫu.
- Cân nhắc thêm: chạy song song NHIỀU tài khoản trên NHIỀU giả lập khác
  nhau đã hoạt động sẵn (đã có qua chạy đa luồng theo giả lập) - nếu người
  dùng cần mở rộng thêm, có thể thêm bảng "gán nhóm giả lập" cho xoay vòng
  hàng loạt.
## 2026-10-08 - pig_bot: ghép lại bản sửa ổn định lên main mới (pig_stable_fix_v2.patch)
- Repo main bị force-push (5aeb391) nên pig_stable_fix.patch cũ không apply được; đã ghép lại, chỉ sửa pig_bot.py.
- Giữ nguyên phần của main (drop_mode tap, y0 thả theo độ cao thật, _dark_body, calibrate cắt đuôi, reset_params).
- Thêm: find_popups/_in_popup lọc băng điểm khỏi detect_pigs, chờ bàn cờ yên (_wait_stable), phạt heo nhỏ chen giữa 2 heo to (_block_wedge_penalty, w_block/w_wedge), think_min.
- CHƯA test trên LDPlayer thật.
- Sửa lỗi 'The truth value of an array ... is ambiguous' (v3): 2 chỗ `_wait_stable(...) or frame` trong run_auto_pig_step dùng `or` với mảng ảnh numpy -> đổi sang kiểm tra `is not None`. Patch dùng: pig_stable_fix_v3.patch (thay v2).

## 2026-10-08 - pig_bot: L1 thả thẳng, bớt lăn xa (pig_l1_direct.patch)
- Lỗi: L1 thả lên vai heo to rồi lăn xa tới L1 khác; mô phỏng thấy nhiều x cho cùng kết quả (hoà điểm) nên chọn x tuỳ ý -> L1 rải rác, dễ kẹt.
- simulate(..., info=) trả quãng lăn ngang của con vừa thả (info['travel']); choose_drop trừ w_travel x quãng lăn (EvalParams.w_travel=260, con cấp<=2 nặng hơn x1.5) và thưởng thêm khi con nhỏ thả thẳng chạm gộp ngay (travel<3% W).
- Sửa nhỏ: mô phỏng kiểm tra độ bền ±1.2% trước đây thiếu độ cao thả y0, nay đã truyền y0_for(r).
- Chỉnh bằng w_travel trong bước (0 = tắt). CHƯA test trên LDPlayer thật.

## 2026-10-08 - pig_bot: công cụ so sánh dự đoán vs thật (pig_cmp_tools.patch)
- Mục đích: tìm nguyên nhân chạy thật kém hơn mô phỏng: do ĐỌC (đọc sớm/nhầm), do THẢ lệch x, hay mô phỏng LĂN/NẢY khác thật.
- pig_bot.py: mỗi lượt lưu thêm debug_pig/pig_NNNN_cmp.png = ảnh THẬT sau khi heo nằm yên + vòng xanh (thật) + vòng tím (dự đoán) + nhãn số px lệch từng con + vạch cam (x đã thả). Dọn ảnh cũ tách riêng 2 nhóm (shots_keep mỗi nhóm).
- pig_report.py (file mới): `python pig_report.py debug_pig [--fit]` đọc pig_log.jsonl, in từng lượt: sai số, con lệch nhiều nhất, phân loại tốt/LĂN/ĐỌC, lệch ngang TB của con vừa thả; --fit chạy calibrate offline và ghi pig_params_fit.json.
- Trên log cũ (18 lượt): khi đọc sạch thì dự đoán khớp (sai số 0.003-0.04); lượt hỏng chủ yếu là lỗi ĐỌC. CHƯA có log chạy thật mới để kết luận.
- Lưu ý: pig_l1_direct.patch (w_travel) chưa áp được lên main hiện tại, chưa đưa vào.
