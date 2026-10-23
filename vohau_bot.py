# -*- coding: utf-8 -*-
"""
Bot auto "Võ Hậu Khai Quốc" (ải "Phượng Chiếu Chinh Nhung": hoán đổi khối vuông 7x6 đánh địch) - điều khiển qua ADB,
dùng cho bước `auto_vohau`.

>>> TRẠNG THÁI: nhận diện đúng 126/126 ô trên 3 ảnh chụp 720x1280 (bàn thường, bàn có bom + mũi tên, bàn bị tối khi chọn mục tiêu).
>>> Chưa chạy thử trên LDPlayer thật -> chạy `test: true` trước, rồi chạy thật vài nước xem log.
>>> 2026-10-17: thêm QUÁI (đọc thanh máu, chỉ ô ăn THẲNG CỘT dưới quái mới bắn trúng), chọn mục tiêu kỹ năng bằng cách nhấn vào THANH MÁU quái máu nhiều
    nhất, bảng 5 kỹ năng theo màu nghề, chống kẹt - xem mục 7. Đã kiểm trên 7 ảnh chụp 720x1280 (đọc đúng cả chữ máu a/b).

======================================================================================================
1) LUẬT CHƠI (ảnh "Giới thiệu" + người dùng nói: "chơi giống Công Viên Kỳ Thú, có bom với mũi tên")
======================================================================================================
- Bàn 7 CỘT x 6 HÀNG khối vuông. 5 loại khối khác cả MÀU lẫn HÌNH: xanh dương (thoi) = 'B', xanh lá (tam giác) = 'G', tím (lục giác) = 'P',
  đỏ (ngũ giác) = 'R', cam (bát giác) = 'O'. 5 nghề Trị Thế Năng Thần ở đáy màn hình ứng với 5 màu (biểu tượng khối nhỏ ở góc thẻ).
- 2 khối ĐẶC BIỆT: BOM đen (viền vàng, ngòi lấp lánh) = 'X' và MŨI TÊN 4 HƯỚNG sọc đỏ-vàng = 'A'.
- Hoán đổi 2 khối KỀ NHAU (vuốt từ ô này sang ô kề); xếp 3+ khối cùng màu thành hàng/cột thì loại bỏ, khối trên rơi xuống, khối mới rơi vào.
  Loại khối màu nào thì nghề màu đó đánh địch + nhận năng lượng.
- LUẬT BOM/MŨI TÊN = Y HỆT "Cửa Hàng Kỳ Thú" (người dùng xác nhận 2026-10-14, dùng lại từ candy_bot.py):
  a. Kéo BOM sang ô kề: nổ 3x3 quanh vị trí mới. Kéo MŨI TÊN sang ô kề: xoá cả HÀNG và CỘT của nó.
  b. Kéo bánh đặc biệt vào bánh đặc biệt (tâm = ô đích): BOM+BOM nổ 5x5; MŨI TÊN+MŨI TÊN xoá 3 hàng + 3 cột; BOM+MŨI TÊN xoá 3 đường liền nhau
     THEO CHIỀU KÉO + 1 đường vuông góc (kéo dọc: 3 HÀNG + 1 cột; kéo ngang: 3 CỘT + 1 hàng), kéo vào ô sát mép thì hụt 1 đường.
  c. Ăn ĐÚNG 4 khối thẳng hàng -> sinh BOM; >= 5 thẳng hàng -> MŨI TÊN; hình L hoặc T (3 ngang + 3 dọc cùng loại chung 1 ô) -> MŨI TÊN ở ô giao.
  d. Khối mới rơi NGẪU NHIÊN (mô phỏng: đều 5 màu - ĐOÁN tỉ lệ).
- Thanh năng lượng cam mảnh dưới mỗi thẻ nghề: đầy thì nhấn vào THẺ để thi triển kỹ năng. Mỗi nghề 1 kỹ năng khác nhau; CÓ KỸ NĂNG PHẢI
  CHỌN MỤC TIÊU: sau khi nhấn thẻ, toàn màn hình TỐI lại (chỉ còn quái + thẻ vừa chọn sáng) -> phải nhấn vào QUÁI thì kỹ năng mới tung ra.

======================================================================================================
2) HÌNH HỌC (toạ độ THAM CHIẾU ảnh 720x1280, bot co giãn theo kích thước ảnh) - ĐO trên ảnh thật
======================================================================================================
- Tâm cột x = 75, 169.5, 264, 358, 452, 546, 641 (bước ~94.2); tâm hàng y = 471, 565, 659, 754, 849, 942; vùng bàn `DEFAULT_BOARD` = (28,424)-(688,989).
- 5 thẻ nghề: tâm bấm (95/227/360/492/625, 1080); thanh năng lượng cam ở y=1168 bắt đầu x = 38/170/303/435/568 rộng ~113px; thanh máu xanh ở y~1157;
  biểu tượng màu của nghề ở (68/196/326/457/592, ~1135). Quái ở khoảng (345, 255) - nơi nhấn khi cần chọn mục tiêu (`MONSTER_XY`).

======================================================================================================
3) NHẬN DIỆN (`classify_cell`, `read_grid`) - KHÔNG cần ảnh mẫu, KHÔNG phụ thuộc độ sáng
======================================================================================================
- Mỗi ô: cắt phần giữa (56%), lấy các điểm ảnh ĐỦ BÃO HOÀ (S>90, V>40% độ sáng p95 của ô - nên màn hình bị tối vẫn đúng).
  Ít điểm bão hoà (< 12%) = ô trống/chưa rõ '?'. BOM = phần lớn ô xám nhạt (S<60 từ 50%) + ít điểm bão hoà (< 45%) + sắc vàng.
  MŨI TÊN = có CẢ HAI dải màu đỏ (H<=8/>=172) và vàng (H 16-32), mỗi dải >= 12% điểm bão hoà. Còn lại = khối thường: lấy GÓC MÀU (hue, trung bình
  vòng) gần nhất trong B=100, G=67, P=144, R=6, O=19 (OpenCV 0-179), lệch quá 10 = '?'.
- `_stable_read`: chụp lặp tới khi 2 lần đọc liên tiếp GIỐNG HỆT nhau (và còn tối đa 3 ô '?') = hết hoạt ảnh rơi/ăn.
- Thẻ nghề: `read_energy` (mức đầy thanh năng lượng), `read_hp` (thanh máu xanh, 0 = nghề đã chết), `read_card_kinds` (màu của nghề -> khối nào).
- Màn hình tối (đang chọn mục tiêu): `is_dim` = độ sáng trung vị vùng bàn < `dim_v` (110; bình thường ~182, khi tối ~52).

======================================================================================================
4) THUẬT TOÁN
======================================================================================================
- Mô phỏng đầy đủ như Kỳ Thú (`apply_swap`/`resolve`: đổi chỗ, ăn, sinh bom/mũi tên, combo, rơi, khối mới ngẫu nhiên, dây chuyền).
- Bước 1: xếp hạng mọi nước đổi 2 ô kề nhau bằng `eval_result` (khối ăn x trọng số màu + bom/mũi tên dùng/sinh ra + dây chuyền + số nước còn đi được +
  bom/mũi tên nằm cạnh nhau + thưởng combo AA > XA > XX). Bước 2 (`plan_moves`): lấy `top_k` nước tốt nhất + mọi nước dùng bom/mũi tên, mô phỏng lặp nhiều
  mẫu với khối mới rơi NGẪU NHIÊN trong `think_s` giây, chọn nước có điểm TRUNG BÌNH cao nhất.
- Trọng số màu `hero_weights`: khối màu của nghề còn sống = 1.0; nghề đã chết (thanh máu 0) = `w_dead` (0.4) vì khối đó không đánh được; `w_color` nhân thêm.
- Kỹ năng (`_cast_ready`): mỗi vòng đọc thanh năng lượng, thẻ nào >= `energy_full` (0.92) và còn sống thì NHẤN thẻ; chờ `cast_tap_wait_s`, chụp lại,
  nếu màn hình TỐI (đang chọn mục tiêu) thì NHẤN VÀO QUÁI (`monster_xy`); nếu vẫn tối thì nhấn thêm tối đa `target_tries` lần. Nhấn xong chụp + đọc lại bàn
  (kỹ năng có thể đổi bàn). Không nhấn lại 1 thẻ trong `cast_cooldown_s` (4s). Vòng lặp gặp màn hình tối (kỹ năng treo chờ mục tiêu) cũng tự nhấn quái.

======================================================================================================
5) CHỖ CÒN ĐOÁN
======================================================================================================
- Tỉ lệ khối mới rơi (coi đều 5 màu); thanh năng lượng "đầy" (>= 92% vạch cam; ảnh mẫu có thẻ đầy đọc 96%); kỹ năng nào cần chọn mục tiêu nào (bot tự dò
  bằng màn hình tối - nếu có kỹ năng làm tối nhưng cần chọn thứ khác ngoài quái thì chưa xử lý); `gravity` không còn (luôn rơi); đọc số hiệp địch đếm ngược
  (x3, x2...) chưa làm; ván có nhiều đợt quái (Đợt 1/1) bot chạy tới khi hết bàn/thoát.

======================================================================================================
7) QUÁI + KỸ NĂNG (MỚI 2026-10-17, người dùng chụp mô tả kỹ năng + giải thích luật bắn)
======================================================================================================
- Quái nằm phía trên bàn, mỗi quái 1 THANH MÁU đỏ (chữ 'a/b' ở giữa): quái thường rộng 3 cột (hàng trước, y~386), boss 5 cột (hàng sau, y~350, bị sprite che
  mép). `read_enemies` tìm thanh bằng màu (đỏ BGR~(66,77,173) + nền xám) rồi tâm chữ = tâm thanh -> các cột quái đứng trên (số LẺ cột); OCR chữ 'a/b' lấy máu
  thật (không có tesseract thì ước từ vạch đỏ). Quái chết = thanh biến mất; hết quái trên sân thì đợt kế tiếp hiện ra (bot đọc lại mỗi nước nên tự theo kịp).
- LUẬT BẮN (người dùng): chỉ khối ăn nằm THẲNG CỘT dưới quái mới bắn lên trúng quái đó; khối ăn ở cột không có quái thì 'sịt' (hụt). Ví dụ ăn 3 ô mà 2 ô
  nằm dưới quái: 2 ô trúng, 1 ô hụt. Bot tính điều này khi chấm nước: mỗi khối ăn = trọng số màu x trọng số CỘT (`col_weights`: cột có quái 1.0 + `w_focus` x
  (1 - tỉ lệ máu quái đó) để ưu tiên quái sắp chết; cột không quái = `w_miss` 0.15). Cột 2 quái chồng nhau (boss 5 cột chồng 2 quái 3 cột): `overlap`='front' =
  quái hàng trước ăn đạn (đo trên ảnh: 2 lính bên ngoài mất máu nhiều hơn boss nhiều) - ĐOÁN, chỉnh bằng field `overlap` nếu thực tế khác.
- Ô sinh/bom/mũi tên/combo vẫn tính như cũ; khối bị bom/mũi tên nổ cũng tính theo cột của khối đó.
- 5 KỸ NĂNG (bảng `SKILLS`; thi triển xong đều NỔ TOÀN BỘ khối cùng màu nghề trên sân): P tím Sát Cơ Bút Mực = đổi 5 khối cùng màu thành bom ngẫu nhiên;
  R đỏ Hổ Uy Chấn Thế = 2100 sát thương TẤT CẢ quái; B lam Đào Lý Mãn Viên = +49 tấn công cả đội 2 hiệp; O vàng Kiếm Ý Đại Hà = 4200 sát thương lên 1 quái
  PHẢI CHỌN; G lục Diệu Thủ Hồi Xuân = hồi 140 máu cả đội kể cả đồng đội chết.
- CHỌN MỤC TIÊU (chỗ từng bị KẸT): nghề thuộc `target_kinds` ('O') hoặc màn hình tối sau khi nhấn thẻ -> nhấn vào THANH MÁU của quái MÁU NHIỀU NHẤT
  (`pick_target`), thử đổi điểm nhấn (thanh máu -> 1/4 trái thanh -> thân quái -> quái khác -> `monster_xy`) tối đa `target_tries` (4) lần; vẫn tối thì nhấn
  LẠI THẺ để huỷ (`cancel_stuck`). Chống nhấn mãi: thẻ vừa nhấn mà vẫn đầy thì nghỉ gấp đôi (tối đa 30s); tối đa 3 lần nhấn thẻ liền nhau rồi bắt buộc đi 1 nước.
- Quy tắc tung: thứ tự `cast_order` ('BPORG': buff trước, hồi máu sau cùng); R/O (`need_enemy_kinds`) chờ `wave_wait_s` (4s) nếu không thấy quái (đang qua
  đợt); G chỉ tung khi có người dưới `heal_below` (0.85) máu hoặc đã chết. Màu nghề đọc từ biểu tượng góc thẻ hay sai khi thẻ sáng viền (tím->đỏ) nên KHOÁ ở lần
  đọc đầu ra đủ 5 màu khác nhau, hoặc khai báo `hero_kinds` ['P','R','B','O','G'].
- Chữ 'x2/x3' cạnh thanh máu: bot KHÔNG dùng (chưa chắc là số đợt hay số lượt trước khi quái đánh); số đợt 'Đợt a/b' chưa đọc.

======================================================================================================
6) FIELD CỦA BƯỚC `auto_vohau` (đều tuỳ chọn)
======================================================================================================
  test (false)        - true = CHẾ ĐỘ TEST: chụp 1 lần, nhận diện, chọn nước, lưu ảnh debug_vohau/, KHÔNG bấm
  board               - [x0, y0, x1, y1] vùng bàn cờ trong ảnh 720x1280 (mặc định DEFAULT_BOARD); rows (6) cols (7) - số hàng / số cột
  swap_any (false)    - true = cho đổi 2 ô BẤT KỲ (không cần kề nhau)
  w_color             - nhân thêm trọng số màu: {"B":1.5,...} hoặc danh sách 5 số theo thứ tự B,G,P,R,O; hero_weight (true) - tự giảm trọng số màu nghề đã chết;
                        w_dead (0.4)
  think_s (1.0)       - số giây suy nghĩ mỗi nước (Monte Carlo); 0 = chỉ xếp hạng 1 lượt; top_k (10) - số nước đưa vào Monte Carlo
  w_clear (1) w_used (2) w_made (6) w_chain (3) w_future (1) w_pair (2) w_aa (30) w_xa (20) w_xx (12) - trọng số chấm điểm (xem `Weights`)
  max_moves (0)       - số nước tối đa (0 = tới khi hết/bị Dừng); max_seconds (0) - giới hạn thời gian
  settle_s (1.2)      - chờ sau mỗi nước trước khi chụp lại; read_gap (0.3) - giãn cách 2 lần chụp so bàn; stable_timeout (8) - tối đa chờ bàn đứng yên
  drag_ms (200)       - thời gian vuốt
  auto_cast (true)    - tự nhấn thẻ khi thanh năng lượng đầy (>= energy_full 0.92) + chọn quái nếu cần; false = không tự nhấn
  monster_xy [x, y]   - toạ độ nhấn vào quái khi cần chọn mục tiêu (ảnh 720x1280, mặc định 345,255); dim_v (110) - ngưỡng độ sáng coi là "màn hình tối"
  cast_tap_wait_s (0.8) - chờ sau khi nhấn thẻ trước khi chụp kiểm tra tối; target_tries (2) - số lần nhấn quái tối đa; cast_wait_s (1.5) - chờ hoạt ảnh kỹ năng
  cast_cooldown_s (4) - không nhấn lại cùng 1 thẻ trong khoảng này
  cards [[x,y],...]   - CHẾ ĐỘ THỦ CÔNG: nếu khai báo thì bỏ qua đọc năng lượng, cứ `cast_every` (2) nước lại nhấn lần lượt các thẻ ở đây (rồi tự xử lý chọn quái)
  lost_limit (4)      - số lần liên tiếp không thấy bàn/không có nước đi thì kết thúc bước
  debug (false)       - lưu ảnh debug_vohau/ mỗi nước (test luôn lưu)
  MỚI (mục 7): w_miss (0.15) w_focus (0.5) overlap ('front'|'narrow'|'all') back_cols (5) ocr_hp (true) | target_kinds ('O') need_enemy_kinds ('OR')
  ready_mode ('glow'|'energy') glow_thr (0.08) - thẻ ĐẦY = có quầng vàng sáng quanh thẻ (thanh 98% chưa chắc đầy)
  cast_order ('BPORG') heal_below (0.85) wave_wait_s (4) cancel_stuck (true) hero_kinds (['P','R','B','O','G']); target_tries nay mặc định 4
  MỚI (2026-10-17, mục 8): cast_min_beams (3) cast_patience (2) kind_tries (3) white_thr (0.6)

======================================================================================================
8) ĐẦY NỘ + THỨ TỰ TUNG KỸ NĂNG (MỚI 2026-10-17)
======================================================================================================
- Thẻ ĐẦY NỘ (`_is_ready`) = thanh nộ >= 85% VÀ (quầng vàng sáng quanh thẻ `read_glow` >= `glow_thr` HOẶC đáy thanh nộ sáng trắng `read_barlight` >= `white_thr`).
  Đo trên 6 ảnh: thẻ đầy quầng 0.11-0.62 / đáy 0.79-1.0; thẻ chưa đầy (kể cả thanh 88-95%) quầng <= 0.04 / đáy 0.33. Hai dấu hiệu độc lập nên quầng nhấp nháy xuống thấp vẫn nhận.
- Màu nghề: icon góc thẻ đọc lại bằng vòng tròn nhỏ + điểm rất bão hoà (`CARD_ICON` đo lại; trước đó lam bị đọc thành lục, lục thành không rõ). Đọc `kind_tries` lần
  không ra đủ 5 màu khác nhau thì dùng `DEFAULT_HERO_KINDS` = tím, đỏ, lam, vàng, lục (đúng 5 tướng người dùng gửi); đội hình khác thì khai báo `hero_kinds`.
- Thứ tự tung (`_cast_ready`): tướng HỒI MÁU (lục) khi có đồng đội ĐÃ CHẾT (thẻ xám) = số 1 (hồi sinh); còn lại theo `cast_order` (B buff trước), cùng hạng thì thẻ nổ được
  nhiều TIA hơn trước (`_beams`: số khối màu đó trên sân x trọng số cột có quái). Kỹ năng tím (không sát thương trực tiếp) chờ tối đa `cast_patience` nước để đủ `cast_min_beams` tia;
  đỏ/vàng/lam có hiệu ứng riêng nên tung ngay khi đầy.

Chạy riêng kiểm tra nhận diện + nước đi trên ảnh chụp màn hình:  python vohau_bot.py anh.png [--board x0 y0 x1 y1] [--rows 6] [--cols 7] [--think 1.0]
"""

from __future__ import annotations

import os
import random
import re
import sys
import time
from dataclasses import dataclass, fields
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ----------------------------------------------------------------------------
# Hằng số hình học (ảnh chuẩn 720x1280) - ĐO trên ảnh thật
# ----------------------------------------------------------------------------
REF_W, REF_H = 720, 1280
DEFAULT_BOARD = (28.0, 424.0, 688.0, 989.0)      # x0, y0, x1, y1 của vùng bàn cờ
DEFAULT_ROWS, DEFAULT_COLS = 6, 7
DEBUG_DIR = "debug_vohau"
INNER = 0.56                                      # tỉ lệ cạnh mảng cắt giữa ô so với cạnh ô (tránh viền/bóng)

KINDS = "BGPRO"                                   # 5 màu: xanh dương, xanh lá, tím, đỏ, cam
SPECIALS = "XA"                                   # X = bom, A = mũi tên 4 hướng
NAMES = {"B": "xanh dương", "G": "xanh lá", "P": "tím", "R": "đỏ", "O": "cam", "X": "bom", "A": "mũi tên"}
HUE_CENTERS = {"B": 100.0, "G": 67.0, "P": 144.0, "R": 6.0, "O": 19.0}     # góc màu OpenCV (0-179), đo trên ảnh thật
HUE_MAX_DIST = 10.0

# 5 thẻ nghề ở đáy màn hình
CARD_CENTERS = ((95.0, 1080.0), (227.0, 1080.0), (360.0, 1080.0), (492.0, 1080.0), (625.0, 1080.0))
CARD_ICON = ((59, 1135), (193, 1135), (325, 1135), (457, 1135), (590, 1135))   # biểu tượng màu nghề
BAR_X0 = (38, 170, 303, 435, 568)                 # điểm đầu thanh năng lượng/thanh máu của từng thẻ
BAR_W = 113
ENERGY_Y = 1168                                   # thanh năng lượng cam mảnh
HP_Y = 1157                                       # thanh máu xanh
CARD_ICON_OLD = ((68, 1135), (196, 1136), (326, 1135), (457, 1135), (592, 1135))   # toạ độ cũ (dự phòng)
DEFAULT_HERO_KINDS = ("P", "R", "B", "O", "G")        # 5 tướng theo thứ tự thẻ (người dùng xác nhận 2026-10-17): tím, đỏ, lam, vàng, lục
BAR_WHITE_MIN = 0.60                              # thanh nộ ĐẦY thì 3 hàng đáy thanh sáng trắng (đo: đầy >= 0.79, chưa đầy 0.33)
READY_ENERGY_MIN = 0.85                           # thẻ chỉ coi là ĐẦY khi thanh nộ >= mức này (chặn quầng sáng còn sót sau khi vừa tung)
# 5 kỹ năng (người dùng chụp mô tả 2026-10-17). Mỗi kỹ năng thi triển xong còn NỔ TOÀN BỘ khối cùng màu nghề trên sân.
SKILLS = {
    "P": ("Sát Cơ Bút Mực", "đổi 5 khối cùng màu thành bom ngẫu nhiên", "none"),
    "R": ("Hổ Uy Chấn Thế", "2100 sát thương lên TẤT CẢ quái", "none"),
    "B": ("Đào Lý Mãn Viên", "tăng tấn công cả đội 2 hiệp", "none"),
    "O": ("Kiếm Ý Đại Hà", "4200 sát thương lên 1 quái do mình CHỌN", "target"),
    "G": ("Diệu Thủ Hồi Xuân", "hồi máu cả đội (cả đồng đội đã chết)", "none"),
}
MONSTER_XY = (345.0, 255.0)
ENEMY_BAND = (300.0, 420.0)                       # dải y (ảnh chuẩn) chứa thanh máu quái: hàng sau ~y350 (boss), hàng trước ~y386                       # nơi nhấn vào quái khi kỹ năng cần chọn mục tiêu

# màu vẽ nhãn khi lưu ảnh debug (BGR)
_LABEL_BGR = {"B": (235, 160, 60), "G": (70, 200, 70), "P": (200, 70, 190), "R": (60, 60, 235), "O": (0, 150, 255),
              "X": (30, 30, 30), "A": (0, 255, 255), "?": (128, 128, 128)}


class _Stop(Exception):
    pass


Grid = List[List[str]]


# ----------------------------------------------------------------------------
# 1) Hình học + nhận diện
# ----------------------------------------------------------------------------
@dataclass
class Geo:
    x0: float
    y0: float
    x1: float
    y1: float
    rows: int
    cols: int
    sx: float
    sy: float

    @property
    def cw(self) -> float:
        return (self.x1 - self.x0) / self.cols

    @property
    def ch(self) -> float:
        return (self.y1 - self.y0) / self.rows

    def cx(self, c) -> float:
        """Toạ độ X (pixel THẬT của khung ảnh) của tâm cột c."""
        return (self.x0 + self.cw * (c + 0.5)) * self.sx

    def cy(self, r) -> float:
        """Toạ độ Y (pixel THẬT của khung ảnh) của tâm hàng r."""
        return (self.y0 + self.ch * (r + 0.5)) * self.sy


def make_geo(frame, board=None, rows=DEFAULT_ROWS, cols=DEFAULT_COLS) -> Geo:
    h, w = frame.shape[:2]
    b = tuple(float(v) for v in (board or DEFAULT_BOARD))
    return Geo(b[0], b[1], b[2], b[3], int(rows), int(cols), w / REF_W, h / REF_H)


def _cell_patch(frame, geo: Geo, r: int, c: int):
    """Mảng cắt giữa ô (r, c) (pixel THẬT)."""
    cx, cy = geo.cx(c), geo.cy(r)
    hw = geo.cw * geo.sx * INNER / 2
    hh = geo.ch * geo.sy * INNER / 2
    x1, x2 = int(max(0, cx - hw)), int(min(frame.shape[1], cx + hw))
    y1, y2 = int(max(0, cy - hh)), int(min(frame.shape[0], cy + hh))
    return frame[y1:y2, x1:x2]


def _hue_dist(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _circ_mean_hue(h: np.ndarray) -> float:
    """Trung bình VÒNG của góc màu OpenCV (0-179) - đúng cả với đỏ nằm hai bên mốc 0."""
    ang = h.astype(np.float64) * (2.0 * np.pi / 180.0)
    m = np.arctan2(np.sin(ang).mean(), np.cos(ang).mean())
    return float((m * 180.0 / (2.0 * np.pi)) % 180.0)


def classify_hsv(hsv: np.ndarray) -> str:
    """hsv: mảng (n, 3) float các điểm ảnh của 1 ô -> 'B','G','P','R','O' (khối thường), 'X' bom, 'A' mũi tên, '?' (trống/không rõ)."""
    n = len(hsv)
    if n == 0:
        return "?"
    H, S, V = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    p95 = float(np.percentile(V, 95))
    sat = (S > 90) & (V > 0.4 * p95)
    ns = int(sat.sum())
    satfrac = ns / n
    if satfrac < 0.12 or ns < 20:
        return "?"
    hs = H[sat]
    hm = _circ_mean_hue(hs)
    low_s = float((S < 60).mean())
    if low_s >= 0.5 and satfrac < 0.45 and 14.0 <= hm <= 34.0:
        return "X"
    fr = float((((hs <= 8) | (hs >= 172))).mean())
    fg = float((((hs >= 16) & (hs <= 32))).mean())
    if min(fr, fg) >= 0.12:
        return "A"
    best = min(KINDS, key=lambda k: _hue_dist(hm, HUE_CENTERS[k]))
    return best if _hue_dist(hm, HUE_CENTERS[best]) <= HUE_MAX_DIST else "?"


def classify_cell(patch_bgr) -> str:
    if patch_bgr is None or patch_bgr.size == 0:
        return "?"
    hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    return classify_hsv(hsv)


def read_grid(frame, board=None, rows=DEFAULT_ROWS, cols=DEFAULT_COLS):
    """-> (geo, grid[r][c] = 'B','G','P','R','O','X','A' hoặc '?')."""
    geo = make_geo(frame, board, rows, cols)
    grid = [[classify_cell(_cell_patch(frame, geo, r, c)) for c in range(geo.cols)] for r in range(geo.rows)]
    return geo, grid


def grid_text(grid) -> str:
    return "\n".join(" ".join(row) for row in grid)


def unknown_count(grid) -> int:
    return sum(1 for row in grid for k in row if k == "?")


def _scaled(frame):
    h, w = frame.shape[:2]
    return w / REF_W, h / REF_H


def read_energy(frame) -> List[float]:
    """Mức đầy 0..1 của thanh năng lượng cam dưới từng thẻ nghề (đếm điểm ảnh CAM trên hàng ENERGY_Y / BAR_W). Thẻ không thấy -> 0.
    (Khi màn hình bị tối thì đọc ra ~0 - chỉ dùng lúc sáng.)"""
    sx, sy = _scaled(frame)
    h = frame.shape[0]
    out = []
    ys = [int(ENERGY_Y * sy) + d for d in (-1, 0, 1)]
    for x0 in BAR_X0:
        xa, xb = int(x0 * sx), int((x0 + BAR_W) * sx)
        best = 0.0
        for y in ys:
            if not (0 <= y < h) or xb <= xa:
                continue
            seg = cv2.cvtColor(frame[y:y + 1, xa:xb], cv2.COLOR_BGR2HSV).reshape(-1, 3)
            orange = (seg[:, 0] >= 8) & (seg[:, 0] <= 25) & (seg[:, 1] > 140) & (seg[:, 2] > 200)
            best = max(best, float(orange.sum()) / max(1, xb - xa))
        out.append(min(1.0, best))
    return out


CARD_X0 = (35, 167, 300, 432, 565)                # mép trái từng thẻ nghề (ảnh chuẩn); thẻ rộng ~120, cao y 1015-1172


def read_glow(frame) -> List[float]:
    """Độ SÁNG VIỀN VÀNG quanh từng thẻ nghề 0..1: thẻ ĐẦY năng lượng (sẵn sàng tung kỹ năng) có quầng vàng sáng xung quanh, thẻ chưa đầy chỉ có
    viền kem mỏng. Đo trên ảnh: thẻ sáng 0.11-0.55 (quầng nhấp nháy), thẻ chưa đầy <= 0.04. (Thanh năng lượng đọc 98-99% vẫn có thể CHƯA đầy.)"""
    sx, sy = _scaled(frame)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    out = []
    for x in CARD_X0:
        x1, y0, y1 = x + 120, 1015, 1172
        bands = [(y0 - 9, y0 - 2, x + 8, x1 - 8), (y1 + 2, y1 + 9, x + 8, x1 - 8), (y0 + 10, y1 - 10, x - 9, x - 2), (y0 + 10, y1 - 10, x1 + 2, x1 + 9)]
        best = 0.0
        for (ya, yb, xa, xb) in bands:
            a = hsv[int(ya * sy):int(yb * sy), int(max(0, xa) * sx):int(xb * sx)].reshape(-1, 3)
            if len(a) == 0:
                continue
            m = (a[:, 0] >= 14) & (a[:, 0] <= 38) & (a[:, 1] >= 40) & (a[:, 2] >= 165)
            best = max(best, float(m.mean()))
        out.append(best)
    return out


def read_barlight(frame) -> List[float]:
    """Độ SÁNG TRẮNG ở 3 hàng đáy thanh nộ của từng thẻ 0..1: thanh nộ ĐẦY thì sáng trắng (đo >= 0.79), chưa đầy ~0.33 (viền kem của thẻ).
    Dấu hiệu thứ 2 độc lập với quầng vàng (`read_glow`, quầng nhấp nháy có lúc xuống thấp)."""
    sx, sy = _scaled(frame)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    out = []
    for x in CARD_X0:
        ws = hsv[int(1170 * sy):int(1173 * sy), int((x + 8) * sx):int((x + 112) * sx)].reshape(-1, 3)
        out.append(float(((ws[:, 1] < 70) & (ws[:, 2] > 230)).mean()) if ws.size else 0.0)
    return out


def read_hp(frame) -> List[float]:
    """Mức máu 0..1 (xấp xỉ: chữ '300/300' đè lên thanh nên tối đa ~0.9) của từng thẻ nghề; nghề đã chết = 0. Chỉ đúng khi màn hình sáng."""
    sx, sy = _scaled(frame)
    h = frame.shape[0]
    out = []
    for x0 in BAR_X0:
        xa, xb = int(x0 * sx), int((x0 + BAR_W) * sx)
        best = 0.0
        for d in (-3, -1, 0, 1, 3):
            y = int((HP_Y + d) * sy)
            if not (0 <= y < h) or xb <= xa:
                continue
            seg = cv2.cvtColor(frame[y:y + 1, xa:xb], cv2.COLOR_BGR2HSV).reshape(-1, 3)
            g = (seg[:, 0] >= 40) & (seg[:, 0] <= 85) & (seg[:, 1] > 50) & (seg[:, 2] > 50)
            best = max(best, float(g.sum()) / max(1, xb - xa))
        out.append(best)
    return out


def _icon_kind(frame, x, y, sx, sy, strict=True):
    r = max(3, int(6 * min(sx, sy)))
    cx, cy = int(x * sx), int(y * sy)
    p = frame[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1]
    if p.size == 0:
        return None
    hsv = cv2.cvtColor(p, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    sat = (hsv[:, 1] > (110 if strict else 70)) & (hsv[:, 2] > (150 if strict else 50))
    if sat.sum() < (4 if strict else 10):
        return None
    hm = _circ_mean_hue(hsv[sat, 0])
    best = min(KINDS, key=lambda k: _hue_dist(hm, HUE_CENTERS[k]))
    return best if _hue_dist(hm, HUE_CENTERS[best]) <= HUE_MAX_DIST + 4 else None


def read_card_kinds(frame) -> List[Optional[str]]:
    """Màu khối ('B','G','P','R','O') của từng nghề, đọc từ biểu tượng nhỏ ở góc thẻ (None nếu không rõ).
    Chỉ lấy điểm ảnh RẤT bão hoà trong vòng tròn nhỏ (cũ lấy cả chân dung/chữ cấp nên lam->lục, lục->không rõ); không rõ thì thử toạ độ cũ `CARD_ICON_OLD`.
    Đo trên 6 ảnh người dùng: đúng P,R,B,O,G ở 5/6 ảnh (ảnh còn lại bị bảng mô tả kỹ năng che 2 thẻ) - bot còn có dự phòng `DEFAULT_HERO_KINDS`."""
    sx, sy = _scaled(frame)
    out: List[Optional[str]] = []
    for i, (x, y) in enumerate(CARD_ICON):
        k = _icon_kind(frame, x, y, sx, sy, True)
        if k is None:
            ox, oy = CARD_ICON_OLD[i]
            k = _icon_kind(frame, ox, oy, sx, sy, False)
        out.append(k)
    return out


# ----------------------------------------------------------------------------
# 1b) QUÁI: đọc thanh máu -> vị trí, số cột bị bắn trúng, máu (MỚI 2026-10-17)
# ----------------------------------------------------------------------------
@dataclass
class Enemy:
    x0: float          # đầu/cuối thanh máu (toạ độ ảnh chuẩn 720x1280; có thể hụt do sprite che)
    x1: float
    y: float           # tâm dọc thanh máu
    frac: float        # tỉ lệ máu còn 0..1 (từ vùng đỏ nhìn thấy; OCR sửa lại nếu có)
    cx: float          # tâm ngang (tâm cột ở giữa)
    cols: List[int]    # các cột bàn cờ nằm thẳng dưới quái = cột có khối ăn thì "bắn lên" trúng quái này
    hp: float = 0.0    # máu hiện tại (OCR "a/b"; không đọc được thì ước = frac x số cột x 2400)
    hp_max: float = 0.0
    front: bool = False

    @property
    def span(self) -> int:
        return len(self.cols)


def _runs_1d(mask: np.ndarray, gap: int = 0):
    xs = np.flatnonzero(mask)
    if len(xs) == 0:
        return []
    out, s, p = [], int(xs[0]), int(xs[0])
    for x in xs[1:]:
        x = int(x)
        if x - p > gap + 1:
            out.append((s, p))
            s = x
        p = x
    out.append((s, p))
    return out


def _ocr_hp_text(crop_bgr) -> Optional[Tuple[float, float]]:
    """OCR chữ 'a/b' (máu hiện tại / tối đa) trên thanh máu -> (a, b) hoặc None (không có tesseract / không đọc được). Thử vài ngưỡng sáng
    vì chữ trắng nằm đè lên nền đỏ/xám."""
    try:
        import pytesseract
    except Exception:
        return None
    try:
        g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        for thr in (170, 155, 185):
            _, th = cv2.threshold(g, thr, 255, cv2.THRESH_BINARY)
            th = cv2.copyMakeBorder(255 - th, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
            txt = pytesseract.image_to_string(th, config="--psm 7 -c tessedit_char_whitelist=0123456789/")
            m = re.search(r"(\d{1,6})\s*/\s*(\d{3,6})", txt)
            if m:
                cur, mx = float(m.group(1)), float(m.group(2))
                if mx > 0 and cur <= mx:
                    return cur, mx
    except Exception:
        pass
    return None


def read_enemies(frame, board=None, cols=DEFAULT_COLS, ocr=True, y_band=ENEMY_BAND, back_cols=5) -> List[Enemy]:
    """Tìm quái còn sống qua THANH MÁU phía trên bàn (đo trên ảnh thật): thanh = vùng ĐỎ (máu còn, BGR~(66,77,173)) nối với vùng xám tối (máu mất)
    + chữ 'a/b' trắng ở GIỮA thanh (nên tâm chữ = tâm thanh, cả khi sprite che mép thanh như boss).
    Thanh rộng bằng số cột quái đứng: quái thường 3 cột (hàng trước, y~386), boss 5 cột (hàng sau, y~350, bị sprite che nên nhìn thấy hẹp hơn,
    vì vậy thanh hàng sau lấy tối thiểu `back_cols` cột); luôn đứng giữa 1 cột nên số cột là số LẺ. Quái chết = thanh biến mất = không đọc ra."""
    sx, sy = _scaled(frame)
    b = [float(v) for v in (board or DEFAULT_BOARD)]
    cw = (b[2] - b[0]) / cols
    ya, yb = int(y_band[0] * sy), int(y_band[1] * sy)
    reg = frame[ya:yb]
    if reg.size == 0:
        return []
    hsv = cv2.cvtColor(reg, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    red = (((H <= 6) | (H >= 175)) & (S >= 125) & (S <= 185) & (V >= 150) & (V <= 195))
    white = (S < 70) & (V > 180)
    union = red | ((V < 112) & (S < 100)) | white
    gap = max(2, int(10 * sx))
    cand = []                                    # (y, a, c, đầu đỏ, cuối đỏ)
    for yy in range(reg.shape[0]):
        if red[yy].sum() < 3:
            continue
        for (a, c) in _runs_1d(union[yy], gap):
            if (c - a) < 100 * sx:
                continue
            rr = np.flatnonzero(red[yy, a:c + 1])
            if len(rr) >= 3:
                cand.append((yy, a, c, a + int(rr[0]), a + int(rr[-1])))
    bars: List[list] = []
    for yy, a, c, ra, rb in cand:
        for bar in bars:
            if yy - bar["y1"] <= 3 and min(c, bar["c"][-1]) - max(a, bar["a"][-1]) > 0.5 * min(c - a, bar["c"][-1] - bar["a"][-1]):
                bar["y1"] = yy
                bar["a"].append(a)
                bar["c"].append(c)
                bar["ra"].append(ra)
                bar["rb"].append(rb)
                break
        else:
            bars.append({"y0": yy, "y1": yy, "a": [a], "c": [c], "ra": [ra], "rb": [rb]})
    out: List[Enemy] = []
    for bar in bars:
        if len(bar["a"]) < 6:
            continue
        run_a, run_c = float(np.median(bar["a"])) / sx, float(np.median(bar["c"])) / sx
        red_l, red_r = float(np.min(bar["ra"])) / sx, float(np.max(bar["rb"])) / sx
        y0, y1 = bar["y0"], bar["y1"]
        # tâm thanh = tâm cụm chữ trắng 'a/b' gần giữa đoạn nhìn thấy nhất (chữ nằm đúng giữa thanh)
        wcols = np.flatnonzero(white[y0:y1 + 1].sum(axis=0) >= 2)
        centre = (run_a + run_c) / 2.0
        best = None
        for (wa, wc) in _runs_1d(np.isin(np.arange(reg.shape[1]), wcols), int(24 * sx)):
            if 40 * sx <= (wc - wa) <= 150 * sx:
                mid = (wa + wc) / 2.0 / sx
                if run_a - 5 <= mid <= run_c + 5 and (best is None or abs(mid - centre) < abs(best - centre)):
                    best = mid
        cx = best if best is not None else centre
        left_ext = cx - min(red_l, run_a + 40) if red_l - run_a > 12 or True else cx - run_a
        left_ext = cx - red_l
        right_ext = run_c - cx
        half = max(left_ext, right_ext, 1.0)
        n = int(np.ceil(2 * half / cw - 0.25))
        n = max(3, n + (1 - n % 2))              # số LẺ, tối thiểu 3 cột
        e_y = (ya + (y0 + y1) / 2.0) / sy
        c_mid = min(max(int(round((cx - b[0]) / cw - 0.5)), 0), cols - 1)
        out.append(Enemy(cx - half, cx + half, e_y, 0.0, cx, [], 0.0, 0.0, False))
        out[-1].cols = [k for k in range(c_mid - n // 2, c_mid + n // 2 + 1) if 0 <= k < cols]
        out[-1]._n = n                           # type: ignore[attr-defined]
        out[-1]._red = (red_l, red_r, run_a, run_c)  # type: ignore[attr-defined]
    if out:
        ymax = max(e.y for e in out)
        for e in out:
            e.front = abs(e.y - ymax) < 12
            if not e.front and e.span < int(back_cols):                 # hàng sau (boss): sprite che nên nhìn hẹp hơn thật
                cmid = e.cols[len(e.cols) // 2]
                e.cols = [k for k in range(cmid - int(back_cols) // 2, cmid + int(back_cols) // 2 + 1) if 0 <= k < cols]
            red_l, red_r, run_a, run_c = e._red                         # type: ignore[attr-defined]
            width = max(1.0, run_c - red_l)
            e.frac = min(1.0, max(0.0, (red_r - red_l) / width))
            e.hp_max = float(e.span * 2400)                             # ước khi không OCR được (chỉ để so quái nào nhiều máu hơn)
            e.hp = e.frac * e.hp_max
            if ocr:
                cxp = int(e.cx * sx)
                ymid = int(e.y * sy)
                mid = frame[max(0, ymid - 11):ymid + 11, max(0, cxp - int(85 * sx)):min(frame.shape[1], cxp + int(85 * sx))]
                got = _ocr_hp_text(mid) if mid.size else None
                if got:
                    e.hp, e.hp_max = got
                    e.frac = got[0] / got[1]
    out.sort(key=lambda e: e.cx)
    return out


def col_weights(enemies: List[Enemy], cols: int, w_miss: float = 0.15, w_focus: float = 0.5, overlap: str = "front") -> List[float]:
    """Trọng số từng CỘT của bàn: ô ăn nằm thẳng dưới quái thì bắn trúng (1.0 + thưởng nếu quái sắp chết), cột không có quái = bắn hụt (`w_miss`).
    Cột 2 quái chồng nhau: `overlap` = 'front' (quái đứng trước/thanh máu thấp hơn ăn đạn - đo trên ảnh: 2 lính bên ngoài mất máu nhiều hơn boss),
    'narrow' (quái hẹp hơn), 'all' (tính cho mọi quái chồng, lấy trọng số cao nhất)."""
    w = [float(w_miss)] * cols
    if not enemies:
        return [1.0] * cols
    owner: Dict[int, Enemy] = {}
    for c in range(cols):
        cov = [e for e in enemies if c in e.cols]
        if not cov:
            continue
        if overlap == "all":
            best = max(cov, key=lambda e: 1.0 - e.frac)
        elif overlap == "narrow":
            best = min(cov, key=lambda e: (e.span, -e.y))
        else:
            best = max(cov, key=lambda e: (e.y, -e.span))
        owner[c] = best
        w[c] = 1.0 + float(w_focus) * (1.0 - min(1.0, max(0.0, best.frac)))
    return w


def pick_target(enemies: List[Enemy]) -> Optional[Enemy]:
    """Mục tiêu cho kỹ năng chọn 1 quái: quái có MÁU NHIỀU NHẤT (theo yêu cầu người dùng)."""
    return max(enemies, key=lambda e: (e.hp, e.span)) if enemies else None


def is_dim(frame, dim_v: float = 110.0, board=None) -> bool:
    """True nếu màn hình đang TỐI (kỹ năng đang chờ chọn mục tiêu): độ sáng trung vị vùng bàn cờ < dim_v (bình thường ~182, khi tối ~52)."""
    b = [float(v) for v in (board or DEFAULT_BOARD)]
    sx, sy = _scaled(frame)
    reg = frame[int(b[1] * sy):int(b[3] * sy), int(b[0] * sx):int(b[2] * sx)]
    if reg.size == 0:
        return False
    v = cv2.cvtColor(reg, cv2.COLOR_BGR2HSV)[:, :, 2]
    return float(np.median(v)) < float(dim_v)


# ----------------------------------------------------------------------------
# 2) Mô phỏng (luật Kỳ Thú - xem mục 1 docstring) - bản tổng quát hoá số hàng/cột + 5 màu từ candy_bot.py
# ----------------------------------------------------------------------------
def _dims(g: Grid) -> Tuple[int, int]:
    return len(g), len(g[0])


def _runs(g: Grid):
    """Mọi đoạn >= 3 khối THƯỜNG cùng màu liền nhau (ngang + dọc) -> list (list_ô, loại)."""
    rows, cols = _dims(g)
    out = []
    for r in range(rows):
        c = 0
        while c < cols:
            k = g[r][c]
            if k not in KINDS:
                c += 1
                continue
            e = c
            while e + 1 < cols and g[r][e + 1] == k:
                e += 1
            if e - c + 1 >= 3:
                out.append(([(r, x) for x in range(c, e + 1)], k))
            c = e + 1
    for c in range(cols):
        r = 0
        while r < rows:
            k = g[r][c]
            if k not in KINDS:
                r += 1
                continue
            e = r
            while e + 1 < rows and g[e + 1][c] == k:
                e += 1
            if e - r + 1 >= 3:
                out.append(([(x, c) for x in range(r, e + 1)], k))
            r = e + 1
    return out


def find_matches(g: Grid):
    """Tập ô thuộc hàng/cột >= 3 khối cùng màu THƯỜNG (ô '.', '?', bom/mũi tên không tạo hàng)."""
    hit = set()
    for cells, _ in _runs(g):
        hit.update(cells)
    return hit


def _blast_cells(g: Grid, r, c, bomb_radius=1):
    rows, cols = _dims(g)
    k = g[r][c]
    cells = set()
    if k == "X":
        for dr in range(-bomb_radius, bomb_radius + 1):
            for dc in range(-bomb_radius, bomb_radius + 1):
                if 0 <= r + dr < rows and 0 <= c + dc < cols:
                    cells.add((r + dr, c + dc))
    elif k == "A":
        cells.update((r, x) for x in range(cols))
        cells.update((y, c) for y in range(rows))
    return cells


def _gravity(g: Grid):
    rows, cols = _dims(g)
    for c in range(cols):
        col = [g[r][c] for r in range(rows) if g[r][c] != "."]
        col = ["."] * (rows - len(col)) + col
        for r in range(rows):
            g[r][c] = col[r]


def _refill(g: Grid, rng):
    """Khối mới rơi xuống NGẪU NHIÊN (đều 5 màu thường) vào mọi ô trống."""
    rows, cols = _dims(g)
    for r in range(rows):
        for c in range(cols):
            if g[r][c] == ".":
                g[r][c] = rng.choice(KINDS)


def resolve(g: Grid, first_extra=None, bomb_radius=1, rng=None, swapped=(), weigh=None, acc=None):
    """Ăn + (sinh bom/mũi tên) + rơi + (khối mới ngẫu nhiên nếu có rng) + ăn dây chuyền.
    - Đoạn đúng 4 khối thẳng hàng -> sinh BOM; đoạn >= 5 -> sinh MŨI TÊN; hình L / T -> MŨI TÊN ở ô giao. Chỗ sinh của đoạn thẳng = ô vừa kéo nằm
      trong đoạn, không thì giữa đoạn.
    - first_extra = tập ô đã bị khối đặc biệt kích hoạt ở tầng đầu; rng None = chỉ tính phần đã biết (ô trống bên trên giữ nguyên trống).
    - weigh(màu, cột) -> trọng số 1 khối thường bị ăn ở cột đó (khối ăn thẳng dưới quái mới bắn trúng); tổng cộng dồn vào acc['w'].
    -> (grid_mới, {màu: số khối ăn}, số_tầng, số_khối_đặc_biệt_dùng, hàng_trung_bình_vùng_ăn, số_khối_đặc_biệt_sinh_ra)."""
    g = [row[:] for row in g]
    counts: Dict[str, int] = {}
    layers = specials_used = made = 0
    row_sum = 0.0
    n_cleared = 0
    extra = set(first_extra or ())
    swapped = set(swapped)
    while layers < 14:
        hit = set()
        spawn = {}
        runs = _runs(g)
        hr = [(i, set(c), k) for i, (c, k) in enumerate(runs) if c[0][0] == c[-1][0]]       # đoạn ngang
        vr = [(i, set(c), k) for i, (c, k) in enumerate(runs) if c[0][1] == c[-1][1]]       # đoạn dọc
        in_lt = set()
        for hi, hs, hk in hr:                    # hình L / T (3 ngang + 3 dọc chung 1 ô, cùng màu) -> MŨI TÊN ở ô giao
            for vi, vs, vk in vr:
                if hk == vk:
                    inter = hs & vs
                    if inter:
                        spawn[min(inter)] = "A"
                        in_lt.update((hi, vi))
        for i, (cells, _k) in enumerate(runs):
            hit.update(cells)
            n = len(cells)
            if n >= 4 and i not in in_lt:
                sp = "X" if n == 4 else "A"
                pick = [x for x in cells if x in swapped]
                cell = pick[0] if pick else cells[n // 2]
                if spawn.get(cell) != "A":
                    spawn[cell] = sp
        swapped = set()
        hit |= extra
        extra = set()
        stack = list(hit)                        # bom/mũi tên nằm trong vùng ăn cũng nổ (dây chuyền)
        seen = set(hit)
        while stack:
            r, c = stack.pop()
            if g[r][c] in SPECIALS:
                for cell in _blast_cells(g, r, c, bomb_radius):
                    if cell not in seen:
                        seen.add(cell)
                        stack.append(cell)
        hit = seen
        if not hit:
            break
        layers += 1
        for r, c in hit:
            k = g[r][c]
            if k in KINDS:
                counts[k] = counts.get(k, 0) + 1
                if weigh is not None and acc is not None:
                    acc["w"] = acc.get("w", 0.0) + weigh(k, c)
            elif k in SPECIALS:
                specials_used += 1
            if k != ".":
                n_cleared += 1
                row_sum += r
            g[r][c] = "."
        for (r, c), sp in spawn.items():
            g[r][c] = sp
            made += 1
        _gravity(g)
        if rng is not None:
            _refill(g, rng)
    avg_row = (row_sum / n_cleared) if n_cleared else 0.0
    return g, counts, layers, specials_used, avg_row, made


def _combo_cells(g: Grid, ka, kb, a, b, bomb_radius=1):
    """Kéo 2 khối đặc biệt vào nhau (a = ô bị kéo, b = ô đích, tâm hiệu ứng = b). Luật b ở mục 1 docstring."""
    rows, cols = _dims(g)
    rb, cb_ = b
    horizontal = (a[0] == b[0])
    cells = set()

    def rws(r0, r1):
        for r in range(max(0, r0), min(rows, r1 + 1)):
            cells.update((r, x) for x in range(cols))

    def cls(c0, c1):
        for c in range(max(0, c0), min(cols, c1 + 1)):
            cells.update((y, c) for y in range(rows))

    if ka == "X" and kb == "X":
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                if 0 <= rb + dr < rows and 0 <= cb_ + dc < cols:
                    cells.add((rb + dr, cb_ + dc))
    elif ka == "A" and kb == "A":
        rws(rb - 1, rb + 1)
        cls(cb_ - 1, cb_ + 1)
    else:                                   # bom + mũi tên: 3 đường XẾP LIỀN NHAU THEO CHIỀU KÉO + 1 đường vuông góc
        if horizontal:
            cls(cb_ - 1, cb_ + 1)
            rws(rb, rb)
        else:
            rws(rb - 1, rb + 1)
            cls(cb_, cb_)
    return cells


def apply_swap(g: Grid, a, b, bomb_radius=1, rng=None, weigh=None, acc=None):
    """Kéo khối ở ô a sang ô b rồi mô phỏng. Trả None nếu nước vô hiệu (không ăn được gì). rng != None = có khối mới rơi."""
    (r1, c1), (r2, c2) = a, b
    if g[r1][c1] in ("?", ".") or g[r2][c2] in ("?", "."):
        return None
    if g[r1][c1] == g[r2][c2] and g[r1][c1] not in SPECIALS:
        return None
    if g[r1][c1] in SPECIALS and g[r2][c2] in SPECIALS:
        cells = _combo_cells(g, g[r1][c1], g[r2][c2], a, b, bomb_radius)
        ng = [row[:] for row in g]
        ng[r1][c1] = ng[r2][c2] = "."       # 2 khối đã dùng vào combo, không nổ thêm kiểu đơn
        res = resolve(ng, cells, bomb_radius, rng, weigh=weigh, acc=acc)
        return (res[0], res[1], res[2], res[3] + 2, res[4], res[5])
    ng = [row[:] for row in g]
    ng[r1][c1], ng[r2][c2] = ng[r2][c2], ng[r1][c1]
    extra = set()
    for (r, c) in (a, b):                   # kéo khối đặc biệt sang ô kề = kích hoạt nó tại vị trí MỚI
        if ng[r][c] in SPECIALS:
            extra.add((r, c))
    if not extra and not find_matches(ng):
        return None
    return resolve(ng, extra, bomb_radius, rng, swapped=(a, b), weigh=weigh, acc=acc)


def candidate_swaps(rows, cols, swap_any=False):
    if swap_any:
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        return [(cells[i], cells[j]) for i in range(len(cells)) for j in range(i + 1, len(cells))]
    out = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                out.append(((r, c), (r, c + 1)))
            if r + 1 < rows:
                out.append(((r, c), (r + 1, c)))
    return out


def count_future_moves(g: Grid, cap=6) -> int:
    """Số nước đổi 2 ô kề nhau còn ăn được trên bàn (rẻ: chỉ kiểm tra có hàng 3 hoặc có khối đặc biệt, không mô phỏng đầy đủ). Dừng ở `cap`."""
    rows, cols = _dims(g)
    n = 0
    for (r1, c1), (r2, c2) in candidate_swaps(rows, cols):
        x, y = g[r1][c1], g[r2][c2]
        if x in ("?", ".") or y in ("?", "."):
            continue
        if x == y and x not in SPECIALS:
            continue
        if x in SPECIALS or y in SPECIALS:
            n += 1
        else:
            ng = [row[:] for row in g]
            ng[r1][c1], ng[r2][c2] = y, x
            if find_matches(ng):
                n += 1
        if n >= cap:
            break
    return n


def pair_count(g: Grid) -> int:
    """Số cặp khối đặc biệt nằm cạnh nhau (sẵn sàng ghép combo)."""
    rows, cols = _dims(g)
    n = 0
    for r in range(rows):
        for c in range(cols):
            if g[r][c] in SPECIALS:
                if c + 1 < cols and g[r][c + 1] in SPECIALS:
                    n += 1
                if r + 1 < rows and g[r + 1][c] in SPECIALS:
                    n += 1
    return n


# ----------------------------------------------------------------------------
# 3) Chấm điểm + chọn nước
# ----------------------------------------------------------------------------
@dataclass
class Weights:
    w_clear: float = 1.0       # mỗi khối thường ăn được (x trọng số màu)
    w_used: float = 2.0        # mỗi bom/mũi tên được dùng/nổ
    w_made: float = 6.0        # mỗi bom/mũi tên mới sinh ra
    w_chain: float = 3.0       # mỗi tầng ăn dây chuyền thêm
    w_future: float = 1.0      # mỗi nước còn đi được trên bàn sau đó (tối đa 6)
    w_pair: float = 2.0        # mỗi cặp bom/mũi tên nằm cạnh nhau sau đó
    w_aa: float = 30.0         # combo mũi tên + mũi tên
    w_xa: float = 20.0         # combo bom + mũi tên
    w_xx: float = 12.0         # combo bom + bom


def eval_result(res, a_kind, b_kind, w: Weights, cw: Dict[str, float], acc=None) -> float:
    g2, counts, layers, used, _avg, made = res
    if acc is not None and "w" in acc:       # đã nhân trọng số màu x trọng số CỘT (quái đứng trên cột nào)
        s = w.w_clear * acc["w"]
    else:
        s = w.w_clear * sum(cw.get(k, 1.0) * n for k, n in counts.items())
    s += w.w_used * used + w.w_made * made + w.w_chain * max(0, layers - 1)
    s += w.w_future * count_future_moves(g2, 6) + w.w_pair * pair_count(g2)
    if a_kind in SPECIALS and b_kind in SPECIALS:
        s += w.w_aa if (a_kind == "A" and b_kind == "A") else (w.w_xx if (a_kind == "X" and b_kind == "X") else w.w_xa)
    return s


def plan_moves(grid: Grid, cw: Dict[str, float], w: Optional[Weights] = None, swap_any=False, rng=None, think_s=1.0, top_k=10,
               bomb_radius=1, now=time.time, colw: Optional[List[float]] = None):
    """-> (danh sách (điểm, ô a, ô b, {màu: số khối ăn chắc}) giảm dần theo điểm, số mẫu mô phỏng)."""
    w = w or Weights()
    rng = rng or random.Random()
    rows, cols = _dims(grid)
    weigh = (lambda k, c: cw.get(k, 1.0) * colw[c]) if colw else None
    cand = []
    for a, b in candidate_swaps(rows, cols, swap_any):
        acc = {} if weigh else None
        res = apply_swap(grid, a, b, bomb_radius, None, weigh, acc)
        if res is None:
            continue
        ka, kb = grid[a[0]][a[1]], grid[b[0]][b[1]]
        cand.append((eval_result(res, ka, kb, w, cw, acc), a, b, res[1], ka, kb))
    if not cand:
        return [], 0
    cand.sort(key=lambda m: -m[0])
    keep = cand[:top_k] + [m for m in cand[top_k:] if (m[4] in SPECIALS or m[5] in SPECIALS)][:8]
    if think_s <= 0 or len(keep) == 1:
        return [(m[0], m[1], m[2], m[3]) for m in keep], 0
    sums = [0.0] * len(keep)
    cnt = [0] * len(keep)
    t_end = now() + float(think_s)
    rounds = 0
    while now() < t_end and rounds < 400:
        for i, (_sc, a, b, _c, ka, kb) in enumerate(keep):
            acc = {} if weigh else None
            res = apply_swap(grid, a, b, bomb_radius, rng, weigh, acc)
            if res is None:
                continue
            sums[i] += eval_result(res, ka, kb, w, cw, acc)
            cnt[i] += 1
        rounds += 1
    ranked = [((sums[i] / cnt[i]) if cnt[i] else keep[i][0], keep[i][1], keep[i][2], keep[i][3]) for i in range(len(keep))]
    ranked.sort(key=lambda m: -m[0])
    return ranked, rounds * len(keep)


def hero_weights(kinds, hp, w_dead=0.4, extra=None) -> Dict[str, float]:
    """Trọng số từng màu: nghề còn sống = 1.0, nghề đã chết (thanh máu 0) = w_dead (khối đó không đánh được); `extra` nhân thêm."""
    cw = {k: 1.0 for k in KINDS}
    for k, h in zip(kinds or [], hp or []):
        if k in cw and h is not None and h < 0.05:
            cw[k] = float(w_dead)
    for k, v in (extra or {}).items():
        if k in cw:
            cw[k] *= float(v)
    return cw


def parse_w_color(v) -> Dict[str, float]:
    if not v:
        return {}
    if isinstance(v, dict):
        return {str(k).upper(): float(x) for k, x in v.items() if str(k).upper() in KINDS}
    try:
        return {k: float(x) for k, x in zip(KINDS, v)}
    except Exception:
        return {}


# ----------------------------------------------------------------------------
# 4) Ảnh debug
# ----------------------------------------------------------------------------
def save_debug(frame, geo: Geo, grid, move=None, tag="vohau"):
    """Vẽ lưới + nhãn từng ô lên ảnh, mũi tên nước đi (nếu có) -> debug_vohau/<tag>_<giờ>.png. -> đường dẫn (hoặc None)."""
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        img = frame.copy()
        for r in range(geo.rows):
            for c in range(geo.cols):
                cx, cy = geo.cx(c), geo.cy(r)
                hw, hh = geo.cw * geo.sx / 2, geo.ch * geo.sy / 2
                v = grid[r][c]
                col = _LABEL_BGR.get(v, (128, 128, 128))
                cv2.rectangle(img, (int(cx - hw), int(cy - hh)), (int(cx + hw), int(cy + hh)), col, 2)
                cv2.putText(img, v, (int(cx - 9), int(cy + 9)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 4, cv2.LINE_AA)
                cv2.putText(img, v, (int(cx - 9), int(cy + 9)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2, cv2.LINE_AA)
        if move:
            (r1, c1), (r2, c2) = move
            cv2.arrowedLine(img, (int(geo.cx(c1)), int(geo.cy(r1))), (int(geo.cx(c2)), int(geo.cy(r2))), (0, 255, 255), 4, tipLength=0.35)
        path = os.path.join(DEBUG_DIR, f"{tag}_{time.strftime('%H%M%S')}_{int((time.time() % 1) * 1000):03d}.png")
        cv2.imencode(".png", img)[1].tofile(path)
        return path
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 5) Bot
# ----------------------------------------------------------------------------
class VoHauBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, board=None, rows=DEFAULT_ROWS, cols=DEFAULT_COLS,
                 swap_any=False, w_color=None, hero_weight=True, w_dead=0.4, weights=None, think_s=1.0, top_k=10,
                 max_moves=0, max_seconds=0, settle_s=1.2, read_gap=0.3, stable_timeout=8.0, drag_ms=200,
                 auto_cast=True, energy_full=0.92, monster_xy=None, dim_v=110.0, cast_tap_wait_s=0.8, target_tries=4,
                 cast_wait_s=1.5, cast_cooldown_s=4.0, cards=None, cast_every=2, lost_limit=4, debug=False, seed=None,
                 w_miss=0.15, w_focus=0.5, overlap="front", back_cols=5, ocr_hp=True, target_kinds="O", need_enemy_kinds="OR",
                 cast_order="BPORG", heal_below=0.85, wave_wait_s=4.0, cancel_stuck=True, hero_kinds=None, ready_mode="glow", glow_thr=0.08,
                 cast_min_beams=3.0, cast_patience=2, kind_tries=3, white_thr=BAR_WHITE_MIN,
                 sleep=time.sleep, now=time.time):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test, self.debug = bool(test), bool(debug)
        self.board = tuple(board) if board and len(board) == 4 else None
        self.rows, self.cols = int(rows), int(cols)
        self.swap_any = bool(swap_any)
        self.w_color = parse_w_color(w_color)
        self.hero_weight, self.w_dead = bool(hero_weight), float(w_dead)
        self.w = weights or Weights()
        self.think_s, self.top_k = float(think_s), int(top_k)
        self.max_moves, self.max_seconds = int(max_moves or 0), float(max_seconds or 0)
        self.settle_s, self.read_gap, self.stable_timeout = float(settle_s), float(read_gap), float(stable_timeout)
        self.drag_ms = int(drag_ms)
        self.auto_cast, self.energy_full = bool(auto_cast), float(energy_full)
        self.monster_xy = tuple(float(v) for v in monster_xy[:2]) if monster_xy and len(monster_xy) >= 2 else MONSTER_XY
        self.dim_v = float(dim_v)
        self.cast_tap_wait_s, self.target_tries = float(cast_tap_wait_s), max(1, int(target_tries))
        self.cast_wait_s, self.cast_cooldown_s = float(cast_wait_s), float(cast_cooldown_s)
        self.cards = [(float(p[0]), float(p[1])) for p in (cards or []) if p and len(p) >= 2]
        self.cast_every = int(cast_every or 0)
        self.lost_limit = int(lost_limit)
        self.rng = random.Random(seed)
        self.w_miss, self.w_focus, self.overlap = float(w_miss), float(w_focus), str(overlap)
        self.back_cols, self.ocr_hp = int(back_cols), bool(ocr_hp)
        self.target_kinds = str(target_kinds or "").upper()
        self.need_enemy_kinds = str(need_enemy_kinds or "").upper()
        self.cast_order = str(cast_order or "").upper()
        self.ready_mode, self.glow_thr = str(ready_mode or "glow").lower(), float(glow_thr)
        self.heal_below, self.wave_wait_s, self.cancel_stuck = float(heal_below), float(wave_wait_s), bool(cancel_stuck)
        self.cast_min_beams, self.cast_patience = float(cast_min_beams), int(cast_patience)
        self.kind_tries, self.white_thr = int(kind_tries), float(white_thr)
        self._kind_reads = 0
        self._grid = None
        self._colw: Optional[List[float]] = None
        self._hold: Dict[int, int] = {}                 # số nước thẻ i đã ĐẦY mà bot chưa tung (chờ đủ tia)
        self.enemies: List[Enemy] = []
        self._last_enemy_t = None
        self._locked_kinds: Optional[List[Optional[str]]] = None
        if hero_kinds:
            hk = [str(k).upper() if str(k).upper() in KINDS else None for k in list(hero_kinds)[:5]]
            if len(hk) == 5:
                self._locked_kinds = hk
        self._pending_card: Optional[int] = None
        self._cool: Dict[int, float] = {}               # thời gian nghỉ riêng từng thẻ (tăng gấp đôi nếu vừa nhấn lại mà thanh vẫn đầy = kỹ năng không tung ra)
        self._casts_since_move = 0
        self.max_casts_per_move = 3                      # tối đa số lần nhấn thẻ liền nhau trước khi BẮT BUỘC đi 1 nước (chống kẹt vì nhấn mãi)
        self.sleep, self.now = sleep, now
        self.t0 = now()
        self.moves = 0
        self._last_cast: Dict[int, float] = {}
        self._dim_streak = 0

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

    def _stable_read(self, max_unknown=3):
        """Chụp lặp tới khi 2 lần đọc bàn liên tiếp GIỐNG HỆT nhau (còn tối đa `max_unknown` ô '?'). -> (frame, geo, grid, ổn_định?)."""
        t_end = self.now() + self.stable_timeout
        prev = None
        while True:
            self._check()
            fr = self._shot()
            geo, grid = read_grid(fr, self.board, self.rows, self.cols)
            if prev is not None and grid == prev:
                unk = unknown_count(grid)
                # giống hệt nhau và hoặc đã rõ bàn, hoặc gần như không có bàn (màn hình khác) -> khỏi chờ thêm, để vòng ngoài xử lý "mất bàn"
                if unk <= max_unknown or unk > geo.rows * geo.cols * 0.4:
                    return fr, geo, grid, True
            prev = grid
            if self.now() >= t_end:
                return fr, geo, grid, False
            self.sleep(self.read_gap)

    def _do_swap(self, geo: Geo, a, b):
        (r1, c1), (r2, c2) = a, b
        self.adb.swipe_px(geo.cx(c1), geo.cy(r1), geo.cx(c2), geo.cy(r2), self.drag_ms)

    def _tap_ref(self, frame, xy):
        sx, sy = _scaled(frame)
        self.adb.tap_px(xy[0] * sx, xy[1] * sy)

    def _look_enemies(self, frame) -> List[Enemy]:
        """Đọc quái từ thanh máu; nhớ lại lần đọc gần nhất (màn hình tối/hiệu ứng có thể làm mất thanh máu trong 1 khung)."""
        try:
            es = read_enemies(frame, self.board, self.cols, self.ocr_hp, back_cols=self.back_cols)
        except Exception as ex:                       # không để lỗi đọc quái làm dừng cả bot
            self.log("warn", f"VõHậu: lỗi đọc thanh máu quái: {ex}")
            es = []
        if es:
            self.enemies = es
            self._last_enemy_t = self.now()
        return es

    def _tap_target_points(self, frame, enemies: List[Enemy]) -> List[Tuple[float, float]]:
        """Các điểm thử nhấn để CHỌN quái (ảnh chuẩn): quái nhiều máu nhất trước - nhấn vào THANH MÁU (người dùng: chỉ vào thanh máu là được),
        rồi tới thân quái phía trên thanh máu, rồi các quái còn lại, cuối cùng `monster_xy`."""
        pts: List[Tuple[float, float]] = []
        order = sorted(enemies, key=lambda e: (-e.hp, -e.span))
        for e in order[:1]:
            pts.append((e.cx, e.y))
            pts.append((e.cx - 0.25 * (e.x1 - e.x0), e.y))
            pts.append((e.cx, e.y - 70.0))
        for e in order[1:]:
            pts.append((e.cx, e.y))
        pts.append(self.monster_xy)
        return pts

    def _resolve_target(self, frame, kind=None) -> bool:
        """Chọn mục tiêu cho kỹ năng: khi màn hình TỐI (kỹ năng chờ chọn) hoặc kỹ năng thuộc `target_kinds` thì nhấn vào thanh máu của quái MÁU NHIỀU
        NHẤT (đổi điểm nhấn mỗi lần thử, tối đa `target_tries`). Vẫn tối sau tất cả -> (cancel_stuck) nhấn lại thẻ để huỷ, khỏi kẹt. -> có nhấn không."""
        tapped = False
        fr = frame
        for t in range(self.target_tries):
            dim = is_dim(fr, self.dim_v, self.board)
            if not dim and not (t == 0 and kind is not None and kind in self.target_kinds):
                break
            self._check()
            es = self._look_enemies(fr) or self.enemies
            pts = self._tap_target_points(fr, es)
            xy = pts[min(t, len(pts) - 1)]
            tgt = pick_target(es)
            self.log("info", "VõHậu: chọn mục tiêu kỹ năng" + (f" -> quái {int(tgt.hp)}/{int(tgt.hp_max)} máu (cột {tgt.cols[0] + 1}-{tgt.cols[-1] + 1})" if tgt else " (không thấy thanh máu, nhấn vị trí mặc định)")
                     + f" ở ({xy[0]:.0f},{xy[1]:.0f}) lần {t + 1}/{self.target_tries}")
            self._tap_ref(fr, xy)
            tapped = True
            self.sleep(self.cast_tap_wait_s)
            fr = self._shot()
        if tapped:
            if is_dim(fr, self.dim_v, self.board):
                self.log("warn", "VõHậu: nhấn mục tiêu rồi mà màn hình vẫn tối - kỹ năng chưa tung ra")
                if self.cancel_stuck and self._pending_card is not None:
                    self.log("warn", "VõHậu: nhấn lại thẻ để huỷ chọn mục tiêu (khỏi kẹt)")
                    self._tap_ref(fr, CARD_CENTERS[self._pending_card] if self._pending_card < len(CARD_CENTERS) else (360.0, 1080.0))
                    self.sleep(self.cast_tap_wait_s)
            self.sleep(self.cast_wait_s)
        return tapped

    def _cast_card(self, frame, i, e=None, kind=None):
        """Nhấn thẻ i rồi xử lý chọn mục tiêu nếu cần."""
        nm = SKILLS.get(kind or "", ("", "", ""))[0]
        self.log("info", f"VõHậu: thẻ {i + 1}" + (f" ({NAMES.get(kind, kind)}: {nm})" if nm else "") + (f" đầy năng lượng ({e:.0%})" if e is not None else "") + " -> thi triển kỹ năng")
        prev = self._last_cast.get(i)
        if prev is not None and self.now() - prev < 3 * self._cool.get(i, self.cast_cooldown_s):
            self._cool[i] = min(30.0, self._cool.get(i, self.cast_cooldown_s) * 2)
            self.log("warn", f"VõHậu: thẻ {i + 1} vừa nhấn mà vẫn đầy - nghỉ {self._cool[i]:.0f}s trước khi nhấn lại")
        else:
            self._cool[i] = self.cast_cooldown_s
        self._casts_since_move += 1
        self._pending_card = i
        self._tap_ref(frame, CARD_CENTERS[i] if i < len(CARD_CENTERS) else self.cards[i])
        self._last_cast[i] = self.now()
        self.sleep(self.cast_tap_wait_s)
        fr2 = self._shot()
        tapped = self._resolve_target(fr2, kind)
        self._pending_card = None
        if not tapped:
            self.sleep(self.cast_wait_s)

    def _hero_kinds(self, frame) -> List[Optional[str]]:
        """Màu từng nghề. Chỉ KHOÁ lại ở lần đọc đầu tiên ra đủ 5 màu khác nhau (hoặc theo field `hero_kinds`), các lần sau dùng lại.
        Đọc `kind_tries` lần mà vẫn không ra đủ 5 màu thì dùng thứ tự mặc định `DEFAULT_HERO_KINDS` (tím, đỏ, lam, vàng, lục; kind_tries 0 = không dự phòng)."""
        if self._locked_kinds:
            return self._locked_kinds
        ks = read_card_kinds(frame)
        if all(ks) and len(set(ks)) == 5:
            self._locked_kinds = ks
            self.log("info", "VõHậu: 5 nghề (trái -> phải): " + ", ".join(f"{NAMES[k]} - {SKILLS[k][0]}" for k in ks))
            return ks
        self._kind_reads += 1
        if self.kind_tries > 0 and self._kind_reads >= self.kind_tries:
            self._locked_kinds = list(DEFAULT_HERO_KINDS)
            self.log("warn", f"VõHậu: {self._kind_reads} lần đọc vẫn không ra đủ 5 màu nghề ({ks}) -> dùng thứ tự mặc định "
                             + ", ".join(DEFAULT_HERO_KINDS) + " (khai báo `hero_kinds` nếu đội hình khác)")
            return self._locked_kinds
        return ks

    def _want_cast(self, kind, hp, enemies) -> bool:
        """Có nên thi triển kỹ năng của nghề màu `kind` lúc này không (nghề có năng lượng đầy)."""
        if kind in self.need_enemy_kinds and not enemies:
            # đang qua đợt quái mới (không thấy thanh máu): chờ `wave_wait_s` rồi mới tung, để khỏi bắn vào khoảng không / kẹt chọn mục tiêu
            if self._last_enemy_t is not None and self.now() - self._last_enemy_t < self.wave_wait_s:
                return False
        if kind == "G":                                   # hồi máu: chỉ khi có người thiếu máu hoặc đã chết (hồi sinh)
            full = 0.9                                    # read_hp tối đa ~0.9 vì chữ đè lên thanh
            if hp and all(h >= self.heal_below * full for h in hp):
                return False
        return True

    def _is_ready(self, i, energy, glow, white=None) -> bool:
        """Thẻ i đã ĐẦY? ready_mode 'glow' (mặc định) = thanh nộ >= READY_ENERGY_MIN VÀ (có quầng vàng sáng quanh thẻ HOẶC đáy thanh nộ sáng trắng);
        'energy' = thanh nộ >= energy_full (kiểu cũ, hay nhận nhầm 98%)."""
        if self.ready_mode == "energy":
            return energy >= self.energy_full
        if energy < READY_ENERGY_MIN:
            return False
        return glow[i] >= self.glow_thr or (white is not None and white[i] >= self.white_thr)

    def _beams(self, kind) -> float:
        """Số TIA trúng quái nếu nổ hết khối màu `kind` trên bàn lúc này (mỗi khối 1 tia x trọng số cột `col_weights`; không biết quái = 1/khối)."""
        g = self._grid
        if not g or kind not in KINDS:
            return 0.0
        return sum((self._colw[c] if self._colw and c < len(self._colw) else 1.0) for row in g for c, k in enumerate(row) if k == kind)

    def _cast_ready(self, frame, enemies=None) -> bool:
        """Nhấn MỘT thẻ ĐẦY NỘ + còn sống (không lặp lại 1 thẻ trong `cast_cooldown_s`) và qua được `_want_cast`. -> có nhấn thẻ nào không.
        Thứ tự: tướng HỒI MÁU (G) khi có đồng đội ĐÃ CHẾT = số 1 (hồi sinh); còn lại theo `cast_order` (B buff trước), cùng hạng thì thẻ nổ được NHIỀU TIA hơn
        trước. Kỹ năng tím (P: chỉ đổi 5 khối thành bom + nổ khối Tím, không sát thương trực tiếp) chờ tối đa `cast_patience` nước cho tới khi nổ hết khối Tím
        được >= `cast_min_beams` tia (0 = tắt)."""
        if self._casts_since_move >= self.max_casts_per_move:
            return False
        energies, hp, glow, white = read_energy(frame), read_hp(frame), read_glow(frame), read_barlight(frame)
        kinds = self._hero_kinds(frame)
        enemies = self.enemies if enemies is None else enemies
        dead = [j for j, h in enumerate(hp) if h < 0.05]
        ready = []
        for i, e in enumerate(energies):
            if not self._is_ready(i, e, glow, white) or hp[i] < 0.05 or self.now() - self._last_cast.get(i, -1e9) < self._cool.get(i, self.cast_cooldown_s):
                continue
            k = kinds[i] if i < len(kinds) else None
            if k is not None and not self._want_cast(k, hp, enemies):
                continue
            beams = self._beams(k) if k else 0.0
            if k == "P" and self.cast_min_beams > 0 and beams < self.cast_min_beams and self._hold.get(i, 0) < self.cast_patience:
                self.log("info", f"VõHậu: thẻ {i + 1} (tím) đã đầy nhưng nổ hết khối Tím chỉ được {beams:.1f} tia -> chờ ({self._hold.get(i, 0)}/{self.cast_patience} nước)")
                continue
            if k == "G" and dead:
                pr = -1                                   # có người chết: hồi sinh trước mọi kỹ năng khác
            else:
                pr = self.cast_order.index(k) if (k is not None and k in self.cast_order) else len(self.cast_order)
            ready.append((pr, -beams, i, e, k, beams))
        if not ready:
            return False
        _pr, _nb, i, e, k, beams = min(ready)
        self._check()
        if k == "G" and dead:
            self.log("info", f"VõHậu: tướng {', '.join(str(j + 1) for j in dead)} đã chết -> dùng tướng hồi máu hồi sinh")
        elif k:
            self.log("info", f"VõHậu: thẻ {i + 1} nổ hết khối {NAMES[k]} trên sân = {beams:.1f} tia trúng quái")
        self._hold[i] = 0
        self._cast_card(frame, i, e, k)
        return True

    def _cast_manual(self, frame):
        """Chế độ thủ công (`cards` khai báo): nhấn lần lượt các thẻ ở `cards`, mỗi thẻ xử lý chọn mục tiêu nếu cần."""
        for j, (x, y) in enumerate(self.cards):
            self._check()
            self.log("info", f"VõHậu: nhấn thẻ thủ công {j + 1} ({x:.0f},{y:.0f})")
            self._tap_ref(frame, (x, y))
            self.sleep(self.cast_tap_wait_s)
            fr2 = self._shot()
            self._resolve_target(fr2)
            frame = fr2 if not is_dim(fr2, self.dim_v, self.board) else frame

    def run(self) -> bool:
        lost = 0
        try:
            while True:
                self._check()
                if self.max_moves and self.moves >= self.max_moves:
                    self.log("info", f"VõHậu: đủ {self.moves} nước, dừng")
                    return True
                fr, geo, grid, stable = self._stable_read()
                unk = unknown_count(grid)
                # màn hình TỐI mà vẫn thấy bàn cờ = kỹ năng đang chờ chọn mục tiêu (màn tối không có bàn = thoát ván, KHÔNG nhấn quái);
                # nhấn quái tối đa 3 vòng liền để khỏi lặp vô hạn nếu màn hình tối vì lý do khác
                if self.auto_cast and not self.test and unk <= geo.rows * geo.cols * 0.4 and is_dim(fr, self.dim_v, self.board):
                    if self._dim_streak < 3:
                        self._dim_streak += 1
                        if self._resolve_target(fr):
                            continue
                else:
                    self._dim_streak = 0
                if unk > geo.rows * geo.cols * 0.4:
                    lost += 1
                    self.log("warn", f"VõHậu: không thấy bàn cờ rõ ({unk}/{geo.rows * geo.cols} ô lạ) ({lost}/{self.lost_limit})")
                    if self.test:
                        save_debug(fr, geo, grid)
                        return False
                    if lost >= self.lost_limit:
                        self.log("info", "VõHậu: coi như đã hết lượt/thoát bàn, kết thúc")
                        return True
                    self.sleep(0.8)
                    continue
                if not stable:
                    self.log("warn", f"VõHậu: bàn chưa đứng yên sau {self.stable_timeout:.0f}s ({unk} ô lạ), vẫn thử đi")
                energies = read_energy(fr)
                hp = read_hp(fr)
                kinds = self._hero_kinds(fr)
                es = self._look_enemies(fr)
                colw = col_weights(es, geo.cols, self.w_miss, self.w_focus, self.overlap) if es else None
                self._grid, self._colw = grid, colw
                if self.test:
                    for e in es:
                        self.log("info", f"VõHậu TEST - quái ({e.cx:.0f},{e.y:.0f}) máu {e.hp:.0f}/{e.hp_max:.0f} ({e.frac:.0%}) đứng trên cột {e.cols[0] + 1}-{e.cols[-1] + 1}"
                                         + (" [hàng trước]" if e.front else " [hàng sau]"))
                    if es:
                        t = pick_target(es)
                        self.log("info", f"VõHậu TEST - kỹ năng chọn mục tiêu sẽ nhấn quái máu nhiều nhất: {t.hp:.0f}/{t.hp_max:.0f} tại ({t.cx:.0f},{t.y:.0f})")
                        self.log("info", "VõHậu TEST - trọng số cột (khối ăn thẳng dưới quái mới bắn trúng): " + " ".join(f"{x:.2f}" for x in colw))
                    else:
                        self.log("info", "VõHậu TEST - không thấy thanh máu quái (đang chuyển đợt?) -> mọi cột trọng số 1")
                if self.auto_cast and not self.cards:
                    if self.test:
                        self.log("info", "VõHậu TEST - 5 thẻ (màu nghề / năng lượng / máu): " + ", ".join(
                            f"{k or '?'}/{e:.0%}/{h:.0%}/quầng {g:.2f}/đáy {wh:.2f}{'*' if self._is_ready(j, e, read_glow(fr), read_barlight(fr)) else ''}" for j, (k, e, h, g, wh) in enumerate(zip(kinds, energies, hp, read_glow(fr), read_barlight(fr)))))
                    elif self._cast_ready(fr, es):
                        continue          # kỹ năng có thể đổi bàn -> chụp + đọc lại
                if self.hero_weight:
                    cw = hero_weights(kinds, hp, self.w_dead, self.w_color)
                else:
                    cw = {k: 1.0 for k in KINDS}
                    cw.update(self.w_color)
                ranked, nsamp = plan_moves(grid, cw, self.w, self.swap_any, self.rng, self.think_s, self.top_k, now=self.now, colw=colw)
                if not ranked:
                    lost += 1
                    self.log("warn", f"VõHậu: không có nước ăn nào trên bàn nhìn thấy ({lost}/{self.lost_limit})")
                    if self.test:
                        save_debug(fr, geo, grid)
                        self.log("info", "VõHậu TEST - bàn nhận diện:\n" + grid_text(grid))
                        return False
                    if lost >= self.lost_limit:
                        return False
                    self.sleep(1.0)
                    continue
                lost = 0
                sc, a, b, counts = ranked[0]
                ka, kb = grid[a[0]][a[1]], grid[b[0]][b[1]]
                desc = ", ".join(f"{NAMES[k]} x{n}" for k, n in sorted(counts.items())) or "khối đặc biệt"
                sp = (" [" + NAMES.get(ka, ka) + "+" + NAMES.get(kb, kb) + "]") if (ka in SPECIALS or kb in SPECIALS) else ""
                self.log("info", f"VõHậu nước {self.moves + 1}: đổi ({a[0]},{a[1]}) <-> ({b[0]},{b[1]}){sp} | ăn chắc {desc} | điểm kỳ vọng {sc:.1f} ({nsamp} mẫu)")
                if self.test or self.debug:
                    p = save_debug(fr, geo, grid, (a, b))
                    if self.test:
                        top5 = [(round(m[0], 1), m[1], m[2]) for m in ranked[:5]]
                        self.log("info", "VõHậu TEST - bàn nhận diện:\n" + grid_text(grid)
                                 + f"\n5 nước tốt nhất: {top5}" + (f"\nẢnh debug: {p}" if p else ""))
                        return True
                self._do_swap(geo, a, b)
                self.moves += 1
                self._casts_since_move = 0
                for _j in range(5):
                    self._hold[_j] = self._hold.get(_j, 0) + 1
                self.sleep(self.settle_s)
                if self.cards and self.cast_every > 0 and self.moves % self.cast_every == 0:
                    self._cast_manual(fr)
        except _Stop as e:
            self.log("info", f"VõHậu: dừng ({e})")
            return False


def run_auto_vohau_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_vohau` (field xem mục 6 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    d = Weights()
    w = Weights(**{f.name: float(step.get(f.name, getattr(d, f.name))) for f in fields(Weights)})
    bot = VoHauBot(
        adb, log=log, should_stop=should_stop, test=step.get("test", False), board=step.get("board"),
        rows=step.get("rows", DEFAULT_ROWS), cols=step.get("cols", DEFAULT_COLS), swap_any=step.get("swap_any", False),
        w_color=step.get("w_color"), hero_weight=step.get("hero_weight", True), w_dead=step.get("w_dead", 0.4), weights=w,
        think_s=step.get("think_s", 1.0), top_k=step.get("top_k", 10),
        max_moves=step.get("max_moves", 0), max_seconds=step.get("max_seconds", 0), settle_s=step.get("settle_s", 1.2),
        read_gap=step.get("read_gap", 0.3), stable_timeout=step.get("stable_timeout", 8), drag_ms=step.get("drag_ms", 200),
        auto_cast=step.get("auto_cast", True), energy_full=step.get("energy_full", 0.92), monster_xy=step.get("monster_xy"),
        dim_v=step.get("dim_v", 110), cast_tap_wait_s=step.get("cast_tap_wait_s", 0.8), target_tries=step.get("target_tries", 4),
        cast_wait_s=step.get("cast_wait_s", 1.5), cast_cooldown_s=step.get("cast_cooldown_s", 4.0),
        cards=step.get("cards"), cast_every=step.get("cast_every", 2),
        lost_limit=step.get("lost_limit", 4), debug=step.get("debug", False),
        w_miss=step.get("w_miss", 0.15), w_focus=step.get("w_focus", 0.5), overlap=step.get("overlap", "front"),
        back_cols=step.get("back_cols", 5), ocr_hp=step.get("ocr_hp", True), target_kinds=step.get("target_kinds", "O"),
        need_enemy_kinds=step.get("need_enemy_kinds", "OR"), cast_order=step.get("cast_order", "BPORG"),
        heal_below=step.get("heal_below", 0.85), wave_wait_s=step.get("wave_wait_s", 4.0), cancel_stuck=step.get("cancel_stuck", True),
        hero_kinds=step.get("hero_kinds"), ready_mode=step.get("ready_mode", "glow"), glow_thr=step.get("glow_thr", 0.08),
        cast_min_beams=step.get("cast_min_beams", 3.0), cast_patience=step.get("cast_patience", 2), kind_tries=step.get("kind_tries", 3),
        white_thr=step.get("white_thr", BAR_WHITE_MIN),
    )
    return bot.run()


if __name__ == "__main__":
    # Kiểm tra nhận diện + nước đi trên ảnh chụp màn hình: python vohau_bot.py anh.png [--board x0 y0 x1 y1] [--rows 6] [--cols 7] [--think 1.0]
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    argv = sys.argv[1:]
    img_path = argv[0]
    opts = {"board": None, "rows": DEFAULT_ROWS, "cols": DEFAULT_COLS, "think": 1.0}
    i = 1
    while i < len(argv):
        if argv[i] == "--board" and i + 4 < len(argv):
            opts["board"] = [float(v) for v in argv[i + 1:i + 5]]
            i += 5
        elif argv[i] in ("--rows", "--cols") and i + 1 < len(argv):
            opts[argv[i][2:]] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--think" and i + 1 < len(argv):
            opts["think"] = float(argv[i + 1])
            i += 2
        else:
            i += 1
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    geo, grid = read_grid(img, opts["board"], opts["rows"], opts["cols"])
    print(f"Bàn {geo.cols} cột x {geo.rows} hàng, vùng {geo.x0:.0f},{geo.y0:.0f} - {geo.x1:.0f},{geo.y1:.0f} (ảnh chuẩn 720x1280)")
    print("Ô: B=xanh dương G=xanh lá P=tím R=đỏ O=cam X=bom A=mũi tên ?=không rõ")
    print(grid_text(grid))
    dim = is_dim(img, board=opts["board"])
    print("Màn hình TỐI (đang chọn mục tiêu):", dim)
    kinds, energies, hp = read_card_kinds(img), read_energy(img), read_hp(img)
    print("5 thẻ (màu nghề / năng lượng / máu):", ", ".join(f"{k or '?'}/{e:.0%}/{h:.0%}" for k, e, h in zip(kinds, energies, hp)))
    es = read_enemies(img, opts["board"], opts["cols"])
    print(f"Quái đọc được: {len(es)}")
    for e in es:
        print(f"   tâm ({e.cx:.0f},{e.y:.0f}) máu {e.hp:.0f}/{e.hp_max:.0f} ({e.frac:.0%}) cột {[c + 1 for c in e.cols]} {'hàng trước' if e.front else 'hàng sau'}")
    colw = col_weights(es, opts["cols"]) if es else None
    if es:
        t = pick_target(es)
        print(f"Kỹ năng chọn mục tiêu sẽ nhấn: ({t.cx:.0f},{t.y:.0f}) (quái máu nhiều nhất); trọng số cột:", [round(x, 2) for x in colw])
    cw = hero_weights(kinds, hp)
    ranked, nsamp = plan_moves(grid, cw, Weights(), think_s=opts["think"], colw=colw)
    print(f"{len(ranked)} nước xét ({nsamp} mẫu). Top 5 (điểm, ô a, ô b, khối ăn chắc):")
    for m in ranked[:5]:
        print("  ", round(m[0], 1), m[1], m[2], m[3])
    print("Ảnh debug:", save_debug(img, geo, grid, (ranked[0][1], ranked[0][2]) if ranked else None))
