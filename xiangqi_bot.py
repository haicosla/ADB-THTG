# -*- coding: utf-8 -*-
"""
Bot auto "Cờ Tướng - Đối Thủ Ngang Tài" (game xe sinh tồn, chế độ Luyện Tập) - điều khiển qua ADB, bước `auto_xiangqi`.

>>> VIẾT LẠI 2026-11-16 (xem AI_PROGRESS.md). Nguyên nhân bot cũ đi vào nước chết / không ăn quân / kẹt ở Sổ Tay:
>>>   1. File mẫu chữ templates/xq_kinds.json không có (hoặc nhận sai) -> MỌI quân địch bị coi là XE (`unknown_as="r"`)
>>>      -> tính sai ô nguy hiểm hoàn toàn.
>>>   2. Bot không dùng thông tin GAME TỰ VẼ: khi xe được chọn, game vẽ dấu NGOẶC ở mọi ô xe đi được:
>>>        - ngoặc XANH  = ô đi được và an toàn;
>>>        - ngoặc ĐỎ    = ô đi được nhưng đang bị quân địch ăn (nước chết).
>>>      (đã đối chiếu trên ảnh: ô (hàng 2, cột 7) ngay cạnh quân tốt (2,6) hiện ngoặc đỏ, các ô khác xanh).
>>>   3. Bảng "Sổ Tay Quân Cờ" (hiện ra khi bấm nhầm quân) che bàn: nó có bàn cờ MINI cũng vạch đỏ nên `find_grid` cũ dò
>>>      nhầm bàn mini rồi bấm lung tung. Giờ kiểm tra popup TRƯỚC, bấm nút X (ô vuông xanh góc trên phải) để tắt rồi chơi tiếp.

======================================================================================================
1) GAME (những điều đã biết)
======================================================================================================
- Người chơi chỉ có 1 XE (chữ ĐỎ 車). Bàn 8 CỘT x 9 HÀNG giao điểm, ô vuông, không cung/sông. Quân địch là đĩa gỗ chữ XANH LỤC
  có hình "ma" xanh phía trên (quân: 卒 tốt, 士 sĩ, 象 tượng, 炮 pháo, 馬 mã, 車 xe, 将 tướng).
- Mỗi lượt: xe đi 1 nước (đi thẳng ngang/dọc, gặp quân thì ăn quân đầu tiên và dừng) -> 1 quân địch NGẪU NHIÊN đi.
  Ăn được xe là THUA. "1 vòng" = 1 lượt đi. Sống đủ "Điều kiện vượt ải: Còn N vòng" thì qua ải. Điểm cộng khi ăn quân
  (Sĩ = 10 điểm theo Sổ Tay). Khay phía trên có quân CHỜ + đồng hồ cát = số lượt tới khi chúng hiện ở ô ngẫu nhiên.
- Sổ Tay Quân Cờ (tab Tốt/Sĩ/Tượng/Pháo...): Sĩ đi 1 ô CHÉO, ăn quân ở ô đặt xuống sau khi di chuyển.
- LUẬT TỐT MỚI (cập nhật 2026-11-16): Tốt địch ĐI và ĂN ở cả 4 hướng (tiến, lùi, trái, phải) trong phạm vi 1 ô, tức Tốt kiểm soát
  4 ô liền kề ngang/dọc (đã thấy trên ảnh: tốt (2,6) làm ô (2,7) đỏ, tốt (7,3) làm ô (8,3) và (7,2) đỏ). Không còn hướng tiến cố định.

======================================================================================================
2) CÁCH BOT CHƠI MỖI LƯỢT
======================================================================================================
  a. Chụp -> nếu có bảng Sổ Tay (nền giấy be chiếm giữa màn hình) thì bấm X tắt rồi chụp lại (không tính là lượt).
  a2. (2026-11-16 #11) CHỈ KHI xe ta đã hiện các dấu NGOẶC XANH (+) ở ô xe đi được thì màn mới tính là ỔN ĐỊNH và mới đọc/tính nước đi;
     chưa thấy ngoặc xanh = còn hoạt ảnh (địch đi / quân hiện / hình ma chạy) -> chờ tiếp, không tính. Chờ quá `marks_wait_s` mà vẫn
     không có ngoặc thì chạm xe 1 lần cho game vẽ ngoặc rồi chờ lại; vẫn không có `nomark_limit` lần liên tiếp thì DỪNG + lưu ảnh debug.
     Đã ổn định mà có quân KHÔNG ĐỌC ĐƯỢC loại (hoặc không xác định được xe ta) -> DỪNG, lưu ảnh gốc + ảnh vẽ vào debug_xiangqi/
     (unread_raw_*.png, unread_*.jpg; ô không đọc được có vòng VÀNG) để cắt thêm ảnh mẫu rồi chạy lại.
  b. Dò lưới từ vạch đỏ (chỉ nhận bàn CHÍNH: rộng >= 75% bề ngang màn), tìm đĩa quân, xe mình = chữ đỏ.
  c. Đọc ngoặc xanh/đỏ do game vẽ (`read_marks`). Chưa thấy ngoặc (xe chưa được chọn) -> chạm xe 1 lần để game vẽ.
  d. Ô ĐỎ = bỏ. Ô XANH = an toàn. Ô không đọc được (sát xe bị hình ma che, ô có quân...) -> dùng mô hình luật tự tính.
  e. Trong các ô an toàn: ĂN QUÂN trước (ưu tiên quân giá trị cao), không có thì chọn ô nhiều đường thoát, chiếu được nhiều quân
     (chiếu đôi), ít bị quân MỚI hiện từ khay chiếu trúng (đọc quân trong khay).
  f. Thao tác TỰ HỌC: thử lần lượt "chạm ô đích" -> "chạm góc ô" -> "kéo" -> "chạm xe rồi chạm ô". Nếu sau nước đi mà xe không
     di chuyển hoặc bật Sổ Tay thì đổi cách chạm (ăn quân và đi thường học riêng) và nhớ cho các lần chạy sau.

======================================================================================================
3) FIELD CỦA BƯỚC `auto_xiangqi` (đều tuỳ chọn)
======================================================================================================
  test (false)        - true = TEST: chụp 1 lần, nhận diện, in bàn + ngoặc đọc được + nước đi, lưu ảnh debug, KHÔNG bấm
  max_rounds (0)      - số lượt đi tối đa (0 = tới khi hết ván / bị Dừng)
  max_seconds (0)     - giới hạn thời gian (0 = không giới hạn)
  settle_s (1.3)      - chờ sau mỗi nước (hoạt ảnh địch đi / quân hiện)
  input_mode ("auto") - "auto" = tự học; hoặc ép 1 kiểu: "tap" (chạm ô đích), "tap_corner", "tap_tap" (chạm xe rồi ô đích), "drag"
  unknown_as ("u")    - loại quân coi là gì khi không nhận ra chữ ('u' = quân lạ, giả định ăn các nước NGẮN của tốt/sĩ/tượng/mã/tướng; đừng đặt 'r')
  img_match (0.72)    - điểm khớp tối thiểu khi nhận quân bằng ẢNH tự cắt trong templates/xiangqi/ (xem mục 6)
  min_match (0.68)    - điểm khớp mẫu tối thiểu để chấp nhận loại quân (thấp hơn = coi là quân LẠ 'u', rất thận trọng: ăn cả ô thẳng/chéo/mã/tượng)
  [2026-11-17] THỨ TỰ LƯỢT khi đồng hồ cát = 1: xe đi -> địch đi -> khay THẢ quân (quân khay không đi, không ăn được xe) -> tới lượt xe.
                        Rủi ro khay = xe HẾT Ô AN TOÀN sau khi thả (phạt LOSS x xác suất, giả lập ngẫu nhiên) + chút phạt nếu bị chiếu. Khi số đồng hồ = k > 1 thì
                        tìm sâu cũng trừ rủi ro này ở nước thứ k của xe. Ảnh mẫu số đồng hồ: templates/xiangqi/time_1.png, time_2.png ... (xem load_timer_templates).
  spawn_risk_every_turn (0.3) - hệ số rủi ro quân mới hiện từ khay khi KHÔNG đọc được số đếm ngược của đồng hồ cát (0 nếu khay trống)
  spawn_risk_at_timer (0.6) - khi ĐỌC ĐƯỢC số đồng hồ cát: số = 1 -> nước đi này làm TOÀN BỘ khay hiện ra, rủi ro = xác suất có quân khay hiện
                        đúng ô chiếu xe x hệ số này; số > 1 -> không tính rủi ro khay (chưa có quân nào hiện). Số đọc bằng mẫu ảnh 1..7
  close_popup (true)  - tự tắt bảng Sổ Tay Quân Cờ
  stable_timeout_s (4.0) - tối đa chờ bàn đứng yên trước khi đọc (địch đi / quân hiện / hình ma còn chạy)
  stable_gap_s (0.3)  - nghỉ giữa các lần chụp khi chờ đứng yên
  enemy_wait_s (5.0)  - sau nước của xe, chờ tối đa bấy nhiêu giây cho quân địch ĐI (xe tới đích mà địch chưa đổi chỗ = chưa đọc bàn; 0 = tắt)
  stable_frames (2)   - số khung liền nhau phải cùng vị trí quân + xe mới coi là đứng yên (loại quân chọn theo ĐA SỐ các khung)
  save_shots (true)   - BẬT/TẮT lưu ảnh mỗi nước (xe -> đích, ngoặc, dự đoán) vào debug_xiangqi/step_*.jpg; sai dự đoán lưu thêm miss_*.jpg
                        (GUI: hỏi lúc tạo bước, hoặc chuột phải vào bước -> "📷 Bật/Tắt lưu ảnh dự đoán")
  shot_keep (120)     - giữ tối đa bấy nhiêu ảnh step_*/miss_* (xoá ảnh cũ)
  require_marks (true) - CHỈ tính nước khi xe ta đã hiện ngoặc XANH (+) (xem a2); false = như bản cũ (đọc ngay khi bàn đứng yên)
  marks_wait_s (6.0)  - chờ tối đa bấy nhiêu giây cho ngoặc xanh hiện ra (sau khi địch đã đi) trước khi chạm xe 1 lần
  fast_ready (true)   - [2026-11-18] ngoặc xanh phủ >= `marks_full_ratio` (0.8) số ô trống xe đi được = bàn SẴN SÀNG: đọc NGAY 1 khung, không đợi 2 khung giống nhau
                        và không chờ địch đi; false = như cũ (đợi `stable_frames` khung giống nhau)
  nomark_limit (3)    - số lần liên tiếp (đã chạm xe mà vẫn không thấy ngoặc xanh) thì DỪNG + lưu ảnh debug
  stop_on_unread (true) - có quân địch KHÔNG đọc được loại (hoặc không tìm ra xe ta) thì DỪNG + lưu ảnh vào debug_xiangqi/ thay vì đoán 'u';
                        false = như bản cũ (coi là quân lạ 'u' rồi chơi tiếp)
  unread_retries (4)  - quân KHÔNG đọc được loại (vd. quân tướng có hoạt ảnh) -> chờ + quét lại tối đa bấy nhiêu lần rồi mới DỪNG (0 = dừng ngay như cũ);
                        cũng là số lần thử tối thiểu khi không xác định được xe ta
  unread_retry_wait_s (0.8) - nghỉ giữa các lần quét lại (giây)
  stop_on_missing (true) - [2026-11-17] SAU nước của xe chỉ 1 quân địch đi, nên bàn đọc thiếu >= 2 quân (hoặc thiếu 1 mà không thấy quân nào đi) = có quân bị ĐỌC SÓT
                        (hay gặp: TƯỚNG phát sáng/loé điện nên Hough không thấy vòng tròn). Quét lại `unread_retries` lần, vẫn thiếu thì DỪNG, KHÔNG đi tiếp.
  TRÍ NHỚ quân [2026-11-17] - bot nhớ bàn địch của lượt trước (self.last_good). Quân lượt trước đã đọc chắc mà khung này (a) không đọc được loại -> giữ loại cũ,
                        (b) mất hẳn vòng tròn nhưng ô vẫn còn đĩa sáng (cell_occupied) -> giữ lại; riêng TƯỚNG ngưỡng thấp hơn (MEM_OCC_THR_KING). Log: "giữ quân từ TRÍ NHỚ".
  debug (false)       - lưu ảnh debug_xiangqi/ mỗi lượt (test luôn lưu)
  lost_limit (4)      - số lần liên tiếp không thấy bàn/xe thì kết thúc bước
  search_depth (4)    - ĐỘ SÂU tìm kiếm số nước của xe (1-12; 1 = chỉ nhìn 1 nước như bản cũ). Sâu hơn = thấy chuỗi ăn quân dài hơn
                        nhưng tốn thời gian; bị chặn bởi `search_time_s` nên tầng sâu quá sức sẽ tự bỏ (log báo độ sâu đạt được)
  beam_width (6)      - mỗi tầng chỉ đào sâu tiếp `beam_width` nước TỐT NHẤT của xe (ăn quân / chiếu đôi / độ thoáng cao) để tránh bùng nổ
  search_time_s (3)   - hạn thời gian tìm kiếm cho 1 lượt (giây; 0 = không giới hạn). Tìm theo kiểu sâu dần (tầng 2, 3, ... tới
                        search_depth), hết giờ thì lấy kết quả của tầng sâu nhất đã xong
  capture_slack (10)  - khi tìm sâu, chỉ ăn quân thay nước điểm cao nhất nếu kém không quá chừng này điểm (0 = chỉ theo điểm
                        sâu; tối đa 15, giá trị lớn hơn bị chặn xuống 15 để không dính bẫy tham ăn). Điểm sâu đã trừ nước ăn xong bị kẹt hết đường thoát
  w_skewer (0.3)     - thưởng ĐÒN XIÊN/DỤ (mục 5c): xe dọa quân B mà SAU B cùng đường còn quân C -> B chạy thì C lộ ra cho xe ăn.
                        Điểm = w_skewer x hệ số ăn x giá trị C (0 = tắt, bản cũ không biết đòn này)
  king_blast (true)  - ĂN TƯỚNG xong thì NƯỚC KẾ TIẾP nổ sạch mọi quân cùng HÀNG + CỘT với ô đích (mục 5d): bot chọn ô đích nổ được
                        nhiều giá trị nhất, tính an toàn SAU khi nổ, bỏ qua ngoặc đỏ của game cho nước đó; false = tắt
  w_king_blast (20)  - thưởng thêm cho nước ĂN TƯỚNG (kỳ vọng vụ nổ kế tiếp) để bot ưu tiên ăn tướng
  stop_on_doom (true) - NƯỚC KẾ TIẾP CHẮC CHẾT (mọi nước đi của xe đều nguy hiểm: ngoặc đỏ của game hoặc mô hình luật báo bị ăn)
                        thì bot DỪNG (đọc lại 1 lần cho chắc, lưu ảnh debug_xiangqi/doom_*.jpg, KHÔNG bấm, kết thúc bước, kịch bản chạy tiếp);
                        false = như cũ (vẫn bấm nước ít nguy hiểm nhất)
  search_depth       - cũng chỉnh được ở GUI: tạo bước (menu ♟️ Auto Cờ Tướng) hỏi độ sâu; chuột phải vào bước -> "🎚 Chỉnh độ sâu tìm kiếm"

[2026-11-18 #3] simple_mode (true) - CHẾ ĐỘ ĂN NHANH: không dự đoán nước chết (bỏ rủi ro khay thả quân, địch ngẫu nhiên chiếu, phạt bị chiếu, phạt hết đường
                        ở tầng tìm kiếm). Chỉ đi nước AN TOÀN. Có nước ĂN an toàn là ăn (nhiều nước ăn thì chọn nước có chuỗi ăn tốt nhất khi tìm sâu);
                        không ăn được thì chọn nước chiếu / xiên / fork để lượt sau ăn. false = xử lý kỹ như bản 7.
[2026-11-18 #4] careful_after_rounds (120) / careful_min_pieces (20): simple_mode CHỈ chạy khi lượt < 120 VÀ bàn <= 20 quân địch. Từ lượt 120 trở đi hoặc bàn > 20
                        quân thì mỗi lượt tự chuyển sang XỬ LÝ KỸ như bản 7 (dự đoán rủi ro khay / bị chiếu / hết đường). 0 = tắt mốc đó.
                        Lưu ý: số lượt đếm theo bot trong lần chạy bước này (chạy lại bước thì đếm lại từ 0).
[2026-11-18 #5] w_simple_doom (600): chế độ ĂN NHANH vẫn trừ P[địch đi ngẫu nhiên làm xe hết ô an toàn] x hệ số này (tránh chết sớm <100 nước). 0 = tắt.
                        careful_capture_slack (45): chế độ XỬ LÝ KỸ (bàn đông quân) vẫn ĂN nếu nước ăn an toàn kém nước tốt nhất không quá chừng này điểm (ăn xe/pháo triệt để hơn).
  rc_many (2), w_rc_base (14), w_rc_adj (10) - ƯU TIÊN DIỆT XE/PHÁO (cap_value): bàn có >= rc_many xe+pháo thì ăn xe/pháo được cộng w_rc_base, thêm w_rc_adj cho
                        mỗi xe/pháo khác đứng CẠNH quân bị ăn (8 ô quanh, tối đa 2) -> dọn cụm xe/pháo trước. rc_many = 0 = tắt.

TÌM KIẾM SÂU (Beam Minimax, mục 5b): lượt của XE = nút Max (bỏ nước vào ô bị chiếu, giữ top `beam_width` nước); lượt của ĐỊCH = nút
phản ứng (game chỉ cho 1 quân NGẪU NHIÊN đi, nhưng bộ tìm kiếm giả định địch thông minh nhất): xe dọa >= 2 quân thì địch cứu quân giá
trị cao nhất (còn quân khác đứng yên cho xe ăn ở lượt sau), dọa 1 quân thì quân đó chạy sang ô xe không ăn được (nếu có). Điểm tích lũy
= tổng điểm quân ăn (chiết khấu `gamma` theo tầng) - phạt bị chiếu + thưởng độ thoáng (mobility) - phạt tắc đường. Không dọa quân nào
thì coi như bàn giữ nguyên (nhánh yên tĩnh cũng bị cắt mạnh ở tầng sâu).

======================================================================================================
6) ẢNH MẪU TỰ CẮT TAY (nhận diện quân)
======================================================================================================
Thư mục `templates/xiangqi/` (tự tạo khi chạy): để ảnh quân bạn tự cắt (cắt ôm vừa đĩa quân, từ ảnh GỐC chưa vẽ) + file
`xq_kinds.json` (mẫu mặt nạ cũ cũng nằm ở đây; file cũ `templates/xq_kinds.json` vẫn được đọc nếu có).
  Tên ảnh = <loại>_<số>.png, loại: r c n p b a k  HOẶC  xe phao ma tot tuong(=tượng 象) si vua(=tướng 将). Ví dụ b_1.png, a_2.png, xe_1.png.
  XE CỦA TA (xe chữ ĐỎ) cũng có mẫu riêng: ta_1.png (hoặc xe_ta_1.png, xe_do_1.png, minh_1.png, x_1.png) - cắt cả lúc xe đứng yên lẫn lúc
  được chọn (có ngoặc/tia sáng). Lưu ý xe_1.png là xe ĐỊCH. Có mẫu xe ta thì bot nhận xe bằng ảnh trước, không bị nhầm quân địch.
  Nên cắt 3-5 ảnh mỗi loại, ở các ô khác nhau; ảnh cắt từ màn 720 rộng (bước lưới ~86.7px), màn khác tự co giãn.
Thứ tự nhận 1 quân: (1) khớp ẢNH mẫu (điểm >= img_match và hơn loại thứ 2 >= 0.04) -> (2) KHÔNG nhận được bằng ảnh thì dùng
cách cũ (mẫu mặt nạ + json, điểm >= min_match) -> (3) vẫn không thì coi là quân LẠ 'u'. Thêm/sửa ảnh KHÔNG cần khởi động lại.

Chạy riêng kiểm tra 1 ảnh:  python xiangqi_bot.py anh.png [--depth 4..8] [--beam N] [--time giây]
Thêm mẫu chữ:               python xiangqi_bot.py anh.png <hàng> <cột> <loại: r c n p b a k>
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

ROWS, COLS = 9, 8
MASK_S = 40
TEMPLATE_DIR = os.path.join("templates", "xiangqi")          # THƯ MỤC MẪU: ảnh quân tự cắt tay + xq_kinds.json
TEMPLATE_FILE = os.path.join(TEMPLATE_DIR, "xq_kinds.json")
LEGACY_TEMPLATE_FILE = os.path.join("templates", "xq_kinds.json")   # nơi cũ - vẫn đọc nếu có
IMG_MATCH_THR = 0.72     # điểm khớp ảnh mẫu tối thiểu (TM_CCOEFF_NORMED)
IMG_MARGIN = 0.04        # loại tốt nhất phải hơn loại thứ 2 ít nhất bấy nhiêu
IMG_REF_PITCH = 86.7     # bước lưới của ảnh mà bạn cắt mẫu (bàn rộng 720px); màn khác tự co giãn theo bước lưới
_KIND_ALIASES = {"r": "r", "xe": "r", "c": "c", "phao": "c", "n": "n", "ma": "n", "p": "p", "tot": "p",
                 "b": "b", "tuong": "b", "voi": "b", "a": "a", "si": "a", "k": "k", "vua": "k", "tuongsoai": "k"}
DEBUG_DIR = "debug_xiangqi"
ROOK_DEBUG_COLOR = (0, 200, 0)   # màu (BGR) tô XE TA (vòng tròn + chữ X) trên ảnh debug: XANH LÁ (đổi ở đây nếu muốn màu khác)
LOSS = 1000.0
MAX_CAPTURE_SLACK = 15.0   # capture_slack không bao giờ vượt mức này (tránh bẫy tham ăn rồi bị vây kẹt)
MEM_PRIOR_THR = 0.45     # [TRÍ NHỚ] điểm khớp ảnh mẫu tối thiểu để chấp nhận "vẫn là quân cũ ở ô này" (thấp hơn IMG_MATCH_THR vì quân có hoạt ảnh/phát sáng)
MEM_OCC_THR = 0.45       # [TRÍ NHỚ] tỉ lệ pixel "màu đĩa" (kem sáng) trong ô để coi ô còn quân dù Hough không thấy vòng tròn
MEM_OCC_THR_KING = 0.35  # như trên nhưng riêng TƯỚNG (hay phát sáng/loé điện nên đĩa bị nhoè)
GREEN_MIN = 4          # điểm ngoặc xanh tối thiểu (ở bàn rộng 720px; tự co giãn theo độ phân giải)
RED_MIN = 60           # điểm ngoặc đỏ tối thiểu

# r=xe c=pháo n=mã p=tốt b=tượng a=sĩ k=tướng u=quân lạ ; 'X' = xe của người chơi
KIND_NAMES = {"r": "車", "c": "炮", "n": "馬", "p": "卒", "b": "象", "a": "士", "k": "将", "u": "?", "X": "車(ta)"}

# Mẫu chữ dựng sẵn (mặt nạ 40x40 nén hex): 'p' lấy từ quân thật trên bàn 720x1280; các loại khác lấy từ ảnh Hình Tượng
# (độ khớp thấp hơn nên chỉ là dự phòng - nên thêm mẫu thật bằng lệnh CLI). Mẫu trong templates/xq_kinds.json được nạp thêm.
BUILTIN_MASKS = {
    "p": [
        "00000000000000000000000000000000001e0000000000c00000000030000000001c0000000006000000000300000000018000038001c00003c000c0003ffe006000ffff006000ffff003000fc300030000c300010001c780018007efc001800ffce001801e3c2201801ffffe01801ffffe01803ffffc01003e1838010010180001000018000000001800020000180000000018000400001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        "0000000000000000000000000000000000060000000000400000000010000000000c000000000200000000010000000000800000c000400001e00000000fff8020007fff8000007fff8010003f0c000000061c000000071e0008001f3f0008003f6300000070e10000007ffff80000fffff00001ffffe00001f861e00000c06000000000e000000000c000000000c000000000c000000000c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001c000000001e00040001fff8000007fff8020007fff8000003e1800100006180000000e3c0000001f7f0008007f67000800f0e3000800fffff00800fffff00801ffffe00801f0c1c0000080c000000000c000000000c000000000c000000000c0000000008000000000000000000000000000000000000000000000000000100000000040000000020000000000000000000000000000000000",
        "00000000000000000000000000000000007e00000003ffc000000000f0000000001c000000200600000070030000007f8380003ffff9c0003ffff1c0001f878000040f8fc0e00c0fdfe0f00c1df8e0700838780070181ffffe4018fffffe401cff7bfed01cf8307cf810607000f800007000f00c007000700c007001300e003003e007000007c004800007c001c0001f8001f000780001e600780000e7fe7800007fff7800003f9ffc00000f9ff0000003ffc00000007e0000000000000000000000000000000000",
    ],
    "a": [
        "00000000000000000000000000000000007e00000002ffc000000fc7c000001c003c000030000e0000e000030001c000018003800001c001000c00c004000c00e006001c00400c007fc0300c0fffff300e1ffffe30061f9c7c380e0c1c00381e001c00301e001c00381e001c00381c003fc0780807fff0300f07fff0300f07fbf00007000000e007000001e003400003c000600007c000f8001c8000f9003e000073f33e00003fff9c00000fcff0000003cfc00000006e0000000000000000000000000000000000",
    ],
    "b": [
        "00000000000000000000000000000000007200000002ffc000000effe000001c007c000010000e0000e000030001c018018003c07fc0c001bfefc0c0003f1f0060063ffff8400e03fff8000c07fff0300c0fffe030060ff860380607fce0381e1fffe0301e3fff00301e3fff80381c3fede038083f8cfc300b1f1c7e300f1c783e00070070086007800000e003400003c002600003c000f8000e8000f8001e000079803e00003bff9c00000fcfb0000003cfc0000000660000000000000000000000000000000000",
    ],
    "c": [
        "00000000000000000000000000000000007600000003ffc000000ff7f000003cf0fc00006030fe0000c008fe0001800cc38003061c03c002069fc1c00007fff0c0067ffff0800c7cff30f00c7cffe0700c0c3760700c0d3f60781c1fbec0601c3bb1c0601c793780781cf03700f810e03e0cf802003ffcf00e001ff9300f0000f1b007000003e007800007e000c0000fc001f0003dc001f000780000f6007c000067ff7e00003fff7c00000f9ff00000039fc00000007e0000000000000000000000000000000000",
    ],
    "n": [
        "00000000000000000000000000000000007600000002ffc000000effc000001e07f800003803860000e001030001c00fe380038ffff9c0018ffff0c000071fe0e00607fff8400e07fff0100e07fff0700e07ffe03006073ffc380607fffe381e0ffffc301e0f1118301e0999d8381c3991d87808700030700f201ff0b00f001fe010078007e0e007800001e003400003c002600007c000f0002c8000f8003c000073813e00003bffbc00000fcff0000003cfc00000004e0000000000000000000000000000000000",
    ],
    "r": [
        "0000000000000000000000000000000000000000000201c000000300c000000f002400000c000e000000000700010000018003010c80c0018ffffcc0000fff1c600601ffe0600f07fffc000e07bffc300e07fff8300607fff8180407fff8181c0ffff8101c000e00101e01ffff381e1fffff38083f0e7f3008180c04300f000c000007000c004007800000e003800001c003000001c0007000060000f8000c000079001e00003bff9c00000fe790000003e7c0000000660000000000000000000000000000000000",
    ],
    "k": [
        "0000000000000000000000000000000000060000000000000000000010000000000c00000000460000060fe3000066ffe380006cfe61c0006cf7e000007c3fc06000fffc00e008cdf0c0f0080cc7fef0087cfffec018fffffcc0184dc0c0c0184cfcc0f0104cf8c0f000cc00c0f01ccc01c0600ecc3f80200e003f83e00e000007c005000007800180000f8003e000310003e204780001effefd8000fffe7f00007fbffe00003f1ffc00000f9ff0000003ffc00000007e0000000000000000000000000000000000",
    ],
}


@dataclass
class Config:
    pawn_dir: int = 1                 # (KHÔNG CÒN DÙNG từ luật Tốt mới 4 hướng; giữ tên để file khác không lỗi)
    pawn_side_from_row: int = 0       # (KHÔNG CÒN DÙNG, như trên)
    capture_weight: float = 2.0       # hệ số giá trị quân ăn được
    # GIÁ TRỊ QUÂN = mức đóng góp vào việc làm THOÁNG bàn + giữ xe sống (KHÔNG phải điểm game): sống 200 lượt thì điểm chỉ quan trọng ở lượt cuối,
    # còn ăn được NHIỀU quân + bàn thoáng quan trọng hơn ăn quân to. Nên các quân gần ngang nhau; quân đường dài (pháo/xe) và mã nhỉnh hơn một chút
    # vì chúng khoá nhiều ô của xe nhất; tướng cao hơn vì ăn tướng kích hoạt vụ NỔ hàng + cột (phần nổ được tính riêng trong tìm kiếm).
    value: dict = field(default_factory=lambda: {"p": 12, "a": 12, "b": 12, "n": 14, "c": 16, "r": 16, "k": 30, "u": 8})
    # --- tìm kiếm sâu (mục 5b) ---
    search_depth: int = 4             # số nước xe nhìn trước (1-12)
    beam_width: int = 6               # số nước tốt nhất giữ lại ở mỗi tầng (6: đủ chỗ cho cả nước ăn quân lẫn nước chạy về ô thoáng)
    search_time_s: float = 3        # hạn thời gian 1 lượt (0 = không giới hạn)
    gamma: float = 0.7                # chiết khấu điểm mỗi tầng sâu (đoán xa kém chắc hơn vì địch đi NGẪU NHIÊN)
    w_mobility: float = 1.0           # thưởng mỗi ô xe đi tới được (độ thoáng, tối đa 12 ô) - tăng để ưu tiên ô thoáng, giữ cờ sống lâu
    w_blocked: float = 4.0            # phạt mỗi hướng xe bị tắc (sát mép = 1, chỉ đi được 1 ô = 0.5)
    w_check: float = 4.0              # phạt nền NHẸ khi sau lượt địch xe bị chiếu nhưng vẫn còn đường thoát (chỉ mất 1 nước để chạy)
    w_check_exit: float = 12.0        # phạt thêm = w_check_exit / số ô thoát an toàn còn lại: còn nhiều đường thì gần như bỏ qua (còn 4 = 3), chỉ nặng khi sắp hết đường (còn 1 = 12). HẾT đường = THUA (no_safe_penalty/react_mate_cost, không đổi)
                                      # bị chiếu mà KHÔNG còn ô thoát an toàn nào = THUA (-LOSS, cắt nhánh, xem _Search._after)
    simple_mode: bool = True          # [2026-11-18 #3] CHẾ ĐỘ ĂN NHANH: bỏ mọi dự đoán nước chết (rủi ro khay, địch ngẫu nhiên chiếu, phạt bị chiếu); chỉ đi nước AN TOÀN, có nước ăn an toàn là ăn (chọn nước ăn có chuỗi ăn tốt nhất), không thì chiếu/xiên/fork để ăn
    careful_after_rounds: int = 150   # từ lượt thứ N trở đi (đếm lượt của bot trong lần chạy) HOẶC bàn > careful_min_pieces quân địch: tắt simple_mode, xử lý KỸ như bản 7 (có dự đoán rủi ro). 0 = không dùng mốc lượt
    careful_min_pieces: int = 30      # bàn có NHIỀU hơn chừng này quân địch -> xử lý kỹ như bản 7. 0 = không dùng mốc số quân
    rc_many: int = 2                  # bàn có >= chừng này xe + pháo địch thì ưu tiên diệt xe/pháo (xem cap_value)
    w_rc_base: float = 14.0           # cộng giá trị quân khi ăn xe/pháo lúc xe+pháo đông (đơn vị = giá trị quân, nhân capture_weight)
    w_rc_adj: float = 10.0            # cộng thêm cho MỖI xe/pháo khác đứng CẠNH quân bị ăn (8 ô quanh, tối đa 2): ăn cụm xe/pháo trước
    react_checks: bool = False        # địch đi NGẪU NHIÊN: mô hình thêm khả năng 1 quân bất kỳ đi tới ô chiếu xe (xem _Search.reply)
    react_mate_cost: float = 150.0    # chi phí khi 1 quân NGẪU NHIÊN (xác suất p) chiếu xe hết đường thoát: phạt p x chi phí này (không phải LOSS vì chưa chắc quân đó được chọn ăn)
    react_check_cap: int = 6          # số nước chiếu tối đa được chấm độ thoát cho mỗi nút (giữ tốc độ)
    react_check_scale: float = 1.0    # hệ số nhân xác suất 'có quân chiếu xe' (tính thiên về an toàn; kết quả bị chặn <= 1)
    spawn_samples: int = 40           # số lần giả lập thả khay (quân rơi ô trống ngẫu nhiên) để ước lượng xác suất xe HẾT ĐƯỜNG đi sau khi khay hiện
    w_spawn_check: float = 8.0        # phạt nhẹ khi khay hiện ra làm xe bị chiếu (quân khay KHÔNG ăn được xe, chỉ ép xe phải chạy)
    w_fork: float = 8.0               # thưởng dọa >= 2 quân cùng lúc (dọa 1 quân thì địch chắc chắn chạy nên không thưởng) = w_fork x (số quân dọa - 1)
    enemy_doom: bool = True           # phạt P[địch đi NGẪU NHIÊN 1 quân khiến xe HẾT ô an toàn] x w_enemy_doom (xe hết ô an toàn = địch chắc chắn ăn = thua)
    w_enemy_doom: float = 1000.0      # = LOSS. Giả lập (địch chắc chắn ăn xe khi ăn được, 120 ván): bật -> sống TB 88 lượt/thua 79%; tắt -> 79 lượt/87%
    quiet_keep: int = 2               # số nước YÊN TĨNH (không ăn/dọa) tốt nhất (độ thoáng cao) luôn giữ trong beam, kể cả tầng sâu
    no_safe_penalty: float = 1000.0   # xe hết ô an toàn = coi như THUA (bằng LOSS); không bị chiết khấu gamma theo độ sâu
    w_simple_doom: float = 600.0      # [2026-11-18 #5] simple_mode vẫn trừ P[địch đi ngẫu nhiên làm xe HẾT ô an toàn] x hệ số này (chỉ chặn nước chết 1 đường thoát, không dự đoán khay/chiếu) -> ăn nhanh mà ít chết sớm
    careful_capture_slack: float = 25.0  # [2026-11-18 #5] chế độ XỬ LÝ KỸ (bàn đông quân): nước ĂN an toàn kém nước tốt nhất không quá chừng này điểm vẫn ăn (bản cũ chỉ 10-15 nên bỏ lỡ ăn xe/pháo)
    capture_slack: float = 10.0       # tìm sâu: chỉ chọn nước ĂN QUÂN thay nước điểm cao nhất khi kém không quá chừng này điểm (0 = chỉ theo điểm sâu; bị chặn <= MAX_CAPTURE_SLACK)
    # --- đòn XIÊN / DỤ (mục 5c) ---
    w_skewer: float = 0.3             # thưởng khi xe dọa quân B mà SAU B cùng đường còn quân C: B chạy thì C lộ ra cho xe ăn (điểm = w_skewer x giá trị ăn C)
    # --- ăn TƯỚNG xong: nước đi KẾ TIẾP nổ sạch hàng + cột của ô đích (mục 5d) ---
    king_blast: bool = True           # bật xử lý hiệu ứng nổ sau khi ăn tướng
    w_king_blast: float = 20.0        # thưởng thêm khi ĂN TƯỚNG (kỳ vọng nước nổ kế tiếp), cộng vào điểm ăn quân
    spawn_hit: float = 0.6            # đồng hồ cát = 1: rủi ro = P(có quân khay hiện đúng ô chiếu xe) x hệ số này (xem `_spawn_prob`)


# ----------------------------------------------------------------------------
# 1) Dò lưới từ vạch đỏ
# ----------------------------------------------------------------------------
@dataclass
class Grid:
    xs: list
    ys: list
    pitch: float

    def px(self, r, c):
        return self.xs[c], self.ys[r]


def _peaks(v, thr, gap=3):
    idx = np.where(v > thr)[0]
    out, start, prev = [], None, None
    for i in idx:
        if start is None:
            start = i
        elif i - prev > gap:
            out.append((start + prev) / 2.0)
            start = i
        prev = i
    if start is not None:
        out.append((start + prev) / 2.0)
    return out


def _fit_lattice(peaks, n, pitch=None, tol=0.12):
    """Tìm dãy n điểm cách đều khớp nhiều đỉnh nhất. Trả (origin, pitch, số khớp) hoặc None."""
    if not peaks:
        return None
    cand_pitch = [pitch] if pitch else sorted({round(b - a, 1) for a in peaks for b in peaks if b - a > 20})
    best = None
    for p in cand_pitch:
        for a in peaks:
            for k0 in range(0, n):
                origin = a - k0 * p
                if origin < 0:
                    continue
                inl = []
                for kk in range(n):
                    x = origin + kk * p
                    m = [q for q in peaks if abs(q - x) <= tol * p]
                    if m:
                        inl.append((kk, min(m, key=lambda q: abs(q - x))))
                if len(inl) < 2 and not pitch:
                    continue
                if best is None or len(inl) > best[2]:
                    ks = np.array([i[0] for i in inl], float)
                    ps = np.array([i[1] for i in inl], float)
                    if pitch:
                        o2 = float(np.mean(ps - ks * p)); p2 = p
                    elif len(inl) >= 2:
                        p2, o2 = np.polyfit(ks, ps, 1)
                    else:
                        o2, p2 = origin, p
                    best = (float(o2), float(p2), len(inl))
    return best


def find_grid(frame, min_span=0.75) -> Optional[Grid]:
    """Dò bàn CHÍNH. min_span: bề ngang bàn (7 bước) tối thiểu theo tỉ lệ bề ngang ảnh - loại bàn MINI trong Sổ Tay."""
    h, w = frame.shape[:2]
    b, g, r = [frame[:, :, i].astype(int) for i in range(3)]
    red = ((r - g > 60) & (r - b > 60) & (r > 110) & (r < 230) & (g < 110)).astype(np.uint8)
    row_pk = _peaks(red.sum(1), w * 0.30)
    fy = _fit_lattice(row_pk, ROWS)
    if not fy or fy[2] < 6:
        return None
    oy, py, _ = fy
    ys = [oy + i * py for i in range(ROWS)]
    y0, y1 = int(max(0, ys[0] - py * 0.3)), int(min(h, ys[-1] + py * 0.3))
    col_pk = _peaks(red[y0:y1].sum(0), (y1 - y0) * 0.25)
    fx = _fit_lattice(col_pk, COLS, pitch=py, tol=0.15)
    if not fx or fx[2] < 2:
        return None
    ox = fx[0]
    xs = [ox + i * py for i in range(COLS)]
    if xs[-1] > w or xs[0] < 0:
        return None
    if (xs[-1] - xs[0]) < min_span * w:
        return None
    return Grid(xs=xs, ys=ys, pitch=float(py))


# ----------------------------------------------------------------------------
# 2) Bảng Sổ Tay / popup
# ----------------------------------------------------------------------------
def _cream_mask(frame):
    b, g, r = [frame[:, :, i].astype(int) for i in range(3)]
    return (r > 225) & (g > 195) & (b > 150) & (r - b > 30) & (r - b < 85) & (r - g < 35)


def is_popup(frame) -> bool:
    """Có bảng nền giấy be (Sổ Tay Quân Cờ / Hình Tượng...) phủ giữa màn hình không. Bàn gỗ thì cam, không phải be."""
    h, w = frame.shape[:2]
    cm = _cream_mask(frame)
    return float(cm[int(.60 * h):int(.80 * h), int(.10 * w):int(.90 * w)].mean()) > 0.35


def find_close_button(frame):
    """Toạ độ tâm nút X (ô vuông xanh xám ở góc trên phải bảng). Không thấy thì lấy vị trí theo tỉ lệ (0.917, 0.134)."""
    h, w = frame.shape[:2]
    x0, x1, y0, y1 = int(.78 * w), int(.995 * w), int(.06 * h), int(.22 * h)
    box = frame[y0:y1, x0:x1]
    b, g, r = [box[:, :, i].astype(int) for i in range(3)]
    teal = ((g > r + 12) & (g >= b + 3) & (g > 85) & (g < 165) & (r < 140)).astype(np.uint8)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(teal, connectivity=8)
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if area < (0.03 * w) ** 2 or bw > 0.2 * w or bh > 0.2 * w or not (0.6 < bw / max(bh, 1) < 1.7):
            continue
        if best is None or area > best[0]:
            best = (area, cent[i][0] + x0, cent[i][1] + y0)
    if best:
        return float(best[1]), float(best[2]), True
    return 0.917 * w, 0.134 * h, False


# ----------------------------------------------------------------------------
# 3) Ngoặc xanh / đỏ do game vẽ quanh các ô xe đi được
# ----------------------------------------------------------------------------
def read_marks(frame, grid):
    """{(hàng, cột): (điểm xanh, điểm đỏ)} - đếm điểm ảnh ngoặc ở 4 góc mỗi ô (cách tâm 0.12-0.46 bước)."""
    h, w = frame.shape[:2]
    b, g, r = [frame[:, :, i].astype(np.int16) for i in range(3)]
    gm = (g > r + 8) & (g > b + 30) & (g > 110)
    rm = (r > 200) & (r - g > 100) & (r - b > 120)
    p = grid.pitch
    marks = {}
    for rr in range(ROWS):
        for cc in range(COLS):
            x, y = grid.px(rr, cc)
            gs = rs = 0
            for sx in (-1, 1):
                for sy in (-1, 1):
                    xa, xb = sorted((x + sx * p * .12, x + sx * p * .46))
                    ya, yb = sorted((y + sy * p * .12, y + sy * p * .46))
                    xa, xb, ya, yb = max(0, int(xa)), min(w, int(xb)), max(0, int(ya)), min(h, int(yb))
                    if xb > xa and yb > ya:
                        gs += int(gm[ya:yb, xa:xb].sum())
                        rs += int(rm[ya:yb, xa:xb].sum())
            marks[(rr, cc)] = (gs, rs)
    return marks


def overlay_states(marks, grid, skip=None):
    """{ô: 'green'|'red'} chỉ gồm ô đọc được (ô khác = không rõ). skip = ô xe đang đứng (có khung chọn riêng)."""
    sc = (grid.pitch / 86.8) ** 2
    out = {}
    for cell, (gs, rs) in marks.items():
        if cell == skip:
            continue
        if rs >= RED_MIN * sc and rs > gs:
            out[cell] = "red"
        elif gs >= GREEN_MIN * sc and rs < RED_MIN * sc:
            out[cell] = "green"
    return out


def marks_ready2(frame, grid, st):
    """Như marks_ready nhưng thêm độ PHỦ ngoặc: -> (số ô xanh, số ô có ngoặc, số ô xe tới được, số ô TRỐNG xe tới được, số ô trống đã có ngoặc xanh/đỏ).
    [2026-11-18] Ngoặc phủ gần hết các ô trống xe đi được = game đã vẽ xong = bàn SẴN SÀNG (đọc ngay, không cần đợi 2 khung giống nhau / chờ địch đi)."""
    ov = overlay_states(read_marks(frame, grid), grid, skip=st.rook)
    moves = rook_moves(st.board, st.rook)
    empt = [d for d, k in moves if k is None]
    pool = empt or [d for d, _k in moves]
    return (sum(1 for d in pool if ov.get(d) == "green"), sum(1 for d in pool if d in ov), len(pool),
            len(empt), sum(1 for d in empt if d in ov))


def marks_ready(frame, grid, st):
    """Xe ta đã hiện NGOẶC XANH (+) ở các ô xe đi được chưa -> (số ô xanh, số ô có ngoặc xanh/đỏ, số ô xe tới được).
    Chỉ xét ô xe tới được; ưu tiên ô TRỐNG (ô có quân địch có chữ xanh lục dễ bị đọc nhầm là ngoặc xanh). Không có ngoặc xanh nào =
    game còn đang chạy hoạt ảnh (hoặc xe chưa được chọn) -> màn chưa ổn định, chưa được tính nước đi."""
    ov = overlay_states(read_marks(frame, grid), grid, skip=st.rook)
    moves = rook_moves(st.board, st.rook)
    pool = [d for d, k in moves if k is None] or [d for d, _k in moves]
    return (sum(1 for d in pool if ov.get(d) == "green"), sum(1 for d in pool if d in ov), len(pool))


# ----------------------------------------------------------------------------
# 4) Nhận diện quân
# ----------------------------------------------------------------------------
_YY, _XX = np.mgrid[0:MASK_S, 0:MASK_S]
_CM = (((_YY - MASK_S / 2 + .5) ** 2 + (_XX - MASK_S / 2 + .5) ** 2) <= (MASK_S * 0.42) ** 2)


def _patch(frame, x, y, pitch):
    R = int(pitch * 0.36)
    p = frame[max(0, int(y - R)):int(y + R), max(0, int(x - R)):int(x + R)]
    if p.size == 0:
        return None
    return cv2.resize(p, (MASK_S, MASK_S), interpolation=cv2.INTER_AREA)


def ink_mask(patch) -> np.ndarray:
    g = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    vals = g[_CM].reshape(-1, 1).astype(np.uint8)
    t, _ = cv2.threshold(vals, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return ((g < t) & _CM).astype(np.float32)


def red_score(patch):
    b, g, r = [patch[:, :, i].astype(int) for i in range(3)]
    red = int(((r > 110) & (r - g > 60) & (r - b > 50) & _CM).sum())
    grn = int(((g > r + 8) & (g > b - 10) & (r < 100) & _CM).sum())
    return red, grn


def ink_is_red(patch) -> bool:
    red, grn = red_score(patch)
    return red > max(60, 2 * grn)


_TEMPLATES = None
_TEMPLATES_SIG = None


def _file_sig(path):
    try:
        st = os.stat(path)
        return (path, st.st_mtime_ns, st.st_size)
    except OSError:
        return (path, 0, 0)


def _hex_to_mask(h):
    bits = bin(int(h, 16))[2:].zfill(MASK_S * MASK_S)
    return np.array([int(ch) for ch in bits], np.float32).reshape(MASK_S, MASK_S)


def load_templates(path=TEMPLATE_FILE):
    """{loại: [mặt nạ 40x40]} = mẫu dựng sẵn + templates/xiangqi/xq_kinds.json (+ templates/xq_kinds.json cũ nếu có).
    Tự nạp lại khi file json đổi (Dashboard chạy lâu không cần khởi động lại)."""
    global _TEMPLATES, _TEMPLATES_SIG
    sig = (_file_sig(path), _file_sig(LEGACY_TEMPLATE_FILE))
    if _TEMPLATES is not None and _TEMPLATES_SIG == sig:
        return _TEMPLATES
    out = {}
    for kind, hs in BUILTIN_MASKS.items():
        for h in hs:
            try:
                out.setdefault(kind, []).append(_hex_to_mask(h))
            except Exception:
                pass
    for fp in (LEGACY_TEMPLATE_FILE, path):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            for smp in data.get("samples", []):
                m = np.array([int(ch) for ch in smp["mask"]], np.float32).reshape(MASK_S, MASK_S)
                out.setdefault(smp["kind"], []).append(m)
        except Exception:
            pass
    _TEMPLATES, _TEMPLATES_SIG = out, sig
    return out


# --- ẢNH MẪU TỰ CẮT TAY: templates/xiangqi/<loại>_<số>.png (vd b_1.png, a_2.png, xe_1.png, tot_3.png) ---
_IMG_TEMPLATES = None
_IMG_SIG = None


_ROOK_ME_RE = re.compile(r"^(xe[_\- ]?(ta|minh|do|mine)|ta|minh|mine|me|rook[_\- ]?me|x)(?![a-z])")


def _kind_from_filename(name):
    """Tên file -> loại quân. 'X' = XE CỦA TA (xe chữ đỏ): ta_1.png, xe_ta_1.png, xe_do_1.png, minh_1.png, mine_1.png, x_1.png.
    (xe_1.png vẫn là xe ĐỊCH.)"""
    base = os.path.splitext(name)[0].lower().strip()
    if _ROOK_ME_RE.match(base):
        return "X"
    key = ""
    for ch in base:
        if ch.isalpha():
            key += ch
        else:
            break
    return _KIND_ALIASES.get(key)


def load_image_templates(folder=TEMPLATE_DIR):
    """{loại: [ảnh xám float32]} đọc từ `templates/xiangqi/*.png|jpg|bmp` (tên file bắt đầu bằng loại: r c n p b a k hoặc
    xe phao ma tot tuong si vua). File tên không hiểu thì bỏ qua. Tự nạp lại khi thư mục đổi."""
    global _IMG_TEMPLATES, _IMG_SIG
    try:
        names = sorted(f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")))
    except OSError:
        _IMG_TEMPLATES, _IMG_SIG = {}, None
        return {}
    sig = tuple(_file_sig(os.path.join(folder, f)) for f in names)
    if _IMG_TEMPLATES is not None and _IMG_SIG == sig:
        return _IMG_TEMPLATES
    _TPL_SCALED.clear()
    _SCORE_CACHE.clear()
    out = {}
    for f in names:
        kind = _kind_from_filename(f)
        if kind is None:
            continue
        try:
            im = cv2.imdecode(np.fromfile(os.path.join(folder, f), dtype=np.uint8), cv2.IMREAD_COLOR)
            if im is None or min(im.shape[:2]) < 12:
                continue
            g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
            if g.std() < 1e-3:
                continue
            out.setdefault(kind, []).append(g)
        except Exception:
            pass
    _IMG_TEMPLATES, _IMG_SIG = out, sig
    return out


_TPL_SCALED = {}       # (id(mẫu), h, w) -> (mẫu đã resize, mặt nạ tròn)  - khỏi resize + vẽ mặt nạ lại ở mỗi quân/khung
_SCORE_CACHE = {}      # (ô, pitch) -> [(thumbnail lõi đĩa, {loại: điểm})]  - quân không đổi giữa các khung/lượt thì khỏi matchTemplate lại
_CACHE_MAD = 5.0       # ngưỡng lệch xám trung bình (0-255) coi là CÙNG quân; tăng = cache trúng nhiều hơn nhưng dễ nhầm hơn
RB_PROF = {}           # thời gian từng bước của read_board lần gần nhất (để log)


def _image_scores(gray, x, y, pitch):
    """{loại: điểm khớp tốt nhất} của MỌI loại ảnh mẫu (kể cả 'X' = xe ta) với vùng quanh tâm đĩa; {} khi chưa có mẫu/không khớp được.
    (nhiều tỉ lệ quanh pitch/IMG_REF_PITCH, mặt nạ tròn để bỏ nền gỗ)"""
    tpl = load_image_templates()
    if not tpl:
        return {}
    h, w = gray.shape[:2]
    half = int(pitch * 0.80)
    x0, y0 = int(round(x)) - half, int(round(y)) - half
    # Quân SÁT MÉP (cột 0 / cột cuối) làm vùng so khớp tràn ra ngoài khung hình: bản cũ bỏ qua luôn (không nhận bằng ảnh) -> đệm viền
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(w, x0 + 2 * half), min(h, y0 + 2 * half)
    if xb - xa < half or yb - ya < half:
        return {}
    win = gray[ya:yb, xa:xb]
    pl, pt, pr, pb = xa - x0, ya - y0, (x0 + 2 * half) - xb, (y0 + 2 * half) - yb
    if pl or pt or pr or pb:
        win = cv2.copyMakeBorder(win, pt, pb, pl, pr, cv2.BORDER_REPLICATE)
    # Cache chịu nhiễu: hình ma xanh bay trên đầu mỗi quân đổi từng khung nên so pixel-đúng-từng-điểm không bao giờ trúng.
    # Chỉ so phần LÕI đĩa quân (±0.3 bước, nơi có chữ) ở dạng thumbnail 20x20; lệch trung bình < _CACHE_MAD thì dùng lại điểm cũ.
    hh = win.shape[0]
    core = win[int(hh * 0.31):int(hh * 0.69), int(hh * 0.31):int(hh * 0.69)] if win.shape[0] == win.shape[1] else win
    thumb = cv2.resize(core, (20, 20), interpolation=cv2.INTER_AREA).astype(np.float32)
    ckey = (int(round(x / 4.0)), int(round(y / 4.0)), round(float(pitch), 1))
    for th_, sc_hit in _SCORE_CACHE.get(ckey, ()):
        if float(np.abs(th_ - thumb).mean()) < _CACHE_MAD:
            return dict(sc_hit)
    win = win.astype(np.float32)
    s0 = pitch / IMG_REF_PITCH
    best = {}
    for kind, ims in tpl.items():
        for g in ims:
            for sc in (0.9, 1.0, 1.1):
                th, tw = max(8, int(round(g.shape[0] * s0 * sc))), max(8, int(round(g.shape[1] * s0 * sc)))
                if th >= win.shape[0] or tw >= win.shape[1]:
                    continue
                tk = (id(g), th, tw)
                ent = _TPL_SCALED.get(tk)
                if ent is None:
                    t = cv2.resize(g, (tw, th), interpolation=cv2.INTER_AREA)
                    if t.std() < 1e-3:
                        ent = (None, None)
                    else:
                        mk = np.zeros((th, tw), np.float32)
                        cv2.circle(mk, (tw // 2, th // 2), int(min(th, tw) * 0.46), 1.0, -1)
                        ent = (t, mk)
                    _TPL_SCALED[tk] = ent
                t, mk = ent
                if t is None:
                    continue
                try:
                    res = cv2.matchTemplate(win, t, cv2.TM_CCOEFF_NORMED, mask=mk)
                except Exception:
                    res = cv2.matchTemplate(win, t, cv2.TM_CCOEFF_NORMED)
                res = np.nan_to_num(res, nan=-1.0, posinf=-1.0, neginf=-1.0)
                sc_ = float(res.max())
                if sc_ > best.get(kind, -1.0):
                    best[kind] = sc_
    # CHỈ lưu cache kết quả CHẮC CHẮN (điểm cao + hơn loại thứ 2 rõ). Kết quả kém (vd. hình ma che chữ đúng lúc đó) mà lưu lại thì các khung sau
    # có cùng lõi đĩa sẽ dính điểm xấu đó mãi -> quân bị coi là "không đọc được". Kết quả kém thì cứ tính lại ở khung sau.
    vals = sorted(best.values(), reverse=True)
    if vals and vals[0] >= 0.80 and (len(vals) < 2 or vals[0] - vals[1] >= 0.06):
        if len(_SCORE_CACHE) > 400:
            _SCORE_CACHE.clear()
        lst = _SCORE_CACHE.setdefault(ckey, [])
        lst.append((thumb, dict(best)))
        del lst[:-4]                   # mỗi ô giữ tối đa 4 mẫu gần nhất
    return best


def classify_by_images(gray, x, y, pitch):
    """Nhận loại quân ĐỊCH bằng ảnh mẫu tự cắt (không xét mẫu 'X' = xe ta).
    -> (loại, điểm tốt nhất, điểm loại thứ 2) hoặc (None, 0, 0) khi chưa có ảnh mẫu / không khớp được."""
    best = {k: v for k, v in _image_scores(gray, x, y, pitch).items() if k != "X"}
    if not best:
        return None, 0.0, 0.0
    order = sorted(best.items(), key=lambda kv: -kv[1])
    second = order[1][1] if len(order) > 1 else -1.0
    return order[0][0], order[0][1], second


def rook_image_score(gray, x, y, pitch):
    """Điểm khớp với ảnh mẫu XE TA (ta_*.png ...) và điểm loại địch tốt nhất. None = chưa có mẫu xe ta."""
    if "X" not in load_image_templates():
        return None
    sc = _image_scores(gray, x, y, pitch)
    other = max([v for k, v in sc.items() if k != "X"] or [-1.0])
    return sc.get("X", -1.0), other


def classify_piece(gray, patch, x, y, pitch, min_match, img_match=IMG_MATCH_THR):
    """-> (loại hoặc None, điểm, nguồn). Thứ tự: ẢNH MẪU tự cắt (img) -> mẫu mặt nạ/json cũ (mask) -> None (không nhận ra)."""
    k, sc, sc2 = classify_by_images(gray, x, y, pitch)
    if k is not None and sc >= img_match and sc - sc2 >= IMG_MARGIN:
        return k, sc, "img"
    kind, score = classify_kind(ink_mask(patch))
    if kind is not None and score >= min_match:
        return kind, score, "mask"
    return None, max(score, 0.0), "none"


def add_template(kind, mask, path=TEMPLATE_FILE):
    global _TEMPLATES, _TEMPLATES_SIG
    data = {"size": MASK_S, "samples": []}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["samples"].append({"kind": kind, "mask": "".join("1" if v > 0.5 else "0" for v in mask.reshape(-1))})
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    _TEMPLATES = None
    _TEMPLATES_SIG = None


def classify_kind(mask, templates=None):
    """-> (loại, điểm). 1-NN (TM_CCOEFF_NORMED) trên mọi mẫu; điểm thấp = không chắc."""
    templates = templates if templates is not None else load_templates()
    best, bs = None, -1.0
    if mask.std() < 1e-3:
        return None, 0.0
    for kind, ms in templates.items():
        for t in ms:
            if t.std() < 1e-3:
                continue
            s = float(cv2.matchTemplate(mask, t, cv2.TM_CCOEFF_NORMED)[0][0])
            if s > bs:
                bs, best = s, kind
    return best, bs


@dataclass
class BoardState:
    board: dict
    rook: Optional[tuple]
    low_conf: list = field(default_factory=list)
    src: dict = field(default_factory=dict)      # {ô: 'img' | 'mask' | 'none'} nguồn nhận diện từng quân
    mem: list = field(default_factory=list)       # [(ô, loại)] quân GIỮ LẠI từ trí nhớ lượt trước (không đọc được ở khung này)
    swept: list = field(default_factory=list)     # [(ô, loại | None)] ô có ĐĨA nhưng Hough không thấy vòng tròn (quét đĩa); loại lấy từ khay nếu suy ra được
    rook_why: str = ""                            # xe ta được chọn nhờ: img (ảnh mẫu xe ta) | red | marks (ngoặc game) | hint (vị trí dự kiến)


def _hough_discs(gray, p, y_lo=None, y_hi=None):
    c = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=p * 0.6, param1=120, param2=28,
                         minRadius=int(p * 0.30), maxRadius=int(p * 0.44))
    return [] if c is None else [(float(x), float(y)) for x, y, _ in c[0]]


def detect_discs(frame, grid):
    gray = cv2.medianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 5)
    p = grid.pitch
    cells = set()
    for x, y in _hough_discs(gray, p):
        ci = int(round((x - grid.xs[0]) / p))
        ri = int(np.argmin([abs(y - yy) for yy in grid.ys]))
        if 0 <= ci < COLS and abs(x - grid.xs[ci]) < p * 0.3 and abs(y - grid.ys[ri]) < p * 0.3:
            cells.add((ri, ci))
    return sorted(cells)


def pick_rook(found, gray, grid, ov, hint=None, img_match=IMG_MATCH_THR):
    """Chọn XE TA trong các đĩa quân. found = [(ô, patch, (đỏ, xanh))]. -> (ô | None, lý do).
    Bản cũ chỉ lấy đĩa có NHIỀU điểm đỏ nhất: quân địch nằm cạnh xe bị hình ma/hào quang ĐỎ của xe che lên nên có lúc ăn điểm đỏ hơn
    xe thật (chữ xe bị tia sáng chọn làm nhạt) -> nhận nhầm quân địch là xe. Giờ xét lần lượt:
      1. ảnh mẫu XE TA (templates/xiangqi/ta_*.png) nếu có;
      2. ứng viên chữ ĐỎ (đỏ nhiều, ít xanh);
      3. NGOẶC game vẽ (khi xe được chọn) phải nằm trên cùng HÀNG/CỘT với xe - ứng viên làm ngoặc lệch hàng/cột thì bị loại;
      4. vị trí xe dự kiến (xe chỉ di chuyển bằng nước của chính mình);
      5. còn nhiều ứng viên: điểm (đỏ - 2 x xanh) cao nhất."""
    if not found:
        return None, "none"
    info = {cell: (red, grn) for cell, _p, (red, grn) in found}
    why = "red"
    cands = [cell for cell, patch, _ in found if ink_is_red(patch)]
    strong = []
    for cell, _p, _s in found:
        xs = rook_image_score(gray, *grid.px(*cell), grid.pitch)
        if xs is not None and xs[0] >= img_match and xs[0] - xs[1] >= IMG_MARGIN:
            strong.append((xs[0], cell))
    if strong:
        cands, why = [cell for _s, cell in sorted(strong, reverse=True)], "img"
    # ngoặc game (chỉ có khi xe đang được chọn): xe thật nằm ở TÂM của "chữ thập" ngoặc -> điểm = số ô ngoặc cùng hàng/cột - số ô lệch
    marked = list(ov or {})
    if len(marked) >= 3:
        def mscore(cell):
            on = sum(1 for m in marked if m != cell and (m[0] == cell[0] or m[1] == cell[1]))
            return on - (sum(1 for m in marked if m != cell) - on), on
        pool = set(cands) | {c for c, (red, _g) in info.items() if red >= 40}
        if pool:
            bm = max(pool, key=lambda c: (mscore(c)[0], info[c][0]))
            cur = max(cands, key=lambda c: info[c][0] - 2 * info[c][1]) if cands else None
            cur_sc = mscore(cur)[0] if cur else -999
            if bm != cur and mscore(bm)[1] >= 3 and mscore(bm)[0] - cur_sc >= 3:
                cands, why = [bm], "marks"
    if hint and len(cands) >= 1:
        inh = [c for c in cands if c in hint]
        if inh:
            cands = inh
    elif hint and not cands:
        ih = [c for c in hint if c in info and info[c][0] >= 40]
        if ih:
            return ih[0], "hint"
    if not cands:
        return None, "none"
    best = max(cands, key=lambda c: (info[c][0] - 2 * info[c][1]) if c in info else -1e9)
    return best, why


def cell_occupied(frame, grid, cell, thr=MEM_OCC_THR, hsv=None) -> bool:
    """Ô có đĩa quân không? Đo tỉ lệ pixel màu ĐĨA (sáng, ít bão hòa) trong vòng tròn 0.33 bước quanh tâm ô. Ô trống (gỗ, ngoặc xanh, nắng) <= ~0.27;
    đĩa quân (kể cả đang phát sáng / loé điện) >= ~0.5. Dùng khi Hough không thấy vòng tròn của quân (vd. TƯỚNG đang có hoạt ảnh)."""
    try:
        x, y = grid.px(*cell)
        R = max(4, int(grid.pitch * 0.33))
        x0, y0 = int(x) - R, int(y) - R
        xa, ya = max(0, x0), max(0, y0)
        sub = frame[ya:int(y) + R + 1, xa:int(x) + R + 1]
        if sub.size == 0:
            return False
        h = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
        yy, xx = np.mgrid[0:h.shape[0], 0:h.shape[1]]
        m = ((yy + ya - y) ** 2 + (xx + xa - x) ** 2) <= R * R
        if not m.any():
            return False
        s_, v_ = h[:, :, 1][m].astype(int), h[:, :, 2][m].astype(int)
        return float(((s_ < 110) & (v_ > 170)).mean()) >= thr
    except Exception:
        return False


DISC_SWEEP_THR = 0.30    # [QUÉT ĐĨA] tỉ lệ pixel "màu đĩa ẤM" tối thiểu để coi ô có quân (đĩa thật >= 0.31 kể cả đang phát sáng; hình ma xanh <= 0.20)


def cell_has_disc(frame, grid, cell, thr=DISC_SWEEP_THR) -> bool:
    """Ô có ĐĨA quân thật không (dù Hough không thấy vòng tròn vì quân đang phát sáng / loé điện)? Đếm pixel sáng, ít bão hoà VÀ ấm (R > B + 25)
    trong vòng tròn 0.33 bước quanh tâm ô. Hình ma / hào quang XANH NHẠT (B >= R) bị loại nên ô dưới hình ma không bị tính nhầm là có quân."""
    try:
        x, y = grid.px(*cell)
        R_ = max(4, int(grid.pitch * 0.33))
        x0, y0 = int(x) - R_, int(y) - R_
        xa, ya = max(0, x0), max(0, y0)
        sub = frame[ya:int(y) + R_ + 1, xa:int(x) + R_ + 1]
        if sub.size == 0:
            return False
        h = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
        yy, xx = np.mgrid[0:h.shape[0], 0:h.shape[1]]
        m = ((yy + ya - y) ** 2 + (xx + xa - x) ** 2) <= R_ * R_
        if not m.any():
            return False
        s_, v_ = h[:, :, 1][m].astype(int), h[:, :, 2][m].astype(int)
        b_, r_ = sub[:, :, 0][m].astype(int), sub[:, :, 2][m].astype(int)
        return float(((s_ < 110) & (v_ > 170) & (r_ - b_ > 25)).mean()) >= thr
    except Exception:
        return False


def read_board(frame, grid, unknown_as="u", min_match=0.68, img_match=IMG_MATCH_THR, rook_hint=None, prev=None, spawn_hint=None) -> BoardState:
    board, low, srcs, mem = {}, [], {}, []
    found = []
    _p0 = time.time()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _discs = detect_discs(frame, grid)
    _p1 = time.time()
    for (r, c) in _discs:
        x, y = grid.px(r, c)
        patch = _patch(frame, x, y, grid.pitch)
        if patch is not None:
            found.append(((r, c), patch, red_score(patch)))
    try:
        ov = overlay_states(read_marks(frame, grid), grid)
    except Exception:
        ov = {}
    _p2 = time.time()
    rook, why = pick_rook(found, gray, grid, ov, hint=rook_hint, img_match=img_match)
    _p3 = time.time()
    RB_PROF.update(discs=_p1 - _p0, marks=_p2 - _p1, rook=_p3 - _p2, n=len(found))
    for (r, c), patch, _ in found:
        if (r, c) == rook:
            board[(r, c)] = "X"
            continue
        x, y = grid.px(r, c)
        kind, score, src = classify_piece(gray, patch, x, y, grid.pitch, min_match, img_match)
        # [TRÍ NHỚ] lượt trước ô này có quân loại pk (đã đọc chắc) -> ƯU TIÊN pk:
        #   - không đọc ra gì (None)            -> giữ pk  (đĩa vẫn ở ô cũ, chỉ hoạt ảnh làm nhoè chữ)
        #   - đọc ra loại KHÁC bằng mẫu mặt nạ (yếu) mà ảnh mẫu vẫn khớp pk >= MEM_PRIOR_THR -> giữ pk
        pk = prev.get((r, c)) if prev else None
        if pk and pk not in ("u", "X") and (kind is None or (kind != pk and src == "mask")):
            sc_all = _image_scores(gray, x, y, grid.pitch)
            s_pk = sc_all.get(pk, -1.0)
            s_oth = max([v for k_, v in sc_all.items() if k_ not in (pk, "X")] or [-1.0])
            if kind is None or (s_pk >= MEM_PRIOR_THR and s_pk + 0.10 >= s_oth):
                kind, src = pk, "mem"
                mem.append(((r, c), pk))
        srcs[(r, c)] = src
        if kind is None:
            low.append(((r, c), None, round(score, 2)))
            kind = unknown_as
        board[(r, c)] = kind
    # [TRÍ NHỚ] quân lượt trước MẤT HẲN khỏi danh sách đĩa (Hough không thấy vòng tròn vì phát sáng/loé điện/chớp) nhưng ô vẫn còn đĩa -> giữ lại.
    # Ô quân địch vừa đi khỏi thì trống (tỉ lệ đĩa thấp) nên không bị giữ nhầm.
    if prev:
        # [2026-11-18] CHỐNG QUÂN MA: quân địch chỉ DI CHUYỂN (không nhân đôi). Nếu loại pk đã đọc đủ số quân như lượt trước thì ô cũ còn "sáng" chỉ là
        # HÌNH MA / hào quang của quân vừa đi khỏi (vd. tướng đi (4,4)->(5,4), hình ma tướng còn đọng ở (4,4)) -> KHÔNG giữ lại từ trí nhớ.
        prev_cnt, now_cnt = {}, {}
        for pk_ in prev.values():
            prev_cnt[pk_] = prev_cnt.get(pk_, 0) + 1
        for ck_, k_ in board.items():
            if ck_ != rook:
                now_cnt[k_] = now_cnt.get(k_, 0) + 1
        for cell, pk in prev.items():
            if cell in board or cell == rook or pk in ("u", "X"):
                continue
            if now_cnt.get(pk, 0) >= prev_cnt.get(pk, 0):
                continue
            if cell_occupied(frame, grid, cell, MEM_OCC_THR_KING if pk == "k" else MEM_OCC_THR):
                board[cell] = pk
                srcs[cell] = "mem"
                mem.append((cell, pk))
                now_cnt[pk] = now_cnt.get(pk, 0) + 1
    # [2026-11-18] QUÉT ĐĨA: ô có đĩa quân (màu ấm) mà chưa có quân nào được đọc (tướng mới hiện từ khay đang phát sáng/loé điện nên Hough không thấy
    # vòng tròn; trí nhớ không có vì chưa từng thấy nó) -> KHÔNG bỏ qua (bot tưởng ô trống, đi vào đường pháo/xe bị quân đó che). Suy ra loại từ KHAY
    # lượt trước (spawn_hint trừ các quân mới đã đọc được) nếu chỉ còn đúng 1 loại cho 1 ô; không suy ra được -> quân LẠ 'u' (low_conf -> bot quét lại / dừng).
    swept = []
    for r_ in range(ROWS):
        for c_ in range(COLS):
            cell = (r_, c_)
            if cell in board or cell == rook:
                continue
            if cell_has_disc(frame, grid, cell):
                swept.append(cell)
    if swept:
        leftover = []
        if spawn_hint and prev is not None:
            leftover = [k_ for k_ in spawn_hint if k_ not in ("u", "X")]
            for cell, k_ in board.items():
                if cell not in prev and cell != rook and k_ in leftover:
                    leftover.remove(k_)
        sw_out = []
        for cell in swept:
            if len(swept) == 1 and len(leftover) == 1:
                board[cell], srcs[cell] = leftover[0], "tray"
                sw_out.append((cell, leftover[0]))
            else:
                board[cell], srcs[cell] = unknown_as, "none"
                low.append((cell, None, 0.0))
                sw_out.append((cell, None))
        swept = sw_out
    RB_PROF["classify"] = time.time() - _p3
    return BoardState(board=board, rook=rook, low_conf=low, src=srcs, mem=mem, rook_why=why, swept=swept)


def read_tray(frame, grid, unknown_as="u", min_match=0.68, img_match=IMG_MATCH_THR):
    """Quân đang CHỜ trong khay phía trên bàn -> list loại quân (rỗng = khay trống). Chỉ xét đĩa nằm trên bàn,
    cách mép bàn >= 1.5 bước (loại biểu tượng góc màn hình)."""
    try:
        h, w = frame.shape[:2]
        p = grid.pitch
        ya, yb = int(max(0, grid.ys[0] - 2.9 * p)), int(max(0, grid.ys[0] - 0.75 * p))
        if yb - ya < p:
            return None
        gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray_full, 5)
        strip = gray[ya:yb]
        c = cv2.HoughCircles(strip, cv2.HOUGH_GRADIENT, dp=1, minDist=p * 0.6, param1=120, param2=28,
                             minRadius=int(p * 0.30), maxRadius=int(p * 0.44))
        out = []
        if c is not None:
            for x, y, _ in c[0]:
                if grid.xs[0] + 1.5 * p <= x <= grid.xs[-1] - 1.5 * p:
                    patch = _patch(frame, x, y + ya, p)
                    if patch is None or ink_is_red(patch):
                        continue
                    kind, _score, _src = classify_piece(gray_full, patch, x, y + ya, p, min_match, img_match)
                    out.append(kind if kind else unknown_as)
        return out
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 5) Luật + solver
# ----------------------------------------------------------------------------
def between(b, a, c):
    r1, c1 = a
    r2, c2 = c
    n = 0
    if r1 == r2:
        for x in range(min(c1, c2) + 1, max(c1, c2)):
            n += (r1, x) in b
    else:
        for x in range(min(r1, r2) + 1, max(r1, r2)):
            n += (x, c1) in b
    return n


def attacks(kind, pos, tgt, b, cfg):
    """Quân địch `kind` ở `pos` có ăn được ô `tgt` không."""
    r, c = pos
    dr, dc = tgt[0] - r, tgt[1] - c
    if kind == "r":
        return (dr == 0 or dc == 0) and between(b, pos, tgt) == 0
    if kind == "c":
        return (dr == 0 or dc == 0) and between(b, pos, tgt) == 1
    if kind == "n":
        ar, ac = abs(dr), abs(dc)
        if (ar, ac) == (2, 1):
            return (r + dr // 2, c) not in b
        if (ar, ac) == (1, 2):
            return (r, c + dc // 2) not in b
        return False
    if kind == "p":
        # LUẬT MỚI: Tốt ăn được 4 ô liền kề (tiến, lùi, trái, phải) - khoảng cách Manhattan = 1
        return abs(tgt[0] - pos[0]) + abs(tgt[1] - pos[1]) == 1
    if kind == "b":
        return abs(dr) == 2 and abs(dc) == 2 and (r + dr // 2, c + dc // 2) not in b
    if kind == "a":
        return abs(dr) == 1 and abs(dc) == 1
    if kind == "k":
        return abs(dr) + abs(dc) == 1
    if kind == "u":
        # QUÂN LẠ (chưa đọc chắc chữ): giả định xấu nhất trong các quân đi NGẮN - tốt/tướng (1 ô thẳng), sĩ (1 chéo),
        # tượng (2 chéo, chặn mắt), mã (chữ L, chặn chân). Không tính xe/pháo (đường dài) vì sẽ coi cả bàn là nguy hiểm.
        ar, ac = abs(dr), abs(dc)
        if ar + ac == 1 or (ar, ac) == (1, 1):
            return True
        if (ar, ac) == (2, 2):
            return (r + dr // 2, c + dc // 2) not in b
        if (ar, ac) == (2, 1):
            return (r + dr // 2, c) not in b
        if (ar, ac) == (1, 2):
            return (r, c + dc // 2) not in b
    return False


def rook_moves(b, rook):
    r, c = rook
    out = []
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nr, nc = r + dr, c + dc
        while 0 <= nr < ROWS and 0 <= nc < COLS:
            k = b.get((nr, nc))
            out.append(((nr, nc), k if k != "X" else None))
            if k is not None:
                break
            nr += dr
            nc += dc
    return out


def after_move(b, rook, dest):
    nb = dict(b)
    nb.pop(rook, None)
    nb[dest] = "X"
    return nb


def is_attacked(b, rook, cfg):
    return any(attacks(k, p, rook, b, cfg) for p, k in b.items() if k != "X")


def count_attackers(b, rook, cfg):
    return sum(1 for p, k in b.items() if k != "X" and attacks(k, p, rook, b, cfg))


def exits(b, rook, cfg):
    return sum(1 for d, _ in rook_moves(b, rook) if not is_attacked(after_move(b, rook, d), d, cfg))


def spawn_risk(nb, dest, tray, cfg, scale=1.0):
    """Xác suất (gần đúng) mất xe vì quân MỚI hiện ra chiếu xe rồi được chọn đi ăn. tray = list loại quân sắp hiện."""
    empties = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in nb]
    if not empties or not tray:
        return 0.0
    n_after = len(nb) - 1 + len(tray)
    risk = 0.0
    for kind in set(tray):
        n_att = sum(attacks(kind, sq, dest, nb, cfg) for sq in empties)
        risk += tray.count(kind) * n_att / len(empties)
    return min(1.0, risk / max(n_after, 1) * 2.0) * scale


def spawn_risk_timer(nb, dest, tray, cfg):
    """Đồng hồ cát = 1: nước đi NÀY làm cả khay hiện ra (mỗi quân 1 ô trống ngẫu nhiên). Trả xác suất ÍT NHẤT 1 quân khay hiện đúng ô chiếu xe
    ở `dest` (xấp xỉ độc lập giữa các quân). Không tính xem địch có được chọn đi ăn hay không (hệ số đó nằm ở cfg.spawn_hit)."""
    empties = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in nb]
    if not empties or not tray:
        return 0.0
    safe = 1.0
    for kind in tray:
        n_att = sum(attacks(kind, sq, dest, nb, cfg) for sq in empties)
        safe *= 1.0 - min(1.0, n_att / len(empties))
    return 1.0 - safe


def _spawn_prob(nb, dest, tray, cfg, scale, spawn_in=None):
    """Rủi ro (0..1) bị quân khay hiện ra ăn xe sau nước đi tới `dest`. spawn_in = số đồng hồ cát đọc được (None = không đọc được ->
    mô hình cũ, hệ số cố định `scale`). spawn_in > 1: chưa có quân nào hiện ở nước này -> 0. spawn_in <= 1: tính theo cả khay."""
    if spawn_in is None:
        return spawn_risk(nb, dest, tray, cfg, scale)
    if spawn_in > 1:
        return 0.0
    return spawn_risk_timer(nb, dest, tray, cfg) * cfg.spawn_hit


def fork_bonus(n, cfg):
    """Thưởng dọa nhiều quân: dọa 1 quân thì địch chắc chắn chạy (vô nghĩa nếu không tạo đường/xiên), chỉ dọa >= 2 quân mới có giá trị."""
    return cfg.w_fork * (min(n, 3) - 1) if n >= 2 else 0.0


_SPAWN_CACHE = {}


def spawn_outcomes(nb, dest, tray, cfg, samples=None):
    """THỨ TỰ LƯỢT khi đồng hồ cát = 1: xe đi -> địch đi -> khay THẢ quân vào ô trống ngẫu nhiên (quân khay KHÔNG đi, KHÔNG ăn được xe) ->
    tới lượt xe. Nên rủi ro của khay không phải 'bị ăn ngay' mà là: sau khi thả, xe HẾT Ô AN TOÀN để đi (kẹt = thua) hoặc bị chiếu (phải chạy).
    Giả lập `samples` lần thả khay ngẫu nhiên trên bàn `nb` (xe ở `dest`), trả (P[xe hết ô an toàn], P[xe bị chiếu])."""
    tray = list(tray or [])
    if not tray:
        return 0.0, 0.0
    n = max(1, int(samples if samples is not None else cfg.spawn_samples))
    key = (frozenset(nb.items()), dest, tuple(sorted(tray)), n)
    hit = _SPAWN_CACHE.get(key)
    if hit is not None:
        return hit
    empties = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in nb]
    if not empties:
        return 0.0, 0.0
    rng = random.Random(len(nb) * 7919 + dest[0] * 131 + dest[1] * 17 + len(tray))
    doom = chk = 0
    for _ in range(n):
        b2 = dict(nb)
        for kind, sq in zip(tray, rng.sample(empties, min(len(tray), len(empties)))):
            b2[sq] = kind
        if is_attacked(b2, dest, cfg):
            chk += 1
        if exits(b2, dest, cfg) == 0:
            doom += 1
    res = (doom / n, chk / n)
    if len(_SPAWN_CACHE) > 30000:
        _SPAWN_CACHE.clear()
    _SPAWN_CACHE[key] = res
    return res


_DOOM_CACHE = {}


def random_doom_prob(nb, d, cfg):
    """Xác suất sau khi xe tới `d` (bàn `nb`), 1 quân địch NGẪU NHIÊN (chọn đều 1 quân còn nước đi, rồi chọn đều 1 nước) đi khiến xe HẾT ô an toàn
    ở lượt sau. Liệt kê CHÍNH XÁC mọi nước đi của địch (không giả định địch 'săn xe'): bắt các thế xe chỉ sống nhờ 1 đường thoát duy nhất mà
    1 quân bước vào là chặn hết (kiểu chết ở ảnh doom_0172: sĩ bước vào (7,3) chặn cả hàng thoát)."""
    key = (frozenset(nb.items()), d)
    hit = _DOOM_CACHE.get(key)
    if hit is not None:
        return hit
    per_piece = []
    for q, kind in list(nb.items()):
        if kind == "X":
            continue
        b2 = dict(nb)
        del b2[q]
        moves = piece_moves(kind, q, b2)
        if not moves:
            continue
        bad = 0
        for sq in moves:
            b2[sq] = kind
            if exits(b2, d, cfg) == 0:
                bad += 1
            del b2[sq]
        per_piece.append(bad / len(moves))
    res = sum(per_piece) / len(per_piece) if per_piece else 0.0
    if len(_DOOM_CACHE) > 30000:
        _DOOM_CACHE.clear()
    _DOOM_CACHE[key] = res
    return res


def enemy_doom_penalty(nb, d, cfg):
    if not cfg.enemy_doom:
        return 0.0
    w = cfg.w_simple_doom if cfg.simple_mode else cfg.w_enemy_doom
    return w * random_doom_prob(nb, d, cfg) if w > 0 else 0.0


def spawn_penalty(nb, dest, tray, cfg, scale=1.0, spawn_in=None):
    """Điểm phạt do khay hiện ra sau nước đi tới `dest`: LOSS x P[xe hết đường đi] + w_spawn_check x P[bị chiếu]. spawn_in > 1: chưa thả -> 0;
    spawn_in <= 1: thả ở nước này (trọng số 1); spawn_in None (không đọc được đồng hồ): nhân thêm hệ số `scale` (mặc định 0.3)."""
    if not tray or cfg.simple_mode:
        return 0.0
    if spawn_in is None:
        w, samples = scale, max(8, int(cfg.spawn_samples) // 2)
    elif spawn_in > 1:
        return 0.0
    else:
        w, samples = 1.0, None
    pd, pc = spawn_outcomes(nb, dest, tray, cfg, samples)
    return w * (LOSS * pd + cfg.w_spawn_check * pc)


# Mẫu chữ số của bộ đếm ĐỒNG HỒ CÁT (bên dưới khay quân chờ), chuẩn hoá về 12 x 20 ('#' = nét chữ màu hồng). Mới có 1..7;
# số khác (8, 9, 0, 10+) -> không đọc được (None) -> bot dùng mô hình cũ (`spawn_risk_every_turn`).
_TIMER_W, _TIMER_H = 12, 20
_TIMER_TPL_ROWS = {
    1: (
        "..........##",
        "..........##",
        "........####",
        "..##########",
        "############",
        "############",
        "........####",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
    ),
    2: (
        "..######....",
        ".######..##.",
        "####.....###",
        "###.......##",
        "##.........#",
        "##.........#",
        "..........##",
        "..........##",
        ".........##.",
        "........###.",
        ".......###..",
        ".....####...",
        "...####.....",
        "..####......",
        ".###........",
        "###.........",
        "##..........",
        "##..........",
        "############",
        "############",
    ),
    3: (
        "...#####....",
        ".#######.#..",
        "####.....##.",
        "###......##.",
        "##........#.",
        "##........#.",
        "..........#.",
        ".........#..",
        ".......###..",
        ".....######.",
        ".....######.",
        "........###.",
        "..........##",
        "...........#",
        "...........#",
        "##.........#",
        "##........##",
        "###......##.",
        ".#########..",
        "...#####....",
    ),
    4: (
        ".......##...",
        ".......##...",
        "......###...",
        "......###...",
        ".....####...",
        ".....#..#...",
        "....##..#...",
        "....##..#...",
        "...##...#...",
        "..##....#...",
        ".##.....#...",
        ".##.....#...",
        ".##.....#...",
        "####...####.",
        "############",
        "........##..",
        "........##..",
        "........#...",
        "........#...",
        "........#...",
    ),
    5: (
        ".##########.",
        ".#########..",
        ".#..........",
        ".#..........",
        "##..........",
        "##..........",
        "##..........",
        "#########...",
        "#####..###..",
        "###.......##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "##........#.",
        "###......##.",
        ".######.....",
        "...####.....",
    ),
    6: (
        ".....####...",
        "...#######..",
        "..###...###.",
        ".###.....##.",
        ".##.........",
        ".##.........",
        ".##.........",
        "###.........",
        "##########..",
        "####...####.",
        "###.....####",
        "##........##",
        "##........##",
        "##.........#",
        "...........#",
        "..........##",
        "..........##",
        ".........##.",
        "....######..",
        ".....###....",
    ),
    7: (
        "############",
        "..##########",
        "........###.",
        "........##..",
        ".......###..",
        ".......###..",
        ".......##...",
        "......##....",
        "......##....",
        "....####....",
        ".#######....",
        "...####.....",
        "...###......",
        "...###......",
        "...##.......",
        "...##.......",
        "...##.......",
        "..###.......",
        "..###.......",
        "...#........",
    ),
}
_TIMER_TPL = {k: np.array([[1.0 if ch == "#" else 0.0 for ch in row] for row in rows], np.float32) for k, rows in _TIMER_TPL_ROWS.items()}


def _pink_mask(roi):
    roi = roi.astype(np.int16)
    b, g, r = roi[..., 0], roi[..., 1], roi[..., 2]
    return ((r > 170) & (r - g > 70) & (r - b > 60) & (np.abs(g - b) < 50)).astype(np.uint8)   # chữ hồng; nền gỗ (cam) bị loại vì G >> B


def _split_glyphs(m, p):
    """Tách từng chữ số trong mặt nạ nhị phân `m` -> list ma trận 20 x 12 (trái -> phải). p = bước lưới (để lọc nhiễu theo chiều cao)."""
    cols = m.sum(axis=0) > 0
    out, i, n = [], 0, len(cols)
    while i < n:
        if not cols[i]:
            i += 1
            continue
        j = i
        while j < n and (cols[j] or (j + 1 < n and cols[j + 1])):     # cho phép khe 1 cột trong cùng 1 chữ số
            j += 1
        sub = m[:, i:j]
        ys = np.where(sub.sum(axis=1) > 0)[0]
        if len(ys) >= 0.12 * p and sub.sum() >= 20:
            sub = sub[ys[0]:ys[-1] + 1]
            out.append(cv2.resize(sub.astype(np.float32), (_TIMER_W, _TIMER_H), interpolation=cv2.INTER_AREA))
        i = j + 1
    return out


def _timer_glyphs(frame, grid):
    """Tách từng chữ số của bộ đếm đồng hồ cát (nằm ngay bên phải biểu tượng đồng hồ, dưới khay) -> list ma trận 20 x 12 (trái -> phải)."""
    p = grid.pitch
    cx = (grid.xs[0] + grid.xs[-1]) / 2.0
    h, w = frame.shape[:2]
    x0, x1 = max(0, int(cx)), min(w, int(cx + 0.75 * p))
    y0, y1 = max(0, int(grid.ys[0] - 1.45 * p)), min(h, int(grid.ys[0] - 0.9 * p))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return []
    return _split_glyphs(_pink_mask(frame[y0:y1, x0:x1]), p)


_TIMER_IMG = None
_TIMER_IMG_SIG = None
TIMER_SKIPPED = []      # file time_*.png không tách được đúng số chữ số (để log báo)


def load_timer_templates(folder=TEMPLATE_DIR):
    """{chữ số (int): [ma trận 20x12]} đọc từ ẢNH MẪU ĐỒNG HỒ CÁT `templates/xiangqi/time_<số>.png` (hoặc time_<số>_<stt>.png, dongho_..., timer_...).
    Ảnh cắt ôm chữ số HỒNG của đồng hồ (từ ảnh gốc chưa vẽ): `time_3.png` chứa số 3, `time_12.png` chứa số 12 (2 chữ số 1 và 2).
    Có thể có NHIỀU ảnh cho cùng 1 số (time_1.png, time_1_b.png, ...). Mẫu nạp thêm vào bộ mẫu dựng sẵn (1..7); thêm/sửa ảnh không cần khởi động lại."""
    global _TIMER_IMG, _TIMER_IMG_SIG
    try:
        names = sorted(f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")))
    except OSError:
        _TIMER_IMG, _TIMER_IMG_SIG = {}, None
        return {}
    names = [f for f in names if re.match(r"^(?:time|timer|dongho)[_\-\s]*\d+", f, re.I)]
    sig = tuple(_file_sig(os.path.join(folder, f)) for f in names)
    if _TIMER_IMG is not None and _TIMER_IMG_SIG == sig:
        return _TIMER_IMG
    out = {}
    del TIMER_SKIPPED[:]
    for f in names:
        digits = re.match(r"^(?:time|timer|dongho)[_\-\s]*(\d+)", f, re.I).group(1)
        try:
            im = cv2.imdecode(np.fromfile(os.path.join(folder, f), dtype=np.uint8), cv2.IMREAD_COLOR)
            if im is None:
                TIMER_SKIPPED.append(f)
                continue
            gl = _split_glyphs(_pink_mask(im), IMG_REF_PITCH)
            if len(gl) != len(digits):
                TIMER_SKIPPED.append(f)
                continue
            for ch, g in zip(digits, gl):
                out.setdefault(int(ch), []).append(g)
        except Exception:
            TIMER_SKIPPED.append(f)
    _TIMER_IMG, _TIMER_IMG_SIG = out, sig
    return out


def read_spawn_timer(frame, grid, min_sim=0.75, min_gap=0.15):
    """Số đếm ngược trên đồng hồ cát (số nước đi tới khi khay hiện ra; 1 = nước đi kế tiếp làm khay hiện). None = không đọc được."""
    try:
        gl = _timer_glyphs(frame, grid)
        if not gl or len(gl) > 2:
            return None
        digits = []
        for g in gl:
            a = g - g.mean()
            tpls = {k: [t] for k, t in _TIMER_TPL.items()}
            for k, lst in load_timer_templates().items():          # ảnh mẫu time_<n>.png của bạn (nhiều mẫu mỗi chữ số)
                tpls.setdefault(k, []).extend(lst)
            sims = []
            for k, lst in tpls.items():
                best_sim = -1.0
                for t in lst:
                    tb = t - t.mean()
                    best_sim = max(best_sim, float((a * tb).sum() / (np.linalg.norm(a) * np.linalg.norm(tb) + 1e-6)))
                sims.append((best_sim, k))
            sims.sort(reverse=True)
            if sims[0][0] < min_sim or (len(sims) > 1 and sims[0][0] - sims[1][0] < min_gap):
                return None
            digits.append(sims[0][1])
        return int("".join(str(d) for d in digits))
    except Exception:
        return None


DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIRS_DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def piece_moves(kind, pos, b):
    """Các ô TRỐNG mà quân địch `kind` ở `pos` đi tới được (chỉ đi, không ăn). Khớp với `attacks`: pháo đi như xe (ăn mới cần
    nhảy qua 1 quân), tốt đi 4 hướng 1 ô (luật mới), tướng/quân lạ đi 1 ô ngang/dọc."""
    r, c = pos
    out = []
    if kind in ("r", "c"):
        for dr, dc in DIRS4:
            nr, nc = r + dr, c + dc
            while 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in b:
                out.append((nr, nc))
                nr += dr
                nc += dc
    elif kind == "n":
        for dr, dc in ((2, 1), (2, -1), (-2, 1), (-2, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in b and (r + dr // 2, c) not in b:
                out.append((nr, nc))
        for dr, dc in ((1, 2), (1, -2), (-1, 2), (-1, -2)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in b and (r, c + dc // 2) not in b:
                out.append((nr, nc))
    elif kind == "b":
        for dr, dc in DIRS_DIAG:
            nr, nc = r + 2 * dr, c + 2 * dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in b and (r + dr, c + dc) not in b:
                out.append((nr, nc))
    elif kind == "a":
        for dr, dc in DIRS_DIAG:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in b:
                out.append((nr, nc))
    else:                                   # p (tốt, luật mới), k, u
        for dr, dc in DIRS4:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in b:
                out.append((nr, nc))
    return out


def _rays(b, rook):
    """Như rook_moves nhưng kèm độ dài 4 tia (số ô đi được mỗi hướng, kể cả ô ăn quân) để tính độ thoáng / tắc đường."""
    r, c = rook
    moves, lens = [], []
    for dr, dc in DIRS4:
        nr, nc, n = r + dr, c + dc, 0
        while 0 <= nr < ROWS and 0 <= nc < COLS:
            k = b.get((nr, nc))
            n += 1
            moves.append(((nr, nc), None if (k is None or k == "X") else k))
            if k is not None:
                break
            nr += dr
            nc += dc
        lens.append(n)
    return moves, lens


# ----------------------------------------------------------------------------
# 5c) Đòn xiên / dụ + 5d) hiệu ứng nổ sau khi ăn tướng
# ----------------------------------------------------------------------------
def cap_value(b, q, kind, cfg):
    """Giá trị ăn quân `kind` ở ô `q` trên bàn `b` (bàn TRƯỚC khi ăn). Giá trị gốc theo loại; khi xe + pháo địch ĐÔNG (>= rc_many) thì ăn xe/pháo được cộng
    w_rc_base, và cộng thêm w_rc_adj cho mỗi xe/pháo khác đứng CẠNH (8 ô quanh, tối đa 2) -> ưu tiên dọn cụm xe/pháo vì chúng chiếm đường và dễ vây xe ta."""
    v = cfg.value.get(kind, 20)
    if kind in ("r", "c") and cfg.rc_many > 0:
        rc = [p for p, k in b.items() if k in ("r", "c")]
        if len(rc) >= cfg.rc_many:
            adj = sum(1 for p in rc if p != q and max(abs(p[0] - q[0]), abs(p[1] - q[1])) == 1)
            v += cfg.w_rc_base + cfg.w_rc_adj * min(adj, 2)
    return v


def safe_capture(nb, d, q, cfg):
    """[2026-11-18 #6] Xe ở `d` ăn quân ở `q` (trên bàn `nb`) rồi có AN TOÀN không (xe ở `q` không bị quân nào ăn lại)? 'Ăn thì chết' = False."""
    return not is_attacked(after_move(nb, d, q), q, cfg)


def safe_threats(nb, d, cfg):
    """Số quân xe ở `d` đang dọa mà ĂN ĐƯỢC AN TOÀN (không bị ăn lại). Quân được bảo vệ (ăn xong chết) KHÔNG tính là dọa thật -> chiếu đôi/fork chỉ có giá trị khi cả 2 đều ăn được an toàn."""
    return sum(1 for q, k in rook_moves(nb, d) if k is not None and safe_capture(nb, d, q, cfg))


def _skewer_safe(nb, d, c_pos, b_kind, cfg):
    """Đòn xiên thật: B chạy đi (bàn không còn B) thì xe ăn C ở `c_pos` phải AN TOÀN."""
    b2 = dict(nb)
    for q in list(b2):
        if b2[q] == b_kind and q != c_pos and (q[0] == d[0] or q[1] == d[1]) and between(nb, d, q) == 0:
            del b2[q]
            break
    return safe_capture(b2, d, c_pos, cfg)


def skewer_value(nb, d, cfg):
    """Đòn XIÊN: từ ô `d` xe dọa quân B (quân đầu tiên trên tia); nếu SAU B cùng tia còn quân C thì B chạy là C lộ ra cho xe ăn.
    Trả điểm thưởng lớn nhất trong 4 tia = w_skewer x capture_weight x giá trị C (0 nếu không có). Chỉ tính khi C có giá trị >= 1/2 B
    (không dọa quân to để xiên quân bé) và C KHÔNG đang bảo vệ B bằng cách ăn xe (đã loại ở ô an toàn)."""
    best = 0.0
    r, c = d
    for dr, dc in DIRS4:
        nr, nc = r + dr, c + dc
        first = None
        while 0 <= nr < ROWS and 0 <= nc < COLS:
            k = nb.get((nr, nc))
            if k is not None and k != "X":
                if first is None:
                    first = k
                else:
                    vb, vc = cfg.value.get(first, 20), cfg.value.get(k, 20)
                    if vc * 2 >= vb and _skewer_safe(nb, d, (nr, nc), first, cfg):
                        best = max(best, cfg.w_skewer * cfg.capture_weight * vc)
                    break
            nr += dr
            nc += dc
    return best


def blast_victims(b, d):
    """Hiệu ứng sau khi ĂN TƯỚNG: nước đi kế tiếp tiêu diệt MỌI quân ở cùng hàng + cùng cột với ô đích `d` (tâm = ô đích)."""
    return [p for p, k in b.items() if k != "X" and (p[0] == d[0] or p[1] == d[1])]


def blast_value(b, d, cfg):
    return sum(cfg.value.get(b[p], 20) for p in blast_victims(b, d))


# ----------------------------------------------------------------------------
# 5b) Tìm kiếm sâu (Beam Minimax): xe = nút Max, địch = nút phản ứng (giả định địch thông minh nhất)
# ----------------------------------------------------------------------------
class _Deadline(Exception):
    pass


class _Search:
    """Một lần tìm kiếm cho 1 lượt. `memo` nhớ các thế đã tính (khoá gồm cả tầng còn lại) nên các tầng sâu dần dùng lại được."""

    def __init__(self, cfg, beam, deadline=None, now=time.time):
        self.cfg, self.beam = cfg, max(1, int(beam))
        self.deadline, self.now = deadline, now
        self.nodes = 0
        self.memo = {}
        self.spawn_tray, self.spawn_ply = None, None     # khay + tầng (nước thứ mấy của xe) mà khay thả quân; None = không mô hình hoá

    def _tick(self):
        self.nodes += 1
        if self.deadline is not None and self.now() > self.deadline:
            raise _Deadline()

    def _flee(self, nb, d):
        """Phản ứng 'cứu quân' của địch khi xe ở `d` (xem docstring `react`). Trả bàn mới (hoặc `nb` nếu không quân nào bị dọa/chạy được)."""
        cfg = self.cfg
        thr = [(p, k) for p, k in rook_moves(nb, d) if k is not None]
        if not thr:
            return nb
        thr.sort(key=lambda t: -cfg.value.get(t[1], 20))
        for q, kind in thr:
            b2 = dict(nb)
            del b2[q]
            best = None
            for sq in piece_moves(kind, q, b2):
                if (sq[0] == d[0] or sq[1] == d[1]) and between(b2, d, sq) == 0:
                    continue                                  # xe vẫn ăn được ô này
                key = (1 if attacks(kind, sq, d, b2, cfg) else 0, abs(sq[0] - d[0]) + abs(sq[1] - d[1]))
                if best is None or key > best[0]:
                    best = (key, sq)
            if best is not None:
                b2[best[1]] = kind
                return b2
        return nb

    def _random_check(self, nb, d):
        """Địch đi NGẪU NHIÊN nên BẤT KỲ quân nào cũng có thể đi tới ô chiếu xe (không chỉ quân bị xe dọa). Quét mọi nước đi của địch:
        trả (bàn_chiếu_nguy_hiểm_nhất, xác_suất) - bàn mà sau khi 1 quân đi chiếu xe thì xe còn ÍT ô thoát nhất; xác suất ~ P(quân được chọn
        đi tới ô chiếu) tính theo 'chọn đều 1 quân rồi chọn đều 1 nước' x react_check_scale (chặn <= 1). Không có nước chiếu -> (None, 0)."""
        cfg = self.cfg
        pieces = [(p, k) for p, k in nb.items() if k != "X"]
        if not pieces:
            return None, 0.0
        cands, prob, n_mov = [], 0.0, 0
        for q, kind in pieces:
            b2 = dict(nb)
            del b2[q]
            moves = piece_moves(kind, q, b2)
            if not moves:
                continue
            n_mov += 1
            hits = [sq for sq in moves if attacks(kind, sq, d, b2, cfg)]
            if hits:
                prob += len(hits) / len(moves)
                for sq in hits:
                    cands.append((abs(sq[0] - d[0]) + abs(sq[1] - d[1]), q, kind, sq))
        if not cands or n_mov == 0:
            return None, 0.0
        prob = min(1.0, prob / n_mov * cfg.react_check_scale)
        cands.sort(key=lambda t: t[0])                         # quân gần xe trước (hay làm xe hết đường hơn)
        worst, worst_ex = None, 10 ** 9
        for _dist, q, kind, sq in cands[:max(1, int(cfg.react_check_cap))]:
            b2 = dict(nb)
            del b2[q]
            b2[sq] = kind
            ex = exits(b2, d, cfg)
            if ex < worst_ex:
                worst, worst_ex = b2, ex
                if ex == 0:
                    break
        return worst, prob

    def reply(self, nb, d):
        """Phản ứng của địch sau khi xe tới `d` -> (bàn_đi_tiếp, bàn_bị_chiếu, trọng_số).
        - bàn_đi_tiếp: bàn dùng để tìm kiếm tiếp (kết quả 'cứu quân' như `react`, hoặc `nb` nếu địch không cần cứu quân).
        - bàn_bị_chiếu: bàn mà xe bị CHIẾU sau phản ứng đó (None nếu không có khả năng bị chiếu); trọng_số = xác suất xảy ra (1.0 khi chính
          nước cứu quân của địch đã chiếu xe - giả định xấu như bản cũ; < 1 khi chỉ là 1 quân ngẫu nhiên có thể đi tới ô chiếu)."""
        cfg = self.cfg
        base = self._flee(nb, d)
        if cfg.simple_mode:                                   # chế độ ăn nhanh: không dự đoán bị chiếu / nước chết
            return base, None, 0.0
        if is_attacked(base, d, cfg):
            return base, base, 1.0
        if cfg.react_checks:
            chk, p = self._random_check(base, d)
            if chk is not None and p > 0.0:
                return base, chk, p
        return base, None, 0.0

    def react(self, nb, d):
        """Giữ tên cũ cho code khác gọi: chỉ trả bàn đi tiếp của `reply`.
        Địch bị dọa >= 2 quân: cứu quân giá trị CAO NHẤT trong số quân còn cách chạy (quân khác đứng yên cho xe ăn lượt sau);
        bị dọa 1 quân: quân đó chạy sang ô xe không ăn được (ưu tiên ô lại chiếu xe, rồi ô xa xe); không quân nào bị dọa / không
        quân nào chạy được: bàn giữ nguyên. (Khả năng quân KHÁC ngẫu nhiên chiếu xe được tính riêng trong `reply` / `_after`.)"""
        return self.reply(nb, d)[0]

    def _candidates(self, b, rook, blast=False):
        """Nước đi AN TOÀN của xe (bỏ ô bị chiếu): điểm ĂN QUÂN (cộng dồn theo chuỗi) tách riêng khỏi điểm VỊ TRÍ (độ thoáng + dọa
        quân - tắc đường; chỉ tính ở thế cuối chuỗi để không át điểm ăn quân). Xếp theo tổng hai điểm, cao trước.
        -> [(tổng, đích, quân_ăn, bàn_sau, có_giao_tranh, điểm_ăn, điểm_vị_trí)]"""
        cfg = self.cfg
        capw, val = cfg.capture_weight, cfg.value
        out = []
        for d, cap in rook_moves(b, rook):
            nb = after_move(b, rook, d)
            blast_gain = 0.0
            if blast:                                      # nước NỔ (ngay sau khi ăn tướng): mọi quân cùng hàng + cột với đích biến mất
                blast_gain = capw * blast_value(b, d, cfg)
                for q in blast_victims(nb, d):
                    nb.pop(q, None)
            if is_attacked(nb, d, cfg):
                continue
            mv, lens = _rays(nb, d)
            threat = safe_threats(nb, d, cfg)
            jam = sum(1.0 if n == 0 else (0.5 if n == 1 else 0.0) for n in lens)
            cg = blast_gain if blast else (capw * cap_value(b, d, cap, cfg) if cap else 0.0)
            if cap == "k" and cfg.king_blast:
                cg += cfg.w_king_blast
            pos = cfg.w_mobility * min(len(mv), 12) + fork_bonus(threat, cfg) - cfg.w_blocked * jam + skewer_value(nb, d, cfg)
            out.append((cg + pos, d, cap, nb, bool(cap) or threat > 0 or blast_gain > 0, cg, pos))
        out.sort(key=lambda t: -t[0])
        return out

    def _select(self, cands, ply):
        """Cắt tỉa beam: ưu tiên nước có giao tranh (ăn / dọa quân) NHƯNG luôn giữ lại `quiet_keep` nước YÊN TĨNH tốt nhất (đã xếp theo
        độ thoáng - tắc đường) ở MỌI tầng. Trong cờ sinh tồn, lùi xe về ô thoáng là nước yên tĩnh nhưng quyết định sống/chết."""
        cfg = self.cfg
        tact = [c for c in cands if c[4]]
        quiet = [c for c in cands if not c[4]]
        q_keep = max(0, int(cfg.quiet_keep))
        q = max(q_keep, self.beam - len(tact)) if ply < 2 else q_keep     # tầng nông: nước yên tĩnh lấp chỗ trống của beam
        q = min(q, len(quiet))
        n_t = max(1 if tact else 0, self.beam - q)
        sel = tact[:n_t] + quiet[:q]
        if not sel:
            sel = cands[:1]
        return sel

    def _after(self, nb, d, cg, depth, ply, cap=None):
        """Giá trị của 1 nước xe tới `d` (bàn sau nước đi `nb`, điểm ăn/vị trí `cg`) gồm phản ứng của địch + tìm kiếm tiếp `depth` nước.
        - Sau phản ứng xe bị CHIẾU mà KHÔNG còn ô thoát an toàn nào -> THUA: -LOSS, không tìm kiếm tiếp nhánh đó (nếu chỉ là 1 quân ngẫu nhiên
          có XÁC SUẤT p chiếu được thì trừ p x LOSS vào kỳ vọng và vẫn tìm tiếp trên nhánh còn lại).
        - Bị chiếu nhưng còn đường thoát: phạt (w_check + w_check_exit / số ô thoát) x xác suất - càng ít đường thoát càng nặng.
        - Điểm thua (<= -LOSS/2) KHÔNG bị chiết khấu gamma: thua ở tầng sâu vẫn nặng như thua gần.
        Trả (điểm, chuỗi_nước_tiếp)."""
        cfg = self.cfg
        b_next, chk, w = self.reply(nb, d)
        pen = 0.0
        if chk is not None:
            n_exit = exits(chk, d, cfg)
            if n_exit == 0:
                if w >= 1.0:
                    return cg - LOSS, []
                pen = w * min(cfg.react_mate_cost, LOSS)
            else:
                pen = w * (cfg.w_check + cfg.w_check_exit / n_exit)
        if self.spawn_ply is not None and ply == self.spawn_ply and self.spawn_tray:
            pen += spawn_penalty(b_next, d, self.spawn_tray, cfg, 1.0, 1)     # khay thả quân sau nước này: xe hết đường = thua
        fut, line = self.search(b_next, d, depth, ply + 1, bool(cap == "k" and cfg.king_blast))   # ăn tướng -> nước KẾ TIẾP trong chuỗi là nước NỔ
        fut_term = fut if fut <= -0.5 * LOSS else cfg.gamma * fut
        return cg - pen + fut_term, line

    def search(self, b, rook, depth, ply, blast=False):
        """Nút Max: điểm tích lũy tốt nhất của xe trong `depth` nước tới -> (điểm, [(đích, quân_ăn), ...])."""
        key = (frozenset(b.items()), rook, depth, ply if self.spawn_ply is not None else min(ply, 2), blast)
        hit = self.memo.get(key)
        if hit is not None:
            return hit
        self._tick()
        cfg = self.cfg
        cands = self._candidates(b, rook, blast)
        if not cands:
            res = (0.0 if cfg.simple_mode else -min(cfg.no_safe_penalty, LOSS), [])
        elif depth <= 1:                                   # thế cuối chuỗi: điểm ăn + điểm vị trí
            if self.spawn_ply is not None and ply == self.spawn_ply and self.spawn_tray:
                best = None                                # nước cuối này trùng lúc khay thả quân: trừ rủi ro hết đường
                for c in cands[:3]:
                    v_ = c[0] - spawn_penalty(c[3], c[1], self.spawn_tray, cfg, 1.0, 1)
                    if best is None or v_ > best[0]:
                        best = (v_, c)
                res = (best[0], [(best[1][1], best[1][2])])
            else:
                c = cands[0]
                res = (c[0], [(c[1], c[2])])
        else:
            res = (-1e18, [])
            for _g, d, cap, nb, _t, cg, _pos in self._select(cands, ply):
                tot, line = self._after(nb, d, cg, depth - 1, ply, cap)
                if tot > res[0]:
                    res = (tot, [(d, cap)] + line)
        self.memo[key] = res
        return res


def deep_rank(board, rook, cfg, base, depth, beam, time_limit, info=None, now=time.time, tray=None, spawn_in=None, root_blast=False):
    """Chấm lại các nước đi gốc `base` (kết quả 1 tầng của rank_moves) bằng tìm kiếm sâu dần tầng 2..depth trong hạn `time_limit`
    giây. Ô nguy hiểm giữ nguyên điểm. Trả danh sách cùng dạng, tốt nhất ở đầu; `info` (dict) nhận thống kê tìm kiếm."""
    t0 = now()
    # chừa 6% biên an toàn: giải phóng bảng nhớ (memo) lúc kết thúc cũng tốn vài ms nằm ngoài vòng kiểm tra giờ
    deadline = t0 + 0.94 * float(time_limit) if time_limit and float(time_limit) > 0 else None
    S = _Search(cfg, beam, deadline, now)
    if spawn_in is not None and spawn_in > 1 and tray:        # khay thả ở nước thứ `spawn_in` của xe (nước 1 đã tính trong điểm gốc)
        S.spawn_tray, S.spawn_ply = list(tray), int(spawn_in) - 1
    safe = [o for o in base if not o[3]]
    done, reached = None, 1
    if safe:
        for D in range(2, int(depth) + 1):
            if deadline is not None and now() > deadline:
                break
            res = {}
            try:
                for d, cap, v, _dg, _src in safe:
                    nb = after_move(board, rook, d)
                    if root_blast:                                 # nước gốc là nước NỔ: bàn sau nước đi đã mất các quân cùng hàng/cột
                        for q in blast_victims(nb, d):
                            nb.pop(q, None)
                    tot, line = S._after(nb, d, v, D - 1, 0, cap)
                    res[d] = (tot, [(d, cap)] + line)
            except _Deadline:
                break
            done, reached = res, D
    out = list(base)
    if done:
        out = [(d, cap, done[d][0] if d in done else v, dg, src) for d, cap, v, dg, src in base]
        out.sort(key=lambda o: -o[2])
    if info is not None:
        best = next((o for o in out if not o[3]), None)
        info.update(depth=reached, max_depth=int(depth), beam=int(beam), nodes=S.nodes,
                    ms=(now() - t0) * 1000.0, rook=rook,
                    line=(done[best[0]][1] if (done and best and best[0] in done) else ([(best[0], best[1])] if best else [])),
                    score=(best[2] if best else None), timeout=bool(done is None or reached < int(depth)))
    return out


def format_search(info):
    """Dòng log: độ sâu đang tìm kiếm + chuỗi nước đi tốt nhất và điểm dự đoán."""
    if not info or "depth" not in info:
        return ""
    cur, parts = info.get("rook"), []
    for d, cap in info.get("line") or []:
        parts.append(f"{d}" + (f" ĂN {KIND_NAMES.get(cap, cap)}" if cap else ""))
    sc = info.get("score")
    return (f"tìm sâu {info['depth']}/{info['max_depth']} tầng (beam {info['beam']}, {info['nodes']} nút, {info['ms']:.0f}ms"
            + (", hết giờ ở tầng sau" if info.get("timeout") and info["depth"] < info["max_depth"] else "")
            + f") | chuỗi tốt nhất từ {cur}: " + (" > ".join(parts) if parts else "(không có)")
            + (f" | điểm dự đoán {sc:.1f}" if sc is not None else ""))


def rank_moves(board, rook, cfg, tray=None, spawn_scale=0.3, overlay=None, depth=None, beam=None, time_limit=None, info=None, blast=False, spawn_in=None):
    """Danh sách nước đi đã chấm, tốt nhất ở đầu: [(ô_đích, quân_ăn, điểm, nguy_hiểm, nguồn_nguy_hiểm)].
    overlay = {ô: 'green'|'red'} do game vẽ: đỏ = nguy hiểm; xanh chỉ tin khi ô trống VÀ mô hình luật cũng thấy an toàn; ô không rõ -> mô hình.
    depth/beam/time_limit (mặc định lấy từ cfg.search_depth / beam_width / search_time_s): depth > 1 thì chấm lại bằng tìm kiếm sâu
    (`deep_rank`); `info` (dict) nhận thống kê tìm kiếm (độ sâu đạt được, số nút, chuỗi tốt nhất, điểm dự đoán).
    blast=True: vừa ĂN TƯỚNG xong -> nước này nổ sạch hàng + cột của ô đích (mục 5d): chấm theo tổng giá trị quân bị nổ, an toàn tính SAU khi nổ,
    bỏ qua ngoặc đỏ của game (game vẽ chưa tính vụ nổ) và không tìm sâu."""
    t_start = time.time()
    overlay = overlay or {}
    if blast:
        out = _rank_blast(board, rook, cfg, tray, spawn_scale, info, spawn_in)
        b_depth = cfg.search_depth if depth is None else depth
        b_beam = cfg.beam_width if beam is None else beam
        b_time = cfg.search_time_s if time_limit is None else time_limit
        if int(b_depth) > 1:                                # tìm sâu tiếp từ bàn SAU khi nổ (chuỗi ăn quân / thoát kẹt tiếp theo)
            if b_time and float(b_time) > 0:
                b_time = max(0.001, float(b_time) - (time.time() - t_start))
            out = deep_rank(board, rook, cfg, out, b_depth, b_beam, b_time, info, tray=tray, spawn_in=spawn_in, root_blast=True)
        return out
    kinds = ["n", "c", "r"] if tray is None else list(tray)     # chưa đọc được khay -> giả định; khay trống -> không có rủi ro
    scale = spawn_scale
    out = []
    for d, cap in rook_moves(board, rook):
        nb = after_move(board, rook, d)
        st = overlay.get(d)
        if st == "red" and d == (rook[0] - 1, rook[1]):
            st = None        # hình ma ĐỎ của quân xe tràn lên ô ngay phía trên nó (đã thấy ở ảnh doom/step) -> không phải ngoặc đỏ thật: để mô hình luật quyết
        if st == "red":
            danger, src = True, "game"
        else:
            md = is_attacked(nb, d, cfg)
            if st == "green" and cap is None and not md:
                danger, src = False, "game"
            else:
                # Nguy hiểm = game vẽ ĐỎ hoặc mô hình luật báo bị ăn. Ngoặc XANH KHÔNG đủ để coi là an toàn: ở ô có quân (nước ĂN)
                # game vẫn vẽ xanh dù xe bị ăn lại (đã gặp: xe ăn sĩ ở (1,3), tốt (2,3) bên dưới ăn lại xe).
                danger, src = md, "model"
        cv_ = cap_value(board, d, cap, cfg) if cap else 0
        if danger:
            v = -LOSS + 0.1 * cv_ - 50.0 * count_attackers(nb, d, cfg)
        else:
            fork = safe_threats(nb, d, cfg)
            sp_pen = spawn_penalty(nb, d, kinds, cfg, scale, spawn_in) + enemy_doom_penalty(nb, d, cfg)
            v = (cfg.capture_weight * cv_ + 1.0 * min(exits(nb, d, cfg), 8) + fork_bonus(fork, cfg) - sp_pen
                 + skewer_value(nb, d, cfg) + (cfg.w_king_blast if (cap == "k" and cfg.king_blast) else 0.0))
        out.append((d, cap, v, danger, src))
    out.sort(key=lambda o: -o[2])
    depth = cfg.search_depth if depth is None else depth
    beam = cfg.beam_width if beam is None else beam
    time_limit = cfg.search_time_s if time_limit is None else time_limit
    if int(depth) > 1:
        if time_limit and float(time_limit) > 0:                # hạn 1 lượt gồm cả thời gian chấm 1 tầng ở trên
            time_limit = max(0.001, float(time_limit) - (time.time() - t_start))
        out = deep_rank(board, rook, cfg, out, depth, beam, time_limit, info, tray=tray, spawn_in=spawn_in)
    elif info is not None:
        best = next((o for o in out if not o[3]), None)
        info.update(depth=1, max_depth=1, beam=int(beam), nodes=0, ms=0.0, rook=rook, timeout=False,
                    line=[(best[0], best[1])] if best else [], score=best[2] if best else None)
    return out


def _rank_blast(board, rook, cfg, tray, spawn_scale, info=None, spawn_in=None):
    """Xếp hạng nước đi khi xe ĐANG CÓ HIỆU ỨNG NỔ (vừa ăn tướng): đích `d` nổ sạch mọi quân cùng hàng/cột. Điểm = giá trị quân bị nổ
    (x capture_weight) + chút điểm vị trí (độ thoáng, ít bị chiếu) trên bàn SAU khi nổ; ô còn bị quân sống sót ăn = nguy hiểm."""
    kinds = ["n", "c", "r"] if tray is None else list(tray)
    out = []
    for d, cap in rook_moves(board, rook):
        nb = after_move(board, rook, d)
        for q in blast_victims(nb, d):
            nb.pop(q, None)
        gain = cfg.capture_weight * blast_value(board, d, cfg)
        danger = is_attacked(nb, d, cfg)
        if danger:
            v = -LOSS + 0.1 * gain - 50.0 * count_attackers(nb, d, cfg)
        else:
            fork = safe_threats(nb, d, cfg)
            sp_pen = spawn_penalty(nb, d, kinds, cfg, spawn_scale, spawn_in) + enemy_doom_penalty(nb, d, cfg)
            v = gain + 1.0 * min(exits(nb, d, cfg), 8) + fork_bonus(fork, cfg) - sp_pen
        out.append((d, cap, v, danger, "blast"))
    out.sort(key=lambda o: -o[2])
    if info is not None:
        best = next((o for o in out if not o[3]), None)
        info.update(depth=1, max_depth=1, beam=0, nodes=0, ms=0.0, rook=rook, timeout=False, blast=True,
                    line=[(best[0], best[1])] if best else [], score=best[2] if best else None)
    return out


def pick_move(rk, deep=False, slack=0.0, blast=False, capture_first=False, max_slack=MAX_CAPTURE_SLACK):
    """Chọn từ danh sách đã chấm. Có ô an toàn: không tìm sâu -> ĂN QUÂN an toàn trước (quân giá trị cao trước), không có thì ô an
    toàn tốt nhất. Có tìm sâu (deep) -> nước điểm cao nhất, nhưng nếu có nước ĂN QUÂN an toàn mà điểm kém nước tốt nhất không quá
    `slack` (chặn <= MAX_CAPTURE_SLACK = 15) thì vẫn ăn (điểm sâu đã trừ nước ăn xong bị kẹt hết đường thoát). Hết ô an toàn: ô ít nguy hiểm nhất.
    Trả (ô_đích, quân_ăn_loại, điểm) hoặc None."""
    if not rk:
        return None
    safe = [o for o in rk if not o[3]]
    if not safe:
        best = rk[0]
        return best[0], best[1], best[2]
    caps = [o for o in safe if o[1] is not None]
    if blast:                                  # nổ hàng + cột: chỉ theo điểm (không ưu tiên 'ăn' vì quân bị nổ không nằm ở ô đích)
        best = safe[0]
        return best[0], best[1], best[2]
    if capture_first and caps:                 # chế độ ăn nhanh: có nước ĂN AN TOÀN là ăn (nước ăn điểm cao nhất = chuỗi ăn quân tốt nhất)
        best = caps[0]
        return best[0], best[1], best[2]
    if deep:
        slack = max(0.0, min(float(slack), float(max_slack)))   # chặn bẫy tham ăn: chỉ cho lệch tối đa vài điểm
        best = safe[0]
        # chỉ ăn thay nước tốt nhất khi điểm sâu của nước ăn gần ngang VÀ không phải nhánh sắp thua
        if caps and best[1] is None and caps[0][2] > -0.5 * LOSS and caps[0][2] >= best[2] - slack:
            best = caps[0]
    else:
        best = caps[0] if caps else safe[0]
    return best[0], best[1], best[2]


def is_doomed(rk):
    """True = NƯỚC KẾ TIẾP CHẮC CHẮN CHẾT: có nước đi nhưng TẤT CẢ đều nguy hiểm (game vẽ ngoặc đỏ hoặc mô hình luật báo bị ăn),
    không còn ô an toàn nào. `rk` là danh sách của `rank_moves`. Danh sách rỗng (xe không có nước) KHÔNG tính (đã có nhánh riêng)."""
    return bool(rk) and all(o[3] for o in rk)


def choose_move(board, rook, cfg, tray=None, spawn_scale=0.3, overlay=None, depth=None, beam=None, time_limit=None, info=None, blast=False, spawn_in=None):
    """Chọn nước đi cho xe (xem `rank_moves` / `pick_move`). Trả (ô_đích, quân_ăn_loại, điểm) hoặc None."""
    info = info if info is not None else {}
    rk = rank_moves(board, rook, cfg, tray, spawn_scale, overlay, depth, beam, time_limit, info, blast, spawn_in)
    sl = cfg.capture_slack if cfg.simple_mode else max(cfg.capture_slack, cfg.careful_capture_slack)
    return pick_move(rk, info.get("depth", 1) > 1, 0.0 if (spawn_in is not None and spawn_in <= 1) else sl, blast, cfg.simple_mode,
                     max_slack=MAX_CAPTURE_SLACK if cfg.simple_mode else max(MAX_CAPTURE_SLACK, cfg.careful_capture_slack))


# ----------------------------------------------------------------------------
# 6) Chạy bước
# ----------------------------------------------------------------------------
class _Stop(Exception):
    pass


def board_text(st: BoardState, overlay=None):
    rows = []
    for r in range(ROWS):
        cells = []
        for c in range(COLS):
            k = st.board.get((r, c))
            if k:
                cells.append(k)
            else:
                o = (overlay or {}).get((r, c))
                cells.append({"green": "+", "red": "!"}.get(o, "."))
        rows.append(" ".join(cells))
    return "\n".join(rows)


def save_debug(frame, grid, st, move=None, tag="xq", overlay=None, out_dir=None):
    try:
        os.makedirs(out_dir or DEBUG_DIR, exist_ok=True)
        im = frame.copy()
        for (r, c), k in st.board.items():
            x, y = grid.px(r, c)
            col = ROOK_DEBUG_COLOR if k == "X" else (200, 0, 150)
            cv2.circle(im, (int(x), int(y)), int(grid.pitch * 0.4), col, 2)
            cv2.putText(im, k, (int(x) - 8, int(y) + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
        for (r, c), o in (overlay or {}).items():
            x, y = grid.px(r, c)
            cv2.circle(im, (int(x), int(y)), 7, (0, 200, 0) if o == "green" else (0, 0, 255), -1)
        if move:
            x, y = grid.px(*move)
            cv2.circle(im, (int(x), int(y)), int(grid.pitch * 0.46), (255, 0, 0), 3)
        path = os.path.join(out_dir or DEBUG_DIR, f"{tag}_{time.strftime('%H%M%S')}.png")
        cv2.imencode(".png", im)[1].tofile(path)
        return path
    except Exception:
        return None


ALL_MODES = ("tap", "tap_corner", "drag", "tap_tap")
_ORDER = {"quiet": ["tap", "tap_corner", "drag", "tap_tap"], "cap": ["tap", "drag", "tap_corner", "tap_tap"]}
_LEARNED = {"quiet": 0, "cap": 0}          # nhớ kiểu chạm đã chạy được cho các lần chạy bước sau (mặc định khi không biết giả lập)
_LEARNED_BY = {}                           # {mã giả lập: {"quiet", "cap"}} - mỗi giả lập nhớ riêng kiểu chạm (chạy song song nhiều giả lập)


class XiangqiBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_rounds=0, max_seconds=0, settle_s=1.3,
                 input_mode="auto", unknown_as="u", min_match=0.68, spawn_risk_every_turn=0.3, debug=False, img_match=IMG_MATCH_THR,
                 lost_limit=4, close_popup=True, stable_timeout_s=4.0, stable_gap_s=0.3, stable_frames=2, enemy_wait_s=5.0,
                 save_shots=True, shot_keep=120, sleep=time.sleep, now=time.time,
                 search_depth=None, beam_width=None, search_time_s=None, capture_slack=None,
                 w_skewer=None, king_blast=None, w_king_blast=None,
                 simple_mode=None, careful_after_rounds=None, careful_min_pieces=None, rc_many=None, w_rc_base=None, w_rc_adj=None,
                 w_simple_doom=None, careful_capture_slack=None,
                 require_marks=True, marks_wait_s=6.0, fast_ready=True, marks_full_ratio=0.8, nomark_limit=3, stop_on_unread=True, stop_on_doom=True, spawn_risk_at_timer=None,
                 unread_retries=4, unread_retry_wait_s=0.8, stop_on_missing=True):
        # [2026-11-18 #7] Tham số chiến thuật để None = lấy MẶC ĐỊNH TỪ class Config (đổi số ở Config là đủ). Chỉ khi bước auto_xiangqi
        # có field cùng tên thì field đó mới ghi đè.
        _d = Config()
        _pick = lambda v, dflt: dflt if v is None else v
        search_depth, beam_width = _pick(search_depth, _d.search_depth), _pick(beam_width, _d.beam_width)
        search_time_s, capture_slack = _pick(search_time_s, _d.search_time_s), _pick(capture_slack, _d.capture_slack)
        w_skewer, king_blast, w_king_blast = _pick(w_skewer, _d.w_skewer), _pick(king_blast, _d.king_blast), _pick(w_king_blast, _d.w_king_blast)
        simple_mode = _pick(simple_mode, _d.simple_mode)
        careful_after_rounds, careful_min_pieces = _pick(careful_after_rounds, _d.careful_after_rounds), _pick(careful_min_pieces, _d.careful_min_pieces)
        rc_many, w_rc_base, w_rc_adj = _pick(rc_many, _d.rc_many), _pick(w_rc_base, _d.w_rc_base), _pick(w_rc_adj, _d.w_rc_adj)
        w_simple_doom, careful_capture_slack = _pick(w_simple_doom, _d.w_simple_doom), _pick(careful_capture_slack, _d.careful_capture_slack)
        spawn_risk_at_timer = _pick(spawn_risk_at_timer, _d.spawn_hit)
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test, self.debug = bool(test), bool(debug)
        self.max_rounds = int(max_rounds or 0)
        self.max_seconds = float(max_seconds or 0)
        self.settle_s = float(settle_s)
        self.forced = input_mode if input_mode in ALL_MODES else None
        self.unknown_as, self.min_match = unknown_as or "u", float(min_match)
        self.img_match = float(img_match)
        self.spawn_scale = float(spawn_risk_every_turn)
        self.lost_limit = int(lost_limit)
        self.close_popup = bool(close_popup)
        self.stable_timeout_s, self.stable_gap_s = float(stable_timeout_s), float(stable_gap_s)
        self.stable_frames = max(2, int(stable_frames))
        self.enemy_wait_s = max(0.0, float(enemy_wait_s))      # sau nước của xe: chờ TỐI ĐA bấy nhiêu giây cho quân địch đi (0 = không chờ)
        self.save_shots, self.shot_keep = bool(save_shots), int(shot_keep)
        self.require_marks = bool(require_marks) and not bool(test)   # TEST chỉ chụp 1 lần nên không đòi ngoặc xanh
        self.marks_wait_s = max(0.5, float(marks_wait_s))
        self.fast_ready = bool(fast_ready)                          # ngoặc xanh phủ đủ = bàn sẵn sàng: đọc ngay 1 khung
        self.marks_full_ratio = min(1.0, max(0.3, float(marks_full_ratio)))   # tỉ lệ ô trống xe đi được phải có ngoặc để coi là "phủ đủ"
        self.nomark_limit = max(1, int(nomark_limit))
        self.stop_on_unread = bool(stop_on_unread) and not bool(test)
        self.unread_retries = max(0, int(unread_retries))          # quân không đọc được (vd. tướng đang có hoạt ảnh): quét lại tối đa bấy nhiêu lần rồi mới dừng
        self.unread_retry_wait_s = max(0.1, float(unread_retry_wait_s))
        self.stop_on_missing = bool(stop_on_missing) and not bool(test)   # mất quân không giải thích được (sau khi quét lại) -> DỪNG thay vì đi tiếp
        self.last_good = None             # {ô: loại} bàn địch của lượt gần nhất đã đọc chắc = TRÍ NHỚ để ưu tiên đọc (đặc biệt tướng)
        self.marks_missing = False        # lần _stable gần nhất hết hạn chờ mà chưa thấy ngoặc xanh
        self.tap_marks = 0                # số lượt liên tiếp game KHÔNG tự vẽ ngoặc (phải chạm xe) -> lần sau chờ ngắn hơn
        self.pred = None                  # dự đoán sau nước vừa đi
        self.pstat = [0, 0, 0]            # [dự đoán đúng, lệch, tổng]
        self.sleep, self.now = sleep, now
        self.cfg = Config()
        self.cfg.simple_mode = bool(simple_mode)
        self.simple_base = bool(simple_mode)     # simple_mode người dùng chọn; mỗi lượt có thể bị tắt tạm khi bàn đông quân / quá lượt (careful_*)
        self.mode_logged = None
        self.cfg.careful_after_rounds = max(0, int(careful_after_rounds))
        self.cfg.careful_min_pieces = max(0, int(careful_min_pieces))
        self.cfg.w_simple_doom = max(0.0, float(w_simple_doom))
        self.cfg.careful_capture_slack = max(0.0, float(careful_capture_slack))
        self.cfg.rc_many = max(0, int(rc_many))
        self.cfg.w_rc_base, self.cfg.w_rc_adj = max(0.0, float(w_rc_base)), max(0.0, float(w_rc_adj))
        try:                              # độ sâu 1-12, beam 1-12; giá trị sai thì dùng mặc định
            self.cfg.search_depth = max(1, min(12, int(search_depth)))
        except (TypeError, ValueError):
            pass
        try:
            self.cfg.beam_width = max(1, min(12, int(beam_width)))
        except (TypeError, ValueError):
            pass
        try:
            self.cfg.search_time_s = max(0.0, float(search_time_s))
        except (TypeError, ValueError):
            pass
        try:
            self.cfg.capture_slack = max(0.0, float(capture_slack))
        except (TypeError, ValueError):
            pass
        try:                              # đòn xiên (dụ quân chặn chạy để lộ quân sau) + hiệu ứng nổ sau khi ăn tướng
            self.cfg.w_skewer = max(0.0, float(w_skewer))
        except (TypeError, ValueError):
            pass
        self.cfg.king_blast = bool(king_blast)
        try:
            self.cfg.w_king_blast = max(0.0, float(w_king_blast))
        except (TypeError, ValueError):
            pass
        try:                              # hệ số rủi ro khi đọc được đồng hồ cát = 1 (khay hiện ngay ở nước này)
            self.cfg.spawn_hit = min(1.0, max(0.0, float(spawn_risk_at_timer)))
        except (TypeError, ValueError):
            pass
        self.stop_on_doom = bool(stop_on_doom)   # True = nước kế tiếp CHẮC CHẮN chết (mọi nước đều nguy hiểm) thì DỪNG, không bấm
        self.doom_streak = 0              # số lần đọc liên tiếp (bàn không đổi) mà mọi nước đều chết
        self.blast = False                # True = vừa ĂN TƯỚNG xong: nước đi kế tiếp nổ sạch hàng + cột của ô đích
        self.pending_blast = False        # nước đang chờ xác nhận có phải nước NỔ không
        self.t0 = now()
        self.rounds = 0
        dev = str(getattr(adb, "device_id", "") or "").strip()
        self.dev_tag = re.sub(r"[^0-9A-Za-z._-]+", "_", dev) if dev else ""
        self.debug_dir = os.path.join(DEBUG_DIR, self.dev_tag) if self.dev_tag else DEBUG_DIR   # ảnh debug riêng từng giả lập
        self.learned = _LEARNED_BY.setdefault(self.dev_tag, dict(_LEARNED)) if self.dev_tag else _LEARNED
        self.idx = dict(self.learned)
        self.pending = None               # (src, dst, cap, kind, mode)
        self.rook_hint = None             # ô xe có thể đang đứng (ô cũ + ô đích của nước vừa đi): xe chỉ di chuyển bằng nước của mình
        self.consec_fail = 0
        self.popups = 0
        self.mis = [0, 0]                 # [số ô game ≠ mô hình, số ô so sánh được]

    # --- tiện ích ---
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

    def _mode(self, kind):
        if self.forced:
            return self.forced
        order = _ORDER[kind]
        return order[self.idx[kind] % len(order)]

    def _fail(self, why):
        if not self.pending:
            return
        src, dst, cap, kind, mode = self.pending
        self.pending = None
        self.consec_fail += 1
        if not self.forced:
            self.idx[kind] += 1
        self.log("warn", f"Xiangqi: nước {src}->{dst} ({'ăn' if cap else 'đi'}, kiểu '{mode}') KHÔNG được: {why}"
                         + ("" if self.forced else f" -> đổi sang kiểu '{self._mode(kind)}'"))
        if self.consec_fail >= 2 * len(ALL_MODES) + 2:
            raise _Stop("thử hết các kiểu chạm mà xe vẫn không đi")

    def _ok(self):
        if not self.pending:
            return
        kind, cap = self.pending[3], self.pending[2]
        self.pending = None
        self.consec_fail = 0
        self.learned[kind] = self.idx[kind]
        self.rounds += 1
        if self.pending_blast:             # nước NỔ đã đi xong -> hết hiệu ứng
            self.pending_blast, self.blast = False, False
        if cap == "k" and self.cfg.king_blast:
            self.blast = True
            self.log("info", "Xiangqi: ĂN TƯỚNG -> nước đi KẾ TIẾP sẽ NỔ sạch quân cùng hàng + cột của ô đích")

    def _tap_rook(self, grid, rook):
        x, y = grid.px(*rook)
        self.adb.tap_px(x, y)
        self.sleep(0.4)

    def _do_move(self, grid, src, dst, cap):
        kind = "cap" if cap else "quiet"
        mode = self._mode(kind)
        sx, sy = grid.px(*src)
        dx, dy = grid.px(*dst)
        p = grid.pitch
        if mode == "drag":
            self.adb.swipe_px(sx, sy, dx, dy, 250)
        elif mode == "tap_tap":
            self.adb.tap_px(sx, sy)
            self.sleep(0.25)
            self.adb.tap_px(dx, dy)
        elif mode == "tap_corner":
            ox = -0.3 * p if dst[1] >= COLS // 2 else 0.3 * p
            oy = -0.3 * p if dst[0] >= ROWS // 2 else 0.3 * p
            self.adb.tap_px(dx + ox, dy + oy)
        else:
            self.adb.tap_px(dx, dy)
        self.pending = (src, dst, cap, kind, mode)
        self.rook_hint = (src, dst)

    def _spawn_hint(self):
        """Khay lượt trước (các quân SẮP hiện) khi nước vừa rồi làm khay thả quân (đồng hồ <= 1 hoặc không đọc được) -> dùng đoán loại quân mới hiện mà chưa đọc được."""
        pr = self.pred
        if not pr or not pr.get("tray"):
            return None
        si = pr.get("spawn_in")
        if si is not None and si > 1:
            return None
        return [k for k in pr["tray"] if k not in ("u", "X")] or None

    def _stable(self):
        """Chờ bàn ĐỨNG YÊN rồi mới đọc: chụp liên tiếp tới khi `stable_frames` khung liền nhau cho cùng tập ô có quân + vị trí xe
        (địch đi / quân hiện / hình ma chạy sẽ làm bàn đổi). Loại quân lấy theo ĐA SỐ các khung ổn định (1 khung nhoè không làm nhầm).
        Trả (khung cuối, lưới, BoardState, đã_đứng_yên, số_khung). Gặp popup / không thấy bàn thì trả ngay để vòng chính xử lý."""
        hist = []                          # [(khoá, board, st)]
        t_end = self.now() + self.stable_timeout_s
        pr = self.pred if (self.pred and not self.test and self.enemy_wait_s > 0) else None
        t_enemy = self.now() + self.enemy_wait_s if pr else 0.0     # hạn chờ địch ĐI sau nước của xe
        waited = 0
        n = 0
        self.marks_missing = False
        t_marks = None                     # hạn chờ ngoặc xanh (đặt khi bắt đầu xét ngoặc, sau khi địch đã đi)
        marks_seen = False
        while True:
            self._check()
            _t0 = time.time()
            fr = self._shot()
            _t1 = time.time()
            n += 1
            if (self.close_popup and is_popup(fr)):
                return fr, None, None, False, n
            # cache lưới bàn: find_grid chạy trên cả khung hình nên chậm; lưới gần như không đổi trong 1 ván
            grid = getattr(self, "_grid_cache", None)
            if grid is None or fr.shape[:2] != getattr(self, "_grid_shape", None) or n % 8 == 0:
                grid = find_grid(fr)
                self._grid_cache, self._grid_shape = grid, fr.shape[:2]
            _t2 = time.time()
            st = read_board(fr, grid, self.unknown_as, self.min_match, self.img_match, rook_hint=self.rook_hint, prev=(self.pred["enemy"] if self.pred else self.last_good), spawn_hint=self._spawn_hint()) if grid else None
            _t3 = time.time()
            self.log("info", f"Xiangqi ⏱ khung {n}: chụp {_t1 - _t0:.2f}s | find_grid {_t2 - _t1:.2f}s | read_board {_t3 - _t2:.2f}s "
                     f"[tìm đĩa {RB_PROF.get('discs', 0):.2f} | ngoặc {RB_PROF.get('marks', 0):.2f} | chọn xe {RB_PROF.get('rook', 0):.2f} | nhận quân {RB_PROF.get('classify', 0):.2f}s, {RB_PROF.get('n', 0)} đĩa]")
            if grid is None or st is None or st.rook is None:
                return fr, grid, st, False, n
            mk, full = None, False
            if self.require_marks:
                mk = marks_ready2(fr, grid, st)
                # NGOẶC XANH PHỦ ĐỦ (>= marks_full_ratio số ô trống xe đi được, và có ít nhất 1 ô xanh) = game vẽ xong = bàn sẵn sàng
                full = bool(self.fast_ready and mk[0] >= 1 and (mk[3] == 0 or mk[4] >= self.marks_full_ratio * mk[3]))
            if pr and not full and st.rook == pr["dst"] and self.now() < t_enemy:
                # xe đã tới đích nhưng quân địch CHƯA đi (mỗi lượt đúng 1 địch đi / quân mới hiện) -> chưa phải lúc đọc bàn, chờ tiếp
                if {p for p, k in st.board.items() if k != "X"} == set(pr["enemy"]):
                    waited += 1
                    hist = []
                    t_end = self.now() + self.stable_timeout_s
                    self.sleep(self.stable_gap_s)
                    continue
            if waited and pr:
                self.log("info", f"Xiangqi: đã chờ địch đi {waited} khung")
                waited, pr = 0, None
            if self.require_marks:
                # CHỈ khi xe ta hiện ngoặc XANH (+) màn mới ổn định; chưa có = còn hoạt ảnh -> không tính, chờ tiếp
                ng, na, npool = mk[0], mk[1], mk[2]
                if ng < 1:
                    hist = []
                    if t_marks is None:
                        t_marks = self.now() + (self.marks_wait_s if self.tap_marks < 2 else min(self.marks_wait_s, 1.5))
                    if self.now() < t_marks:
                        self.sleep(self.stable_gap_s)
                        continue
                    if na >= min(2, npool) and npool > 0:
                        self.log("warn", f"Xiangqi: chỉ thấy ngoặc ĐỎ ({na}/{npool} ô), không có ngoặc xanh (mọi nước đều bị chiếu?) -> vẫn tính")
                    else:
                        self.marks_missing = True
                        self.log("warn", f"Xiangqi: sau {self.marks_wait_s:.1f}s xe {st.rook} chưa hiện ngoặc xanh (+) -> coi là CHƯA ổn định")
                        return fr, grid, st, False, n
                if not marks_seen:
                    marks_seen = True
                    t_end = self.now() + self.stable_timeout_s      # tính hạn đợi đứng yên từ lúc ngoặc xanh hiện
                if full:
                    self.log("info", f"Xiangqi: ngoặc xanh đã phủ đủ ({mk[4]}/{mk[3]} ô trống) -> bàn SẴN SÀNG, đọc ngay khung {n}")
                    return fr, grid, st, True, n
            key = (frozenset(st.board.keys()), st.rook)
            if hist and hist[-1][0] != key:
                hist = []
            hist.append((key, st.board, st))
            if len(hist) >= self.stable_frames and any(h[1] != hist[-1][1] for h in hist[-self.stable_frames:-1]):
                hist = hist[-1:]                   # cùng ô nhưng ĐỌC KHÁC loại quân giữa các khung -> chưa chắc, đọc thêm (chỉ cần N khung đọc GIỐNG HỆT nhau)
            if len(hist) >= self.stable_frames:
                votes = {}
                for _, bd, _s in hist[-self.stable_frames:]:
                    for p, k in bd.items():
                        votes.setdefault(p, []).append(k)
                merged = {p: max(set(ks), key=ks.count) for p, ks in votes.items()}
                st2 = BoardState(board=merged, rook=st.rook, low_conf=st.low_conf, src=st.src, mem=st.mem, rook_why=st.rook_why, swept=st.swept)   # giữ src để log đếm đúng nguồn nhận diện
                return fr, grid, st2, True, n
            if self.now() >= t_end:
                self.log("warn", f"Xiangqi: bàn chưa đứng yên sau {self.stable_timeout_s:.1f}s ({n} khung), vẫn đọc khung cuối")
                return fr, grid, st, False, n
            self.sleep(self.stable_gap_s)

    def _save_step(self, fr, grid, st, dst, cap, ov, score, tag="step", force=False):
        """Lưu ảnh mỗi nước: quân đọc được, ngoặc game, mũi tên xe -> đích + dòng dự đoán. Trả đường dẫn hoặc None.
        force=True: lưu dù đã tắt save_shots (ảnh lỗi `unread`/`nomarks`, không bị _prune_shots xoá)."""
        if not self.save_shots and not force:
            return None
        try:
            os.makedirs(self.debug_dir, exist_ok=True)
            im = fr.copy()
            p = grid.pitch
            if st.low_conf and tag in ("step", "miss"):      # có quân đọc không chắc -> lưu thêm ảnh GỐC (chưa vẽ) để thêm mẫu chữ bằng CLI (ảnh đã vẽ làm hỏng chữ)
                try:
                    cv2.imencode(".png", fr)[1].tofile(os.path.join(self.debug_dir, f"raw_{self.rounds + 1:04d}_{time.strftime('%H%M%S')}.png"))
                except Exception:
                    pass
            for (r, c), k in st.board.items():
                x, y = grid.px(r, c)
                col = ROOK_DEBUG_COLOR if k == "X" else (255, 0, 255)   # xe ta: XANH LÁ; quân địch: tím
                cv2.circle(im, (int(x), int(y)), int(p * 0.4), col, 2)
                col = ROOK_DEBUG_COLOR if k == "X" else (0, 0, 255)     # chữ ghi chú loại quân: ĐỎ (xe ta: xanh lá cùng màu vòng)
                # chữ loại quân viết ở RÌA TRÊN-TRÁI vòng tròn (không đè lên chữ Hán trên quân -> ảnh dùng cắt mẫu được)
                cv2.putText(im, k, (int(x - p * 0.48), int(y - p * 0.30)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            for lc in (st.low_conf or []):                          # quân KHÔNG đọc được loại: vòng VÀNG dày
                try:
                    x, y = grid.px(*lc[0])
                    cv2.circle(im, (int(x), int(y)), int(p * 0.46), (0, 255, 255), 4)
                except Exception:
                    pass
            for (r, c), o in (ov or {}).items():
                x, y = grid.px(r, c)
                cv2.circle(im, (int(x - p * 0.28), int(y - p * 0.28)), 5, (0, 200, 0) if o == "green" else (0, 0, 255), -1)   # chấm ở rìa trên-trái ô
            if dst:
                a, b = grid.px(*st.rook), grid.px(*dst)
                dx_, dy_ = b[0] - a[0], b[1] - a[1]
                ln_ = max(1e-6, (dx_ * dx_ + dy_ * dy_) ** 0.5)
                ux_, uy_ = dx_ / ln_, dy_ / ln_
                a2 = (a[0] + ux_ * p * 0.42, a[1] + uy_ * p * 0.42)       # mũi tên chỉ đi từ RÌA vòng xe tới RÌA vòng đích (không đè lên quân)
                b2 = (b[0] - ux_ * p * 0.36, b[1] - uy_ * p * 0.36)
                if ln_ > p * 0.78 + 8:
                    cv2.arrowedLine(im, (int(a2[0]), int(a2[1])), (int(b2[0]), int(b2[1])), (255, 0, 0), 2, tipLength=min(0.3, 14.0 / max(1.0, ln_ - p * 0.78)))
                cv2.circle(im, (int(b[0]), int(b[1])), int(p * 0.34), (255, 0, 0), 2)
                txt = f"L{self.rounds + 1} {st.rook}->{dst}" + (f" an {cap}" if cap else "") + f" d={score:.0f}"
                cv2.putText(im, txt, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)   # chữ ĐỎ, nhỏ
            path = os.path.join(self.debug_dir, f"{tag}_{self.rounds + 1:04d}_{time.strftime('%H%M%S')}_{int(time.time() * 1000) % 1000:03d}.jpg")
            cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(path)
            self._prune_shots()
            return path
        except Exception:
            return None

    def _prune_shots(self):
        try:
            fs = sorted((f for f in os.listdir(self.debug_dir) if f.startswith(("step_", "miss_", "raw_")) and f.endswith((".jpg", ".png"))),
                        key=lambda f: os.path.getmtime(os.path.join(self.debug_dir, f)))
            for f in fs[:max(0, len(fs) - self.shot_keep)]:
                os.remove(os.path.join(self.debug_dir, f))
        except Exception:
            pass

    def _save_unread(self, fr, grid, st, tag="unread"):
        """Bot DỪNG vì không đọc được quân / không thấy ngoặc xanh: lưu ảnh GỐC (`<tag>_raw_*.png`, để cắt ảnh mẫu) + ảnh vẽ
        (`<tag>_*.jpg`: loại quân đọc được, vòng vàng quanh quân không đọc được) vào debug_xiangqi/. Luôn lưu (không phụ thuộc save_shots)"""
        try:
            os.makedirs(self.debug_dir, exist_ok=True)
            stamp = f"{time.strftime('%H%M%S')}_{int(time.time() * 1000) % 1000:03d}"
            raw = os.path.join(self.debug_dir, f"{tag}_raw_{self.rounds + 1:04d}_{stamp}.png")
            cv2.imencode(".png", fr)[1].tofile(raw)
            if grid is not None and st is not None:
                try:
                    ov = overlay_states(read_marks(fr, grid), grid, skip=st.rook)
                except Exception:
                    ov = {}
                self._save_step(fr, grid, st, None, None, ov, 0, tag=tag, force=True)
            return raw
        except Exception:
            return None

    def _verify(self, fr, grid, st):
        """So bàn THẬT sau nước đi với DỰ ĐOÁN (xe tới đích, quân bị ăn mất, tối đa 1 quân địch đi + quân mới từ khay).
        Lệch = rất có thể đã ĐỌC NHẦM (quân thừa/thiếu, đổi loại) -> log + lưu ảnh miss_*."""
        pr, self.pred = self.pred, None
        if not pr:
            return
        actual = {p: k for p, k in st.board.items() if k != "X"}
        exp = pr["enemy"]
        missing = [p for p in exp if p not in actual]
        extra = [p for p in actual if p not in exp]
        flips = [(p, exp[p], actual[p]) for p in exp if p in actual and exp[p] != actual[p]
                 and "u" not in (exp[p], actual[p])]
        spawn_n = len(pr.get("tray") or [])
        bad = []
        if st.rook != pr["dst"]:
            bad.append(f"xe ở {st.rook} chứ không phải {pr['dst']}")
        if len(missing) > 1:
            bad.append(f"mất {len(missing)} quân {missing[:4]} (chỉ 1 quân địch đi)")
        if len(extra) > 1 + spawn_n:
            bad.append(f"thừa {len(extra)} quân {extra[:4]} (khay {spawn_n})")
        if flips:
            bad.append(f"đổi loại {flips[:3]}")
        self.pstat[2] += 1
        if not bad:
            self.pstat[0] += 1
            mv = f"địch đi {missing[0]}->{extra[0]}" if len(missing) == 1 and len(extra) >= 1 else \
                 (f"quân mới hiện {extra[:3]}" if extra else "địch không đổi chỗ")
            self.log("info", f"Xiangqi dự đoán ĐÚNG (lượt {pr['round']}" + (", đã ăn" if pr["cap"] else "") + f"): {mv}")
        else:
            self.pstat[1] += 1
            p = self._save_step(fr, grid, st, None, None, None, 0, tag="miss")
            self.log("warn", f"Xiangqi dự đoán LỆCH (lượt {pr['round']}): " + "; ".join(bad) + (f" | ảnh {p}" if p else ""))

    def _handle_popup(self, fr):
        """Bảng Sổ Tay hiện ra: tính là nước vừa rồi hỏng (bấm trúng quân địch mở Sổ Tay), bấm X tắt."""
        self.popups += 1
        self._fail("hiện bảng Sổ Tay Quân Cờ")
        x, y, found = find_close_button(fr)
        self.log("info", f"Xiangqi: bảng Sổ Tay hiện -> bấm X tại ({int(x)},{int(y)})" + ("" if found else " [theo tỉ lệ]"))
        if self.test:
            return
        self.adb.tap_px(x, y)
        self.sleep(0.9)

    def _rescan_unread(self, fr, grid, st, stable_ok, nfr):
        """Có quân KHÔNG đọc được loại (hay gặp: quân tướng có hoạt ảnh nên khung chụp bị nhoè/đổi hình) -> chờ rồi quét lại
        tối đa `unread_retries` lần. Hết lần thử mà vẫn còn quân không đọc được thì trả kết quả lần cuối để vòng chính DỪNG.
        Mỗi lần quét lại dùng `_stable()` (chờ bàn đứng yên) nên tránh được khung giữa hoạt ảnh. Trả (fr, grid, st, stable_ok, nfr, ok)
        với ok=False nghĩa là bàn/popup đã đổi (vòng chính xử lý lại từ đầu)."""
        for i in range(1, self.unread_retries + 1):
            self.log("warn", f"Xiangqi: chưa đọc được {len(st.low_conf)} quân {st.low_conf[:4]} -> quét lại {i}/{self.unread_retries}")
            self.sleep(self.unread_retry_wait_s)
            self._check()
            fr2, grid2, st2, ok2, n2 = self._stable()
            if grid2 is None or st2 is None or st2.rook is None or (self.close_popup and is_popup(fr2)):
                return fr2, grid2, st2, ok2, n2, False      # mất bàn / hiện popup: để vòng chính xử lý
            fr, grid, st, stable_ok, nfr = fr2, grid2, st2, ok2, n2
            if not st.low_conf:
                self.log("info", f"Xiangqi: quét lại lần {i} đã đọc được hết quân")
                return fr, grid, st, stable_ok, nfr, True
        return fr, grid, st, stable_ok, nfr, True

    def _unexplained_missing(self, st):
        """Sau nước của xe, game chỉ cho TỐI ĐA 1 quân địch đi (quân mới từ khay chỉ làm THÊM quân). So bàn vừa đọc với dự đoán `pred`:
        mất >= 2 quân, hoặc mất 1 quân mà không có quân nào xuất hiện thêm = có quân bị ĐỌC SÓT (hay gặp: tướng đang loé điện) -> trả danh sách ô mất."""
        pr = self.pred
        if not pr or st is None or st.rook != pr.get("dst"):
            return []
        exp = pr["enemy"]
        actual = {p for p, k in st.board.items() if k != "X"}
        missing = [p for p in exp if p not in actual]
        extra = [p for p in actual if p not in exp]
        if len(missing) >= 2 or (len(missing) == 1 and not extra):
            return missing
        return []

    def _rescan_missing(self, fr, grid, st, stable_ok, nfr):
        """Như _rescan_unread nhưng cho trường hợp MẤT QUÂN không giải thích được: chờ rồi quét lại tối đa `unread_retries` lần."""
        for i in range(1, self.unread_retries + 1):
            self.log("warn", f"Xiangqi: mất quân không giải thích được {self._unexplained_missing(st)} -> quét lại {i}/{self.unread_retries}")
            self.sleep(self.unread_retry_wait_s)
            self._check()
            fr2, grid2, st2, ok2, n2 = self._stable()
            if grid2 is None or st2 is None or st2.rook is None or (self.close_popup and is_popup(fr2)):
                return fr2, grid2, st2, ok2, n2, False
            fr, grid, st, stable_ok, nfr = fr2, grid2, st2, ok2, n2
            if not self._unexplained_missing(st):
                self.log("info", f"Xiangqi: quét lại lần {i} đã đủ quân")
                return fr, grid, st, stable_ok, nfr, True
        return fr, grid, st, stable_ok, nfr, True

    # --- vòng chính ---
    def run(self) -> bool:
        try:        # thư mục ảnh mẫu tự cắt (xem docstring mục 6)
            os.makedirs(TEMPLATE_DIR, exist_ok=True)
            rd = os.path.join(TEMPLATE_DIR, "HUONG_DAN.txt")
            if not os.path.exists(rd):
                with open(rd, "w", encoding="utf-8") as f:
                    f.write("Bỏ ảnh quân cờ tự cắt vào đây. Tên: <loại>_<số>.png - loại: r c n p b a k hoặc xe phao ma tot tuong(=tượng) si vua.\n"
                            "Ví dụ: b_1.png, a_2.png, xe_1.png. Cắt ôm vừa đĩa quân từ ảnh GỐC (chưa vẽ), 3-5 ảnh mỗi loại.\n"
                            "XE CỦA TA (xe chữ đỏ): ta_1.png, ta_2.png (hoặc xe_ta_1.png, xe_do_1.png, minh_1.png, x_1.png). xe_1.png là xe ĐỊCH, đừng đặt nhầm.\n"
                            "Bot thử nhận bằng ảnh ở đây trước; không nhận được thì dùng cách cũ (xq_kinds.json). Không cần khởi động lại khi thêm ảnh.\n")
        except Exception:
            pass
        lost = 0
        nomark = 0
        popup_streak = 0
        try:
            while True:
                self._check()
                if self.max_rounds and self.rounds >= self.max_rounds:
                    self.log("info", f"Xiangqi: đủ {self.rounds} lượt, dừng")
                    return True
                t_a = self.now()
                fr, grid, st, stable_ok, nfr = self._stable()
                if self.close_popup and is_popup(fr):
                    popup_streak += 1
                    if popup_streak > 6:
                        self.log("warn", "Xiangqi: bảng popup không tắt được, kết thúc")
                        return False
                    self._handle_popup(fr)
                    if self.test:
                        return True
                    continue
                popup_streak = 0
                if nfr > 3:
                    self.log("info", f"Xiangqi: đợi bàn đứng yên {nfr} khung")
                if grid is None or st is None or st.rook is None:
                    lost += 1
                    self.log("warn", f"Xiangqi: không thấy bàn/xe ({lost}/{max(self.lost_limit, self.unread_retries)})")
                    if lost >= max(self.lost_limit, self.unread_retries):
                        if self.stop_on_unread and grid is not None and st is not None and st.board:
                            p = self._save_unread(fr, grid, st)
                            self.log("warn", f"Xiangqi: thấy {len(st.board)} quân trên bàn nhưng KHÔNG xác định được xe ta -> DỪNG"
                                             + (f" | ảnh debug: {p}" if p else ""))
                            return False
                        self.log("info", "Xiangqi: coi như ván đã xong/đã thoát bàn, kết thúc")
                        return True
                    self.sleep(0.8)
                    continue
                lost = 0
                if self.require_marks:
                    if self.marks_missing:
                        # không có ngoặc xanh = màn chưa ổn định / xe chưa được chọn -> chạm xe 1 lần cho game vẽ ngoặc rồi chờ lại
                        self.tap_marks += 1
                        self.log("info", f"Xiangqi: chạm xe {st.rook} để game vẽ ngoặc xanh ({nomark + 1}/{self.nomark_limit})")
                        self._tap_rook(grid, st.rook)
                        fr, grid, st, stable_ok, nfr = self._stable()
                        if grid is None or st is None or st.rook is None or is_popup(fr):
                            continue                                  # popup / mất bàn: vòng sau xử lý như thường
                        if self.marks_missing:
                            nomark += 1
                            p = self._save_unread(fr, grid, st, tag="nomarks")
                            self.log("warn", f"Xiangqi: vẫn không thấy ngoặc xanh ({nomark}/{self.nomark_limit})"
                                             + (f" | ảnh debug: {p}" if p else ""))
                            if nomark >= self.nomark_limit:
                                raise _Stop("xe không hiện ngoặc xanh nên màn không ổn định")
                            continue
                    else:
                        self.tap_marks = 0
                    nomark = 0
                if self.stop_on_unread and st.low_conf and self.unread_retries > 0:
                    fr, grid, st, stable_ok, nfr, same = self._rescan_unread(fr, grid, st, stable_ok, nfr)
                    if not same or grid is None or st is None or st.rook is None:
                        continue                                   # popup / mất bàn sau khi quét lại: vòng sau xử lý như thường
                if self.stop_on_unread and st.low_conf:
                    # đã quét lại đủ `unread_retries` lần mà vẫn có quân không đọc được loại -> không đoán nữa, dừng và lưu ảnh để cắt mẫu
                    p = self._save_unread(fr, grid, st)
                    self.log("warn", f"Xiangqi: KHÔNG ĐỌC ĐƯỢC {len(st.low_conf)} quân (ô, đoán, điểm): {st.low_conf[:6]} (đã quét lại {self.unread_retries} lần) -> DỪNG"
                                     + (f" | ảnh debug: {p}" if p else ""))
                    raise _Stop("không đọc được quân")
                if self.stop_on_unread and self.stop_on_missing and self._unexplained_missing(st):
                    if self.unread_retries > 0:
                        fr, grid, st, stable_ok, nfr, same = self._rescan_missing(fr, grid, st, stable_ok, nfr)
                        if not same or grid is None or st is None or st.rook is None:
                            continue
                    miss_ = self._unexplained_missing(st)
                    if miss_:
                        p = self._save_unread(fr, grid, st, tag="missing")
                        self.log("warn", f"Xiangqi: MẤT {len(miss_)} quân {miss_[:4]} so với dự đoán (chỉ 1 quân địch đi), đã quét lại {self.unread_retries} lần "
                                         f"vẫn thiếu -> DỪNG, KHÔNG đi tiếp vì bàn đọc chưa đủ quân" + (f" | ảnh debug: {p}" if p else "")
                                         + " (tắt bằng field stop_on_missing = false)")
                        raise _Stop("mất quân không giải thích được (nghi đọc sót)")
                if st.swept:
                    self.log("warn", "Xiangqi: QUÉT ĐĨA - ô có đĩa quân nhưng không thấy vòng tròn (phát sáng/hoạt ảnh): "
                                     + ", ".join(f"{c}={'?' if k is None else KIND_NAMES.get(k, k) + ' (suy từ khay)'}" for c, k in st.swept[:6]))
                if st.mem:
                    self.log("info", f"Xiangqi: giữ quân từ TRÍ NHỚ lượt trước (khung hiện tại không đọc được): "
                                     + ", ".join(f"{KIND_NAMES.get(k, k)}@{c}" for c, k in st.mem[:6]))
                # chấm nước vừa đi: xe vẫn ở ô cũ = không đi được
                if self.pending:
                    if st.rook == self.pending[0]:
                        self._fail("xe vẫn đứng yên")
                    else:
                        self._ok()
                if self.pred:
                    if st.rook == self.pred["src"]:
                        self.pred = None
                    else:
                        self._verify(fr, grid, st)
                self.last_good = {p: k for p, k in st.board.items() if k not in ("X", "u")}      # TRÍ NHỚ cho lượt sau
                marks = read_marks(fr, grid)
                ov = overlay_states(marks, grid, skip=st.rook)
                reach = [d for d, _ in rook_moves(st.board, st.rook)]
                if not any(c in ov for c in reach):          # chưa thấy ngoặc = xe chưa được chọn
                    if not self.test:
                        self._tap_rook(grid, st.rook)
                        fr2, grid2, st2, _ok2, _n2 = self._stable()
                        if grid2 is not None and st2 is not None and st2.rook == st.rook and not is_popup(fr2):
                            fr, grid, st = fr2, grid2, st2
                            marks = read_marks(fr, grid)
                            ov = overlay_states(marks, grid, skip=st.rook)
                _n = {k: sum(1 for v in st.src.values() if v == k) for k in ("img", "mask", "none")}
                _kc = {}
                for _p, _k in st.board.items():
                    if _k != "X":
                        _kc[_k] = _kc.get(_k, 0) + 1
                self.log("info", f"Xiangqi: nhận quân bằng ẢNH mẫu {_n['img']}, mẫu cũ {_n['mask']}, không nhận ra {_n['none']}"
                                 + " | loại: " + " ".join(f"{k}:{v}" for k, v in sorted(_kc.items())))
                if st.low_conf:
                    self.log("warn", "Xiangqi: quân không chắc loại (ô, đoán, điểm): " + str(st.low_conf[:6]))
                n_enemy = sum(1 for _k in st.board.values() if _k != "X")
                careful = ((self.cfg.careful_after_rounds > 0 and self.rounds + 1 >= self.cfg.careful_after_rounds)
                           or (self.cfg.careful_min_pieces > 0 and n_enemy > self.cfg.careful_min_pieces))
                want_simple = self.simple_base and not careful
                if want_simple != self.cfg.simple_mode or self.mode_logged is None:
                    self.log("info", f"Xiangqi lượt {self.rounds + 1}: {n_enemy} quân -> chế độ " + ("ĂN NHANH (không dự đoán nước chết)" if want_simple else "XỬ LÝ KỸ (có dự đoán rủi ro)"))
                self.cfg.simple_mode, self.mode_logged = want_simple, want_simple
                tray = read_tray(fr, grid, self.unknown_as, self.min_match, self.img_match)
                spawn_in = read_spawn_timer(fr, grid)              # số đếm ngược đồng hồ cát (None = không đọc được -> mô hình rủi ro cũ)
                if spawn_in is None:
                    self.log("info", "Xiangqi: không đọc được số đồng hồ cát, dùng hệ số rủi ro khay cố định")
                elif spawn_in <= 1 and tray:
                    self.log("warn", f"Xiangqi: đồng hồ cát = {spawn_in} -> NƯỚC NÀY khay ({len(tray)} quân: {''.join(tray)}) hiện ra, tính rủi ro theo cả khay")
                t_c = self.now()
                sinfo = {}
                blast_now = bool(self.blast and self.cfg.king_blast)
                rk = rank_moves(st.board, st.rook, self.cfg, tray=tray, spawn_scale=self.spawn_scale, overlay=ov, info=sinfo, blast=blast_now, spawn_in=spawn_in)
                for d, _cap, _v, danger, src in rk:                # so ngoặc game với mô hình luật tự tính (để chỉnh luật)
                    if src == "game":
                        md = is_attacked(after_move(st.board, st.rook, d), d, self.cfg)
                        self.mis[1] += 1
                        self.mis[0] += int(md != danger)
                # khay sắp hiện (đồng hồ = 1): bỏ ưu tiên "cứ ăn quân" (capture_slack), để điểm phạt rủi ro khay không bị che mất
                slack = 0.0 if (spawn_in is not None and spawn_in <= 1 and tray) else (
                    self.cfg.capture_slack if self.cfg.simple_mode else max(self.cfg.capture_slack, self.cfg.careful_capture_slack))
                mv = pick_move(rk, sinfo.get("depth", 1) > 1, slack, blast_now, self.cfg.simple_mode,
                               max_slack=MAX_CAPTURE_SLACK if self.cfg.simple_mode else max(MAX_CAPTURE_SLACK, self.cfg.careful_capture_slack))
                t_d = self.now()
                if mv is None:
                    self.log("warn", "Xiangqi: xe không có nước đi")
                    return False
                dst, cap, score = mv
                if blast_now:
                    self.log("info", f"Xiangqi: NƯỚC NỔ - đích {dst} sẽ tiêu diệt {len(blast_victims(st.board, dst))} quân cùng hàng/cột "
                                     f"(giá trị {blast_value(st.board, dst, self.cfg):.0f})")
                nred = sum(1 for v in ov.values() if v == "red")
                self.log("info", f"Xiangqi lượt {self.rounds + 1}: xe {st.rook} -> {dst}"
                                 + (f" ĂN {KIND_NAMES.get(cap, cap)}" if cap else "")
                                 + f" (điểm {score:.1f}, {len(st.board) - 1} quân địch, ô đỏ {nred}/{len(ov)}"
                                 + (f", khay {len(tray)}" if tray is not None else "") + (f", đồng hồ {spawn_in}" if spawn_in is not None else "") + ")")
                if sinfo.get("depth", 1) > 1 or self.cfg.search_depth > 1:
                    self.log("info", "Xiangqi " + format_search(sinfo))
                if self.test or self.debug:
                    p = save_debug(fr, grid, st, dst, overlay=ov, out_dir=self.debug_dir)
                    if self.test:
                        self.log("info", "Xiangqi TEST - bàn nhận diện (+ xanh, ! đỏ):\n" + board_text(st, ov)
                                 + f"\nKhay: {tray}\nCác nước (đích, ăn, điểm, nguy hiểm, nguồn):\n"
                                 + "\n".join(str((d, c, round(v, 1), dg, s)) for d, c, v, dg, s in rk[:8])
                                 + (f"\nẢnh debug: {p}" if p else ""))
                        return True
                if self.stop_on_doom and is_doomed(rk):
                    # mọi nước đều bị ăn -> bấm cũng chết. Đọc lại 1 lần (bàn chưa đổi) để chắc không phải đọc nhầm khi bàn còn đang động.
                    self.doom_streak += 1
                    if self.doom_streak < 2:
                        self.log("warn", f"Xiangqi: thấy MỌI nước đều chết ({len(rk)} nước), đọc lại để chắc chắn...")
                        self.sleep(0.5)
                        continue
                    srcs = {}
                    for _d, _c, _v, _dg, _s in rk:
                        srcs[_s] = srcs.get(_s, 0) + 1
                    self.log("warn", f"Xiangqi: NƯỚC KẾ TIẾP CHẮC CHẮN CHẾT - xe {st.rook} không còn ô an toàn "
                                     f"({len(rk)} nước đều bị ăn, nguồn: {srcs}), DỪNG, không bấm. "
                                     "(tắt bằng field stop_on_doom = false)")
                    self._save_step(fr, grid, st, None, None, ov, score, tag="doom", force=True)
                    return True
                if is_doomed(rk) and not self.stop_on_doom:
                    # stop_on_doom = false: vẫn đi nước ít quân khống chế nhất. LƯU Ý: luật game = có quân ăn được xe thì CHẮC CHẮN ăn, nên chỉ có ích khi
                    # mô hình luật đánh giá nguy hiểm quá tay (sau 15 lượt đầu game không còn vẽ ngoặc đỏ để đối chiếu).
                    self.log("warn", f"Xiangqi: mọi nước đều nguy hiểm ({len(rk)} nước) - ĐÁNH LIỀU nước ít bị khống chế nhất {dst} "
                                     f"(không dừng; bật stop_on_doom = true nếu muốn dừng)")
                    if self.doom_streak == 0:
                        self._save_step(fr, grid, st, dst, cap, ov, score, tag="doom", force=True)
                    self.doom_streak = 1
                else:
                    self.doom_streak = 0
                shot_path = self._save_step(fr, grid, st, dst, cap, ov, score)
                self._do_move(grid, st.rook, dst, cap)
                t_e = self.now()
                self.log("info", f"Xiangqi ⏱ đọc + chờ màn ổn định {t_c - t_a:.1f}s ({nfr} khung) | TÍNH NƯỚC {t_d - t_c:.2f}s (sâu {sinfo.get('depth', 1)}) "
                                 f"| lưu ảnh + bấm {t_e - t_d:.1f}s | nghỉ sau nước {self.settle_s:.1f}s")
                self.pending_blast = blast_now
                nb_ = after_move(st.board, st.rook, dst)
                if blast_now:                                     # dự đoán: mọi quân cùng hàng/cột với đích đã nổ
                    for q in blast_victims(nb_, dst):
                        nb_.pop(q, None)
                self.pred = {"src": st.rook, "dst": dst, "cap": cap, "round": self.rounds + 1, "tray": tray,
                             "enemy": {p: k for p, k in nb_.items() if k != "X"}, "shot": shot_path, "spawn_in": spawn_in}
                self.sleep(self.settle_s)
        except _Stop as e:
            self.log("info", f"Xiangqi: dừng ({e})")
            return False
        finally:
            if self.pstat[2]:
                self.log("info", f"Xiangqi: dự đoán đúng {self.pstat[0]}/{self.pstat[2]} nước, lệch {self.pstat[1]} "
                                 "(lệch nhiều = đang đọc nhầm quân/bàn chưa đứng yên - xem ảnh debug_xiangqi/miss_*)")
            if self.mis[1]:
                self.log("info", f"Xiangqi: ngoặc game khác mô hình luật {self.mis[0]}/{self.mis[1]} ô "
                                 "(số lớn = luật quân địch trong cfg còn sai); đã tắt Sổ Tay {0} lần".format(self.popups))


def run_auto_xiangqi_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_xiangqi` (field xem docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    mode = step.get("input_mode", "auto")
    bot = XiangqiBot(
        adb, log=log, should_stop=should_stop,
        test=step.get("test", False), max_rounds=step.get("max_rounds", 0), max_seconds=step.get("max_seconds", 0),
        settle_s=step.get("settle_s", 1.3), input_mode=mode,
        unknown_as=("u" if step.get("unknown_as", "u") == "r" else step.get("unknown_as", "u")),
        min_match=step.get("min_match", 0.68), img_match=step.get("img_match", IMG_MATCH_THR),
        spawn_risk_every_turn=step.get("spawn_risk_every_turn", 0.3), debug=step.get("debug", False),
        lost_limit=step.get("lost_limit", 4), close_popup=step.get("close_popup", True),
        stable_timeout_s=step.get("stable_timeout_s", 4.0), stable_gap_s=step.get("stable_gap_s", 0.3),
        stable_frames=step.get("stable_frames", 2), enemy_wait_s=step.get("enemy_wait_s", 5.0), save_shots=step.get("save_shots", True),
        shot_keep=step.get("shot_keep", 120),
        search_depth=step.get("search_depth"), beam_width=step.get("beam_width"),
        search_time_s=step.get("search_time_s"), capture_slack=step.get("capture_slack"),
        w_skewer=step.get("w_skewer"), king_blast=step.get("king_blast"),
        w_king_blast=step.get("w_king_blast"), simple_mode=step.get("simple_mode"),
        careful_after_rounds=step.get("careful_after_rounds"), careful_min_pieces=step.get("careful_min_pieces"),
        rc_many=step.get("rc_many"), w_rc_base=step.get("w_rc_base"), w_rc_adj=step.get("w_rc_adj"),
        w_simple_doom=step.get("w_simple_doom"), careful_capture_slack=step.get("careful_capture_slack"),
        require_marks=step.get("require_marks", True), marks_wait_s=step.get("marks_wait_s", 6.0),
        fast_ready=step.get("fast_ready", True), marks_full_ratio=step.get("marks_full_ratio", 0.8),
        nomark_limit=step.get("nomark_limit", 3), stop_on_unread=step.get("stop_on_unread", True),
        stop_on_doom=step.get("stop_on_doom", True), spawn_risk_at_timer=step.get("spawn_risk_at_timer"),
        unread_retries=step.get("unread_retries", 4), unread_retry_wait_s=step.get("unread_retry_wait_s", 0.8),
        stop_on_missing=step.get("stop_on_missing", True),
    )
    return bot.run()


if __name__ == "__main__":
    # tuỳ chọn tìm kiếm sâu (đứng ở đâu cũng được): --depth N (1-12)  --beam N  --time giây
    _argv, _opts, _i = [sys.argv[0]], {}, 1
    while _i < len(sys.argv):
        if sys.argv[_i] in ("--depth", "--beam", "--time") and _i + 1 < len(sys.argv):
            _opts[sys.argv[_i][2:]] = sys.argv[_i + 1]
            _i += 2
        else:
            _argv.append(sys.argv[_i])
            _i += 1
    sys.argv = _argv
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    _cfg = Config()
    try:
        if "depth" in _opts:
            _cfg.search_depth = max(1, min(12, int(_opts["depth"])))
        if "beam" in _opts:
            _cfg.beam_width = max(1, min(12, int(_opts["beam"])))
        if "time" in _opts:
            _cfg.search_time_s = max(0.0, float(_opts["time"]))
    except ValueError:
        print("Giá trị --depth/--beam/--time không hợp lệ")
        sys.exit(2)
    img = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
    if is_popup(img):
        x_, y_, f_ = find_close_button(img)
        print(f"Đây là BẢNG POPUP (Sổ Tay...). Nút X ở ({x_:.0f},{y_:.0f})" + ("" if f_ else " [theo tỉ lệ]"))
        sys.exit(0)
    g = find_grid(img)
    if g is None:
        print("Không dò được lưới bàn cờ (vạch đỏ) trong ảnh này.")
        sys.exit(1)
    print(f"Lưới: {COLS} cột x {ROWS} hàng, bước {g.pitch:.1f}px, x0={g.xs[0]:.0f}, y0={g.ys[0]:.0f}")
    if len(sys.argv) >= 5:
        r_, c_, kind_ = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        x_, y_ = g.px(r_, c_)
        add_template(kind_, ink_mask(_patch(img, x_, y_, g.pitch)))
        print(f"Đã thêm mẫu '{kind_}' từ ô ({r_},{c_}) vào {TEMPLATE_FILE}")
        sys.exit(0)
    s = read_board(img, g)
    ov_ = overlay_states(read_marks(img, g), g, skip=s.rook)
    tray_ = read_tray(img, g)
    print(board_text(s, ov_))
    print("Xe của mình:", s.rook, "| quân không chắc loại:", s.low_conf, "| khay:", tray_)
    if s.rook:
        info_ = {}
        for row in rank_moves(s.board, s.rook, _cfg, tray_, 0.3, ov_, info=info_)[:6]:
            print(row)
        print("Tìm kiếm:", format_search(info_))
        print("Nước đi chọn:", choose_move(s.board, s.rook, _cfg, tray_, 0.3, ov_))
