# -*- coding: utf-8 -*-
"""
Bot auto "Thế Giới Động Vật" (game DI CƯ ĐỘNG VẬT kiểu Neko Sliding) - điều khiển qua ADB, dùng cho bước `auto_animal`.

>>> TRẠNG THÁI (bản 3, 17/10): đã chạy THẬT trên LDPlayer 1 phiên (log `debug_animal/`: 14 cặp "dự đoán vs bàn thật" + score_log) và sửa theo đó:
>>> (a) TRÂU không biến mất khi hàng đầy mà CO 1 ô, 0 điểm; (b) điểm tính theo THANH + Buff nhiều hàng; (c) bàn chưa ĐỨNG YÊN khi có hàng kín
>>> (game tự ăn hàng mới sinh ra đầy sau ~1-2s -> bản cũ đọc sớm rồi kéo sai chỗ); (d) thêm KỸ NĂNG; (e) đọc năng lượng/đếm ngược trâu.
>>> Cái còn ĐOÁN: chi tiết kỹ năng Đà điểu/Sư tử. (Đã biết 17/10: Gấu đóng băng 3 hiệp - 18/10: số hiệp không cố định, đọc từ bong bóng; kỹ năng không tốn hiệp, trâu không làm gì ngoài việc dài/hiện thêm.)
>>> BẢN 6.1 (chỉnh thông số theo người dùng): `Weights.bull_cell` 6 -> 50; THÊM `Weights.shrink` = 60 (thưởng điểm MỖI Ô TRÂU rút được trong 1 nước, nhân `points`, CHỈ khi tìm nước - không tính vào điểm dự đoán/log);
>>>     `skill_kinds` mặc định "KYPB" -> "K" (chỉ Gấu); `bear_bull_cells` vẫn TẮT (đã bỏ từ bản 6, luôn 0).
>>> BẢN 6 (18/10, người dùng chốt): (a) BỎ Gấu chủ động khi >= 8 ô trâu (`bear_bull_cells` không còn tác dụng): kỹ năng CHỈ dùng khi KẸT hết nước hoặc nước sau CHẾT;
>>>     (b) ƯU TIÊN GẤU trước, không có Gấu / Gấu không cứu được mới dùng kỹ năng khác; mặc định `skill_kinds` = "KYPB" (Gấu, Sư tử, Hươu, Voi - BẬT Hươu + Voi);
>>>     (c) kỹ năng áp lên CẢ LOÀI (ảnh 3->4: 7 sư tử cùng đổi), mô phỏng `skill_apply_kind`; (d) SƯ TỬ theo luật mới `_lion_extend` (khớp 100% ảnh 3->4);
>>>     (e) Gấu đóng băng số hiệp KHÔNG cố định (3, 4...): bot đọc bong bóng "Ra đông sau khi di chuyển N lần" (`read_freeze_count`), mặc định 3 nếu không đọc được.
>>> BẢN 5 (17/10 tối): sửa TREO "bàn đổi trong lúc tính" (đà điểu nhận chập chờn O<->U nên 2 lần đọc không bao giờ khớp): `classify_cell` nhận đà điểu khi còn ít pixel tối,
>>>     so bàn bằng chữ ký LỎNG (`_loose`, bỏ loài), quá `change_limit` lần liền thì bỏ qua recheck; bot dừng thì TỰ THOÁT + LƯU TIẾN ĐỘ (`_exit_save`, `exit_on_stop`);
>>>     hộp thoại thoát bất ngờ (`is_exit_dialog`) chỉ đóng bằng dấu X, không bấm "Kết thúc ván này".
>>> BẢN 4 (17/10, mục tiêu SỐNG SÓT 400 HIỆP): (a) bấm kỹ năng xong game hiện hộp thoại "Gợi ý - Có muốn kích hoạt <loài> X1 không" [Hủy | Xác nhận]:
>>>     bot nhận hộp thoại (`find_skill_confirm`: cặp nút xanh lá + đỏ cùng hàng), BẤM XÁC NHẬN rồi ĐỢI HOẠT ẢNH (`skill_anim_wait` + chờ bàn yên);
>>>     không thấy hộp thoại thì thoát chế độ "Chọn 1 loại động vật" (nút Hủy dưới đáy) và tính 1 lần lỗi; hộp thoại lạ hiện ra bất ngờ thì bấm Hủy.
>>> (b) CHỈ DÙNG KỸ NĂNG KHI KẸT HOẶC CHẮC CHẮN THUA Ở LƯỢT SAU (người dùng chốt 17/10): `choose_skill` chỉ xét khi (1) KHÔNG còn nước đi nào, hoặc
>>>     (2) MỌI nước đi đều làm hàng mới trồi lên chạm thú ở hàng 0 (thua ngay hiệp kế). Rồi chọn (thanh, kỹ năng) có giá trị SAU kỹ năng cao nhất;
>>>     không có kỹ năng nào cứu được thì không dùng. Kỹ năng KHÔNG tốn hiệp (không đẩy hàng mới). Các field `skill_danger_row`/`bull_soon`/`skill_cooldown`/
>>>     `skill_gain`/`freeze_danger` còn nhận để tương thích nhưng KHÔNG còn tác dụng.
>>> (e) BẢN 5 (17/10 tối, "ưu tiên chỉ dùng kỹ năng vào con gấu"): `skill_kinds` mặc định "K" (thứ tự trong chuỗi = ưu tiên); thêm `bear_bull_cells` = 8: Gấu còn được dùng CHỦ ĐỘNG khi bàn có >= 8 ô trâu thừa
>>>     (trâu là thứ làm đầy bàn ở hiệp 300+). Mô phỏng 100 ván (animal_sim, độ sâu 1, trâu thêm mỗi 4 hiệp, giá kỹ năng 3000): không kỹ năng 242 hiệp (28/100 đủ 400) ->
>>>     chỉ Gấu khi kẹt/thua 283 (44/100) -> + trâu >= 8 ô 322 (70/100); ngưỡng 4/6/12 cho 276/298/309; kịch bản trâu 20 hiệp/lần: 264 -> 314 -> 322; độ sâu 2: 14/16 -> 15/16 -> 16/16.
>>> (c) GẤU BẮC CỰC (người dùng xác nhận): đóng băng đúng 3 HIỆP (`FREEZE_TURNS`) + RÚT MỌI TRÂU CÒN 1 Ô (`skill_apply` 'K'); trâu 1 ô bị ăn = 200 điểm.
>>>     `Weights.bull_cell` phạt mỗi ô trâu nên beam thường cũng ưa nước làm trâu co lại.
>>> (d) TRÂU KHÔNG "TẤN CÔNG" làm gì cả: nó chỉ DÀI, mất nhiều hàng đầy mới tiêu diệt (mỗi hàng đầy co 1 ô), và cứ 1 thời gian lại hiện thêm 1 con -> nhanh làm đầy bàn.

======================================================================================================
1) LUẬT GAME (ảnh Giới thiệu + 2 ảnh luyện tập + log thật 17/10)
======================================================================================================
- Bàn 9 CỘT x 11 HÀNG. Mỗi con vật là 1 THANH NGANG dài 1..5 ô (đầu thú bên TRÁI). Chỉ KÉO NGANG trong hàng của nó.
- Mỗi lần kéo xong = 1 HIỆP. Cứ qua 1 hiệp, 1 HÀNG thú mới trồi lên Ở ĐÁY bàn, ĐẨY cả bàn lên 1 hàng. Hình dạng hàng sắp tới hiện ở DẢI VÀNG
  MỎNG dưới đáy bàn (chưa biết loài). Dải này CHỈ HIỆN khi bàn đã yên; đang hoạt ảnh (hoặc đang đóng băng) thì trống.
- Thanh không có gì đỡ bên dưới thì RƠI (cả thanh cứng). Hàng nào ĐẦY 9 ô thì bị ăn, phần phía trên rơi xuống, có thể ăn dây chuyền.
- Hàng MỚI sinh ra có thể đã ĐẦY (log: "OPPOOPPPP"): game KHÔNG ăn ngay mà chờ ~1-2s rồi tự ăn (kèm rơi) => đừng đọc/kéo lúc đó (`_read_stable`).
- Bàn dọn sạch -> thêm 2 hàng mới. Có thú ở HÀNG TRÊN CÙNG (hàng 0) mà hàng mới vẫn xuất hiện -> KẾT THÚC đợt di cư (thua).
- ĐIỂM (đối chiếu ảnh 17/10: số bay "36 12 12 48" + "30 20 10 10 20" kèm chữ "2 Liên +20%"): mỗi THANH bị ăn = 10 điểm x SỐ Ô (đà điểu/hươu nhỏ 10, ngựa vằn/hươu 2 ô 20,
  voi/sư tử 30, gấu 40); trâu co về 1 ô rồi bị ăn = 200. Buff liên hoàn chỉ nhân cho HÀNG THỨ K bị ăn trong hiệp (hàng dưới thứ 1 x1.0, hàng trên thứ 2 x1.2,
  thứ 3 x1.5, thứ 4 x2.0 - từ 5 ĐOÁN +50%/hàng): ảnh cho hàng dưới giữ nguyên (30+20+10+10+20 = 90), hàng trên x1.2 (36+12+12+48 = 108).
  Số điểm = năng lượng - 1000 (ván luyện tập bắt đầu với 1000 năng lượng). LƯU Ý: chữ điểm trên màn ĐẾM LÊN CHẬM nên bot đọc năng lượng làm chuẩn.
- TRÂU RỪNG ('R'): dài tối đa 5. Khi hàng của nó đầy: nó KHÔNG bị ăn mà CO 1 ô (mất ô bên PHẢI, đầu trái giữ nguyên), đứng nguyên chỗ
  (phần trên rơi đè lên nó), 0 điểm; dài 1 mà bị ăn nữa thì mất và được 200 điểm. Khung góc phải trên "Hiệp N / Trâu Rừng sẽ tấn công sau M hiệp":
  M về 0 thì hiện THÊM trâu rồi đếm lại 20 (log: hiệp 13 còn 7 -> hiệp 20 hiện "sau 20 hiệp"). Trâu KHÔNG làm gì khác (người dùng 17/10): chỉ dài và
  mất nhiều hàng đầy để tiêu diệt nên làm đầy bàn rất nhanh (ván thật đã tới hiệp 418, điểm 65946). Bot vẫn đọc M mỗi hiệp để ghi log.
- KỸ NĂNG: thanh năng lượng "1640/1000" (tối đa 2 ống). Đủ 1000 thì bấm CON SƯ TỬ VÀNG cạnh thanh (toạ độ tham chiếu ~(97,345)) rồi chạm vào
  1 khối của con muốn dùng, game hiện hộp thoại "Gợi ý" -> bấm XÁC NHẬN (nút xanh ~(511,710)) -> chờ hoạt ảnh; hiệu ứng theo loài (Đồ Giám): ngựa vằn = kéo dài lấp ô trống 2 bên; voi = rút thành voi con 1 ô; hươu = tách thành
  hươu nhỏ 1 ô; đà điểu = chạy về phía nhiều ô trống hơn, đẻ trứng dọc đường, dừng khi gặp vật cản; sư tử = kéo dài về phía nhiều thú liền kề
  hơn và nuốt chúng; gấu = đóng băng (không hàng mới trồi lên, trâu ngoan). Mô phỏng ở `skill_apply` (ĐOÁN chi tiết Đà điểu/Sư tử).

======================================================================================================
2) HÌNH HỌC (đo trên ảnh 720x1280, vạch lưới tìm bằng profile ảnh)
======================================================================================================
- Vạch dọc x = 61, 128, 194, 260, 326, 393, 459, 525, 591, 658 (ô rộng ~66.3). Vạch ngang y = 436 ... 1164 (11 hàng, ô cao ~66.2).
- Dải xem trước hàng mới ở y ~ 1171-1186 (đoạn vàng (231,219,90)); các đoạn liền nhau cách nhau 2-3px nên tách được từng thanh.
- Bot co giãn theo bề rộng ảnh và NEO ĐÁY (giả định bố cục tựa đáy). `board_visible()` kiểm khung vàng 2 bên bàn.
- Nút kỹ năng `SKILL_BTN` (97,345), khung chữ năng lượng `ENERGY_BOX`, khung đếm ngược trâu `COUNT_BOX` (chỉ giữ chữ ĐỎ), khung điểm `SCORE_BOX`.

======================================================================================================
3) NHẬN DIỆN (`read_grid`)
======================================================================================================
- Mỗi ô: tỉ lệ điểm ảnh theo màu loài trên vùng giữa ô -> '.' trống | 'P' hươu (hồng) | 'R' trâu (đỏ) | 'Y' sư tử (vàng + bờm nâu)
  | 'B' voi (xanh) | 'W' ngựa vằn / 'K' gấu trắng (cùng nền trắng; có vằn đen ở thân = ngựa vằn) | 'O' đà điểu (nâu đen).
- TÁCH THANH: giữa 2 thanh khác nhau luôn có khe nền nâu nên các thanh cùng loài sát nhau vẫn tách đúng (`_gap_between`).
- OCR (pytesseract): `read_energy` (14/14 ảnh log đúng), `read_score` (15/15 sau khi chỉnh ngưỡng), `read_bull_count` (13/15, hay hụt khi nền có thú).

======================================================================================================
4) MÔ PHỎNG + TÌM NƯỚC
======================================================================================================
- `_settle_items`: rơi (từng thanh cứng, mặt nạ bit) + ăn hàng đầy (trâu co lại) + rơi tiếp + ăn dây chuyền.
- `step_state`: 1 hiệp = kéo 1 thanh -> settle -> (còn thú ở hàng 0 thì THUA) -> đẩy bàn lên 1 hàng + hàng mới theo dải xem trước (loài 'U').
  Dải xem trước TRỐNG = không đẩy (đóng băng / hoạt ảnh). Hàng mới sinh đầy thì tự ăn (tính điểm riêng).
- `beam_search`: chuỗi `depth` nước, giữ `beam` trạng thái tốt nhất mỗi tầng. Điểm = điểm THẬT x `Weights.points` (9.0 -> 1 hàng ~100đ ~ 900)
  + `evaluate` (độ đầy từng hàng, thanh vừa khít để lấp, phạt LỖ, phạt CHIỀU CAO - rất nặng khi chạm hàng 0). Nhánh THUA bị đẩy xuống cuối.
  Trọng số `Weights` là số TỰ ĐẶT (chỉnh bằng `animal_sim.py`), cần chỉnh lại khi có thêm log thật. `shrink` = thưởng mỗi ô trâu rút được (bản 6.1).
- `_choose_skill`: thử mọi (thanh, kỹ năng thuộc `skill_kinds`), giá trị = điểm ăn ngay + beam depth `skill_depth` SAU kỹ năng, trừ giá trị nước đi
  thường tốt nhất; dùng khi lợi >= `skill_gain`. Gấu chỉ khi có thanh ở hàng <= `freeze_danger`.
- Log để hiệu chỉnh: `debug_animal/score_log.jsonl` (mỗi hiệp: nước, điểm dự đoán `pred_pts`, `energy_now`, số hàng lệch, đếm ngược trâu),
  `skill_log.jsonl` (mỗi lần dùng kỹ năng: bàn trước / dự đoán / thật + năng lượng), `lech_*.png|txt`, `skill_truoc|sau_*.png`, `trau_*.png`.

======================================================================================================
5) FIELD CỦA BƯỚC `auto_animal` (đều tuỳ chọn)
======================================================================================================
  test (false)        - true = CHẾ ĐỘ TEST: chụp 1 lần, nhận diện, tính nước (+ báo sẽ dùng kỹ năng nào), lưu ảnh debug, KHÔNG bấm
  max_moves (0)       - số hiệp tối đa (0 = chạy tới khi thua / bị Dừng)
  max_seconds (0)     - giới hạn thời gian (0 = không giới hạn)
  depth (3) / beam (30) - độ sâu / độ rộng beam search (depth 2 nhanh hơn ~3 lần, hơi kém)
  depth_crowd (6) / crowd_row (4) - bàn ĐÔNG (thú cao tới hàng <= crowd_row) thì tìm sâu depth_crowd nước thay vì depth (0 = tắt); mô phỏng bull dày: depth 2 chết 1/5 ván, depth 3 sống hết
  settle_s (0.9)      - chờ tối thiểu sau mỗi nước (rồi còn chờ bàn đứng yên: `stable_*`)
  stable_tries (6) / stable_gap (0.35) - khoảng cách giữa 2 lần chụp khi chờ yên (stable_tries giữ cho tương thích, nay giới hạn bằng thời gian)
  stable_max (6.0)    - chờ yên tối đa (giây): đủ cho hàng kín tự ăn + rơi + hàng mới trồi
  preview_wait (1.6)  - chờ dải xem trước hiện tối đa (giây) rồi chấp nhận trống (đóng băng)
  recheck (true)      - chụp lại SAU khi tính; bàn đổi (hàng kín tự ăn...) thì tính lại thay vì kéo sai chỗ
  drag_ms (260)       - thời gian kéo
  verify (true)       - so bàn thật với bàn dự đoán sau mỗi nước, ghi cảnh báo + ảnh nếu lệch
  log_score (true)    - OCR điểm/năng lượng/đếm ngược trâu ghi `score_log.jsonl` (cần pytesseract)
  use_skill (true)    - tự dùng kỹ năng khi đủ năng lượng VÀ thật sự cần (cần đọc được năng lượng bằng OCR)
  (use_skill chỉ dùng khi KẸT hết nước hoặc CHẮC CHẮN THUA lượt sau; skill_danger_row / bull_soon / skill_cooldown nhận để tương thích, KHÔNG còn tác dụng)
  skill_confirm_wait (3.0) - chờ hộp thoại Xác nhận hiện tối đa (giây); skill_anim_wait (2.0) - chờ hoạt ảnh sau Xác nhận (rồi còn chờ bàn yên)
  target_moves (400)  - mục tiêu sống sót: chỉ ghi log khi đạt (không tự dừng; muốn dừng thì dùng max_moves)
  codex_points ({})   - "Điểm di cư" HIỆN TẠI trong Đồ Giám sau khi nâng cấp, vd {"sư tử": 72, "voi": 30} (cả thanh; khoá chữ cái O P W B Y K hoặc tên; thiếu = cấp 1)
  codex_next ({})     - "(Cấp sau +N)" hiện tại trong Đồ Giám, vd {"sư tử": 42}; chỉ dùng để ước lượng con nào đáng nâng trong bảng THỐNG KÊ cuối ván
  skill_kinds ("K") - loài được dùng kỹ năng: K gấu LUÔN ƯU TIÊN trước (nếu có trong chuỗi), các loài còn lại chọn cái có giá trị cao nhất: Y sư tử, P hươu, B voi (mặc định bật), W ngựa vằn, O đà điểu (tắt; O còn đoán)
  bear_bull_cells (0) - ĐÃ BỎ (18/10): giữ cho tương thích, không có tác dụng; kỹ năng chỉ dùng khi KẸT hoặc nước sau CHẾT
  skill_depth (2) / skill_cost (1000) - độ sâu so sánh sau kỹ năng, giá năng lượng (thanh có thể tới 10000); skill_gain / freeze_danger nhận để tương thích, không còn tác dụng
  skill_x / skill_y   - (tuỳ chọn) toạ độ tham chiếu 720x1280 của nút kỹ năng nếu lệch; skill_tap_gap (0.5) giây giữa 2 lần chạm, skill_wait (1.2)
  stuck_limit (6)     - số lần kéo liên tiếp mà bàn không đổi thì dừng (thanh bị khoá / kéo không ăn)
  stop_on_death (true) - HẾT nước đi, kỹ năng không cứu được và mọi nước đều thua ở hiệp kế -> bot DỪNG (không đi nước chết, lưu ảnh chet_chac_*.png) để bạn quyết định hồi sinh bằng kim cương; false = cứ đi nước tốt nhất như cũ
  exit_on_stop (true) - bot DỪNG (hết nước/chắc chắn chết/kéo mãi không ăn) thì tự bấm nút thoát góc dưới trái + XÁC NHẬN (nút xanh) để lưu tiến độ; false = chỉ dừng
  exit_on_max (false) - đủ `max_moves` hiệp thì cũng thoát bàn + lưu tiến độ (như exit_on_stop)
  change_limit (3)    - số lần liền log "bàn đổi trong lúc tính" thì thôi chờ, chấp nhận bản đọc ổn định (chống lặp vô hạn khi nhận diện chập chờn)
  lost_limit (4)      - số lần liên tiếp không thấy bàn (khung vàng) thì coi là hết ván
  debug (false)       - lưu ảnh debug_animal/ mỗi nước (test luôn lưu)

Chạy riêng để kiểm tra nhận diện + nước đi + kỹ năng trên 1 ảnh chụp màn hình:  python animal_bot.py anh.png

======================================================================================================
6) VIỆC CÒN LẠI / ĐANG ĐOÁN (cần log chạy thật)
======================================================================================================
 a. Rơi từng THANH cứng: khớp mọi cặp log. Kéo không xuyên qua thanh khác: chưa thấy trái.
 b. Buff nhiều hàng: đối chiếu `pred_pts` với mức tăng `energy_now` trong score_log (hiệp ăn 2+ hàng).
 c. (Đã rõ) Trâu không tấn công, chỉ hiện thêm khi đếm ngược về 0.
 d. Kỹ năng: có tốn 1 hiệp (đẩy hàng mới) không; Đà điểu đẻ trứng thế nào (trứng có ăn được/ điểm?); Sư tử nuốt tính điểm ra sao; thời gian
    đóng băng của Gấu. Xem `skill_log.jsonl` (cột before/pred/after).
 e. Màn thua / màn kết thúc: chưa có ảnh; bot dừng khi mất khung bàn `lost_limit` lần liên tiếp hoặc bàn không đổi `stuck_limit` lần.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# ----------------------------------------------------------------------------
# Hằng số hình học (đo trên ảnh 720x1280)
# ----------------------------------------------------------------------------
REF_W, REF_H = 720, 1280
COLS, ROWS = 9, 11
BOARD_X0 = 61.5                                # mép trái vùng ô
BOARD_X1 = 658.0                               # mép phải vùng ô
BOARD_Y1 = 1164.0                              # mép DƯỚI của hàng cuối (neo đáy)
PITCH_X = (BOARD_X1 - BOARD_X0) / COLS         # ~66.3
PITCH_Y = 66.2
BACK_BTN = (55.0, 1226.0)                      # nút mũi tên quay lại/thoát ở góc DƯỚI TRÁI (ảnh 720x1280, neo đáy)
EXIT_CLOSE = (634.0, 318.0)                    # dấu X đóng hộp thoại (ảnh 720x1280, tâm màn hình)
STRIP_Y = 1180.0                               # dải xem trước hàng mới
DEBUG_DIR = "debug_animal"
FULL = (1 << COLS) - 1

# ĐIỂM (đối chiếu ảnh 17/10 có số bay "36 12 12 48 / 30 20 10 10 20"): MỖI THANH bị ăn được 10 điểm x SỐ Ô của nó (hươu 1 ô = 10, hươu 2 ô = 20, voi/sư tử 3 ô = 30,
# gấu 4 ô = 40, đà điểu 1 ô = 10...); riêng TRÂU 1 ô bị ăn = 200 (trâu dài bị ăn chỉ co). Buff liên hoàn ("2 Liên +20%") chỉ nhân cho HÀNG THỨ K bị ăn trong hiệp
# (hàng thứ 1 nhân 1.0, thứ 2 nhân 1.2, thứ 3 nhân 1.5, thứ 4 nhân 2.0), KHÔNG nhân cả hai hàng: ảnh cho thấy hàng dưới giữ nguyên, hàng trên x1.2.
CELL_POINTS = 10
BULL_POINTS = 200
# Đồ Giám Động Vật (ảnh 17/10): "Điểm di cư" của CẢ THANH ở cấp hiện tại + "(Cấp sau +N)". Cấp 1: đà điểu 10 (+14), hươu 20 (+28), ngựa vằn 20 (+28), voi 30 (+42),
# sư tử 30 (+42), gấu 40 (+56): nghĩa là mọi loài cùng tăng theo cùng 1 tỉ lệ so với điểm gốc nên nâng con nào lợi hơn chỉ phụ thuộc số lần con đó bị ăn.
BASE_LEN = {"O": 1, "P": 2, "W": 2, "B": 3, "Y": 3, "K": 4}                       # độ dài chuẩn của từng loài (hươu nhỏ 1 ô do kỹ năng Tuần Lộc là ngoại lệ)
CODEX_POINTS = {"O": 10, "P": 20, "W": 20, "B": 30, "Y": 30, "K": 40}            # Điểm di cư hiện tại (mặc định cấp 1)
CODEX_NEXT = {"O": 14, "P": 28, "W": 28, "B": 42, "Y": 42, "K": 56}              # "(Cấp sau +N)" hiện tại
UNIT_POINTS = {k: CODEX_POINTS[k] / BASE_LEN[k] for k in BASE_LEN}                # điểm MỖI Ô theo loài (thanh dài ln ô = ln x đơn vị)


def _kind_key(name):
    """Chấp nhận khoá chữ cái ('Y') hoặc tên tiếng Việt ('sư tử', 'gấu', 'gấu bắc cực', 'tuần lộc'...)."""
    n = str(name).strip()
    if n.upper() in BASE_LEN:
        return n.upper()
    alias = {"đà điểu": "O", "hươu": "P", "tuần lộc": "P", "ngựa vằn": "W", "voi": "B", "sư tử": "Y", "gấu": "K", "gấu trắng": "K", "gấu bắc cực": "K"}
    return alias.get(n.lower())


def set_codex(points=None, nxt=None):
    """Đặt điểm theo Đồ Giám sau khi nâng cấp: `points` = {"sư tử": 72, ...} (Điểm di cư hiện tại CẢ THANH), `nxt` = {"sư tử": 42, ...} (Cấp sau +N).
    Loài không nêu giữ mặc định cấp 1. Gọi lại với None để về mặc định."""
    global CODEX_POINTS, CODEX_NEXT, UNIT_POINTS
    cp = {"O": 10, "P": 20, "W": 20, "B": 30, "Y": 30, "K": 40}
    cn = {"O": 14, "P": 28, "W": 28, "B": 42, "Y": 42, "K": 56}
    for src, dst in ((points, cp), (nxt, cn)):
        for k, v in (src or {}).items():
            kk = _kind_key(k)
            if kk:
                dst[kk] = float(v)
    CODEX_POINTS, CODEX_NEXT = cp, cn
    UNIT_POINTS = {k: CODEX_POINTS[k] / BASE_LEN[k] for k in BASE_LEN}
# Bảng dưới chỉ là điểm THAM KHẢO của từng loài ở độ dài chuẩn (không còn dùng để tính, xem `Rules.value`).
# Trâu (R): khi hàng của nó đầy thì nó KHÔNG biến mất mà CO 1 ô (0 điểm) (mất ô bên phải, đầu bên trái giữ nguyên) - xem `_settle_items`.
# 'E' = trứng đà điểu (kỹ năng, đoán 0 điểm), 'U' = chưa rõ loài (dải xem trước) -> cũng 10 điểm/ô theo độ dài đọc từ dải.
KIND_POINTS = {"O": 10, "P": 20, "W": 20, "B": 30, "Y": 30, "K": 40, "R": 200, "E": 0, "U": 20}
# R = 200: trâu chỉ BIẾN MẤT khi đã co về 1 ô rồi bị ăn (người dùng 17/10); lúc còn dài bị ăn thì chỉ co 1 ô và 0 điểm (xem `_settle_items`).
FREEZE_TURNS = 3                 # Gấu Bắc Cực đóng băng 3 lượt (người dùng xác nhận 17/10): 3 hiệp liền không có hàng mới trồi lên
# Buff ăn nhiều hàng trong 1 hiệp (người dùng nói): 2 hàng +20%, 3 hàng +50%, 4 hàng +100%; từ 5 hàng trở lên ĐOÁN thêm +50%/hàng.
COMBO_TABLE = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0}


def combo_mult(rows):
    if rows <= 0:
        return 1.0
    if rows in COMBO_TABLE:
        return COMBO_TABLE[rows]
    return COMBO_TABLE[4] + 0.5 * (rows - 4)


# Vị trí (toạ độ tham chiếu 720x1280) của nút KỸ NĂNG (con sư tử vàng cạnh thanh năng lượng) và khung chữ "1640/1000"
SKILL_BTN = (97.0, 345.0)
ENERGY_BOX = (290.0, 374.0, 420.0, 402.0)       # x0, y0, x1, y1
SCORE_BOX = (60.0, 128.0, 205.0, 178.0)
COUNT_BOX = (585.0, 172.0, 695.0, 212.0)        # chữ đỏ "sau N hiệp" của Trâu Rừng
FREEZE_BOX = (105.0, 165.0, 335.0, 245.0)      # bong bóng Gấu "Ra đông sau khi di chuyển N lần" (N chữ xanh lá), góc trái trên

# Bảng màu (RGB) lấy mẫu từ ảnh chụp - chỉ để vẽ debug / tài liệu
PROTO = {
    ".": (148, 101, 57),    # ô trống
    "R": (214, 101, 82),    # trâu
    "Y": (247, 182, 74),    # sư tử
    "B": (148, 190, 214),   # voi
    "W": (222, 219, 222),   # ngựa vằn
    "K": (222, 227, 231),   # gấu trắng
    "P": (247, 162, 140),   # hươu
    "O": (84, 60, 60),      # đà điểu
}
NAMES = {"R": "trâu", "Y": "sư tử", "B": "voi", "W": "ngựa vằn", "K": "gấu trắng", "P": "hươu", "O": "đà điểu", "U": "chưa rõ"}


@dataclass
class Geo:
    sx: float
    x0: float
    pitch_x: float
    y_bottom: float
    pitch_y: float

    def cx(self, c):
        return self.x0 + (c + 0.5) * self.pitch_x

    def cy(self, r):
        return self.y_bottom - (ROWS - r - 0.5) * self.pitch_y

    @property
    def strip_y(self):
        return self.y_bottom + (STRIP_Y - BOARD_Y1) * self.sx


def make_geo(frame) -> Geo:
    h, w = frame.shape[:2]
    s = w / REF_W
    return Geo(sx=s, x0=BOARD_X0 * s, pitch_x=PITCH_X * s, y_bottom=h - (REF_H - BOARD_Y1) * s, pitch_y=PITCH_Y * s)


# ----------------------------------------------------------------------------
# 1) Nhận diện
# ----------------------------------------------------------------------------
def _rgb(patch_bgr):
    return patch_bgr.reshape(-1, 3)[:, ::-1].astype(np.int32)


def _near(rgb, col, thr):
    d = rgb - np.array(col, np.int32)
    return (np.abs(d).sum(1) < thr)


def _bg_mask(rgb):
    # Nền nâu của bàn. Khi kỹ năng sẵn sàng viền bàn SÁNG LÊN cam và NHẤP NHÁY (ảnh 17/10 hiệp 307: ô trống cột 0 có R tới ~190, trước bị đọc thành 'trâu' và
    # đọc khác nhau giữa 2 lần chụp -> bot lặp mãi "bàn đổi trong lúc tính"), nên R cho tới 206; màu trâu thật (209,104,83) có B >= 80 nên vẫn khác (B nền <= 76).
    return (rgb[:, 0] >= 126) & (rgb[:, 0] <= 206) & (np.abs(rgb[:, 1] - 102) <= 16) & (np.abs(rgb[:, 2] - 60) <= 16)


def classify_cell(patch_bgr):
    """(nhãn ô, tỉ lệ nền nâu). Nhãn: '.', 'P', 'R', 'Y', 'B', 'W', 'O', 'U' (có thú nhưng chưa rõ loài). 'W' có thể là gấu (xử lý ở mức thanh)."""
    rgb = _rgb(patch_bgr)
    n = len(rgb)
    if n == 0:
        return ".", 1.0
    bg = _bg_mask(rgb)
    fbg = float(bg.mean())
    mx = rgb.max(1)
    mn = rgb.min(1)
    f_dark = float(((mx < 130) & ((mx - mn) < 45)).mean())
    # đà điểu khi viền bàn sáng lên bị cộng thêm màu cam nên sáng hơn (ảnh hiệp 307 cột 8: lúc 'O' lúc 'U'): nới ngưỡng tối nhưng vẫn loại màu nền/bờm sư tử
    f_dark = max(f_dark, float(((mx < 152) & ((mx - mn) < 62) & (rgb[:, 1] < 108)).mean()))
    f_red = float(_near(rgb, (209, 104, 83), 50).mean())
    f_pink = float(_near(rgb, (250, 158, 134), 60).mean())
    f_yel = float(_near(rgb, (250, 181, 80), 70).mean())
    f_blu = float(_near(rgb, (150, 185, 208), 60).mean())
    f_white = float(((mn > 200) & ((mx - mn) < 30)).mean())
    f_mane = float(((rgb[:, 0] >= 135) & (rgb[:, 0] <= 178) & (rgb[:, 1] >= 62) & (rgb[:, 1] <= 94) & (rgb[:, 2] >= 14) & (rgb[:, 2] <= 50)).mean())
    if fbg >= 0.9:
        return ".", fbg
    if f_white >= 0.35:
        return "W", fbg
    if f_blu >= 0.22:
        return "B", fbg
    if f_yel >= 0.18 or (f_mane >= 0.12 and f_yel >= 0.04):
        return "Y", fbg
    if f_pink >= 0.25:
        return "P", fbg
    if f_dark >= 0.30 and f_red < 0.10 and f_pink < 0.10:
        return "O", fbg
    if f_red >= 0.15:
        return "R", fbg
    if f_pink >= 0.10:
        return "P", fbg
    # Nền bàn có dải sáng lệch (vd cột 0 R~172, fbg thấp) -> ô trống bị đọc nhầm thành 'U' = thanh ma: hàng bị tính ĐẦY (bot chờ mãi, treo)
    # và bot kéo ô trống. Màu TRUNG VỊ gần màu nền (không có màu loài nào) => trống.
    med = np.median(rgb, axis=0)
    if abs(med[0] - 165) <= 26 and abs(med[1] - 103) <= 12 and abs(med[2] - 60) <= 14 and fbg >= 0.05:
        return ".", fbg
    # Đà điểu (khỉ nâu) lúc có hoạt ảnh: tỉ lệ pixel tối tụt còn 0.05-0.10 (ảnh log 17/10 ô cuối hàng đáy = 0.09) nên rơi xuống 'U' rồi quay lại 'O'
    # -> 2 lần đọc liền nhau KHÁC nhau mãi, bot lặp "bàn đổi trong lúc tính". Ô có thú + còn pixel tối + không đỏ/hồng = đà điểu.
    if f_dark >= 0.05 and f_red < 0.10 and fbg < 0.5:
        return "O", fbg
    return ("U" if fbg < 0.7 else "."), fbg


def _gap_between(frame, geo: Geo, r, c):
    """True nếu giữa ô (r,c) và (r,c+1) có KHE NỀN NÂU (= 2 thanh khác nhau). Khe không đối xứng quanh vạch lưới nên xét mọi cột
    ảnh trong ±6px: cùng 1 thanh thì không cột nào có nền, 2 thanh thì có cột >50% là nền."""
    xb = int(round(geo.x0 + (c + 1) * geo.pitch_x))
    cy = geo.cy(r)
    ys = np.arange(int(cy - 0.30 * geo.pitch_y), int(cy + 0.30 * geo.pitch_y), 2)
    h, w = frame.shape[:2]
    ys = np.clip(ys, 0, h - 1)
    for dx in range(-6, 7):
        x = min(max(xb + dx, 0), w - 1)
        rgb = frame[ys, x][:, ::-1].astype(np.int32)
        if float(_bg_mask(rgb).mean()) > 0.5:
            return True
    return False


def read_cells(frame, geo: Geo, with_seps=False):
    """-> list ROWS x COLS nhãn ô (và, nếu with_seps, mảng khe seps[r][c] = khe giữa ô c và c+1)."""
    hx, hy = int(geo.pitch_x * 0.36), int(geo.pitch_y * 0.36)
    h, w = frame.shape[:2]
    grid = []
    for r in range(ROWS):
        row = []
        y = int(geo.cy(r))
        for c in range(COLS):
            x = int(geo.cx(c))
            patch = frame[max(0, y - hy):min(h, y + hy), max(0, x - hx):min(w, x + hx)]
            row.append(classify_cell(patch)[0])
        grid.append(row)
    if not with_seps:
        return grid
    seps = [[(grid[r][c] != "." and grid[r][c + 1] != "." and (grid[r][c] != grid[r][c + 1] or _gap_between(frame, geo, r, c)))
             for c in range(COLS - 1)] for r in range(ROWS)]
    return grid, seps


@dataclass(frozen=True)
class Bar:
    row: int
    col: int
    length: int
    kind: str                       # 'P' 'R' 'Y' 'B' 'W' 'K' 'O' 'U'


def bars_from_cells(cells, seps=None):
    """Ghép ô liền nhau cùng loài thành thanh. Có `seps` thì cắt tại khe (tách thanh cùng loài sát nhau)."""
    bars = []
    for r in range(ROWS):
        c = 0
        while c < COLS:
            k = cells[r][c]
            if k == ".":
                c += 1
                continue
            e = c
            while e + 1 < COLS and cells[r][e + 1] == k and not (seps is not None and seps[r][e]):
                e += 1
            bars.append(Bar(r, c, e - c + 1, k))
            c = e + 1
    return bars


def _zebra_or_polar(frame, geo: Geo, b: Bar):
    """Thanh trắng: có vằn đen ở thân (ô sau đầu) = ngựa vằn 'W', không = gấu 'K'."""
    if b.length < 2:
        return "W"
    h, w = frame.shape[:2]
    y = geo.cy(b.row)
    x0 = int(geo.x0 + (b.col + 1) * geo.pitch_x + 0.12 * geo.pitch_x)
    x1 = int(geo.x0 + (b.col + b.length) * geo.pitch_x - 0.12 * geo.pitch_x)
    y0, y1 = int(y - 0.32 * geo.pitch_y), int(y + 0.32 * geo.pitch_y)
    rgb = _rgb(frame[max(0, y0):min(h, y1), max(0, x0):min(w, x1)])
    if len(rgb) == 0:
        return "W"
    frac = float((rgb.max(1) < 80).mean())
    return "W" if frac >= 0.03 else "K"


def read_grid(frame):
    geo = make_geo(frame)
    cells, seps = read_cells(frame, geo, with_seps=True)
    bars = bars_from_cells(cells, seps)
    out = []
    for b in bars:
        if b.kind == "W":
            k = _zebra_or_polar(frame, geo, b)
            if k != b.kind:
                b = Bar(b.row, b.col, b.length, k)
        out.append(b)
    # cập nhật lại cells cho khớp phân loại ngựa vằn/gấu
    cells = [["."] * COLS for _ in range(ROWS)]
    for b in out:
        for c in range(b.col, b.col + b.length):
            cells[b.row][c] = b.kind
    return geo, cells, out


def board_visible(frame, geo: Geo):
    """Khung vàng hai bên bàn còn thấy (dùng để biết còn đang ở màn chơi hay không)."""
    h, w = frame.shape[:2]
    y = int(geo.cy(ROWS // 2))
    ok = 0
    for x in (geo.x0 - 18 * geo.sx, geo.x0 + COLS * geo.pitch_x + 18 * geo.sx):
        xi = int(x)
        if 0 <= xi < w and 0 <= y < h:
            px = frame[y, xi][::-1].astype(np.int32)
            if np.abs(px - np.array([222, 182, 90])).sum() < 90:
                ok += 1
    return ok >= 1


def _pill_boxes(mask, s, min_w, max_w, min_h, max_h):
    """Các khối chữ nhật (nút bầu dục) trong mặt nạ nhị phân: [(x, y, w, h, cx, cy)] theo pixel ảnh; kích thước nhập theo ảnh 720 (nhân `s`)."""
    k = max(3, int(round(11 * s)))
    m = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))       # nối chữ trắng bên trong nút
    n, _lab, st, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = [int(v) for v in st[i]]
        if min_w * s <= w <= max_w * s and min_h * s <= h <= max_h * s and w >= 3.2 * h and a >= 0.55 * w * h:
            out.append((x, y, w, h, x + w / 2.0, y + h / 2.0))
    return out


def find_skill_confirm(frame):
    """Hộp thoại \"Gợi ý - Có muốn kích hoạt <loài> X1 không\" [Hủy đỏ | Xác nhận xanh lá] -> {\"ok\": (x, y), \"cancel\": (x, y)} (pixel ảnh) hoặc None.
    Nhận bằng CẶP nút: 1 nút xanh lá + 1 nút đỏ nằm CÙNG HÀNG (nút đỏ bên trái), kích thước ~200x48 (ảnh 720). Thanh trâu đỏ không lẫn vì thiếu nút xanh đi kèm."""
    h, w = frame.shape[:2]
    s = w / REF_W
    y0, y1 = int(h * 0.22), int(h * 0.82)
    hsv = cv2.cvtColor(frame[y0:y1], cv2.COLOR_BGR2HSV)
    hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    green = (((hh >= 55) & (hh <= 95) & (ss > 70) & (vv > 70)).astype(np.uint8)) * 255
    red = ((((hh < 12) | (hh > 170)) & (ss > 90) & (vv > 120)).astype(np.uint8)) * 255
    gb = _pill_boxes(green, s, 140, 260, 34, 62)
    rb = _pill_boxes(red, s, 140, 260, 34, 62)
    for g in gb:
        for r in rb:
            if abs(g[5] - r[5]) <= 12 * s and r[4] < g[4] - 150 * s:
                return {"ok": (g[4], g[5] + y0), "cancel": (r[4], r[5] + y0)}
    return None


def find_select_cancel(frame):
    """Nút \"Hủy\" xanh lá dưới đáy khi game đang ở chế độ \"Chọn 1 loại động vật trên sân để kích hoạt\" -> (x, y) hoặc None."""
    h, w = frame.shape[:2]
    s = w / REF_W
    y0 = int(h * 0.90)
    hsv = cv2.cvtColor(frame[y0:], cv2.COLOR_BGR2HSV)
    green = (((hsv[..., 0] >= 55) & (hsv[..., 0] <= 95) & (hsv[..., 1] > 60) & (hsv[..., 2] > 70)).astype(np.uint8)) * 255
    for b in _pill_boxes(green, s, 90, 170, 28, 60):
        if abs(b[4] - w / 2.0) <= 60 * s:
            return (b[4], b[5] + y0)
    return None


def read_preview(frame, geo: Geo):
    """Dải xem trước hàng mới ở đáy bàn -> [(cột, dài), ...] (các đoạn vàng; 2 thanh sát nhau cách nhau 2-3px nên tách được)."""
    h, w = frame.shape[:2]
    y = int(round(geo.strip_y))
    if not (0 <= y < h):
        return []
    row = frame[max(0, y - 1):min(h, y + 2), :, ::-1].astype(np.int32).mean(0)
    yel = (np.abs(row - np.array([231, 219, 90])).sum(1) < 90)
    out = []
    x = 0
    lo, hi = geo.x0 - 4, geo.x0 + COLS * geo.pitch_x + 4
    while x < w:
        if yel[x]:
            s = x
            while x < w and yel[x]:
                x += 1
            e = x
            if e > lo and s < hi:
                c0 = int(round((s - geo.x0) / geo.pitch_x))
                c1 = int(round((e - geo.x0) / geo.pitch_x))
                c0, c1 = max(c0, 0), min(c1, COLS)
                if c1 - c0 >= 1:
                    out.append((c0, c1 - c0))
        else:
            x += 1
    return out


def cells_text(cells):
    return "\n".join("".join(row) for row in cells)


def _yb(frame, y_ref):
    """Đổi y tham chiếu (720x1280) sang pixel, NEO ĐÁY (cho nút kỹ năng/thanh năng lượng nằm sát bàn)."""
    h, w = frame.shape[:2]
    sx = w / REF_W
    return h - (REF_H - y_ref) * sx


def _ocr_bin(img, cfg):
    import pytesseract
    return pytesseract.image_to_string(img, config=cfg).strip()


def read_score(frame, geo: Optional[Geo] = None):
    """Điểm ván (OCR). None nếu không đọc được / thiếu pytesseract. Ngưỡng 200 + phóng 3x (bản cũ hay đọc 550 thành 650/50).
    LƯU Ý: số điểm trên màn ĐẾM LÊN CHẬM sau khi ăn - đọc ngay sau nước đi sẽ ra số cũ; muốn chính xác dùng `read_energy` (năng lượng = điểm + 1000)."""
    try:
        h, w = frame.shape[:2]
        sx = w / REF_W
        x0, y0, x1, y1 = [int(v * sx) for v in SCORE_BOX]
        g = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, t = cv2.threshold(g, 200, 255, cv2.THRESH_BINARY)
        t = cv2.copyMakeBorder(255 - t, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
        s = _ocr_bin(t, "--psm 7 -c tessedit_char_whitelist=0123456789")
        return int(s) if s.isdigit() else None
    except Exception:
        return None


def read_energy(frame, geo: Optional[Geo] = None):
    """Thanh năng lượng \"1640/1000\" -> (hiện_có, mốc) hoặc None. Chữ TRẮNG khi đủ năng lượng; khi CHƯA đủ thì số hiện có chuyển ĐỎ
    (18/10: ảnh 4560/6000, 4180/10000, 4470/5000 - bản cũ chỉ lấy chữ trắng nên trả None đúng lúc cần biết có đủ để dùng kỹ năng không).
    Thử lần lượt: xám ngưỡng 200 (cách cũ, 14/14 ảnh chữ trắng) -> kênh R ngưỡng 170 -> kênh R ngưỡng 150 (chữ đỏ và trắng đều R cao, nền xanh/tối R thấp);
    bản nào ra đủ dạng \"số/mốc\" thì lấy ngay, hết cách mới dùng nhánh đoán cũ (chỉ đọc được mốc)."""
    try:
        h, w = frame.shape[:2]
        sx = w / REF_W
        x0, y0, x1, y1 = ENERGY_BOX
        c = frame[int(_yb(frame, y0)):int(_yb(frame, y1)), int(x0 * sx):int(x1 * sx)]
        chans = (("g", cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), 200), ("r", c[..., 2], 170), ("r", c[..., 2], 150))
        first = ""
        for i, (_n, ch, th) in enumerate(chans):
            g = cv2.resize(ch, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            _, t = cv2.threshold(g, th, 255, cv2.THRESH_BINARY)
            t = cv2.copyMakeBorder(255 - t, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
            s = _ocr_bin(t, "--psm 7 -c tessedit_char_whitelist=0123456789/")
            if i == 0:
                first = s
            m = re.match(r"^(\d{1,5})/(\d{3,5})$", s)
            if m:
                return int(m.group(1)), int(m.group(2))
        d = re.sub(r"\D", "", first)
        for need in ("10000", "5000", "4000", "3000", "2000", "1000"):
            if len(d) > len(need) and d.endswith(need):
                return int(d[:-len(need)]), int(need)
    except Exception:
        pass
    return None


def read_bull_count(frame, geo: Optional[Geo] = None):
    """Số \"sau N hiệp\" (chữ ĐỎ) trong khung Trâu Rừng ở góc phải trên -> N hoặc None (lọc theo màu đỏ để bỏ chữ nâu + hình nền)."""
    try:
        h, w = frame.shape[:2]
        sx = w / REF_W
        x0, y0, x1, y1 = [int(v * sx) for v in COUNT_BOX]
        hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        m = (((hsv[..., 0] < 12) | (hsv[..., 0] > 165)) & (hsv[..., 1] > 60) & (hsv[..., 2] > 90)).astype(np.uint8) * 255
        ys, xs = np.where(m > 0)
        if len(xs) < 12:
            return None
        m = m[max(0, ys.min() - 3):ys.max() + 4, max(0, xs.min() - 3):xs.max() + 4]
        m = cv2.resize(m, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        m = cv2.copyMakeBorder(255 - m, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
        s = _ocr_bin(m, "--psm 7 -c tessedit_char_whitelist=0123456789")
        s = s.split()[-1] if s.split() else ""
        return int(s) if s.isdigit() and 0 <= int(s) <= 99 else None
    except Exception:
        return None


def read_freeze_count(frame, geo: Optional[Geo] = None):
    """Gấu Bắc Cực: bong bóng thoại góc trái trên \"Ra đông sau khi di chuyển N lần\" (N chữ XANH LÁ, 3 hoặc 4... không cố định) -> N hoặc None
    (None = không có bong bóng = không đóng băng / không đọc được)."""
    try:
        h, w = frame.shape[:2]
        sx = w / REF_W
        x0, y0, x1, y1 = [int(v * sx) for v in FREEZE_BOX]
        hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        m = ((hsv[..., 0] >= 45) & (hsv[..., 0] <= 100) & (hsv[..., 1] > 60) & (hsv[..., 2] > 60)).astype(np.uint8) * 255
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        boxes = [st[i] for i in range(1, n) if st[i][4] >= 15 and 6 * sx <= st[i][3] <= 40 * sx]
        if not boxes:
            return None
        x, y, bw, bh, _a = max(boxes, key=lambda b: b[4])
        d = 255 - m[max(0, y - 3):y + bh + 3, max(0, x - 3):x + bw + 3]
        d = cv2.resize(d, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        d = cv2.copyMakeBorder(d, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
        s_ = _ocr_bin(d, "--psm 10 -c tessedit_char_whitelist=0123456789")
        return int(s_) if s_.isdigit() and 1 <= int(s_) <= 20 else None
    except Exception:
        return None


def _loose(bars):
    """Chữ ký bàn KHÔNG tính loài (hàng, cột, dài): nhận diện loài chập chờn (O/U...) không làm bot tưởng bàn đã đổi."""
    return tuple((b.row, b.col, b.length) for b in bars)


def _cells_diff(bars_a, bars_b, limit=8):
    """Mô tả các ô khác nhau giữa 2 lần đọc, vd '(10,8): O->U'."""
    ca, cb = _to_cells(bars_a), _to_cells(bars_b)
    out = []
    for r in range(ROWS):
        for c in range(COLS):
            if ca[r][c] != cb[r][c]:
                out.append(f"({r},{c}): {ca[r][c]}->{cb[r][c]}")
    more = f" ... (+{len(out) - limit})" if len(out) > limit else ""
    return ", ".join(out[:limit]) + more


def is_exit_dialog(frame):
    """Hộp thoại \"Thoát sẽ tự động lưu tiến trình, có muốn thoát trò chơi không\" [Kết thúc ván này (đỏ) | Xác nhận (xanh)] - cùng cặp nút với hộp thoại kỹ năng
    nên phân biệt bằng chữ (OCR tiếng Anh đọc ra 'Thoat se tu dong luu tien trinh')."""
    try:
        if find_skill_confirm(frame) is None:
            return False
        h, w = frame.shape[:2]
        crop = frame[int(h * 0.33):int(h * 0.43), int(w * 0.12):int(w * 0.88)]
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        txt = _ocr_bin(g, "--psm 6").lower()
        return ("thoat" in txt) or ("luu" in txt and "tien" in txt) or ("tro choi" in txt)
    except Exception:
        return False


def has_full_row(cells):
    """True nếu có hàng kín 9 ô: hàng đầy KHÔNG phải trạng thái đứng yên (game tự ăn nó sau ~1-2s) => bàn chưa ổn định."""
    return any(all(x != "." for x in row) for row in cells)


# ----------------------------------------------------------------------------
# 2) Mô phỏng (luật mục 1; chỗ đoán ở mục 6)
# ----------------------------------------------------------------------------
def _m(col, length):
    return ((1 << length) - 1) << col


def occupancy(bars):
    occ = {}
    for i, b in enumerate(bars):
        for c in range(b.col, b.col + b.length):
            occ[(b.row, c)] = i
    return occ


def _settle_items(items):
    """items: list [row, col, length, kind]. Rơi + ăn hàng tới khi ổn định.
    -> (items_mới_đã_sắp, số_hàng_ăn, [thanh_đã_ăn (row,col,len,kind,thứ_hạng_hàng)], số_đợt_ăn_dây_chuyền, [số hàng mỗi đợt]).
    TRÂU ('R', luật đo từ log thật 17/10): hàng của nó đầy thì nó KHÔNG bị ăn mà CO 1 ô (mất ô BÊN PHẢI, đầu trái giữ nguyên),
    vẫn đứng nguyên chỗ cũ (phần phía trên rơi xuống đè lên nó); dài 1 mà bị ăn nữa thì biến mất (0 điểm). Chỉ lần biến mất mới vào `removed`."""
    items = [list(t) for t in items]
    cleared = 0
    removed = []
    waves = []
    while True:
        items.sort(key=lambda t: -t[0])
        rm = [0] * ROWS
        for it in items:
            mk = _m(it[1], it[2])
            r = it[0]
            while r + 1 < ROWS and not (rm[r + 1] & mk):
                r += 1
            it[0] = r
            rm[r] |= mk
        full = [r for r in range(ROWS) if rm[r] == FULL]
        if not full:
            break
        fs = set(full)
        done = sum(waves)
        rank_of = {r: done + i + 1 for i, r in enumerate(sorted(full, reverse=True))}      # hàng DƯỚI được tính trước (thứ 1), hàng trên thứ 2...
        keep = []
        for it in items:
            if it[0] in fs:
                if it[3] == "R" and it[2] > 1:
                    it[2] -= 1
                    keep.append(it)
                else:
                    removed.append(tuple(it) + (rank_of[it[0]],))        # (row, col, len, kind, thứ_hạng_hàng_trong_hiệp)
            else:
                keep.append(it)
        items = keep
        cleared += len(full)
        waves.append(len(full))
    return items, cleared, removed, len(waves), waves


def settle(bars):
    """Rơi + ăn hàng tới khi ổn định. Trả (bars_mới, số_hàng_đã_ăn, số_thanh_biến_mất)."""
    items, cl, rem, _, _ = _settle_items([(b.row, b.col, b.length, b.kind) for b in bars])
    return [Bar(*t) for t in items], cl, len(rem)


def gen_moves(bars):
    """Mọi nước: (chỉ số thanh, cột mới). Trượt ngang qua các ô trống liên tiếp."""
    occ = occupancy(bars)
    out = []
    for i, b in enumerate(bars):
        c = b.col
        while c - 1 >= 0 and (b.row, c - 1) not in occ:
            c -= 1
            out.append((i, c))
        c = b.col
        while c + b.length < COLS and (b.row, c + b.length) not in occ:
            c += 1
            out.append((i, c))
    return out


def _gen_moves_items(items):
    rm = [0] * ROWS
    for t in items:
        rm[t[0]] |= _m(t[1], t[2])
    out = []
    for i, (r, c0, ln, _k) in enumerate(items):
        row = rm[r]
        c = c0
        while c - 1 >= 0 and not (row >> (c - 1)) & 1:
            c -= 1
            out.append((i, c))
        c = c0
        while c + ln < COLS and not (row >> (c + ln)) & 1:
            c += 1
            out.append((i, c))
    return out


def _push(items, preview):
    """Đẩy bàn lên 1 hàng + thêm hàng mới (theo dải xem trước) ở đáy. -> (items, dead).
    Dải xem trước TRỐNG = không có hàng mới (đóng băng của Gấu Bắc Cực / đang hoạt ảnh) -> KHÔNG đẩy, không thua."""
    if not preview:
        return items, False
    if any(t[0] == 0 for t in items):
        return items, True
    out = [(t[0] - 1, t[1], t[2], t[3]) for t in items]
    for c, ln in preview or []:
        out.append((ROWS - 1, c, ln, "U"))
    return out, False


@dataclass
class Rules:
    kind_value: dict = None            # ghi đè điểm CẢ THANH theo loài (None -> 10 điểm x số ô, trâu 1 ô = 200: xem `value`)
    wave_bonus: float = 0.0            # (giữ tên cũ cho tương thích; Buff thật giờ tính bằng `combo_mult`)
    pass_through: bool = False         # kéo xuyên qua thanh khác? (đoán: không)
    use_combo: bool = True             # áp Buff liên hoàn cho HÀNG thứ 2/3/4 (+20%/+50%/+100%)

    def value(self, k, ln=1):
        """Điểm 1 thanh bị ăn: điểm mỗi ô theo Đồ Giám (cấp 1 = 10) x số ô (trâu 1 ô = 200, trứng 0). `kind_value` (nếu đặt) ghi đè điểm CẢ THANH theo loài."""
        if self.kind_value is not None:
            return float(self.kind_value.get(k, CELL_POINTS * ln))
        if k == "R":
            return float(BULL_POINTS)
        if k == "E":
            return 0.0
        return float(UNIT_POINTS.get(k, CELL_POINTS) * max(1, ln))


def event_points(removed, waves, rules: Optional[Rules] = None):
    """Điểm của 1 lần ăn (1 hiệp): với mỗi HÀNG bị ăn, tổng điểm các thanh trong hàng đó x Buff của hàng thứ k (`combo_mult(k)`: thứ 1 x1.0, thứ 2 x1.2,
    thứ 3 x1.5, thứ 4 x2.0). Hàng dưới tính trước. Thanh dạng cũ 4 phần tử (không có thứ hạng) coi như cùng hàng thứ 1."""
    rules = rules or Rules()
    per_rank = {}
    for t in removed:
        rk = t[4] if len(t) > 4 else 1
        per_rank[rk] = per_rank.get(rk, 0.0) + rules.value(t[3], t[2])
    return sum(v * (combo_mult(rk) if rules.use_combo else 1.0) for rk, v in per_rank.items())


def step_state_full(items, i, nc, preview, rules: Optional[Rules] = None):
    """1 hiệp: kéo thanh i sang cột nc -> rơi/ăn -> (thua nếu còn thú ở hàng 0) -> đẩy lên + hàng mới.
    -> (items_mới, điểm, thua, hàng_ăn, [các thanh bị ăn trong hiệp])."""
    rules = rules or Rules()
    nb = list(items)
    r, c0, ln, k = nb[i]
    nb[i] = (r, nc, ln, k)
    nb, cl, rem, nw, waves = _settle_items(nb)
    pts = event_points(rem, waves, rules)
    eaten = list(rem)
    nb, dead = _push(nb, preview)
    if not dead and preview:
        nb, c2, rem2, _, waves2 = _settle_items(nb)       # hàng mới sinh ra ĐẦY thì game tự ăn sau ~1-2s (log 17/10)
        cl += c2
        pts += event_points(rem2, waves2, rules)
        eaten += list(rem2)
    return nb, pts, dead, cl, eaten


def step_state(items, i, nc, preview, rules: Optional[Rules] = None):
    """Như `step_state_full` nhưng chỉ trả (items_mới, điểm, thua, hàng_ăn)."""
    return step_state_full(items, i, nc, preview, rules)[:4]


@dataclass
class Weights:
    clear_row: float = 1000.0      # (chỉ dùng cho điểm của bản cũ) thưởng mỗi hàng ăn
    row_fill: float = 6.0          # thưởng độ đầy (bình phương) của các hàng chưa đầy
    hole: float = 5.0              # phạt ô trống nằm DƯỚI một thanh (khó lấp)
    height: float = 3.0            # phạt độ cao của khối
    danger: float = 60.0           # phạt rất nặng khi khối chạm sát hàng 0
    fit: float = 60.0              # thưởng hàng sắp đủ mà có thanh vừa khít phía trên để lấp
    points: float = 9.0            # hệ số điểm ăn được (điểm THẬT: 1 hàng ~100 điểm ~ 900, cùng cỡ bản cũ 9 ô x 100)
    bull_cell: float = 50.0        # phạt MỖI Ô TRÂU trên bàn (trâu càng dài càng gây hại khi tấn công; Gấu Bắc Cực/ăn hàng làm trâu co lại) - bản 6.1: 6 -> 50
    shrink: float = 60.0           # (bản 6.1) thưởng MỖI Ô TRÂU rút được trong 1 nước (tính như điểm ăn, nhân `points`); chỉ để CHỌN NƯỚC, không cộng vào điểm dự đoán. 0 = tắt


def evaluate_items(items, w: Weights):
    if not items:
        return 0.0
    rm = [0] * ROWS
    for t in items:
        rm[t[0]] |= _m(t[1], t[2])
    score = 0.0
    top = ROWS
    for r in range(ROWS):
        if rm[r]:
            top = min(top, r)
            n = bin(rm[r]).count("1")
            score += w.row_fill * (n / COLS) ** 2 * COLS
    # lỗ dưới thanh
    colmask = 0
    holes = 0
    for r in range(ROWS):
        holes += bin(colmask & ~rm[r] & FULL).count("1")
        colmask |= rm[r]
    # hàng sắp đủ có thanh vừa khít ở trên
    lens_above = {}
    byrow = {}
    for t in items:
        byrow.setdefault(t[0], []).append(t)
    avail = {}
    fit = 0.0
    for r in range(ROWS):
        if rm[r]:
            n = bin(rm[r]).count("1")
            if n >= 5 and n < COLS:
                gaps = []
                c = 0
                while c < COLS:
                    if not (rm[r] >> c) & 1:
                        e = c
                        while e + 1 < COLS and not (rm[r] >> (e + 1)) & 1:
                            e += 1
                        gaps.append(e - c + 1)
                        c = e + 1
                    else:
                        c += 1
                pool = dict(avail)
                got = 0
                for g in gaps:
                    if pool.get(g, 0) > 0:
                        pool[g] -= 1
                        got += 1
                fit += w.fit * (n / COLS) * (1.0 if got == len(gaps) else 0.25 * got / len(gaps))
        for t in byrow.get(r, []):
            avail[t[2]] = avail.get(t[2], 0) + 1
    bull = sum(t[2] for t in items if t[3] == "R")
    return score + fit - w.hole * holes - w.height * (ROWS - top) - w.danger * max(0, 3 - top) ** 2 - w.bull_cell * bull


def evaluate(bars, cleared, w: Weights):
    return cleared * w.clear_row + evaluate_items([(b.row, b.col, b.length, b.kind) for b in bars], w)


def apply_move(bars, i, new_col):
    nb = list(bars)
    b = nb[i]
    nb[i] = Bar(b.row, new_col, b.length, b.kind)
    return settle(nb)


DEAD = -1e6


def beam_search(bars, depth=3, beam=30, w: Optional[Weights] = None, preview=None, rules: Optional[Rules] = None, blocked=None):
    """Tìm chuỗi nước. Trả ([(hàng, cột_cũ, dài, cột_mới), ...], điểm). `blocked` = tập nước bị chặn ở bước ĐẦU.
    Có tính đẩy hàng mới (dải xem trước) và THUA khi còn thú ở hàng 0 trước lúc đẩy."""
    w = w or Weights()
    rules = rules or Rules()
    items0 = [(b.row, b.col, b.length, b.kind) for b in bars]
    frontier = [(0.0, 0.0, items0, [], False)]       # (điểm_xếp_hạng, điểm_ăn_tích_luỹ, items, đường, thua)
    best = None
    for d in range(depth):
        nxt = []
        for sc0, acc, cur, path, dead in frontier:
            if dead:
                nxt.append((sc0, acc, cur, path, True))
                continue
            b0 = sum(t[2] for t in cur if t[3] == "R")           # số ô trâu trước nước này (để thưởng `Weights.shrink` khi trâu co)
            moves = _gen_moves_items(cur)
            if d == 0 and blocked:
                moves = [(i, nc) for (i, nc) in moves if (cur[i][0], cur[i][1], cur[i][2], nc) not in blocked]
            for i, nc in moves:
                nb, pts, isdead, _cl = step_state(cur, i, nc, preview, rules)
                tot = acc + pts
                if b0 and w.shrink:                              # nước này làm TRÂU CO -> thưởng (chỉ tìm nước, `pts` thật giữ nguyên)
                    tot += w.shrink * max(0, b0 - sum(t[2] for t in nb if t[3] == "R"))
                mv = (cur[i][0], cur[i][1], cur[i][2], nc)
                if isdead:
                    sc = DEAD + 1000.0 * d + tot * w.points
                else:
                    sc = tot * w.points + evaluate_items(nb, w)
                nxt.append((sc, tot, nb, path + [mv], isdead))
        if not nxt:
            break
        nxt.sort(key=lambda t: -t[0])
        frontier = nxt[:beam]
        best = frontier[0]
    if best is None or not best[3]:
        return [], 0.0
    return best[3], best[0]


# ----------------------------------------------------------------------------
# 2b) KỸ NĂNG (bấm sư tử vàng cạnh thanh năng lượng -> chỉ vào 1 khối của con muốn dùng; mỗi lần tốn 1000 năng lượng)
# Hiệu ứng theo \"Đồ Giám\" (người dùng gửi ảnh). Mức chắc chắn: Ngựa vằn/Voi/Hươu/Gấu = rõ nghĩa; Đà điểu/Sư tử = ĐOÁN chi tiết.
# ----------------------------------------------------------------------------
SKILL_TEXT = {
    "W": "Ngựa vằn: kéo dài thân cho tới khi lấp đầy ô trống ở CẢ HAI bên (trong hàng)",
    "O": "Đà điểu: chạy về phía có nhiều ô trống hơn, ĐẺ TRỨNG dọc đường, dừng khi gặp vật cản",
    "P": "Hươu: tách thành các chú hươu nhỏ 1 ô",
    "B": "Voi: rút ngắn thành voi con 1 ô",
    "Y": "Sư tử: kéo dài về phía có nhiều thú liền kề hơn và NUỐT các thú đó",
    "K": "Gấu Bắc Cực: đóng băng - không có hàng mới trồi lên một thời gian + rút mọi trâu còn 1 ô",
}


def _lion_extend(items, idx):
    """SƯ TỬ (người dùng mô tả 18/10, đối chiếu 6 sư tử ở ảnh trước/sau): kéo dài thân trong hàng của nó.
      - Về mỗi phía, đi theo CHUỖI: ô kế bên là thú -> nuốt luôn (thú biến thành sư tử); ô kế bên trống mà ô sau nó là thú (cách 1 ô) ->
        biến ô trống thành sư tử rồi nuốt thú, rồi ăn tiếp cách 1 ô. Cách 2 ô trở lên thì KHÔNG với tới.
      - Chọn phía nuốt được NHIỀU thú hơn (bằng nhau -> phía phải). Cả 2 phía không có thú thì kéo dài 1 ô về phía còn nhiều chỗ trống hơn.
      - Ngoài các ô lấp khoảng trống, sư tử còn được thêm (1 + số thú đã nuốt - số ô trống đã lấp) ô trống: trước hết tiếp tục theo hướng chuỗi,
        hết chỗ thì sang phía đối diện (dừng khi gặp thú/mép bàn). ĐÃ KHỚP 6/6 hàng ở ảnh 3->4 (animal_sim: `python animal_bot.py ảnh_trước.png ảnh_sau.png`).
      - Sau kỹ năng, nếu thân chưa kín hàng thì mỗi HIỆP kế đuôi tự rút 1 ô cho tới khi còn 3 ô (CHƯA mô phỏng; bot đọc lại bàn thật mỗi hiệp nên không sao).
    -> (items_mới, False) hoặc None nếu không đổi gì."""
    r, c0, ln, k = items[idx]
    rest = [tuple(t) for j, t in enumerate(items) if j != idx]
    occ = {}
    for t in rest:
        if t[0] == r:
            for c in range(t[1], t[1] + t[2]):
                occ[c] = t

    def chain(d):
        lo, hi = c0, c0 + ln - 1
        eaten, filled = [], 0
        while True:
            n1 = (hi if d > 0 else lo) + d
            if not 0 <= n1 < COLS:
                break
            if n1 in occ:
                t = occ[n1]
            else:
                n2 = n1 + d
                if 0 <= n2 < COLS and n2 in occ:
                    t = occ[n2]
                    filled += 1
                else:
                    break
            eaten.append(t)
            if d > 0:
                hi = t[1] + t[2] - 1
            else:
                lo = t[1]
        return eaten, lo, hi, filled

    def free(edge, d):
        n, c = 0, edge + d
        while 0 <= c < COLS and c not in occ:
            n, c = n + 1, c + d
        return n

    er, lr, hr, fr_ = chain(1)
    el, ll, hl, fl_ = chain(-1)
    if len(er) == 0 and len(el) == 0:
        d = 1 if free(c0 + ln - 1, 1) >= free(c0, -1) else -1
        if free(c0 + ln - 1 if d > 0 else c0, d) == 0:
            d = -d
            if free(c0 + ln - 1 if d > 0 else c0, d) == 0:
                return None
        lo, hi, eaten, filled, extra = c0, c0 + ln - 1, [], 0, 1
    elif len(er) >= len(el):
        d, (eaten, lo, hi, filled) = 1, (er, lr, hr, fr_)
        extra = 1 + len(eaten) - filled
    else:
        d, (eaten, lo, hi, filled) = -1, (el, ll, hl, fl_)
        extra = 1 + len(eaten) - filled
    for side in (d, -d):                                # hết chỗ theo hướng chuỗi thì sang phía đối diện
        while extra > 0:
            nxt = (hi if side > 0 else lo) + side
            if not 0 <= nxt < COLS or nxt in occ:
                break
            if side > 0:
                hi = nxt
            else:
                lo = nxt
            extra -= 1
    if lo == c0 and hi == c0 + ln - 1:
        return None
    rest = [t for t in rest if t not in eaten]
    return rest + [(r, lo, hi - lo + 1, "Y")], False


def skill_apply_kind(items, k):
    """Kỹ năng của game áp lên CẢ LOÀI (chọn 1 loại động vật -> mọi con cùng loài trên bàn đều biến đổi; ảnh 3->4: cả 7 sư tử cùng đổi).
    Gấu (K) là hiệu ứng toàn bàn. -> (items_mới, freeze) hoặc None nếu không con nào đổi."""
    if k == "K":
        idx = next((i for i, t in enumerate(items) if t[3] == "K"), None)
        return None if idx is None else skill_apply(items, idx)
    cur = [tuple(t) for t in items]
    changed = False
    for t in sorted(t for t in cur if t[3] == k):
        if t not in cur:
            continue                                     # đã bị sư tử khác nuốt
        res = skill_apply(cur, cur.index(t))
        if res is not None:
            cur, changed = res[0], True
    return (cur, False) if changed else None


def skill_apply(items, idx):
    """Mô phỏng dùng kỹ năng lên thanh `idx` (chưa rơi/ăn - việc đó do `_settle_items`). -> (items_mới, freeze) hoặc None nếu vô tác dụng."""
    r, c0, ln, k = items[idx]
    rest = [tuple(t) for j, t in enumerate(items) if j != idx]
    row = 0
    for t in rest:
        if t[0] == r:
            row |= _m(t[1], t[2])
    if k == "W":
        a = c0
        while a - 1 >= 0 and not (row >> (a - 1)) & 1:
            a -= 1
        b = c0 + ln
        while b < COLS and not (row >> b) & 1:
            b += 1
        if a == c0 and b == c0 + ln:
            return None
        return rest + [(r, a, b - a, "W")], False
    if k == "O":
        le = sum(1 for c in range(0, c0) if not (row >> c) & 1)
        re_ = sum(1 for c in range(c0 + ln, COLS) if not (row >> c) & 1)
        if le == 0 and re_ == 0:
            return None
        if re_ >= le:
            e = c0 + ln
            while e < COLS and not (row >> e) & 1:
                e += 1
            if e == c0 + ln:
                return None
            new = [(r, c, 1, "E") for c in range(c0, e - ln)] + [(r, e - ln, ln, "O")]
        else:
            sc = c0 - 1
            while sc >= 0 and not (row >> sc) & 1:
                sc -= 1
            sc += 1
            if sc == c0:
                return None
            new = [(r, c, 1, "E") for c in range(sc + ln, c0 + ln)] + [(r, sc, ln, "O")]
        return rest + new, False
    if k == "P":
        if ln < 2:
            return None
        return rest + [(r, c, 1, "P") for c in range(c0, c0 + ln)], False
    if k == "B":
        if ln < 2:
            return None
        return rest + [(r, c0, 1, "B")], False
    if k == "Y":
        return _lion_extend(items, idx)
    if k == "K":
        # Gấu Bắc Cực (người dùng xác nhận 17/10): đóng băng + RÚT MỌI TRÂU CÒN 1 Ô (giữ ô đầu bên trái); luôn có tác dụng (đóng băng)
        return [((t[0], t[1], 1, "R") if (t[3] == "R" and t[2] > 1) else tuple(t)) for t in items], True
    return None


def skill_candidates(items, kinds):
    """[(idx, kind, items_sau_kỹ_năng_đã_rơi_ăn, freeze, điểm, số_hàng_ăn)] cho mỗi LOÀI trong `kinds` (chuỗi như \"KYPB\") đang có trên bàn.
    Kỹ năng áp lên CẢ LOÀI (`skill_apply_kind`); `idx` = thanh đầu tiên của loài, là chỗ bot chạm để chọn loài."""
    out = []
    for k in kinds:
        idx = next((i for i, t in enumerate(items) if t[3] == k), None)
        if idx is None:
            continue
        res = skill_apply_kind(items, k)
        if res is None:
            continue
        it2, freeze = res
        it3, cl, rem, nw, waves = _settle_items(it2)
        out.append((idx, k, it3, freeze, event_points(rem, waves), cl))
    return out


def choose_skill(bars, preview, blocked, kinds, depth=2, beam=20, min_gain=0.0, danger_row=None, freeze_danger=None,
                 bull_cnt=None, bull_soon=None, cooldown_ok=True, w: Optional[Weights] = None, bear_bull_cells=0, bear_first=True):
    """Có NÊN dùng kỹ năng lúc này không? CHỈ khi (người dùng chốt 18/10):
      - KẸT  = không còn nước đi hợp lệ nào (hoặc chỉ còn nước đã bị chặn);
      - THUA = mọi nước đi đều làm hàng mới trồi lên chạm thú ở hàng 0 (nước sau chết, `beam_search` depth 1).
    (Đã BỎ nhánh dùng Gấu chủ động khi trên bàn có >= 8 ô trâu; `bear_bull_cells` chỉ còn để tương thích, KHÔNG có tác dụng.)
    Thứ tự: GẤU (K) ĐẦU TIÊN - nếu có Gấu trên bàn và dùng xong còn sống thì dùng Gấu; không có Gấu / Gấu không cứu được thì xét các kỹ năng khác
    trong `kinds` (mặc định Sư tử, Hươu, Voi) và chọn cái có giá trị SAU kỹ năng cao nhất (điểm ăn ngay + beam `depth` hiệp; Gấu đóng băng nên không có hàng mới),
    bỏ cái mà sau đó vẫn kẹt/thua. Kỹ năng áp lên CẢ LOÀI. Không có cái nào ổn thì KHÔNG dùng (khỏi phí).
    `danger_row/freeze_danger/bull_cnt/bull_soon/min_gain/cooldown_ok/bear_bull_cells` chỉ để giữ tên cũ cho tương thích.
    -> (giá_trị_sau_kỹ_năng, cand, giá_trị_nước_thường (DEAD), lý_do) hoặc None."""
    w = w or Weights()
    items = [(b.row, b.col, b.length, b.kind) for b in bars]
    if not items:
        return None
    bp, bsc = beam_search(bars, 1, 10, w=w, preview=preview, blocked=blocked)
    stuck = not bp
    lose = (not stuck) and bsc <= DEAD / 2
    if not (stuck or lose):
        return None
    sd, bm = max(1, int(depth)), min(int(beam), 20)
    why = "KẸT" if stuck else "THUA"
    best = {}
    for cand in skill_candidates(items, kinds):
        idx, k, it3, freeze, pts, cl = cand
        b3 = [Bar(*t) for t in it3]
        if not b3:
            val = pts * w.points + 5000.0
        else:
            p3, s3 = beam_search(b3, sd, bm, w=w, preview=None if freeze else preview)
            if not p3 or s3 <= DEAD / 2:
                continue
            val = pts * w.points + s3
        best[k] = (val, cand, DEAD, why)
    if bear_first and "K" in best and "K" in kinds:    # ƯU TIÊN GẤU (bear_first=False chỉ để mô phỏng so sánh)
        return best["K"]
    others = [v for k, v in best.items() if (k != "K" or not bear_first)]
    return max(others, key=lambda v: v[0]) if others else None


# ----------------------------------------------------------------------------
# 3) Chạy bước
# ----------------------------------------------------------------------------
class _Stop(Exception):
    pass


def save_debug(frame, geo, cells, move=None, tag="an", preview=None):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        im = frame.copy()
        for r in range(ROWS):
            for c in range(COLS):
                k = cells[r][c]
                if k != ".":
                    cv2.putText(im, k, (int(geo.cx(c)) - 6, int(geo.cy(r)) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        for c, ln in preview or []:
            cv2.rectangle(im, (int(geo.x0 + c * geo.pitch_x), int(geo.strip_y) - 9), (int(geo.x0 + (c + ln) * geo.pitch_x), int(geo.strip_y) + 9), (0, 160, 0), 2)
        if move:
            r, c0, ln, nc = move
            cv2.arrowedLine(im, (int(geo.cx(c0) + (ln - 1) * geo.pitch_x / 2), int(geo.cy(r))),
                            (int(geo.cx(nc) + (ln - 1) * geo.pitch_x / 2), int(geo.cy(r))), (0, 0, 255), 4)
        path = os.path.join(DEBUG_DIR, f"{tag}_{time.strftime('%H%M%S')}.png")
        cv2.imencode(".png", im)[1].tofile(path)
        return path
    except Exception:
        return None


def _occ_rows(bars):
    rm = [0] * ROWS
    for b in bars:
        rm[b.row] |= _m(b.col, b.length)
    return rm


class AnimalBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_moves=0, max_seconds=0, depth=3, beam=30,
                 settle_s=0.9, drag_ms=260, debug=False, lost_limit=4, stable_tries=6, stable_gap=0.35, verify=True,
                 log_score=True, stuck_limit=6, sleep=time.sleep, now=time.time,
                 use_skill=True, skill_kinds="K", skill_gain=400.0, skill_depth=2, skill_cost=1000, freeze_danger=3,
                 skill_x=None, skill_y=None, skill_tap_gap=0.5, skill_wait=1.2, preview_wait=1.6, stable_max=6.0, recheck=True,
                 skill_danger_row=2, bull_soon=3, skill_cooldown=0, skill_confirm_wait=3.0, skill_anim_wait=2.0, target_moves=400, stop_on_death=True, exit_on_stop=True, change_limit=3,
                 exit_on_max=False, bear_bull_cells=0, depth_crowd=6, crowd_row=4):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test, self.debug = bool(test), bool(debug)
        self.max_moves, self.max_seconds = int(max_moves or 0), float(max_seconds or 0)
        self.depth, self.beam = int(depth), int(beam)
        self.depth_crowd, self.crowd_row = int(depth_crowd or 0), int(crowd_row)   # bàn ĐÔNG (thú cao tới hàng <= crowd_row) thì tìm sâu `depth_crowd` nước (tìm sâu rất rẻ: depth 5 ~0.2s)
        self.settle_s, self.drag_ms = float(settle_s), int(drag_ms)
        self.lost_limit = int(lost_limit)
        self.stable_tries, self.stable_gap = int(stable_tries), float(stable_gap)
        self.verify, self.log_score = bool(verify), bool(log_score)
        self.stuck_limit = int(stuck_limit)
        self.exit_on_max = bool(exit_on_max)       # đủ `max_moves` hiệp thì cũng thoát bàn + lưu tiến độ (như exit_on_stop)
        self.bear_bull_cells = 0                    # ĐÃ BỎ (18/10): Gấu không còn dùng chủ động theo số ô trâu; giữ tham số cho tương thích
        self._need = None                          # giá năng lượng 1 lần kỹ năng đọc từ thanh "cur/NEED" (tăng sau mỗi lần dùng: 1000 -> 3000...)
        self.exit_on_stop = bool(exit_on_stop)     # bot dừng (chết chắc/hết nước/kéo không ăn) -> tự bấm nút thoát góc dưới trái + Xác nhận (lưu tiến độ)
        self.change_limit = max(1, int(change_limit))   # số lần liền 'bàn đổi trong lúc tính' thì thôi chờ, chấp nhận bản đọc ổn định mới nhất
        self._chg_streak = 0
        self._skip_recheck = False
        self._chg_saved = 0
        self.stop_on_death = bool(stop_on_death)   # hết nước/hết kỹ năng/nước sau chắc chắn chết -> DỪNG để người chơi quyết định hồi sinh bằng kim cương
        self.sleep, self.now = sleep, now
        self.t0 = now()
        self.moves = 0
        self.mismatch = 0
        self._blocked = set()
        self._blocked_sig = None
        self._mm_saved = 0
        # kỹ năng + chờ ổn định (bản 3)
        self.use_skill = bool(use_skill)
        self.skill_kinds = str(skill_kinds or "")
        self.skill_gain, self.skill_depth = float(skill_gain), int(skill_depth)
        self.skill_cost, self.freeze_danger = int(skill_cost), int(freeze_danger)
        self.skill_x, self.skill_y = skill_x, skill_y
        self.skill_tap_gap, self.skill_wait = float(skill_tap_gap), float(skill_wait)
        self.preview_wait, self.stable_max = float(preview_wait), float(stable_max)
        self.recheck = bool(recheck)
        self._skill_fail = 0
        self._skill_fail_move = 0                  # hiệp của lần kỹ năng hụt gần nhất (hụt 3 lần liền thì khoá, nhưng mở lại sau 25 hiệp)
        self._skill_used = 0
        self.skill_danger_row, self.bull_soon = int(skill_danger_row), int(bull_soon)
        self.skill_cooldown = int(skill_cooldown)
        self.skill_confirm_wait, self.skill_anim_wait = float(skill_confirm_wait), float(skill_anim_wait)
        self.target_moves = int(target_moves or 0)
        self._target_logged = False
        self._skill_cd_until = 0       # (không còn dùng: kỹ năng chỉ dùng khi kẹt/thua; giữ cho tương thích)
        self._eaten = {}               # thống kê (DỰ ĐOÁN theo mô hình) mỗi loài: [số thanh, số ô, điểm gốc]
        self._last_rem = []
        self._freeze_left = 0          # số hiệp còn đóng băng của Gấu (dải xem trước trống là BÌNH THƯỜNG, khỏi chờ)
        self._energy = None            # năng lượng đọc/ước lượng gần nhất
        self._bull_cnt = None
        self._bull_saved = 0

    def _check(self):
        if self.should_stop():
            raise _Stop("stop")
        if self.max_seconds and self.now() - self.t0 > self.max_seconds:
            raise _Stop("timeout")

    def _shot(self):
        for _ in range(3):
            fr = self.adb.screencap_fast()
            if fr is not None:
                return fr
            self.sleep(0.3)
        raise RuntimeError("không chụp được màn hình")

    def _read(self):
        fr = self._shot()
        geo, cells, bars = read_grid(fr)
        return fr, geo, cells, bars

    def _read_stable(self):
        """Chụp liên tiếp tới khi bàn ĐỨNG YÊN thật sự: 2 lần đọc giống hệt + KHÔNG còn hàng kín 9 ô (game tự ăn hàng mới sinh ra đầy
        sau ~1-2s - log 17/10: bot đọc đúng lúc đó rồi kéo sai chỗ) + dải xem trước đã hiện (trống = đang hoạt ảnh, hoặc đóng băng:
        chờ tối đa `preview_wait` giây rồi chấp nhận). Tổng chờ tối đa `stable_max` giây."""
        t0 = self.now()
        fr, geo, cells, bars = self._read()
        prev = cells_text(cells) + str(read_preview(fr, geo))
        while True:
            self._check()
            self.sleep(self.stable_gap)
            fr, geo, cells, bars = self._read()
            pv = read_preview(fr, geo)
            cur = cells_text(cells) + str(pv)
            el = self.now() - t0
            if cur == prev and not has_full_row(cells) and (pv or self._freeze_left > 0 or el >= self.preview_wait):
                break
            prev = cur
            if el >= self.stable_max:
                break
        return fr, geo, cells, bars

    def _score_log(self, rec, name="score_log.jsonl"):
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            with open(os.path.join(DEBUG_DIR, name), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _ocr_all(self, fr, geo, want_score=True):
        """Đọc song song điểm / năng lượng / đếm ngược trâu (mỗi lần gọi tesseract ~0.3s)."""
        out = {"score": None, "energy": None, "bull": None}
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=3) as ex:
                f_en = ex.submit(read_energy, fr, geo)
                f_bu = ex.submit(read_bull_count, fr, geo)
                f_sc = ex.submit(read_score, fr, geo) if want_score else None
                out["energy"], out["bull"] = f_en.result(), f_bu.result()
                out["score"] = f_sc.result() if f_sc else None
        except Exception:
            pass
        return out

    # ---- kỹ năng ----
    def _danger_top(self, bars):
        return min((b.row for b in bars), default=ROWS)

    def _choose_skill(self, bars, preview, blocked):
        """Xem `choose_skill` (module): chỉ khi KẸT / THUA (Gấu ưu tiên trước, rồi kỹ năng giá trị cao nhất). -> (giá_trị, cand, base_score, lý_do) hoặc None."""
        return choose_skill(bars, preview, blocked, self.skill_kinds, depth=self.skill_depth, beam=self.beam, min_gain=self.skill_gain,
                            danger_row=self.skill_danger_row, freeze_danger=self.freeze_danger, bull_cnt=self._bull_cnt,
                            bull_soon=self.bull_soon, cooldown_ok=(self.moves >= self._skill_cd_until), bear_bull_cells=self.bear_bull_cells)

    def _tap(self, x, y):
        f = getattr(self.adb, "tap_px", None)
        if f is not None:
            f(x, y)
        else:
            self.adb.tap(int(round(x)), int(round(y)))

    def _cancel_select_mode(self):
        """Thoát chế độ \"Chọn 1 loại động vật trên sân để kích hoạt\" (nút Hủy xanh dưới đáy) để khỏi kẹt khi không ra hộp thoại Xác nhận."""
        try:
            fr = self._shot()
            d = find_skill_confirm(fr)
            if d:
                self._tap(*d["cancel"])
                self.sleep(0.6)
                return
            b = find_select_cancel(fr)
            if b is None:
                h, w = fr.shape[:2]
                b = (w / 2.0, _yb(fr, 1237.0))          # toạ độ tham chiếu của nút Hủy dưới đáy (ảnh 720x1280)
            self._tap(*b)
            self.sleep(0.6)
        except Exception as e:
            self.log("warn", f"Animal: không thoát được chế độ chọn kỹ năng ({e})")

    def _do_skill(self, fr, geo, bar) -> bool:
        """Bấm nút sư tử (cạnh thanh năng lượng) -> chạm 1 khối của thanh `bar` -> game hiện hộp thoại \"Gợi ý\" -> bấm XÁC NHẬN -> ĐỢI hoạt ảnh.
        True = đã bấm Xác nhận (và hộp thoại đã tắt); False = không thấy hộp thoại (đã thoát chế độ chọn)."""
        h, w = fr.shape[:2]
        sx = w / REF_W
        bx = (self.skill_x if self.skill_x is not None else SKILL_BTN[0]) * sx
        by = _yb(fr, self.skill_y if self.skill_y is not None else SKILL_BTN[1])
        self._tap(bx, by)
        self.sleep(self.skill_tap_gap)
        self._tap(geo.cx(bar.col), geo.cy(bar.row))
        # 1) chờ hộp thoại Xác nhận
        t0 = self.now()
        dlg = None
        while True:
            self._check()
            self.sleep(0.35)
            f = self._shot()
            dlg = find_skill_confirm(f)
            if dlg or self.now() - t0 >= self.skill_confirm_wait:
                break
        if dlg is None:
            self.log("warn", "Animal: bấm kỹ năng xong KHÔNG thấy hộp thoại Xác nhận - thoát chế độ chọn")
            self._cancel_select_mode()
            return False
        if self.debug:
            try:
                os.makedirs(DEBUG_DIR, exist_ok=True)
                cv2.imencode(".png", f)[1].tofile(os.path.join(DEBUG_DIR, f"skill_hopthoai_{time.strftime('%H%M%S')}.png"))
            except Exception:
                pass
        # 2) bấm Xác nhận, chờ hộp thoại tắt
        self._tap(*dlg["ok"])
        t1 = self.now()
        while True:
            self._check()
            self.sleep(0.4)
            f2 = self._shot()
            if find_skill_confirm(f2) is None:
                break
            if self.now() - t1 >= 4.0:
                self.log("warn", "Animal: hộp thoại Xác nhận vẫn còn sau 4s, bấm lại")
                self._tap(*dlg["ok"])
                self.sleep(0.6)
                break
        # 3) đợi hoạt ảnh kỹ năng (sau đó người gọi còn chờ bàn đứng yên bằng _read_stable)
        self.sleep(self.skill_anim_wait)
        return True

    def _exit_save(self, why, enabled=None):
        """Bot dừng -> bấm nút thoát (mũi tên góc dưới trái) rồi chọn XÁC NHẬN (nút xanh = thoát và LƯU TIẾN ĐỘ; KHÔNG bấm \"Kết thúc ván này\").
        Không làm gì ở chế độ test / `exit_on_stop: false` (hoặc `enabled` = False; đủ `max_moves` hiệp thì gọi với `enabled=self.exit_on_max`). True = đã bấm Xác nhận và hộp thoại đã tắt."""
        if self.test or not (self.exit_on_stop if enabled is None else enabled):
            return False
        try:
            for attempt in range(3):
                fr = self._shot()
                h, w = fr.shape[:2]
                dlg = find_skill_confirm(fr)
                if dlg is None:
                    self._tap(BACK_BTN[0] * w / REF_W, _yb(fr, BACK_BTN[1]))
                    t0 = self.now()
                    while self.now() - t0 < 3.0:
                        self.sleep(0.4)
                        fr = self._shot()
                        dlg = find_skill_confirm(fr)
                        if dlg:
                            break
                if dlg is None:
                    self.log("warn", f"Animal: bấm nút thoát nhưng không thấy hộp thoại ({attempt + 1}/3)")
                    continue
                if not is_exit_dialog(fr):
                    self.log("warn", "Animal: hộp thoại hiện ra không phải hộp thoại thoát (nghi hộp thoại kỹ năng) - bấm Hủy rồi thử lại")
                    self._tap(*dlg["cancel"])
                    self.sleep(0.8)
                    continue
                self._tap(*dlg["ok"])
                self.sleep(1.2)
                fr2 = self._shot()
                if find_skill_confirm(fr2) is None:
                    self.log("info", f"Animal: đã THOÁT và LƯU TIẾN ĐỘ ({why})")
                    return True
                self.log("warn", "Animal: hộp thoại thoát vẫn còn sau khi bấm Xác nhận, thử lại")
        except _Stop:
            raise
        except Exception as e:
            self.log("warn", f"Animal: không tự thoát được ({e}) - bạn tự bấm thoát góc dưới trái rồi chọn Xác nhận")
            return False
        self.log("warn", "Animal: không tự thoát được - bạn tự bấm thoát góc dưới trái rồi chọn Xác nhận (nút xanh)")
        return False

    def _stop_dead(self, why, fr, geo, cells, preview) -> bool:
        """Hết nước đi / hết kỹ năng cứu / nước sau chắc chắn thua -> DỪNG (không kéo nữa) để người chơi tự quyết định hồi sinh bằng kim cương.
        Lưu ảnh `chet_chac_*.png`; trả False để bước auto_animal báo dừng chứ không coi là thắng."""
        try:
            save_debug(fr, geo, cells, None, tag="chet_chac", preview=preview)
        except Exception:
            pass
        en = self._energy
        sk = "đủ năng lượng nhưng KHÔNG kỹ năng nào cứu được" if (en is not None and en >= self._cost()) else f"không đủ năng lượng kỹ năng ({en}/{self._cost()})"
        self.log("warn", f"Animal: DỪNG - {why}; {sk}; hiệp {self.moves}, kỹ năng đã dùng {self._skill_used} lần. "
                         f"Bàn chưa bị đi nước chết - bạn xem có hồi sinh bằng kim cương không rồi chạy lại.")
        self._exit_save(why)
        return False

    def _cost(self):
        """Giá 1 lần kỹ năng: lấy MỐC đọc từ thanh năng lượng (ảnh 17/10: "7000/3000" - giá tăng sau mỗi lần dùng), chưa đọc được thì dùng `skill_cost`."""
        return int(self._need) if self._need else self.skill_cost

    def _tally(self, removed):
        """Cộng dồn các thanh bị ăn (theo dự đoán của mô hình) vào thống kê từng loài."""
        for t in removed:
            e = self._eaten.setdefault(t[3], [0, 0, 0.0])
            e[0] += 1
            e[1] += t[2]
            e[2] += Rules().value(t[3], t[2])

    def _log_stats(self, why):
        """Bảng loài đã ăn + ước lượng điểm tăng thêm nếu nâng 1 cấp từng loài (dựa trên `CODEX_NEXT`, chưa tính buff liên hoàn) -> chọn con đáng nâng nhất."""
        if not self._eaten:
            return
        tot = sum(v[2] for v in self._eaten.values()) or 1.0
        rows, best = [], None
        for k, (n, cells, pts) in sorted(self._eaten.items(), key=lambda kv: -kv[1][2]):
            if k in BASE_LEN:
                gain = cells * CODEX_NEXT[k] / BASE_LEN[k]
                if best is None or gain > best[1]:
                    best = (k, gain)
                rows.append(f"{NAMES.get(k, k)} {n} thanh ({cells} ô) {pts:.0f}đ = {100 * pts / tot:.0f}% | nâng 1 cấp: +{gain:.0f}đ")
            else:
                rows.append(f"{NAMES.get(k, k)} {n} thanh {pts:.0f}đ")
        tail = f" -> NÂNG {NAMES.get(best[0])} lợi nhất (+{best[1]:.0f}đ trong {self.moves} hiệp này)" if best else ""
        self.log("info", f"Animal THỐNG KÊ ({why}, {self.moves} hiệp, dự đoán): " + "; ".join(rows) + tail)

    def run(self) -> bool:
        """Chạy bot; luôn in bảng thống kê loài đã ăn khi kết thúc."""
        try:
            return self._run_main()
        finally:
            self._log_stats("tổng kết")

    def _run_main(self) -> bool:
        lost = stuck = 0
        pred = None                  # (bars dự đoán không tính hàng mới, move, hàng đã ăn)
        last_move = None
        last_cleared = []
        last_pts = 0.0
        pending = None               # bản ghi điểm chờ đọc số thật (đọc SAU lúc tính để số kịp đếm xong)
        try:
            fr, geo, cells, bars = self._read_stable() if not self.test else self._read()
            while True:
                self._check()
                if self.target_moves and self.moves >= self.target_moves and not self._target_logged:
                    self._target_logged = True
                    self.log("info", f"Animal: ĐẠT MỤC TIÊU sống sót {self.moves}/{self.target_moves} hiệp (kỹ năng đã dùng {self._skill_used} lần)")
                if self.max_moves and self.moves >= self.max_moves:
                    self.log("info", f"Animal: đủ {self.moves} hiệp, dừng")
                    self._exit_save(f"đủ {self.moves} hiệp", self.exit_on_max)
                    return True
                if not board_visible(fr, geo):
                    dlg = find_skill_confirm(fr)
                    if dlg is not None:
                        if is_exit_dialog(fr):
                            # nút đỏ của hộp thoại này là "Kết thúc ván này" -> TUYỆT ĐỐI không bấm; đóng bằng dấu X
                            self.log("warn", "Animal: có hộp thoại THOÁT bất ngờ - đóng bằng dấu X (không bấm Kết thúc ván)")
                            self._tap(EXIT_CLOSE[0] * fr.shape[1] / REF_W, EXIT_CLOSE[1] * fr.shape[0] / REF_H)
                        else:
                            self.log("warn", "Animal: có hộp thoại Xác nhận kỹ năng bất ngờ - bấm Hủy (không tốn năng lượng ngoài kế hoạch)")
                            self._tap(*dlg["cancel"])
                        self.sleep(0.8)
                        fr, geo, cells, bars = self._read()
                        continue
                    lost += 1
                    self.log("warn", f"Animal: không thấy khung bàn ({lost}/{self.lost_limit})")
                    if lost >= self.lost_limit:
                        self.log("info", f"Animal: coi như đã hết ván/thoát bàn sau {self.moves} hiệp, kết thúc")
                        return True
                    self.sleep(0.8)
                    fr, geo, cells, bars = self._read()
                    continue
                lost = 0
                preview = read_preview(fr, geo)
                sig = tuple(bars)
                lsig = _loose(bars)
                # đối chiếu dự đoán với bàn thật
                if pred is not None and self.verify:
                    pr = _occ_rows(pred[0])
                    ob = _occ_rows(bars)
                    diff = sum(bin(pr[r] ^ ob[r]).count("1") for r in range(ROWS))
                    if diff:
                        self.mismatch += 1
                        self.log("warn", f"Animal: bàn thật LỆCH dự đoán {diff} ô sau nước {last_move} (luật mô phỏng có thể sai, xem mục 6 docstring)")
                        if self._mm_saved < 40:
                            self._mm_saved += 1
                            save_debug(fr, geo, cells, last_move if (last_move and last_move[0] != "skill") else None, tag="lech", preview=preview)
                            try:
                                with open(os.path.join(DEBUG_DIR, f"lech_{time.strftime('%H%M%S')}.txt"), "w", encoding="utf-8") as f:
                                    f.write("DỰ ĐOÁN:\n" + cells_text(_to_cells(pred[0])) + "\nTHẬT:\n" + cells_text(cells) + f"\nnước: {last_move}\n")
                            except Exception:
                                pass
                    if self.log_score:
                        pending = {"t": time.strftime("%H:%M:%S"), "move": last_move, "pred_rows": pred[2], "pred_pts": round(last_pts, 1),
                                   "cleared": last_cleared, "lech": diff}
                    pred = None
                if self._blocked_sig is not None and lsig != self._blocked_sig:
                    self._blocked.clear()
                    self._blocked_sig = None
                    stuck = 0
                if not bars:
                    self.log("info", "Animal: bàn trống (đã dọn sạch), chờ hàng mới")
                    self.sleep(0.8)
                    fr, geo, cells, bars = self._read_stable()
                    continue
                t1 = self.now()
                dd = self.depth
                if self.depth_crowd > dd and bars and min(b.row for b in bars) <= self.crowd_row:
                    dd = self.depth_crowd
                path, score = beam_search(bars, dd, self.beam, preview=preview, blocked=self._blocked)
                if path:
                    r, c0, ln, nc = path[0]
                else:
                    r = c0 = ln = nc = None          # KẸT: hết nước đi -> thử kỹ năng ở dưới, không dùng được thì DỪNG (xem `_stop_dead`)
                think = self.now() - t1
                dead_now = False
                if path:
                    _it = [(b.row, b.col, b.length, b.kind) for b in bars]
                    _ix = next((i for i, t in enumerate(_it) if (t[0], t[1], t[2]) == (r, c0, ln)), None)
                    if _ix is not None:
                        dead_now = bool(step_state(_it, _ix, nc, preview)[2])
                # chụp lại SAU khi tính: (1) bàn có đổi trong lúc tính không (hàng đầy tự ăn...), (2) đọc điểm/năng lượng/đếm ngược trâu
                # (lúc này số điểm đã đếm xong; bản cũ đọc ngay sau nước đi nên toàn ra số cũ)
                en = None
                if not self.test:
                    if self.recheck and self._skip_recheck:
                        # lần trước bàn "đổi" liên tục mà 2 lần đọc ổn định vẫn khớp nhau -> nhận diện chập chờn, bỏ qua kiểm tra lần này để khỏi lặp mãi
                        self._skip_recheck = False
                        self._chg_streak = 0
                    elif self.recheck:
                        fr2, geo2, cells2, bars2 = self._read()
                        if _loose(bars2) != lsig:
                            self._chg_streak += 1
                            self.log("info", f"Animal: bàn đổi trong lúc tính (hàng đầy tự ăn/hoạt ảnh) - chờ ổn định rồi tính lại "
                                             f"[{self._chg_streak}/{self.change_limit}] khác: {_cells_diff(bars, bars2)}")
                            if self._chg_saved < 6:
                                self._chg_saved += 1
                                save_debug(fr2, geo2, cells2, None, tag="doi_luc_tinh", preview=read_preview(fr2, geo2))
                            if self._chg_streak >= self.change_limit:
                                self.log("warn", f"Animal: bàn 'đổi' {self._chg_streak} lần liền nhưng đọc ổn định vẫn khớp -> nhận diện chập chờn, "
                                                 f"lần tới đi luôn không kiểm tra lại")
                                self._skip_recheck = True
                            fr, geo, cells, bars = self._read_stable()
                            continue
                        self._chg_streak = 0
                        fr, geo = fr2, geo2
                    if self.log_score or self.use_skill:
                        o = self._ocr_all(fr, geo, want_score=self.log_score)
                        en = o["energy"]
                        if en is not None:
                            self._energy = en[0]
                            if en[1]:
                                self._need = en[1]
                        bc = o["bull"]
                        if bc is not None:
                            if self._bull_cnt is not None and bc > self._bull_cnt:
                                self.log("info", f"Animal: TRÂU ĐÃ TẤN CÔNG (đếm ngược {self._bull_cnt} -> {bc}), lưu ảnh")
                                if self._bull_saved < 12:
                                    self._bull_saved += 1
                                    save_debug(fr, geo, cells, None, tag="trau_den", preview=preview)
                            elif bc <= 1 and self._bull_saved < 12:
                                self._bull_saved += 1
                                save_debug(fr, geo, cells, None, tag="trau_sap", preview=preview)
                            self._bull_cnt = bc
                        if pending is not None:
                            pending.update({"score_now": o["score"], "energy_now": en[0] if en else None, "bull": bc})
                            self._score_log(pending)
                            pending = None
                # ---- kỹ năng ----
                if self._skill_fail >= 3 and self.moves - self._skill_fail_move >= 25:
                    self._skill_fail = 2                              # 3 lần hụt không được khoá kỹ năng cả ván (cứu mạng duy nhất): sau 25 hiệp cho thử lại
                if (self.use_skill and not self.test and self._energy is not None and self._energy >= self._cost()
                        and self._skill_fail < 3 and self.skill_kinds):
                    ch = self._choose_skill(bars, preview, self._blocked)
                    if ch is not None:
                        gain, cand, bsc, why = ch
                        idx, k, it3, freeze, spts, scl = cand
                        tb = bars[idx]
                        self.log("info", f"Animal: DÙNG KỸ NĂNG [{why}] {NAMES.get(k, k)} ở hàng {tb.row} cột {tb.col} (dài {tb.length}) - {SKILL_TEXT.get(k, '')}"
                                         f" | giá trị sau kỹ năng {gain:.0f} | điểm ăn ngay {spts:.0f} | năng lượng {self._energy} | hiệp {self.moves}")
                        e_before = self._energy
                        need_before = self._cost()
                        save_debug(fr, geo, cells, None, tag="skill_truoc", preview=preview)
                        if not self._do_skill(fr, geo, tb):
                            self._skill_fail += 1
                            self._skill_fail_move = self.moves
                            self.log("warn", f"Animal: kỹ năng không kích hoạt được (không có hộp thoại Xác nhận) {self._skill_fail}/3")
                            fr, geo, cells, bars = self._read_stable()
                            continue
                        self._skill_used += 1
                        self._skill_cd_until = self.moves + self.skill_cooldown
                        if k == "K":
                            self._freeze_left = FREEZE_TURNS          # kỹ năng KHÔNG tốn hiệp; mặc định 3, số thật đọc từ bong bóng ngay dưới
                        self.sleep(self.skill_wait)
                        if k == "K":
                            fz = read_freeze_count(self._shot())
                            if fz:
                                self._freeze_left = fz
                                self.log("info", f"Animal: Gấu đóng băng - game báo ra đông sau {fz} lần di chuyển")
                        fr3, geo3, cells3, bars3 = self._read_stable()
                        en3 = read_energy(fr3, geo3)
                        changed = _loose(bars3) != lsig
                        dropped = (en3 is not None and en3[0] <= e_before - need_before // 2)
                        if en3 is not None and en3[1]:
                            self._need = en3[1]
                        save_debug(fr3, geo3, cells3, None, tag="skill_sau", preview=read_preview(fr3, geo3))
                        self._score_log({"t": time.strftime("%H:%M:%S"), "skill": k, "bar": [tb.row, tb.col, tb.length], "pred_pts": round(spts, 1),
                                         "energy_before": e_before, "energy_after": en3[0] if en3 else None, "changed": changed,
                                         "before": cells_text(cells), "pred": cells_text(_to_cells([Bar(*t) for t in it3])), "after": cells_text(cells3)},
                                        name="skill_log.jsonl")
                        if not changed and not dropped and k != "K":
                            self._skill_fail += 1
                            self._skill_fail_move = self.moves
                            self.log("warn", f"Animal: kỹ năng KHÔNG có tác dụng (bàn không đổi, năng lượng không giảm) {self._skill_fail}/3")
                        else:
                            self._skill_fail = 0
                            self._energy = en3[0] if en3 else e_before - need_before
                            pred = ([Bar(*t) for t in it3], ("skill", k, tb.row, tb.col), scl)
                            last_move, last_cleared, last_pts = ("skill", k, tb.row, tb.col), [], spts
                            if k == "K":
                                pred = None                           # đóng băng: không rõ bàn đổi thế nào, chỉ ghi log
                        fr, geo, cells, bars = fr3, geo3, cells3, bars3
                        continue
                if not path:
                    if self.test:
                        self.log("warn", "Animal TEST: KẸT - không còn nước đi nào")
                        return True
                    return self._stop_dead("HẾT NƯỚC ĐI", fr, geo, cells, preview)
                if dead_now and self.stop_on_death and not self.test:
                    return self._stop_dead("MỌI NƯỚC ĐỀU THUA Ở HIỆP KẾ", fr, geo, cells, preview)
                self.log("info", f"Animal hiệp {self.moves + 1}: thanh hàng {r} cột {c0} (dài {ln}) -> cột {nc} (điểm {score:.0f}, {len(bars)} thanh, xem trước {preview}, "
                                 f"trâu sau {self._bull_cnt} hiệp, năng lượng {self._energy}, {think:.1f}s)")
                if self.test or self.debug:
                    p = save_debug(fr, geo, cells, path[0], preview=preview)
                    if self.test:
                        o = self._ocr_all(fr, geo)
                        extra = f"\nĐiểm {o['score']} | năng lượng {o['energy']} | trâu tấn công sau {o['bull']} hiệp"
                        if self.use_skill and o["energy"] and o["energy"][0] >= (o["energy"][1] or self.skill_cost):
                            ch = self._choose_skill(bars, preview, self._blocked)
                            if ch:
                                tb = bars[ch[1][0]]
                                extra += f"\nKỹ năng SẼ DÙNG [{ch[3]}]: {NAMES.get(ch[1][1])} ở hàng {tb.row} cột {tb.col} (giá trị sau {ch[0]:.0f}, ăn ngay {ch[1][4]:.0f} điểm)"
                            else:
                                extra += "\nKỹ năng: đủ năng lượng nhưng CHƯA CẦN dùng (còn nước đi và chưa chắc thua lượt sau) - để dành"
                        self.log("info", "Animal TEST - bàn nhận diện:\n" + cells_text(cells) + f"\nXem trước hàng mới: {preview}\nChuỗi nước: {path}" + extra + (f"\nẢnh debug: {p}" if p else ""))
                        return True
                items = [(b.row, b.col, b.length, b.kind) for b in bars]
                idx = next(i for i, t in enumerate(items) if (t[0], t[1], t[2]) == (r, c0, ln))
                nb, pts, dead, cl, _eat = step_state_full(items, idx, nc, preview)
                self._last_rem = _eat
                pred = ([Bar(*t) for t in nb], (r, c0, ln, nc), cl)
                last_move = (r, c0, ln, nc)
                last_pts = pts
                mv_items = [(r_, (nc if i_ == idx else c_), l_, k_) for i_, (r_, c_, l_, k_) in enumerate(items)]
                last_cleared = [t for t in _settle_items(mv_items)[2]]
                if dead:
                    self.log("warn", "Animal: mọi nước đều dẫn tới THUA ở hiệp kế - vẫn đi nước tốt nhất")
                half = (ln - 1) * geo.pitch_x / 2.0
                self.adb.swipe_px(geo.cx(c0) + half, geo.cy(r), geo.cx(nc) + half, geo.cy(r), self.drag_ms)
                self.moves += 1
                if self._freeze_left > 0:
                    self._freeze_left -= 1
                if self._energy is not None:
                    self._energy += int(round(pts))
                self.sleep(self.settle_s)
                fr, geo, cells, bars = self._read_stable()
                if self._freeze_left > 0:                          # đồng bộ số lần còn lại với bong bóng của game (3 hoặc 4... không cố định)
                    fz = read_freeze_count(fr)
                    if fz:
                        self._freeze_left = fz
                if _loose(bars) == lsig:
                    stuck += 1
                    self._blocked.add(last_move)
                    self._blocked_sig = lsig
                    pred = None
                    self.log("warn", f"Animal: kéo không ăn (bàn không đổi) {stuck}/{self.stuck_limit} - chặn nước {last_move}")
                    if stuck >= self.stuck_limit:
                        self.log("warn", "Animal: kéo mãi không ăn, dừng (có thể đã thua / thanh bị khoá)")
                        self._exit_save("kéo mãi không ăn")
                        return False
                else:
                    self._tally(self._last_rem)
                    if self.moves % 100 == 0:
                        self._log_stats("mỗi 100 hiệp")
        except _Stop as e:
            self.log("info", f"Animal: dừng ({e})")
            return False


def _to_cells(bars):
    cells = [["."] * COLS for _ in range(ROWS)]
    for b in bars:
        for c in range(b.col, b.col + b.length):
            cells[b.row][c] = b.kind
    return cells


def run_auto_animal_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_animal` (field xem mục 5 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    set_codex(step.get("codex_points"), step.get("codex_next"))          # điểm theo Đồ Giám sau khi nâng cấp (mặc định cấp 1)
    bot = AnimalBot(
        adb, log=log, should_stop=should_stop,
        test=step.get("test", False), max_moves=step.get("max_moves", 0), max_seconds=step.get("max_seconds", 0),
        depth=step.get("depth", 3), beam=step.get("beam", 30), settle_s=step.get("settle_s", 0.9),
        drag_ms=step.get("drag_ms", 260), debug=step.get("debug", False), lost_limit=step.get("lost_limit", 4),
        stable_tries=step.get("stable_tries", 6), stable_gap=step.get("stable_gap", 0.35), verify=step.get("verify", True),
        log_score=step.get("log_score", True), stuck_limit=step.get("stuck_limit", 6),
        use_skill=step.get("use_skill", True), skill_kinds=step.get("skill_kinds", "K"), skill_gain=step.get("skill_gain", 400),
        skill_depth=step.get("skill_depth", 2), skill_cost=step.get("skill_cost", 1000), freeze_danger=step.get("freeze_danger", 3),
        skill_x=step.get("skill_x"), skill_y=step.get("skill_y"), skill_tap_gap=step.get("skill_tap_gap", 0.5),
        skill_wait=step.get("skill_wait", 1.2), preview_wait=step.get("preview_wait", 1.6), stable_max=step.get("stable_max", 6.0),
        recheck=step.get("recheck", True), stop_on_death=step.get("stop_on_death", True),
        skill_danger_row=step.get("skill_danger_row", 2), bull_soon=step.get("bull_soon", 3), skill_cooldown=step.get("skill_cooldown", 0),
        skill_confirm_wait=step.get("skill_confirm_wait", 3.0), skill_anim_wait=step.get("skill_anim_wait", 2.0),
        target_moves=step.get("target_moves", 400), exit_on_stop=step.get("exit_on_stop", True), change_limit=step.get("change_limit", 3),
        exit_on_max=step.get("exit_on_max", False), bear_bull_cells=step.get("bear_bull_cells", 0),
        depth_crowd=step.get("depth_crowd", 6), crowd_row=step.get("crowd_row", 4),
    )
    return bot.run()


if __name__ == "__main__":
    # Kiểm tra nhận diện + nước đi trên ảnh chụp màn hình: python animal_bot.py anh.png
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    img = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
    geo, cells, bars = read_grid(img)
    preview = read_preview(img, geo)
    print(f"Bàn {COLS}x{ROWS}, ô {geo.pitch_x:.1f}x{geo.pitch_y:.1f}px. Ô: .=trống P=hươu R=trâu Y=sư tử B=voi W=ngựa vằn K=gấu O=đà điểu")
    print(cells_text(cells))
    print(f"{len(bars)} thanh:", [(b.row, b.col, b.length, b.kind) for b in bars])
    print("Xem trước hàng mới (cột, dài):", preview, "| khung bàn:", board_visible(img, geo), "| điểm OCR:", read_score(img, geo),
          "| năng lượng:", read_energy(img, geo), "| trâu tấn công sau:", read_bull_count(img, geo), "| có hàng kín:", has_full_row(cells))
    _items = [(b.row, b.col, b.length, b.kind) for b in bars]
    print("Hộp thoại Xác nhận kỹ năng:", find_skill_confirm(img), "| nút Hủy chế độ chọn:", find_select_cancel(img))
    _ch = choose_skill(bars, preview, None, "KYPB")
    print("Nên dùng kỹ năng ngay?", ("CÓ - " + str(_ch[3]) + f" ({NAMES.get(_ch[1][1])} hàng {bars[_ch[1][0]].row} cột {bars[_ch[1][0]].col})") if _ch else "chưa cần (còn nước đi / chưa chắc thua lượt sau)")
    for _c in skill_candidates(_items, "KWOPBY"):
        print(f"  kỹ năng {NAMES.get(_c[1])} thanh #{_c[0]} {_items[_c[0]][:3]}: ăn ngay {_c[4]:.0f} điểm ({_c[5]} hàng), đóng băng={_c[3]}")
    t = time.time()
    path, score = beam_search(bars, 3, 30, preview=preview)
    print("Chuỗi nước (hàng, cột cũ, dài, cột mới):", path, "điểm", round(score, 1), f"({time.time() - t:.1f}s)")
    print("Ảnh debug:", save_debug(img, geo, cells, path[0] if path else None, preview=preview))
