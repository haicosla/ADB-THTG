# -*- coding: utf-8 -*-
"""
Bot auto "Nâng Cấp Tối Ưu" (Hợp Tác Xã Nghiên Cứu Công Nghệ Sản Xuất: nâng cấp bằng VÉ để tăng thu nhập) - điều khiển qua ADB, dùng cho bước `auto_upgrade`.

>>> Bản 2 (21/11): sửa 2 lỗi lộ ra khi xem VIDEO quay lúc nâng tay trên LDPlayer 720x1280 (đã chạy lại bằng khung hình video, chưa chạy bot thật):
>>>   (1) TỈ LỆ: giao diện thật to hơn toạ độ mẫu ~1.26 lần (nút 165x42, 2 hàng cách 156, mẫu 132x33/123) nên các vùng đọc (số dư vé, banner mức tăng, mũi tên đổi mục)
>>>       bị lệch -> số dư vé đọc ra None, mức tăng không đọc được. Nay `read_page` tự đo tỉ lệ từ 2 nút (`_scale_from_buttons`), `AdbUI` chốt tỉ lệ sau lần đọc đầu.
>>>   (2) MỨC TĂNG: banner "Tăng Thu Nhập" hiện số CHẠY LÊN từ +0 tới giá trị cuối (~1s) rồi đứng yên (vd +21k, +78k, +80.43k ... +151.7k); bản 1 nhận lần đọc đầu
>>>       nên ghi sai mức tăng (-> kế hoạch sai hiệu quả). Nay `AdbUI.press` đọc lặp tới khi 2 lần liền bằng nhau. Chữ '+tăng' xanh nhạt trên nền xanh ngọc nên đọc bằng kênh
>>>       ĐỎ + tách đoạn theo màu (tổng = chữ vàng, tăng = chữ xanh nhạt): `_gain_segment`.
>>> Bản 9 (23/11): theo ảnh Nhà tắm có banner + Nuôi dưỡng Nghệ Sĩ tab Giọng Hát: (a) banner 'Tăng Thu Nhập' ở VỊ TRÍ CỐ ĐỊNH trên màn hình (BANNER_ABS/GAIN_ABS, trùng nhau ở Ruộng Đồng và Nhà tắm; `_banner_fixed`
>>>   đo tỉ lệ màu xanh ngọc: không banner 0.00, có banner 0.37-0.69) thay cho tìm khối màu (hỏng khi nền cửa sổ có màu xanh ngọc); (b) Nhà tắm: loại vé lấy từ hình vé CỦA HÀNG (viên thuốc số dư bị banner đè -> đọc thành
>>>   'teal'), giá số nguyên luôn đọc đủ 9 lần (3/8 hay nhầm: 1430 từng đọc thành 1480); (c) Nuôi dưỡng: danh sách XOAY VÒNG (`Layout.circular`): không lùi về ô đầu (ô đang mở = ô 1), dừng khi quay lại ô 1,
>>>   `_goto` đi đường ngắn nhất qua đầu/cuối; (d) mỗi nghệ sĩ có 2 kỹ năng = 2 'hàng' (ô 1, 2): phải bấm biểu tượng mới hiện giá/nút (`Layout.slots`, `_slot_glow` nhận biểu tượng đang chọn qua vòng sáng,
>>>   `AdbUI._select_slot/_merge_slots/_carry_rows`, field bước `skills` mặc định 2); `press`/`press_many` tự chọn đúng kỹ năng trước khi bấm.
>>> Bản 8 (22/11): NHIỀU KIỂU MÀN HÌNH + TỰ NHẬN LOẠI VÉ trong 1 file (theo ảnh người dùng gửi): `Layout` + `LAYOUT_A` (Ruộng Đồng, kể cả tab Nghệ Sĩ vé xanh lá), `LAYOUT_B` (Nhà tắm: giá SỐ NGUYÊN
>>>   không đơn vị, số dư góc phải trên), `LAYOUT_C` (Nuôi dưỡng Nghệ Sĩ: 1 hàng, giá hiện 'số dư/giá', ô x10 bên TRÁI nút). `detect_layout` nhận kiểu theo vị trí nút 'Tăng cấp'; mọi toạ độ (giá, số dư, hình vé,
>>>   hình nhận ô, ô x10, mũi tên) theo kiểu. Loại vé: kiểu cũ giữ blue/pink/green; kiểu mới = '<kiểu>:<màu>' (`_hue_name`: đỏ/xanh lá/xanh ngọc/xanh dương/tím/hồng/vàng/trắng) - mỗi kiểu/vé là 1 ngân sách riêng.
>>>   Banner 'Tăng Thu Nhập' của kiểu mới tìm bằng màu (`_find_banner`, đo trên video: khớp hộp cũ). File lưu/CSV tách THEO MÀN HÌNH tự động (`{tab}` = kiểu + số thứ tự danh sách, chọn bằng khoá ô 1: `_tab_pick`),
>>>   file kiểu cũ (chưa có {tab}) tự chuyển tên nếu khớp.
>>> Bản 7 (21/11): theo công thức người dùng gửi (giá cấp N = P0*r^N; tổng vé N cấp = P0*(r^N-1)/(r-1); 10 cấp = 10.56*P0 với r=1.012, 10.41*P0 với r=1.009): đọc chỉ số -> TÍNH số cấp mỗi hàng
>>>   (`_levels_within` công thức đóng k = floor(ln(1+B*(r-1)/P0)/ln r), `_cost_sum`) với ngân sách = số dư - CHỪA 5% vé lúc bắt đầu (`reserve_pct`); hệ số giá mặc định theo hàng (GROWTH_PRIOR trên 1.009 / dưới 1.012),
>>>   hàng đã đo chính xác thì dùng số đo; cuối mỗi lượt log ĐÃ NÂNG / DỰ TÍNH (số cấp, vé tốn, thu nhập tăng) từng hàng + từng loại vé (còn lại, chừa lại). NHIỀU GIẢ LẬP/TÀI KHOẢN: file lưu, CSV, thư mục ảnh debug
>>>   riêng theo `_dev_tag` (device_id + tài khoản), ghi có khoá theo file (`_lock_for`), không biến toàn cục dùng chung giữa các lần chạy.
>>> Bản 6 (21/11): MỨC TĂNG MỖI HÀNG CỐ ĐỊNH (người dùng xác nhận) -> chỉ đo 1 lần (nâng thử lúc quét), các cấp sau bấm LIÊN TIẾP (`press_gap` 0.2s) KHÔNG đọc banner, nhiều cấp thì dùng ô x10
>>>   (`AdbUI.press_many`: tích x10 -> k10 lần bấm -> bỏ tích -> k1 lần bấm lẻ; x10 tự tắt nếu bật không được; nghi x10 còn bật -> dừng). Sau mỗi lô đọc lại giá + số dư 1 lần: kiểm tra tốn vé khớp
>>>   dự kiến (không khớp = chỉ nâng được 1 phần) và đo lại hệ số giá chính xác (qua >= 5 cấp; 1 cấp ở giá >= 1tr chỉ có 3 chữ số nên sai ~0.4%). Từ log thật: hệ số giá/cấp KHÔNG cố định 1.2%,
>>>   có 3 loại ~0.9% (hầu hết hàng trên), ~1.0% và ~1.2% (hầu hết hàng dưới, Ô19-trên) -> phải đo riêng từng hàng. CSV `data/upgrade_data_<thiết bị>.csv` thu thập dữ liệu để phân tích.
>>> Bản 5 (21/11): (a) LỖI 'tăng ?': OCR kỹ (~0.9s) mỗi lần chụp để chờ 2 lần đọc bằng nhau, mà banner chỉ sống ~2s -> chỉ đọc được 1 lần, chờ phí 4s/lần bấm (~8s/ô). Nay chụp liên tục +
>>>   so chữ ký vùng banner (không OCR), số đứng yên (độ lệch 0.0 so với >=1.1 khi đang chạy) thì OCR 1 lần (~0.2s) và đọc luôn trang từ khung đó, không đợi banner tắt: ~3.5s/lần bấm;
>>>   (b) nâng thử NGAY lúc quét (`probe_on_scan`); (c) lưu kết quả đo (mức tăng, hệ số giá, khoá ô) vào data/upgrade_state_<thiết bị>.json sau mỗi lần nâng; chạy lại/chạy tiếp thì ô nào còn khớp
>>>   (`_same_item`) dùng lại, khỏi nâng thử (`_load_state`, `_adopt`, `_save_state`).
>>> Bản 4 (21/11): (a) ĐỌC GIÁ SAI "338.7k" -> "8.7k": 2 chữ số dính nhau bị nhầm là hình tờ vé và bị cắt (`_text_mask` nay chỉ cắt thành phần cao >= 1.35 lần chữ số) - sửa đúng ~2/3 trang trong video
>>>   từng đọc sai giá (vd 439.5k -> 9.5k); (b) về ô đầu / nhảy nhiều ô: bấm mũi tên LIÊN TỤC mỗi 0.15s (`go_edge`, `jump`) rồi kiểm khoá trang, lệch thì tự xác định lại; (c) `next_item` đợi đổi ô bằng khoá rẻ (không OCR mỗi lần chụp).
>>> Bản 3 (21/11): theo ảnh người dùng gửi: danh sách ô TUYẾN TÍNH (không vòng), nút 'Kích hoạt' cũng xanh lá (không được bấm), quét hết danh sách để biết tổng số ô, ô định danh theo vị trí,
>>>   log rõ ô nào/nâng mấy lần/hiệu quả thấp nhất-cao nhất. Chi tiết ở mục 2.
>>> Bản 1 (16/10): CHƯA chạy thử trên LDPlayer thật. Viết dựa trên 5 ảnh người dùng gửi (toạ độ đo từ ảnh, neo theo nút "Tăng cấp" nên không phụ thuộc
>>> chỗ cắt ảnh) + bộ mô phỏng (`python upgrade_bot.py --selftest`). LẦN ĐẦU hãy chạy chế độ TEST (chỉ đọc, KHÔNG bấm Tăng cấp) rồi xem log + ảnh `debug_upgrade/`.

======================================================================================================
1) MỤC TIÊU
======================================================================================================
Có nhiều MỤC (kỹ thuật) để nâng, mỗi mục có 2 hàng nâng ("Cấp Nghiên Cứu Sơ Bộ" và "Đột Phá Chính Xác"), mỗi hàng tốn VÉ (có 3 loại vé: xanh dương / hồng /
xanh lá, mỗi mục dùng 1 loại) và khi nâng sẽ tăng thu nhập. Cần tiêu vé sao cho TỔNG thu nhập tăng nhiều nhất: luôn nâng hàng có
HIỆU QUẢ = (thu nhập tăng thêm) / (số vé tốn) cao nhất, nâng tới khi hiệu quả của nó tụt xuống bằng hàng khác thì chuyển sang hàng đó
(chi phí mỗi cấp tăng dần nên hiệu quả tự giảm dần -> các hàng tự "cân bằng" nhau). Mỗi LOẠI VÉ là 1 ngân sách riêng, cân đối giữa MỌI hàng dùng cùng loại vé.

======================================================================================================
2) CÁCH LÀM (người dùng xác nhận 16/10)
======================================================================================================
- Mức thu nhập tăng của 1 hàng CHỈ BIẾT SAU KHI NÂNG THỬ (hiện "+461.1k" ở đầu cửa sổ). Nên lượt đầu bot NÂNG THỬ mỗi hàng 1 cấp để đo (mất đúng 1 cấp vé của hàng đó,
  cấp đó vẫn được nâng thật nên không phí) rồi lập kế hoạch bằng `plan_upgrades` (tham lam theo hiệu quả, có mô hình chi phí tăng dần `growth` đo từ giá trước/sau khi nâng).
- Mỗi lần nâng đo lại mức tăng + giá mới của hàng đó; nâng tới khi hiệu quả đo được < ngưỡng cân bằng (`cutoff` của kế hoạch) thì bỏ hàng đó, lượt sau lập kế hoạch lại.
- Chỉ nâng TỪNG CẤP 1 (không tick "Nâng cấp x10" / "Nâng cấp đồng bộ" - hãy để 2 ô này KHÔNG tick). Hàng nút xám "Kích hoạt" (chưa mở) hoặc giá chữ ĐỎ (không đủ vé) thì bỏ qua.
- Đi qua các ô bằng 2 MŨI TÊN vàng hai bên cửa sổ. Danh sách là TUYẾN TÍNH, không vòng tròn (người dùng xác nhận 21/11): ô đầu KHÔNG có mũi tên trái, ô cuối KHÔNG có mũi tên phải;
  sau các ô nâng được thường có 3 ô 'Kích hoạt' (chưa mở). Ô được định danh bằng VỊ TRÍ (1 = ô đầu) chứ không bằng hình (vì có ô trùng hình minh hoạ). Bot lùi về ô đầu (`rewind`),
  đi sang phải đọc hết tới khi gặp `end_locked` (3) ô liên tiếp không còn nút 'Tăng cấp' hoặc hết mũi tên phải -> biết TỔNG số ô; các lượt nâng sau chỉ đi đúng khoảng ô có việc (tới/lui).
  Bot KHÔNG tự mở Hợp Tác Xã/chọn tab: hãy mở sẵn 1 ô bất kỳ của tab cần nâng (cửa sổ chi tiết có 2 hàng "Tăng cấp") rồi mới chạy bước; muốn nâng nhiều tab thì xếp nhiều bước + nhiều bước auto_upgrade.
- LOG (21/11): mỗi ô quét 1 dòng; bảng hàng (ô-hàng | vé | giá | tăng | hiệu quả); mỗi lượt in kế hoạch THEO LOẠI VÉ (dư bao nhiêu vé, hiệu quả THẤP NHẤT / CAO NHẤT hiện tại và ở hàng nào,
  ngưỡng biên, từng hàng nâng bao nhiêu lần); mỗi lần nâng 1 dòng (ô-hàng, nâng k/n, giá cũ -> mới, mức tăng, hiệu quả lần này/lần kế, vé còn, thấp nhất/cao nhất); cuối có TỔNG KẾT.
  Hiệu quả = thu nhập tăng thêm / số vé tốn (thu nhập trên mỗi vé); 'Ô3-dưới' = ô thứ 3 từ ô đầu, hàng dưới.

======================================================================================================
3) ĐỌC MÀN HÌNH (mọi toạ độ tính theo nút "Tăng cấp" HÀNG TRÊN, nhân tỉ lệ s = rộng_khung / 720)
======================================================================================================
- Nút: ô xanh lá 132x33 = "Tăng cấp" (bấm được), ô xám cùng cỡ = "Kích hoạt" (chưa bấm được). CẢNH BÁO (21/11): ô CHƯA MỞ nhưng đủ vé cũng hiện nút "Kích hoạt" MÀU XANH LÁ y hệt
  "Tăng cấp" (bấm là tốn vé kích hoạt, vd 69tr) -> chỉ coi là 'Tăng cấp' khi dưới nút có ô tích "Nâng cấp x10" (`_has_x10`); không có thì bot không bấm.
- Giá: số trên mỗi nút (khung `COST_BOX`), CHỮ XANH = đủ vé, CHỮ ĐỎ = thiếu vé. Số dư vé: viên thuốc tối phía trên hàng 1 (`PILL_BOX`), loại vé nhận bằng màu hình tờ vé trong viên thuốc.
- Số có đơn vị k / tr / tỷ ("630.8k", "1.3tr", "6.55tỷ"): tesseract hay RỚT dấu chấm hoặc chữ đơn vị với chữ nhỏ này, nên `read_amount` bỏ hình tờ vé, đọc nhiều biến thể rồi BỎ PHIẾU,
  chèn lại dấu chấm theo chấm nhỏ trên ảnh, và đơn vị lấy từ biến thể nào đọc ra được chữ. Đọc không chắc (thiếu đơn vị) -> trả None, bot KHÔNG đoán.
- Biết đã sang ô khác chưa: so khoá trang = dHash hình minh hoạ (`KEY_BOX`) + dải chân dung 'Đào Tạo Nhân Tài' (`STRIP_BOX`, so độ lệch xám) - `_same_item`; mũi tên có hiện không: `_arrow_visible` (đếm điểm vàng).
- Mức tăng thu nhập: đọc dòng "<tổng> +<tăng>" ở đầu cửa sổ (`GAIN_BOX`) SAU khi nâng. ĐOÁN: các trang Nhân Tài / Nghệ Sĩ chưa có ảnh sau-khi-nâng nên chưa chắc có dòng này; không đọc được
  thì mục đó coi là chưa đo (bot lưu ảnh `debug_upgrade/gain_fail_*.png`, dừng nâng thử mục đó sau `gain_fail_limit` lần để không phí vé).

======================================================================================================
4) FIELD CỦA BƯỚC `auto_upgrade`
======================================================================================================
test (True = chỉ đọc + liệt kê, KHÔNG bấm), max_items (80), max_passes (30), min_eff (0 = nâng tới hết vé; đơn vị thu nhập/vé), reserve (số vé giữ lại mỗi loại, 0),
max_seconds (0 = không giới hạn), cost_growth (không đặt = theo hàng: trên 1.009 / dưới 1.012 cho hàng chưa đo chính xác; đặt số thì ép dùng số đó), reserve_pct (5: chừa lại % số vé LÚC BẮT ĐẦU của từng loại vé làm sai số), account (nhãn tài khoản để tách file lưu/CSV riêng; hoặc dashboard gắn adb.account_key), gain_fail_limit (2), settle_wait (0.2s), gain_wait (4.0s: tối đa chờ số '+tăng' đứng yên),
gain_poll (0.3s: chu kỳ chụp khi chờ số đứng yên), scale (không đặt = tự đo từ nút; đặt tay thì dùng đúng số này),
skills (2: số biểu tượng kỹ năng dùng ở kiểu Nuôi dưỡng Nghệ Sĩ - tối đa 5), rewind (True: lùi về ô đầu trước khi quét; kiểu xoay vòng bỏ qua), end_locked (3: số ô liên tiếp không còn 'Tăng cấp' thì coi là hết danh sách),
probe_on_scan (True: nâng thử 1 cấp mỗi hàng NGAY khi quét tới ô đó, khỏi đi lại dò), resume (True: dùng kết quả đo đã lưu), state_file (mặc định data/upgrade_state_<thiết bị>.json; "" = không lưu),
max_age_hours (0 = không giới hạn tuổi của kết quả đã lưu),
use_x10 (True: nâng >= x10_min cấp thì tích 'Nâng cấp x10', bấm k lần = +10k cấp rồi BỎ TÍCH bấm lẻ phần dư), x10_min (10), press_gap (0.2s: khoảng cách giữa 2 lần bấm 'Tăng cấp' liên tiếp),
data_file (mặc định data/upgrade_data_<thiết bị>.csv: mỗi lần nâng 1 dòng - cấp, giá trước/sau, số dư, vé tốn, mức tăng, hệ số giá; "" = không ghi),
nav_gap (0.15s: khoảng cách giữa 2 lần bấm mũi tên khi bấm LIÊN TỤC - về ô đầu / nhảy nhiều ô; 0.1-0.2s là được), burst (4: số lần bấm liên tục giữa 2 lần kiểm tra còn mũi tên không),
arrow_dx / arrow_dy (186 / -173: vị trí mũi tên PHẢI so với nút Tăng cấp hàng trên, ở khung 720 rộng; mũi tên trái = -345), debug (False).
"""
import csv
import glob
import hashlib
import heapq
import json
import math
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

REF_W = 720

# ---- khung đọc, toạ độ (dx1, dy1, dx2, dy2) so với GÓC TRÁI-TRÊN nút "Tăng cấp" HÀNG TRÊN, ở khung rộng 720 (đo từ ảnh người dùng gửi) ----
BTN_W, BTN_H = 132, 33
ROW_GAP = 123                                   # khoảng cách dọc giữa nút hàng trên và nút hàng dưới
COST_BOX = (-30, -36, 142, -5)                  # giá, tính từ nút CỦA CHÍNH HÀNG ĐÓ
PILL_BOX = (16, -70, 124, -45)                  # số dư vé (viên thuốc tối), tính từ nút hàng TRÊN
ICON_BOX = (16, -70, 60, -45)                   # hình tờ vé trong viên thuốc
KEY_BOX = (-276, -420, -172, -336)              # hình minh hoạ của mục (để nhận biết đang ở mục nào)
GAIN_BOX = (-135, -469, 85, -440)               # dòng "<tổng thu nhập> +<tăng>" ở banner "Tăng Thu Nhập" đè lên đầu cửa sổ (bản 2: đo lại từ video quay thật)
STRIP_BOX = (-282, -248, 145, -85)              # dải chân dung \"Đào Tạo Nhân Tài\" (mỗi ô 1 bộ khác nhau) - dùng nhận biết ô, tránh banner đè lên tiêu đề
BANNER_BOX = (-120, -495, 100, -440)            # vùng banner xanh ngọc \"Tăng Thu Nhập\" (có banner = còn hoạt ảnh)
X10_BOX = (20, 8, 190, 38)                      # (dx1, dy1, dx2, dy2) so với GÓC TRÁI-DƯỚI nút: ô tích + chữ \"Nâng cấp x10\" (chỉ có ở hàng 'Tăng cấp', KHÔNG có ở 'Kích hoạt')
ARROW_R = (186, -173)                           # tâm mũi tên phải (so với góc trái-trên nút hàng trên)
ARROW_L = (-345, -173)


@dataclass(frozen=True)
class Layout:
    """Một KIỂU màn hình nâng cấp. Mọi toạ độ (dx, dy...) tính từ GÓC TRÁI-TRÊN nút 'Tăng cấp' HÀNG TRÊN, ở khung rộng 720 (riêng cost_box: từ nút CỦA HÀNG ĐÓ;
    x10_box / x10_tap: từ nút của hàng đó). Bot tự nhận kiểu màn hình theo vị trí các nút 'Tăng cấp' (`detect_layout`) - 1 file bot dùng cho mọi kiểu."""
    id: str
    label: str
    auto_scale: bool                                    # True: tỉ lệ lấy từ cỡ nút (kiểu Ruộng Đồng cũ); False: tỉ lệ = rộng khung / 720
    expect: Tuple[Tuple[int, int], ...]                 # góc trái-trên các nút 'Tăng cấp' mong đợi (px, khung 720) - dùng nhận kiểu + gán hàng
    cost_box: Tuple[float, float, float, float]
    pill_box: Optional[Tuple[float, float, float, float]]   # số dư vé; None = số dư nằm cùng dòng giá ('số dư/giá')
    icon_box: Tuple[float, float, float, float]         # hình vé (để nhận LOẠI vé)
    key_box: Tuple[float, float, float, float]          # hình nhận ô (chân dung/hình minh hoạ)
    strip_box: Tuple[float, float, float, float]        # dải chân dung nhân tài/nghệ sĩ (mỗi ô khác nhau)
    x10_box: Tuple[float, float, float, float]          # ô tích + chữ 'x10' (chỉ nút 'Tăng cấp' mới có)
    x10_tap: Tuple[float, float]                        # tâm ô tích x10
    arrow_r: Tuple[float, float]
    arrow_l: Tuple[float, float]
    row_gap: float = 0.0
    slash: bool = False                                 # giá hiện dạng 'số dư/giá' (vd 17.99tr/45.15k)
    plain_cost: bool = False                            # giá có thể là số nguyên không đơn vị (vd 2200)
    pill_light: bool = True                             # chữ số dư sáng trên nền tối
    banner_box: Optional[Tuple[float, float, float, float]] = None   # kiểu cũ: banner theo nút; None = dùng vị trí CỐ ĐỊNH trên màn hình (BANNER_ABS/GAIN_ABS)
    circular: bool = False                              # danh sách ô XOAY VÒNG (ô cuối bấm tiếp = về ô đầu, mũi tên luôn hiện): không lùi về ô đầu, phát hiện quay vòng để dừng
    slots: Tuple[Tuple[float, float], ...] = ()         # tâm các biểu tượng kỹ năng (ô 1, 2...) so với góc trái-trên nút: phải bấm chọn mới hiện giá/nút của ô đó
    slot_ring: Tuple[float, float] = (50.0, 62.0)       # vòng sáng quanh biểu tượng ĐANG CHỌN (bán kính trong/ngoài) để biết ô nào đang được chọn


# Kiểu 1 - Ruộng Đồng (Hợp Tác Xã): giấy da, 2 hàng, số dư ở viên thuốc phía trên (đo trên video + ảnh người dùng).
LAYOUT_A = Layout(
    id="ruong", label="Ruộng Đồng", auto_scale=True, expect=((453, 786), (453, 940)),
    cost_box=COST_BOX, pill_box=PILL_BOX, icon_box=ICON_BOX, key_box=KEY_BOX, strip_box=STRIP_BOX,
    x10_box=(20, 41, 190, 71), x10_tap=(29.6, 51.4), arrow_r=ARROW_R, arrow_l=ARROW_L, row_gap=ROW_GAP, banner_box=BANNER_BOX)
# Kiểu 2 - Nhà tắm: khung hồng, 2 hàng, giá là SỐ NGUYÊN (vd 2200), số dư ở góc phải trên (đo trên ảnh 720x1280 người dùng gửi 22/11).
LAYOUT_B = Layout(
    id="nhatam", label="Nhà tắm", auto_scale=False, expect=((480, 769), (480, 928)),
    cost_box=(25, -47, 145, -1), pill_box=(70, -601, 182, -581), icon_box=(30, -42, 72, -5),
    key_box=(-400, -569, -210, -319), strip_box=(-420, -229, 175, -69),
    x10_box=(2, 49, 168, 79), x10_tap=(25, 63), arrow_r=(194, -249), arrow_l=(-442, -249), row_gap=159, plain_cost=True)
# Kiểu 3 - Nuôi dưỡng Nghệ Sĩ: sổ tay, 1 hàng (kỹ năng đang chọn), giá hiện 'số dư/giá', ô x10 nằm BÊN TRÁI nút.
LAYOUT_C = Layout(
    id="nuoiduong", label="Nuôi dưỡng Nghệ Sĩ", auto_scale=False, expect=((504, 950),),
    cost_box=(-52, -44, 136, -8), pill_box=None, icon_box=(-51, -42, -20, -9),
    key_box=(-129, -505, -19, -395), strip_box=(-424, -630, 146, -260),
    x10_box=(-152, 10, -18, 38), x10_tap=(-136, 24), arrow_r=(174, -358), arrow_l=(-467, -358), slash=True, plain_cost=True,
    circular=True, slots=((-358, -175), (-240, -175), (-124, -175), (-9, -175), (106, -175)))
LAYOUTS: Tuple[Layout, ...] = (LAYOUT_A, LAYOUT_B, LAYOUT_C)
LAYOUT_BY_ID = {l.id: l for l in LAYOUTS}


def _slot_glow(frame, top, s, lay) -> List[float]:
    """Với mỗi biểu tượng kỹ năng: tỉ lệ điểm vàng sáng trong vòng quanh nó. Biểu tượng ĐANG CHỌN có vòng sáng (đo: 0.51-0.52), không chọn <= 0.03."""
    H, W = frame.shape[:2]
    r0, r1 = lay.slot_ring[0] * s, lay.slot_ring[1] * s
    out = []
    for sx, sy in lay.slots:
        cx, cy = int(top[0] + sx * s), int(top[1] + sy * s)
        R = int(r1) + 2
        ya, yb, xa, xb = max(0, cy - R), min(H, cy + R), max(0, cx - R), min(W, cx + R)
        if yb <= ya or xb <= xa:
            out.append(0.0)
            continue
        yy, xx = np.mgrid[ya:yb, xa:xb]
        ring = (np.hypot(xx - cx, yy - cy) >= r0) & (np.hypot(xx - cx, yy - cy) <= r1)
        hsv = cv2.cvtColor(frame[ya:yb, xa:xb], cv2.COLOR_BGR2HSV)
        gold = (hsv[..., 0] >= 12) & (hsv[..., 0] <= 32) & (hsv[..., 1] >= 90) & (hsv[..., 2] >= 200)
        out.append(float((gold & ring).sum()) / max(1, int(ring.sum())))
    return out


def _selected_slot(frame, top, s, lay, n=None) -> Optional[int]:
    g = _slot_glow(frame, top, s, lay)
    if n:
        g = g[:n]
    if not g or max(g) < 0.25:
        return None
    return int(np.argmax(g))


def detect_layout(frame) -> Optional[Layout]:
    """Nhận kiểu màn hình theo vị trí các nút 'Tăng cấp' (xanh lá) đo được: kiểu nào khớp nhiều nút mong đợi nhất. Không thấy nút nào khớp -> None."""
    k = frame.shape[1] / REF_W
    btns = find_buttons(frame, k)
    best, best_sc = None, 0
    for lay in LAYOUTS:
        sc = sum(1 for ex, ey in lay.expect if any(abs(b[0] - ex * k) <= 20 * k and abs(b[1] - ey * k) <= 20 * k for b in btns))
        if sc > best_sc:
            best, best_sc = lay, sc
    return best


_UNIT = {"k": 1e3, "tr": 1e6, "ty": 1e9}
_UNIT_NAME = {"k": "k", "tr": "tr", "ty": "tỷ"}
_ALLOW = "0123456789.+ktrỷy"
S_UP = 4                                        # phóng to khi tách chữ


# ----------------------------------------------------------------------------
# 1) Số có đơn vị
# ----------------------------------------------------------------------------
def parse_amount(text) -> Optional[float]:
    """'630.8k' -> 630800, '1.3tr' -> 1.3e6, '6.55tỷ' -> 6.55e9, '650000' -> 650000, '+461.1k' -> 461100. Không hiểu -> None."""
    if text is None:
        return None
    t = str(text).strip().lower().replace(",", ".").replace(" ", "").replace("đ", "")
    t = t.lstrip("+")
    t = t.replace("tỷ", "ty").replace("tỉ", "ty").replace("ỷ", "y")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(k|tr|ty)?", t)
    if not m:
        return None
    v = float(m.group(1))
    if m.group(2):
        v *= _UNIT[m.group(2)]
    return v


def format_amount(v: Optional[float]) -> str:
    if v is None:
        return "?"
    a = abs(v)
    for unit, mul in (("tỷ", 1e9), ("tr", 1e6), ("k", 1e3)):
        if a >= mul:
            return f"{v / mul:.4g}" + unit
    return f"{v:.0f}"


# ----------------------------------------------------------------------------
# 2) Đọc số bằng tesseract (bỏ hình vé, bỏ phiếu, chèn lại dấu chấm)
# ----------------------------------------------------------------------------
@dataclass
class Amount:
    raw: str = ""
    mant: str = ""
    unit: Optional[str] = None                  # 'k' | 'tr' | 'ty' | None
    value: Optional[float] = None
    green: Optional[bool] = None                # màu chữ: True = xanh (đủ vé), False = đỏ (thiếu), None = không rõ


def _tess(img, psm=7, allow=_ALLOW):
    try:
        import pytesseract
        return pytesseract.image_to_string(img, config=f"--psm {psm} -c tessedit_char_whitelist={allow}").strip()
    except Exception:
        return ""


def _text_mask(crop, light_on_dark=False, s_up=S_UP, drop_icon=True):
    """Mặt nạ chữ (255 = mực) đã phóng s_up lần, bỏ hình tờ vé (thành phần lớn nhất bên trái) + đường viền; None nếu không có chữ."""
    if crop is None or crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=s_up, fy=s_up, interpolation=cv2.INTER_CUBIC)
    flag = cv2.THRESH_BINARY if light_on_dark else cv2.THRESH_BINARY_INV
    _, b = cv2.threshold(g, 0, 255, flag + cv2.THRESH_OTSU)
    nl, lab, st, _ = cv2.connectedComponentsWithStats(b)
    cut = 0
    if drop_icon:
        # chiều cao chữ số điển hình (trung vị các thành phần cao >= 10*s_up) -> hình tờ vé cao hơn hẳn (~1.7 lần). Chỉ xét thành phần cao >= 1.35 lần chữ số:
        # 2 chữ số DÍNH nhau (vd "33" rộng 90 ở s_up=4) từng bị nhầm là hình tờ vé -> cắt mất "33" của "338.7k" thành "8.7k" (lỗi 21/11)
        hs = sorted(int(st[i][3]) for i in range(1, nl) if st[i][3] >= 10 * s_up and st[i][4] >= 30 * s_up)
        typ = hs[len(hs) // 2] if len(hs) >= 3 else 0
        for i in range(1, nl):
            x, y, w, h, a = st[i]
            if w >= 18 * s_up and h >= 14 * s_up and a > 150 * s_up * s_up / 4 and (typ == 0 or h >= 1.35 * typ):
                cut = max(cut, x + w)
        b[:, :cut] = 0
        nl, lab, st, _ = cv2.connectedComponentsWithStats(b)
    for i in range(1, nl):
        x, y, w, h, a = st[i]
        if h > 26 * s_up or w > 40 * s_up or a < 6 * s_up or (h <= 2 * s_up and w >= 8 * s_up):
            b[lab == i] = 0
    ys, xs = np.where(b > 0)
    if len(xs) == 0:
        return None
    return b[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _dot_digits_left(mask, s_up=S_UP) -> Optional[int]:
    """Tìm CHẤM THẬP PHÂN (blob nhỏ ~2x2 sát đường chân chữ); trả số chữ số bên trái chấm, None nếu không thấy."""
    nl, lab, st, _ = cv2.connectedComponentsWithStats(mask)
    bottom = mask.shape[0]
    for i in range(1, nl):
        x, y, w, h, a = st[i]
        if w <= 4 * s_up and h <= 4 * s_up and a >= 2 * s_up and y + h >= bottom - 3 * s_up and x > 3 * s_up:
            return max(1, int(round((x / s_up) / 8.5)))
    return None


def _split(cand: str):
    m = re.match(r"^(\+?)(\d[\d.]*)([a-zỷ]*)$", cand)
    if not m:
        return None
    mant = m.group(2).strip(".")
    suf = m.group(3)
    unit = None
    if "k" in suf:
        unit = "k"
    elif "y" in suf or "ỷ" in suf:
        unit = "ty"
    elif "t" in suf or "r" in suf:
        unit = "tr"
    return mant, unit


def _vote(cands: List[str], dot_left: Optional[int]) -> Tuple[str, Optional[str]]:
    """Gộp nhiều lần đọc: chữ số = chuỗi phổ biến nhất (hoà thì ngắn hơn), đơn vị = đơn vị đọc ra được nhiều nhất, dấu chấm = từ ảnh nếu OCR rớt."""
    sp = [x for x in (_split(c) for c in cands) if x]
    if not sp:
        return "", None
    digs: Dict[str, int] = {}
    dotpos: Dict[Tuple[str, int], int] = {}
    units: Dict[str, int] = {}
    for mant, unit in sp:
        d = mant.replace(".", "")
        if not d:
            continue
        digs[d] = digs.get(d, 0) + 1
        if "." in mant:
            k = (d, mant.index("."))
            dotpos[k] = dotpos.get(k, 0) + 1
        if unit:
            units[unit] = units.get(unit, 0) + 1
    if not digs:
        return "", None
    best = sorted(digs.items(), key=lambda kv: (-kv[1], len(kv[0])))[0][0]
    pos = None
    for (d, p), n in sorted(dotpos.items(), key=lambda kv: -kv[1]):
        if d == best:
            pos = p
            break
    if pos is None and dot_left is not None and 0 < dot_left < len(best):
        pos = dot_left
    mant = best if pos is None else best[:pos] + "." + best[pos:]
    unit = sorted(units.items(), key=lambda kv: -kv[1])[0][0] if units else None
    return mant, unit


def _ink_green(crop, light_on_dark) -> Optional[bool]:
    """Chữ xanh (đủ vé) hay đỏ (thiếu vé)? Lấy hue các điểm chữ bão hoà ở nửa PHẢI khung (tránh hình tờ vé bên trái)."""
    if light_on_dark:
        return True
    w = crop.shape[1]
    hsv = cv2.cvtColor(crop[:, int(w * 0.42):], cv2.COLOR_BGR2HSV)
    m = (hsv[..., 1] > 60) & (hsv[..., 2] < 215)
    h = hsv[..., 0][m]
    if len(h) < 8:
        return None
    red = int(((h < 12) | (h >= 160)).sum())
    green = int(((h >= 45) & (h < 100)).sum())
    if max(red, green) < 8:
        return None
    return green > red


def read_amount(crop, light_on_dark=False, thorough=False, plain=False) -> Amount:
    """Đọc 1 số có đơn vị trong khung `crop` (BGR). `thorough` = nhiều biến thể hơn (dùng cho dòng mức tăng khó đọc)."""
    out = Amount()
    variants = [(4, 0, 7), (5, 1, 7), (5, 0, 8), (4, 1, 7)] if not thorough else \
        [(4, 0, 7), (5, 1, 7), (5, 0, 8), (4, 1, 7), (6, 1, 7), (3, 0, 7), (5, 1, 13), (6, 0, 8), (4, 0, 13)]
    cands: List[str] = []
    dot_left = None
    for s_up, blur, psm in variants:
        mask = _text_mask(crop, light_on_dark, s_up)
        if mask is None:
            continue
        if dot_left is None:
            dot_left = _dot_digits_left(mask, s_up)
        img = 255 - mask
        if blur:
            img = cv2.GaussianBlur(img, (0, 0), 1.0)
        img = cv2.copyMakeBorder(img, 16, 16, 24, 24, cv2.BORDER_CONSTANT, value=255)
        c = _tess(img, psm).replace(" ", "")
        if c:
            cands.append(c)
        if not thorough and len(cands) >= 2:
            a, b = _vote(cands[:1], dot_left), _vote(cands[1:2], dot_left)
            if a[1] and a == b:                 # 2 lần đọc đầu giống hệt và có đơn vị -> chắc
                break
    out.raw = "|".join(cands)
    if plain and cands:                                     # giá số nguyên không đơn vị (Nhà tắm): chuỗi toàn chữ số phổ biến nhất; không phục hồi 'dấu chấm' (dễ nhầm nhiễu thành 22.00)
        best = max(set(cands), key=cands.count)
        if re.fullmatch(r"\d{1,6}", best) and cands.count(best) >= max(2, len(cands) // 2):
            out.mant, out.unit, out.value = best, None, float(best)
            out.green = _ink_green(crop, light_on_dark)
            return out
    mant, unit = _vote(cands, dot_left)
    out.mant, out.unit = mant, unit
    if mant and unit:
        out.value = parse_amount(mant + unit)
    elif plain and mant and mant.isdigit() and not unit:
        out.value = float(mant)                             # giá số nguyên không đơn vị (vd 2200 ở Nhà tắm)
    out.green = _ink_green(crop, light_on_dark)
    return out


_ALLOW_SLASH = _ALLOW + "/"


def _parse_pair(c: str):
    """'17.99tr/45.15k' (hoặc '17.99tr45.15k' khi OCR rớt dấu /) -> (số dư, giá). Không hiểu -> None."""
    c = c.replace(" ", "")
    parts = c.split("/") if "/" in c else None
    if parts is None:
        m = re.match(r"^(\d[\d.]*(?:tr|ty|k))(\d[\d.]*(?:tr|ty|k|)?)$", c)
        parts = [m.group(1), m.group(2)] if m else None
    if not parts or len(parts) != 2:
        return None
    out = []
    for part in parts:
        sp = _split(part)
        if not sp:
            return None
        mant, unit = sp
        v = parse_amount(mant + (unit or "")) if (unit or mant.isdigit()) else None
        if v is None:
            return None
        out.append(v)
    return out[0], out[1]


def read_pair(crop, thorough=False):
    """Đọc dòng 'số dư/giá' (kiểu Nuôi dưỡng Nghệ Sĩ). Trả (số dư, giá) hoặc (None, None)."""
    variants = [(4, 0, 7), (5, 1, 7), (5, 0, 8), (4, 1, 7)] if not thorough else \
        [(4, 0, 7), (5, 1, 7), (5, 0, 8), (4, 1, 7), (6, 1, 7), (3, 0, 7), (6, 0, 8)]
    got: List[Tuple[float, float]] = []
    for s_up, blur, psm in variants:
        mask = _text_mask(crop, False, s_up)
        if mask is None:
            continue
        img = 255 - mask
        if blur:
            img = cv2.GaussianBlur(img, (0, 0), 1.0)
        img = cv2.copyMakeBorder(img, 16, 16, 24, 24, cv2.BORDER_CONSTANT, value=255)
        pr = _parse_pair(_tess(img, psm, _ALLOW_SLASH))
        if pr:
            got.append(pr)
            if not thorough and got.count(pr) >= 2:
                return pr
    if not got:
        return None, None
    best = max(set(got), key=got.count)
    return best


def _gain_of(c: str):
    m = re.match(r"^.*?\+(\d[\d.]*)([a-zỷ]*)$", c)
    if not m:
        return None
    mant, unit = _split(m.group(1) + m.group(2)) or (None, None)
    return (mant, unit) if mant else None


def _gain_segment(box):
    """Cắt riêng phần '+<tăng>' (chữ xanh nhạt) khỏi dòng '<tổng> +<tăng>' của banner \"Tăng Thu Nhập\" (tổng = chữ VÀNG, nền xanh ngọc).
    Banner nền xanh ngọc, chữ nhạt -> kênh ĐỎ (R) tách chữ rõ nhất (nền R thấp, chữ R cao), xám/Otsu thì chữ xanh nhạt chìm vào nền.
    Trả ảnh 3 kênh (kênh R nhân 3) đã cắt đúng đoạn '+<tăng>', hoặc None nếu không thấy."""
    if box is None or box.size == 0:
        return None
    up = 3
    big = cv2.resize(box, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    _, b = cv2.threshold(big[..., 2], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    hsv = cv2.cvtColor(big, cv2.COLOR_BGR2HSV)
    nl, lab, st, _ = cv2.connectedComponentsWithStats(b)
    yellow, other = [], []
    for i in range(1, nl):
        x, y, w, h, a = [int(v) for v in st[i]]
        if h < 10 * up or h > 36 * up or w > 40 * up or a < 25 * up:
            continue
        hue = float(np.median(hsv[..., 0][lab == i]))
        (yellow if hue < 40 else other).append((x, w))
    if not other:
        return None
    left = max((x + w for x, w in yellow), default=0)
    gain = [(x, w) for x, w in other if x >= left - 3]
    if not gain:
        return None
    x0 = max(0, min(x for x, _ in gain) // up - 3)
    x1 = min(box.shape[1], max(x + w for x, w in gain) // up + 4)
    if x1 - x0 < 8:
        return None
    r = box[:, x0:x1, 2]
    return cv2.merge([r, r, r])


def read_gain(crop) -> Tuple[Optional[float], Optional[float], str]:
    """Đọc dòng '<tổng> +<tăng>' của banner 'Tăng Thu Nhập'. Trả (mức tăng, tổng, chuỗi thô). Không có đơn vị của mức tăng -> (None, ...).
    Bản 2: chỉ đọc đoạn '+<tăng>' (tách bằng màu, kênh R) bằng `read_amount`, tổng không còn đọc (không dùng) nên trả None.
    LƯU Ý: số này CHẠY LÊN từ +0 tới giá trị cuối trong ~1 giây - phải đọc lặp tới khi 2 lần liền bằng nhau (xem `AdbUI.press`)."""
    seg = _gain_segment(crop)
    if seg is None:
        return None, None, ""
    a = read_amount(seg, True, True)
    return a.value, None, a.raw


# ----------------------------------------------------------------------------
# 3) Nhận diện bố cục cửa sổ chi tiết
# ----------------------------------------------------------------------------
@dataclass
class RowInfo:
    idx: int                                    # 0 = hàng trên (Sơ Bộ), 1 = hàng dưới (Đột Phá)
    x: int
    y: int
    w: int
    h: int
    active: bool                                # nút xanh "Tăng cấp" (True) / xám "Kích hoạt" (False)
    cost: Optional[float] = None
    affordable: Optional[bool] = None           # chữ giá xanh = đủ vé


@dataclass
class Page:
    ok: bool = False
    key: str = ""
    ticket: str = "?"
    balance: Optional[float] = None
    rows: List[RowInfo] = field(default_factory=list)
    top: Optional[Tuple[int, int]] = None       # góc trái-trên nút hàng trên (đã suy ra kể cả khi chỉ thấy 1 nút)
    scale: float = 1.0
    layout: Optional["Layout"] = None            # kiểu màn hình đã nhận (None = kiểu Ruộng Đồng)

    def row(self, idx) -> Optional[RowInfo]:
        for r in self.rows:
            if r.idx == idx:
                return r
        return None


def _box(frame, anchor, box, s):
    ax, ay = anchor
    x1, y1, x2, y2 = box
    H, W = frame.shape[:2]
    a, b = max(0, int(ax + x1 * s)), max(0, int(ay + y1 * s))
    c, d = min(W, int(ax + x2 * s)), min(H, int(ay + y2 * s))
    if c <= a or d <= b:
        return None
    return frame[b:d, a:c]


def _blobs(mask, s):
    k = max(3, int(5 * s)) | 1
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    nl, _, st, _ = cv2.connectedComponentsWithStats(mask)
    out = []
    for i in range(1, nl):
        x, y, w, h, a = [int(v) for v in st[i]]
        if 100 * s <= w <= 230 * s and 22 * s <= h <= 64 * s and 3.0 <= w / max(h, 1) <= 5.0:
            out.append((x, y, w, h))
    return out


def find_buttons(frame, s) -> List[Tuple[int, int, int, int, bool]]:
    """Các nút nâng: (x, y, w, h, active). active = xanh lá 'Tăng cấp'; xám = 'Kích hoạt'. Sắp xếp từ trên xuống."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    green = ((hsv[..., 0] >= 55) & (hsv[..., 0] <= 95) & (hsv[..., 1] >= 70) & (hsv[..., 2] >= 80)).astype(np.uint8) * 255
    grey = ((hsv[..., 1] <= 20) & (hsv[..., 2] >= 100) & (hsv[..., 2] <= 150)).astype(np.uint8) * 255
    res = [(x, y, w, h, True) for x, y, w, h in _blobs(green, s)] + [(x, y, w, h, False) for x, y, w, h in _blobs(grey, s)]
    res.sort(key=lambda r: (r[1], r[0]))
    # gộp nút trùng nhau (cùng chỗ)
    uniq = []
    for r in res:
        if not any(abs(r[0] - u[0]) < 10 * s and abs(r[1] - u[1]) < 10 * s for u in uniq):
            uniq.append(r)
    return uniq


def _ticket_type(icon) -> str:
    """Loại vé theo màu hình tờ vé: blue / pink / green (đếm điểm ảnh bão hoà theo dải hue)."""
    if icon is None or icon.size == 0:
        return "?"
    hsv = cv2.cvtColor(icon, cv2.COLOR_BGR2HSV)
    m = (hsv[..., 1] > 45) & (hsv[..., 2] > 90)
    h = hsv[..., 0][m]
    blue = int(((h >= 85) & (h < 130)).sum())
    pink = int(((h < 8) | (h >= 150)).sum())
    green = int(((h >= 30) & (h < 85)).sum())
    best = max((blue, "blue"), (pink, "pink"), (green, "green"))
    return best[1] if best[0] >= 15 else "?"


def _hue_name(icon) -> str:
    """Tên MÀU của hình vé cho các kiểu màn hình mới (đỏ/xanh lá/xanh ngọc/xanh dương/tím/hồng/vàng/trắng) - tự nhận loại vé lạ.
    Bỏ dải hue 8-35 (màu giấy/nền cam) trừ khi không còn màu nào khác."""
    if icon is None or icon.size == 0:
        return "?"
    hsv = cv2.cvtColor(icon, cv2.COLOR_BGR2HSV)
    m = (hsv[..., 1] > 45) & (hsv[..., 2] > 90)
    h = hsv[..., 0][m]
    cnt = {
        "red": int(((h < 8) | (h >= 165)).sum()),
        "green": int(((h >= 35) & (h < 80)).sum()),
        "teal": int(((h >= 80) & (h < 95)).sum()),
        "blue": int(((h >= 95) & (h < 130)).sum()),
        "purple": int(((h >= 130) & (h < 150)).sum()),
        "pink": int(((h >= 150) & (h < 165)).sum()),
    }
    name, n = max(cnt.items(), key=lambda kv: kv[1])
    if n >= 40:
        return name
    if int(((h >= 8) & (h < 35)).sum()) >= 150:
        return "gold"
    return "white"


def _ticket_key(frame, top, s, lay=None) -> str:
    """Khoá loại vé của trang: Ruộng Đồng giữ tên cũ (blue/pink/green); kiểu khác = '<id kiểu>:<màu>' (vd 'nuoiduong:purple') vì mỗi kiểu/vé là 1 loại tiền riêng."""
    lay = lay or LAYOUT_A
    icon = _box(frame, top, lay.icon_box, s)
    if lay.id == LAYOUT_A.id:
        return _ticket_type(icon)
    nm = _hue_name(icon)
    return "?" if nm == "?" else f"{lay.id}:{nm}"


def _dhash(img, w=9, h=8) -> str:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (w, h), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return "".join("1" if b else "0" for b in bits)


def _hamming(a, b):
    return sum(x != y for x, y in zip(a, b))


KEY_PIC_BITS = 64
STRIP_W, STRIP_H = 24, 12
STRIP_SAME_MAD = 5.0                            # độ lệch xám trung bình tối đa (0-255) để coi 2 dải chân dung là cùng ô (đo trên video: cùng ô <= 1.9, khác ô >= 8.3)


def _strip_sig(img) -> str:
    """Dải chân dung thu nhỏ 24x12 xám, mỗi điểm 4 bit -> chuỗi hex (so bằng độ lệch trung bình, không dùng dHash vì các ô có nền giống nhau)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (STRIP_W, STRIP_H), interpolation=cv2.INTER_AREA)
    return "".join(f"{int(v) >> 4:x}" for v in g.flatten())


def _strip_diff(a: str, b: str) -> float:
    if len(a) != len(b) or not a:
        return 255.0
    return sum(abs(int(x, 16) - int(y, 16)) for x, y in zip(a, b)) * 16.0 / len(a)


def _same_item(a: str, b: str) -> bool:
    """2 khoá trang (hình minh hoạ 64 bit + dải chân dung 'Đào Tạo Nhân Tài') là CÙNG 1 ô? Nhiễu nhẹ / số 'Năng Lực +x' đổi sau khi nâng vẫn là cùng ô;
    2 ô có hình minh hoạ giống nhau (vd 'Bảo Quản Thịt' và 'Kỹ Thuật Phơi Khô') vẫn phân biệt được nhờ dải chân dung."""
    if not a or not b or len(a) != len(b):
        return False
    return _hamming(a[:KEY_PIC_BITS], b[:KEY_PIC_BITS]) <= 6 and _strip_diff(a[KEY_PIC_BITS:], b[KEY_PIC_BITS:]) <= STRIP_SAME_MAD


def _page_key(frame, top, s, lay=None) -> str:
    """Khoá nhận ô (rẻ, KHÔNG OCR): dHash hình minh hoạ + dải chân dung. Dùng để biết đã sang ô khác chưa khi bấm mũi tên."""
    lay = lay or LAYOUT_A
    key_img = _box(frame, top, lay.key_box, s)
    if key_img is None:
        return ""
    strip_img = _box(frame, top, lay.strip_box, s)
    return _dhash(key_img) + (_strip_sig(strip_img) if strip_img is not None else "0" * (STRIP_W * STRIP_H))


def _has_x10(frame, btn, s, lay=None) -> bool:
    """Gần nút có ô tích + chữ 'x10' không? Có = nút là 'Tăng cấp'; không = nút 'Kích hoạt' (cùng màu xanh lá nhưng KHÔNG phải nâng cấp,
    bấm vào sẽ tốn vé kích hoạt ô) -> bot không bấm. Đếm điểm ảnh xám đậm (ô tích / nền ô) + xanh lá đậm (chữ)."""
    lay = lay or LAYOUT_A
    x, y, w, h = btn[:4]
    H, W = frame.shape[:2]
    a, b = max(0, int(x + lay.x10_box[0] * s)), max(0, int(y + lay.x10_box[1] * s))
    c, d = min(W, int(x + lay.x10_box[2] * s)), min(H, int(y + lay.x10_box[3] * s))
    if c <= a or d <= b:
        return False
    hsv = cv2.cvtColor(frame[b:d, a:c], cv2.COLOR_BGR2HSV)
    dark = (hsv[..., 1] <= 70) & (hsv[..., 2] <= 110)
    text = (hsv[..., 0] >= 45) & (hsv[..., 0] <= 90) & (hsv[..., 1] >= 70) & (hsv[..., 2] <= 150)
    return int(dark.sum()) >= 40 * s * s or int(text.sum()) >= 60 * s * s


def _banner_visible(frame, top, s) -> bool:
    """Banner xanh ngọc 'Tăng Thu Nhập' đang hiện (đè lên tiêu đề cửa sổ)? Bình thường vùng này là giấy/chữ nâu, không có màu xanh ngọc bão hoà."""
    box = _box(frame, top, BANNER_BOX, s)
    if box is None or box.size == 0:
        return False
    hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
    m = (hsv[..., 0] >= 78) & (hsv[..., 0] <= 100) & (hsv[..., 1] >= 90) & (hsv[..., 2] >= 110)
    return float(m.mean()) > 0.18


GAIN_STILL_MAD = 0.5                            # độ lệch xám trung bình (0-255) giữa 2 lần chụp vùng banner để coi là 'số đã đứng yên' (đo trên video: đứng yên = 0.0, đang chạy >= 1.1)


def _gain_sig(frame, top, s):
    """Chữ ký rẻ (không OCR) của vùng dòng '<tổng> +<tăng>' - so 2 lần chụp liên tiếp để biết số '+tăng' đã ngừng chạy lên chưa."""
    box = _box(frame, top, GAIN_BOX, s)
    if box is None or box.size == 0:
        return None
    return cv2.resize(cv2.cvtColor(box, cv2.COLOR_BGR2GRAY), (48, 8), interpolation=cv2.INTER_AREA).astype(np.float32)


BANNER_ABS = (146, 132, 580, 250)               # vùng banner 'Tăng Thu Nhập' trên màn hình (px @720): CỐ ĐỊNH, không phụ thuộc cửa sổ (đo: Ruộng Đồng và Nhà tắm trùng nhau)
GAIN_ABS = (279, 194, 560, 231)                 # dòng '<tổng> +<tăng>' trong banner
BANNER_MIN_FRAC = 0.25                          # tỉ lệ điểm xanh ngọc trong BANNER_ABS để coi là banner đang hiện (đo: không banner = 0.00, banner = 0.37-0.69)


def _banner_fixed(frame):
    """Banner đang hiện ở vị trí cố định? Trả hộp dòng '<tổng> +<tăng>' (tuyệt đối) hoặc None. Rẻ + chắc hơn tìm khối màu (khối màu hỏng khi nền cửa sổ có màu xanh ngọc)."""
    k = frame.shape[1] / REF_W
    x1, y1, x2, y2 = [int(v * k) for v in BANNER_ABS]
    sub = frame[y1:y2, x1:x2]
    if sub.size == 0:
        return None
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    m = (hsv[..., 0] >= 78) & (hsv[..., 0] <= 100) & (hsv[..., 1] >= 90) & (hsv[..., 2] >= 110)
    if float(m.mean()) < BANNER_MIN_FRAC:
        return None
    return tuple(int(v * k) for v in GAIN_ABS)


def _find_banner(frame):
    """Tìm banner xanh ngọc 'Tăng Thu Nhập' ở nửa trên màn hình bằng MÀU (không phụ thuộc kiểu cửa sổ). Trả hộp (x1,y1,x2,y2) tuyệt đối của dòng
    '<tổng> +<tăng>' (tỉ lệ hộp banner đo trên video: x 0.31-0.96, y 0.53-0.84) hoặc None nếu không có."""
    H, W = frame.shape[:2]
    k = W / REF_W
    sub = frame[:int(450 * k)]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] >= 78) & (hsv[..., 0] <= 100) & (hsv[..., 1] >= 90) & (hsv[..., 2] >= 110)).astype(np.uint8)
    m[:int(80 * k)] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((int(9 * k) | 1, int(25 * k) | 1), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    best = None
    for i in range(1, n):
        x, y, w, h, a = [int(v) for v in st[i]]
        if w >= 300 * k and 60 * k <= h <= 170 * k and a >= 0.45 * w * h and (best is None or a > best[4]):
            best = (x, y, w, h, a)
    if best is None:
        return None
    x, y, w, h, _a = best
    return int(x + 0.31 * w), int(y + 0.53 * h), int(x + 0.96 * w), int(y + 0.84 * h)


def _crop_abs(frame, box):
    if box is None:
        return None
    H, W = frame.shape[:2]
    x1, y1, x2, y2 = box
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2]


def _gain_sig_box(frame, box):
    c = _crop_abs(frame, box)
    if c is None or c.size == 0:
        return None
    return cv2.resize(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), (48, 8), interpolation=cv2.INTER_AREA).astype(np.float32)


def _sig_diff(a, b) -> float:
    if a is None or b is None or a.shape != b.shape:
        return 255.0
    return float(np.abs(a - b).mean())


X10_TAP = (29.6, 18.4)                          # tâm ô tích 'Nâng cấp x10' so với GÓC TRÁI-DƯỚI nút 'Tăng cấp' (đơn vị mẫu; đo trên ảnh 720x1280: (490,851) khi nút ở (453,786) cỡ 165x42)
X10_HALF = 7                                    # nửa cạnh vùng ô tích dùng để so hình (đơn vị mẫu)


def _x10_square(frame, btn, s, lay=None):
    lay = lay or LAYOUT_A
    x, y = btn[0], btn[1]
    cx, cy, r = int(x + lay.x10_tap[0] * s), int(y + lay.x10_tap[1] * s), max(3, int(X10_HALF * s))
    H, W = frame.shape[:2]
    return frame[max(0, cy - r):min(H, cy + r), max(0, cx - r):min(W, cx + r)]


def _x10_dark(frame, btn, s, lay=None) -> float:
    """Tỉ lệ điểm ảnh xám đậm trong ô tích. Ô BỎ TÍCH = hình vuông xám đậm phẳng (đo = 1.0); ô đã tích sẽ có dấu/màu khác nên tỉ lệ thấp hơn."""
    sq = _x10_square(frame, btn, s, lay)
    if sq.size == 0:
        return 0.0
    hsv = cv2.cvtColor(sq, cv2.COLOR_BGR2HSV)
    return float(((hsv[..., 1] <= 70) & (hsv[..., 2] <= 110)).mean())


def _x10_sig(frame, btn, s, lay=None):
    sq = _x10_square(frame, btn, s, lay)
    if sq.size == 0:
        return None
    return cv2.resize(cv2.cvtColor(sq, cv2.COLOR_BGR2GRAY), (8, 8), interpolation=cv2.INTER_AREA).astype(np.float32)


def _arrow_visible(frame, top, s, step=1, arrow=None) -> bool:
    """Mũi tên vàng đổi ô (phải: step>0, trái: step<0) có hiện không? Ô đầu không có mũi tên trái, ô cuối không có mũi tên phải."""
    dx, dy = arrow if arrow else (ARROW_R if step > 0 else ARROW_L)
    cx, cy, r = int(top[0] + dx * s), int(top[1] + dy * s), int(32 * s)
    H, W = frame.shape[:2]
    sub = frame[max(0, cy - r):min(H, cy + r), max(0, cx - r):min(W, cx + r)]
    if sub.size == 0:
        return False
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    m = (hsv[..., 0] >= 15) & (hsv[..., 0] <= 32) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 170)
    return int(m.sum()) >= 150


def _scale_from_buttons(btns, s0: float) -> float:
    """Tỉ lệ thật của giao diện so với toạ độ mẫu (nút 'Tăng cấp' mẫu 132x33, 2 hàng cách nhau 123).
    Đo thực tế trên LDPlayer 720x1280: nút 165x42, 2 hàng cách 156 -> 1.26 (không phải 1.0 như rộng_khung/720). Không đo được -> giữ s0."""
    ests = [b[2] / BTN_W for b in btns] + [b[3] / BTN_H for b in btns]
    if len(btns) >= 2 and 0.8 * ROW_GAP * s0 <= btns[1][1] - btns[0][1] <= 2.2 * ROW_GAP * s0:
        gap = (btns[1][1] - btns[0][1]) / ROW_GAP
        ests += [gap, gap]                          # khoảng cách 2 hàng chính xác hơn bề rộng nút -> tính 2 lần
    ests.sort()
    s = ests[len(ests) // 2]
    return s if 0.6 <= s <= 2.5 else s0


def read_page(frame, scale=None, thorough=False, layout=None) -> Page:
    """Đọc cửa sổ chi tiết 1 mục: nút, giá, số dư vé + loại vé, khoá nhận mục. Tự nhận KIỂU màn hình (`detect_layout`) nếu không chỉ định `layout`.
    scale mặc định = rộng khung / 720 (kiểu Ruộng Đồng tự đo lại từ cỡ nút)."""
    lay = layout or detect_layout(frame) or LAYOUT_A
    pg = _read_page_a(frame, scale, thorough) if lay.id == LAYOUT_A.id else _read_page_generic(frame, scale, thorough, lay)
    pg.layout = lay
    return pg


def _read_page_generic(frame, scale, thorough, lay: Layout) -> Page:
    """Đọc trang cho các kiểu màn hình mới (Nhà tắm, Nuôi dưỡng Nghệ Sĩ...): nút gán hàng theo vị trí mong đợi của kiểu, giá/số dư/loại vé theo hộp của kiểu."""
    h, w = frame.shape[:2]
    k = w / REF_W
    s = float(scale) if scale else k
    pg = Page(scale=s)
    btns = find_buttons(frame, s)
    rows: List[RowInfo] = []
    for i, (ex, ey) in enumerate(lay.expect):
        cand = [b for b in btns if abs(b[0] - ex * k) <= 22 * k and abs(b[1] - ey * k) <= 22 * k]
        if cand:
            b = min(cand, key=lambda b: abs(b[0] - ex * k) + abs(b[1] - ey * k))
            rows.append(RowInfo(i, *b[:4], b[4]))
    if not rows:
        return pg
    top = (rows[0].x, rows[0].y) if rows[0].idx == 0 else (int(lay.expect[0][0] * k), int(lay.expect[0][1] * k))
    pg.top = top
    bal: Optional[float] = None
    for r in rows:
        if r.active and not _has_x10(frame, (r.x, r.y, r.w, r.h), s, lay):
            r.active = False
        crop = _box(frame, (r.x, r.y), lay.cost_box, s)
        if crop is None:
            continue
        if lay.slash:
            b_, c_ = read_pair(crop, thorough)
            r.cost = c_
            if b_ is not None:
                bal = b_
            r.affordable = (b_ >= c_) if (b_ is not None and c_ is not None) else None
        else:
            a = read_amount(crop, False, thorough or lay.plain_cost, plain=lay.plain_cost)      # chữ số nhỏ dễ nhầm 3/8: giá số nguyên luôn đọc đủ lần (đo 8/8 đúng, đọc nhanh 7/8)
            r.cost, r.affordable = a.value, a.green
    if lay.slots and rows:                                        # kiểu có biểu tượng kỹ năng: trang chỉ hiện giá/nút của kỹ năng ĐANG CHỌN
        sel = _selected_slot(frame, top, s, lay)
        rows[0].idx = sel if sel is not None else 0
    pg.rows = rows
    if lay.slash:
        pg.balance = bal
    elif lay.pill_box is not None:
        pill = _box(frame, top, lay.pill_box, s)
        if pill is not None:
            v = read_amount(pill, lay.pill_light, thorough).value
            pg.balance = v if v is not None else read_amount(pill, lay.pill_light, True).value      # nền viên thuốc không đều: đọc kỹ hơn nếu lần nhanh hỏng
        for r in rows:                                           # có cả số dư và giá -> đủ vé khi số dư >= giá (chính xác hơn đoán màu chữ)
            if pg.balance is not None and r.cost is not None:
                r.affordable = pg.balance >= r.cost
    pg.ticket = _ticket_key(frame, top, s, lay)
    pg.key = _page_key(frame, top, s, lay)
    pg.ok = pg.key != "" and any(r.cost is not None for r in rows)
    return pg


def _read_page_a(frame, scale=None, thorough=False) -> Page:
    """(Kiểu Ruộng Đồng) Đọc cửa sổ chi tiết 1 mục. scale mặc định = rộng khung / 720, rồi tự đo lại từ cỡ nút."""
    h, w = frame.shape[:2]
    s = float(scale) if scale else w / REF_W
    pg = Page(scale=s)
    btns = find_buttons(frame, s)
    if not btns:
        return pg
    if not scale:
        s = _scale_from_buttons(btns, s)            # bản 2: giao diện thật to hơn ảnh mẫu ~1.26 lần -> lấy tỉ lệ từ chính nút đo được
        pg.scale = s
    if len(btns) == 1:
        # chỉ thấy 1 nút: có viên thuốc số dư phía trên thì là hàng trên, không thì là hàng dưới
        x, y = btns[0][0], btns[0][1]
        pill = _box(frame, (x, y), PILL_BOX, s)
        top_is_this = pill is not None and float(cv2.cvtColor(pill, cv2.COLOR_BGR2GRAY).mean()) < 110
        top = (x, y) if top_is_this else (x, int(y - ROW_GAP * s))
        rows = [RowInfo(0 if top_is_this else 1, *btns[0][:4], btns[0][4])]
    else:
        top = (btns[0][0], btns[0][1])
        rows = [RowInfo(i, *b[:4], b[4]) for i, b in enumerate(btns[:2])]
    pg.top = top
    for r in rows:
        if r.active and not _has_x10(frame, (r.x, r.y, r.w, r.h), s):
            r.active = False                        # nút xanh nhưng là 'Kích hoạt' (không có ô 'Nâng cấp x10') -> không phải nâng cấp
        crop = _box(frame, (r.x, r.y), COST_BOX, s)
        if crop is None:
            continue
        a = read_amount(crop, False, thorough)
        r.cost, r.affordable = a.value, a.green
    pg.rows = rows
    pill = _box(frame, top, PILL_BOX, s)
    if pill is not None:
        pg.balance = read_amount(pill, True, thorough).value
    pg.ticket = _ticket_type(_box(frame, top, ICON_BOX, s))
    pg.key = _page_key(frame, top, s)
    pg.ok = pg.key != "" and any(r.cost is not None for r in rows)
    return pg


# ----------------------------------------------------------------------------
# 4) Bộ tối ưu (thuần Python, không phụ thuộc ảnh/ADB)
# ----------------------------------------------------------------------------
@dataclass
class PlanRow:
    key: str
    ticket: str
    cost: float                                 # giá lần nâng kế tiếp
    gain: Optional[float]                       # thu nhập tăng mỗi lần nâng (đã đo), None = chưa đo
    growth: float = 1.02                        # hệ số giá mỗi cấp
    can: bool = True                            # nút bấm được (xanh)


def plan_upgrades(rows: List[PlanRow], balances: Dict[str, float], reserve: float = 0.0, min_eff: float = 0.0,
                  max_total: int = 5000) -> Tuple[Dict[str, int], Dict[str, float]]:
    """Chọn số lần nâng mỗi hàng để TỔNG thu nhập tăng lớn nhất với số vé hiện có, theo từng LOẠI VÉ (mỗi loại 1 ngân sách riêng).

    Tham lam theo hiệu quả gain/cost: luôn nâng hàng có hiệu quả cao nhất, giá nhân `growth` sau mỗi cấp (hiệu quả giảm dần nên tối ưu), dừng khi hết vé
    hoặc hiệu quả < min_eff. Trả (số lần mỗi hàng, ngưỡng hiệu quả biên mỗi loại vé = hiệu quả thấp nhất trong các lần được chọn)."""
    counts: Dict[str, int] = {}
    cutoff: Dict[str, float] = {}
    by_ticket: Dict[str, List[PlanRow]] = {}
    for r in rows:
        if r.can and r.gain is not None and r.gain > 0 and r.cost and r.cost > 0:
            by_ticket.setdefault(r.ticket, []).append(r)
    for tk, rs in by_ticket.items():
        budget = float(balances.get(tk, 0.0)) - float(reserve)
        heap = [(-(r.gain / r.cost), i, r.cost) for i, r in enumerate(rs)]
        heapq.heapify(heap)
        total = 0
        low = None
        while heap and total < max_total:
            neg, i, c = heapq.heappop(heap)
            eff = -neg
            if eff < min_eff:
                break
            if c > budget:
                continue                        # hàng này không đủ vé nữa (giá chỉ tăng), thử hàng khác rẻ hơn
            r = rs[i]
            budget -= c
            counts[r.key] = counts.get(r.key, 0) + 1
            total += 1
            low = eff if low is None else min(low, eff)
            nc = c * max(1.0, r.growth)
            heapq.heappush(heap, (-(r.gain / nc), i, nc))
        if low is not None:
            cutoff[tk] = low
    return counts, cutoff


# ----------------------------------------------------------------------------
# 5) Trạng thái + vòng chạy (dùng giao diện UI trừu tượng để test được không cần ADB)
# ----------------------------------------------------------------------------
# Hệ số giá mỗi cấp mặc định theo hàng (người dùng cung cấp + khớp log thật: hàng trên ~0.9%, hàng dưới ~1.2%; một số hàng dưới ~1.0%) - chỉ dùng khi hàng CHƯA đo được chính xác.
# Công thức: giá cấp thứ N = P0*r^N; tổng vé để nâng N cấp liên tiếp = P0*(r^N-1)/(r-1); số cấp nâng được với ngân sách B = floor(ln(1+B*(r-1)/P0)/ln r).
GROWTH_PRIOR = (1.009, 1.012)
RESERVE_PCT = 5.0                               # chừa lại % số vé (tính theo số vé LÚC BẮT ĐẦU của từng loại vé) để dự phòng sai số công thức/đọc số

_FILE_LOCKS: Dict[str, "threading.Lock"] = {}
_FILE_LOCKS_G = threading.Lock()


def _lock_for(path: str):
    """Khoá theo đường dẫn file: nhiều luồng (nhiều giả lập chạy cùng lúc trong 1 tiến trình) không ghi chồng lên cùng 1 file."""
    with _FILE_LOCKS_G:
        return _FILE_LOCKS.setdefault(os.path.abspath(path), threading.Lock())


def _dev_tag(adb, step=None) -> str:
    """Nhãn thiết bị (+ tài khoản nếu biết) dùng đặt tên file lưu/CSV/thư mục debug riêng cho TỪNG giả lập (và từng tài khoản):
    nhiều giả lập chạy cùng lúc không ghi đè file của nhau. Tài khoản lấy từ step['account'] hoặc adb.account_key / adb.account (nếu dashboard gắn)."""
    step = step or {}
    dev = str(getattr(adb, "device_id", None) or "default")
    acc = step.get("account") or getattr(adb, "account_key", None) or getattr(adb, "account", None)
    tag = dev + (f"__{acc}" if acc else "")
    return re.sub(r"[^0-9A-Za-z._-]+", "_", tag)[:80]


TICKET_NAME = {"blue": "xanh dương", "pink": "hồng", "green": "xanh lá", "red": "đỏ", "teal": "xanh ngọc", "purple": "tím", "gold": "vàng", "white": "trắng", "?": "?"}
LAYOUT_SHORT = {"ruong": "Ruộng Đồng", "nhatam": "Nhà tắm", "nuoiduong": "Nuôi dưỡng"}


def _tk(t: str) -> str:
    """Tên hiển thị của loại vé; khoá dạng '<kiểu>:<màu>' (kiểu màn hình mới) hiện là 'Kiểu/màu', vd 'Nuôi dưỡng/tím'."""
    if ":" in t:
        lid, nm = t.split(":", 1)
        return f"{LAYOUT_SHORT.get(lid, lid)}/{TICKET_NAME.get(nm, nm)}"
    return TICKET_NAME.get(t, t)


@dataclass
class RowState:
    key: str
    item: str
    idx: int
    ticket: str = "?"
    cost: Optional[float] = None
    gain: Optional[float] = None
    growth: Optional[float] = None
    active: bool = False
    affordable: Optional[bool] = None
    presses: int = 0
    gain_fail: int = 0
    dead: bool = False                          # bấm không ăn / không đọc được mức tăng quá nhiều lần -> bỏ
    pos: int = 0                                # vị trí ô trong danh sách (1 = ô đầu)
    gain_sum: float = 0.0                       # tổng thu nhập tăng thêm nhờ các lần nâng của hàng này (theo mức tăng đo được)
    growth_precise: bool = False                # hệ số giá đo đủ chính xác (giá < 1tr hiện 4 chữ số, hoặc đo qua >= 5 cấp liền)
    growth_L: int = 0                           # số cấp dùng để đo hệ số giá (càng lớn càng chính xác)
    batch_fail: int = 0

    def eff(self):
        if self.gain and self.cost:
            return self.gain / self.cost
        return None

    @property
    def name(self) -> str:
        return f"Ô{self.pos}-{'trên' if self.idx == 0 else 'dưới'}"


class _Stop(Exception):
    pass


class UpgradeBot:
    """ui cần có: page() -> Page | None, press(page, idx) -> (Page | None, gain | None),
    next_item(page, step=1) -> Page | None (sang ô kế: step=+1 phải / -1 trái; trả trang mới đã đọc, None = không đổi được/hết danh sách);
    tuỳ chọn (nhanh): go_edge(page, step) -> (Page, số lần bấm) bấm liên tục tới ô đầu/cuối; jump(page, step, n) -> Page bấm liên tục n lần.

    Danh sách ô là TUYẾN TÍNH (ô đầu không có mũi tên trái, ô cuối không có mũi tên phải), KHÔNG vòng tròn. Ô được định danh bằng VỊ TRÍ (1 = ô đầu):
    bot lùi về ô đầu rồi đi sang phải đọc hết (`_scan`) tới khi gặp `end_locked` (3) ô liên tiếp không còn nút 'Tăng cấp' (chưa mở / 'Kích hoạt')
    hoặc hết mũi tên phải; các lượt nâng sau đi tới lui đúng khoảng có việc."""

    def __init__(self, ui, log=None, should_stop=None, test=False, max_items=80, max_passes=30, min_eff=0.0, reserve=0.0,
                 max_seconds=0, cost_growth=None, gain_fail_limit=2, now=time.time, rewind=True, end_locked=3,
                 probe_on_scan=True, state_file=None, resume=True, max_age_hours=0, use_x10=True, x10_min=10, data_file=None, reserve_pct=RESERVE_PCT):
        self.ui = ui
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test = bool(test)
        self.max_items, self.max_passes = int(max_items), int(max_passes)
        self.min_eff, self.reserve = float(min_eff), float(reserve)
        self.max_seconds = float(max_seconds or 0)
        self.cost_growth = float(cost_growth) if cost_growth else None     # ép 1 hệ số giá cho mọi hàng chưa đo chính xác; None = theo hàng (GROWTH_PRIOR)
        self.reserve_pct = max(0.0, float(reserve_pct))
        self.gain_fail_limit = int(gain_fail_limit)
        self.rewind, self.end_locked = bool(rewind), max(1, int(end_locked))
        self.probe_on_scan = bool(probe_on_scan)        # nâng thử mỗi hàng 1 cấp NGAY khi quét tới ô đó (khỏi đi lại lần nữa để dò)
        self.state_file = state_file or None            # file JSON lưu kết quả đo (mức tăng/hệ số giá từng hàng) để chạy lại / chạy tiếp
        self.resume = bool(resume)
        self.max_age_hours = float(max_age_hours or 0)
        self.use_x10 = bool(use_x10)                    # nâng nhiều cấp thì tích 'Nâng cấp x10' (mỗi lần bấm +10 cấp) cho nhanh
        self.x10_min = max(2, int(x10_min))             # chỉ dùng x10 khi cần nâng >= số cấp này
        self.data_file = data_file or None              # CSV thu thập dữ liệu (cấp, giá, vé, mức tăng) để phân tích
        self._saved: Dict = {}                          # kết quả đã nạp từ file lưu
        self.mismatch = 0                               # số ô không khớp ô đã lưu (khác tài khoản / danh sách đổi)
        self.layout: Optional[Layout] = None            # kiểu màn hình nhận được (đọc từ trang đầu tiên)
        self._pass_stat: Dict[str, Dict] = {}           # đã nâng / dự tính của lượt đang chạy (theo hàng)
        self.plan_total = 0                             # tổng số cấp DỰ TÍNH qua các lượt
        self.done_total = 0                             # tổng số cấp ĐÃ nâng theo kế hoạch qua các lượt
        self.adopted = 0                                # số hàng dùng lại mức tăng đã lưu
        self.prev_presses = 0                           # tổng số lần nâng của các lần chạy trước (từ file lưu)
        self._save_err = False
        self.now = now
        self.t0 = now()
        self.rows: Dict[str, RowState] = {}
        self.balances: Dict[str, float] = {}
        self.start_balances: Dict[str, float] = {}
        self.items: List[str] = []
        self.keys: Dict[int, str] = {}          # khoá trang (`Page.key`) của từng ô theo vị trí - để kiểm tra có tới đúng ô sau khi nhảy nhiều ô
        self.presses = 0
        self.pos = 1                            # vị trí ô hiện tại
        self.n_total = 0                        # số ô đã xem khi quét (kể cả ô chưa mở ở cuối)
        self.n_items = 0                        # vị trí ô CUỐI CÙNG còn nâng được
        self.gain_total = 0.0                   # tổng thu nhập tăng thêm (cộng mức tăng đo được ở mỗi lần nâng)

    # ---- tiện ích
    def _check(self):
        if self.should_stop():
            raise _Stop("stop")
        if self.max_seconds and self.now() - self.t0 > self.max_seconds:
            raise _Stop("timeout")

    def _canon(self, key: str) -> str:
        """(Cũ, không còn dùng để định danh ô - nay dùng vị trí.) Khoá mục chuẩn hoá theo dHash."""
        for k in self.items:
            if k == key or (len(k) == len(key) and _hamming(k, key) <= 6):
                return k
        return key

    def _absorb(self, pg: Page, pos: Optional[int] = None):
        """Cập nhật trạng thái các hàng + số dư vé từ 1 trang vừa đọc (ô ở vị trí pos)."""
        pos = self.pos if pos is None else pos
        if pg.ticket != "?" and pg.balance is not None:
            self.balances[pg.ticket] = pg.balance
            self.start_balances.setdefault(pg.ticket, pg.balance)
        for r in pg.rows:
            k = f"{pos}#{r.idx}"
            st = self.rows.get(k)
            if st is None:
                st = self.rows[k] = RowState(k, str(pos), r.idx, pos=pos)
            st.ticket = pg.ticket if pg.ticket != "?" else st.ticket
            if r.cost is not None:
                st.cost = r.cost
            st.active, st.affordable = r.active, r.affordable

    @staticmethod
    def _locked(pg: Page) -> bool:
        """Trang không còn nút 'Tăng cấp' nào (chưa mở / 'Kích hoạt')."""
        return not any(r.active for r in pg.rows)

    def _plan_rows(self) -> List[PlanRow]:
        out = []
        for st in self.rows.values():
            if st.dead or st.cost is None or not st.active:
                continue
            out.append(PlanRow(st.key, st.ticket, st.cost, st.gain, self._growth_of(st),
                               can=(st.affordable is not False)))
        return out

    def _growth_prior(self, idx: int) -> float:
        """Hệ số giá dự phòng cho hàng trên (idx 0) / hàng dưới (idx 1): trung vị các hàng CÙNG vị trí đã đo chính xác (>= 3 hàng), không thì GROWTH_PRIOR."""
        if self.cost_growth:
            return self.cost_growth
        gs = sorted(st.growth for st in self.rows.values() if st.idx == idx and st.growth and st.growth_precise)
        if len(gs) >= 3:
            return gs[len(gs) // 2]
        if self.layout is not None and self.layout.id != LAYOUT_A.id:
            return 1.01                         # kiểu màn hình mới: chưa có số liệu hệ số giá -> dùng 1.01 cho tới khi đo được (giá nhỏ nên đo 1 cấp đã chính xác)
        return GROWTH_PRIOR[min(idx, 1)]

    def _growth_of(self, st: RowState) -> float:
        """Hệ số giá mỗi cấp của hàng: đo chính xác (giá < 1tr hiện 4 chữ số, hoặc qua >= 5 cấp liền) thì dùng số đo; chưa thì dùng mặc định theo hàng.
        (Đo 1 cấp ở giá >= 1tr chỉ có 3 chữ số, sai ~0.4% - lớn hơn cả chênh lệch giữa 0.9% và 1.2%.)"""
        if st.growth and st.growth_precise:
            return max(1.0, st.growth)
        return max(1.0, self._growth_prior(st.idx))

    def _reserve_of(self, tk: str) -> float:
        """Số vé phải chừa lại của loại vé tk = reserve tuyệt đối + reserve_pct % số vé LÚC BẮT ĐẦU (cố định, không co lại sau mỗi lượt)."""
        base = self.start_balances.get(tk, self.balances.get(tk, 0.0)) or 0.0
        return self.reserve + base * self.reserve_pct / 100.0

    @staticmethod
    def _cost_sum(c: float, g: float, n: int) -> float:
        return c * n if g <= 1.0000001 else c * (g ** n - 1.0) / (g - 1.0)

    @staticmethod
    def _levels_within(c: float, g: float, budget: float, nmax: int) -> int:
        """Số cấp lớn nhất (<= nmax) nâng được với ngân sách `budget` khi giá cấp kế = c, nhân g mỗi cấp:
        tổng = c*(g^k-1)/(g-1) <= budget  =>  k = floor(ln(1 + budget*(g-1)/c) / ln g)  (công thức của người dùng), rồi hiệu chỉnh sai số số thực."""
        if budget <= 0 or c <= 0 or nmax <= 0:
            return 0
        if g <= 1.0000001:
            k = int(budget // c)
        else:
            k = int(math.floor(math.log(1.0 + budget * (g - 1.0) / c) / math.log(g)))
        k = max(0, min(nmax, k))
        cs = UpgradeBot._cost_sum
        while k > 0 and cs(c, g, k) > budget:
            k -= 1
        while k < nmax and cs(c, g, k + 1) <= budget:
            k += 1
        return k

    def _split10(self, n: int):
        k10 = n // 10 if (self.use_x10 and n >= self.x10_min) else 0
        return k10, n - 10 * k10

    def _eff_range(self, ticket: Optional[str] = None):
        """(thấp nhất, hàng, cao nhất, hàng) của hiệu quả = tăng thu nhập / vé của lần nâng KẾ TIẾP, trong các hàng đã đo (theo loại vé nếu có)."""
        es = [(st.eff(), st) for st in self.rows.values()
              if st.active and not st.dead and st.eff() is not None and (ticket is None or st.ticket == ticket)]
        if not es:
            return None
        lo = min(es, key=lambda t: t[0])
        hi = max(es, key=lambda t: t[0])
        return lo[0], lo[1], hi[0], hi[1]

    def _eff_text(self, ticket: Optional[str] = None) -> str:
        r = self._eff_range(ticket)
        if r is None:
            return "chưa đo hàng nào"
        lo, lst, hi, hst = r
        return f"thấp nhất {lo:.3g}/vé ({lst.name}), cao nhất {hi:.3g}/vé ({hst.name})"

    # ---- lưu / nạp kết quả đo
    def _tab_pick(self, key1: str) -> str:
        """Chọn id 'tab' (kiểu màn hình + danh sách ô) để đặt tên file lưu/CSV: tìm file đã lưu có khoá ô 1 KHỚP ô 1 hiện tại -> dùng lại id đó, không có thì lấy id mới.
        Nhờ vậy nhiều màn hình nâng cấp khác nhau (Ruộng Đồng, Nghệ Sĩ, Nhà tắm, Nuôi dưỡng...) trên cùng 1 giả lập có file riêng, không ghi đè nhau, KHÔNG cần cấu hình."""
        lid = self.layout.id if self.layout else "ruong"
        tmpl = self.state_file if (self.state_file and "{tab}" in self.state_file) else None
        if tmpl is None:
            return f"{lid}_1"
        used = set()
        for f in sorted(glob.glob(tmpl.replace("{tab}", f"{lid}_*"))):
            m = re.search(re.escape(lid) + r"_(\d+)\.json$", os.path.basename(f))
            if not m:
                continue
            used.add(int(m.group(1)))
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    k1 = json.load(fh).get("keys", {}).get("1")
            except Exception:
                continue
            if k1 and _same_item(key1, k1):
                return f"{lid}_{m.group(1)}"
        n = 1
        while n in used:
            n += 1
        tab = f"{lid}_{n}"
        legacy = tmpl.replace("__{tab}", "")                    # file lưu KIỂU CŨ (chưa có {tab}): nếu khớp ô 1 thì chuyển sang tên mới (giữ kết quả đã đo)
        if legacy != tmpl and os.path.exists(legacy):
            try:
                with open(legacy, "r", encoding="utf-8") as fh:
                    k1 = json.load(fh).get("keys", {}).get("1")
                if k1 and _same_item(key1, k1):
                    os.replace(legacy, tmpl.replace("{tab}", tab))
                    if self.data_file and "{tab}" in self.data_file:
                        old_csv = self.data_file.replace("__{tab}", "")
                        if os.path.exists(old_csv):
                            os.replace(old_csv, self.data_file.replace("{tab}", tab))
            except Exception:
                pass
        return tab

    def _load_state(self):
        """Nạp kết quả đo của các lần chạy trước (mức tăng + hệ số giá từng hàng, khoá nhận ô) để khỏi nâng thử lại. Lỗi/không có file = chạy như lần đầu."""
        self._saved = {}
        if not self.state_file or not self.resume or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            assert isinstance(d, dict) and isinstance(d.get("rows"), dict) and isinstance(d.get("keys"), dict)
        except Exception as e:
            self.log("warn", f"Nâng cấp tối ưu: không đọc được file kết quả đã lưu ({self.state_file}): {e} -> bỏ qua")
            return
        age_h = (time.time() - float(d.get("saved_at", 0))) / 3600.0 if d.get("saved_at") else None
        if self.max_age_hours and age_h is not None and age_h > self.max_age_hours:
            self.log("info", f"Nâng cấp tối ưu: kết quả đã lưu quá cũ ({age_h:.1f}h > {self.max_age_hours:g}h) -> đo lại từ đầu")
            return
        self._saved = d
        self.prev_presses = int(d.get("totals", {}).get("presses", 0) or 0)
        self.log("info", f"Nâng cấp tối ưu: có kết quả đã lưu ({len(d['rows'])} hàng, {len(d['keys'])} ô"
                         + (f", lưu {age_h:.1f}h trước" if age_h is not None else "") + f") - ô nào vẫn khớp thì dùng lại mức tăng, KHÔNG nâng thử lại [{self.state_file}]")

    def _adopt(self, pos: int, pg: Page):
        """Ô ở vị trí pos khớp ô đã lưu (cùng khoá trang) -> lấy lại mức tăng + hệ số giá đã đo cho các hàng của ô."""
        sk = self._saved.get("keys", {}).get(str(pos))
        if sk is None:
            return
        if not _same_item(pg.key, sk):
            self.mismatch += 1
            self.log("warn", f"Nâng cấp tối ưu: ô {pos} KHÁC ô đã lưu (danh sách ô đã đổi / tài khoản khác?) -> không dùng kết quả cũ của ô này")
            return
        for idx in (0, 1):
            sr = self._saved["rows"].get(f"{pos}#{idx}")
            st = self.rows.get(f"{pos}#{idx}")
            if not sr or st is None or st.gain is not None:
                continue
            if sr.get("gain"):
                st.gain = float(sr["gain"])
                self.adopted += 1
            if sr.get("growth"):
                st.growth = float(sr["growth"])
                st.growth_precise = bool(sr.get("growth_precise", False))
                st.growth_L = int(sr.get("growth_L", 0) or 0)

    def _save_state(self):
        if not self.state_file or self.test:
            return
        try:
            rows = {k: {"pos": st.pos, "idx": st.idx, "ticket": st.ticket, "gain": st.gain, "growth": st.growth, "growth_precise": st.growth_precise,
                                  "growth_L": st.growth_L, "cost": st.cost, "presses": st.presses}
                    for k, st in self.rows.items() if st.gain is not None or st.presses}
            old_rows = self._saved.get("rows", {})
            for k, v in old_rows.items():                       # hàng chưa đo lại lần này (ô chưa tới/không khớp) giữ nguyên bản cũ
                if k not in rows and str(v.get("pos")) in self._saved.get("keys", {}) and int(v.get("pos", 0)) not in self.keys:
                    rows[k] = v
            keys = {str(p): k for p, k in self.keys.items()}
            for p, k in self._saved.get("keys", {}).items():
                keys.setdefault(p, k)
            d = {"version": 1, "saved_at": time.time(), "saved_text": time.strftime("%Y-%m-%d %H:%M:%S"), "n_total": self.n_total, "n_items": self.n_items,
                 "totals": {"presses": self.prev_presses + self.presses, "gain": float(self._saved.get("totals", {}).get("gain", 0) or 0) + self.gain_total},
                 "keys": keys, "rows": rows}
            with _lock_for(self.state_file):                    # nhiều luồng/giả lập không ghi chồng lên cùng 1 file (mỗi giả lập đã có file riêng - xem _dev_tag)
                try:
                    import paths
                    paths.save_json(self.state_file, d, backup=False)
                except ImportError:
                    os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
                    tmp = self.state_file + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(d, f, ensure_ascii=False)
                    os.replace(tmp, self.state_file)
        except Exception as e:
            if not self._save_err:
                self._save_err = True
                self.log("warn", f"Nâng cấp tối ưu: không lưu được kết quả ({e})")

    def _csv(self, st: RowState, kind: str, levels: int, c0, c1, b0, b1, gain):
        """Ghi 1 dòng dữ liệu (để phân tích giá theo cấp / mức tăng từng hàng). Mở bằng Excel/Google Sheets được. Mỗi giả lập/tài khoản 1 file riêng."""
        if not self.data_file or self.test:
            return
        try:
            spent = (b0 - b1) if (b0 is not None and b1 is not None) else ""
            row = [time.strftime("%Y-%m-%d %H:%M:%S"), st.pos, "tren" if st.idx == 0 else "duoi", st.ticket, kind, levels,
                   "" if c0 is None else c0, "" if c1 is None else c1, "" if b0 is None else b0, "" if b1 is None else b1, spent,
                   "" if gain is None else gain, "" if not st.growth else round(st.growth, 5), st.presses]
            with _lock_for(self.data_file):
                new = not os.path.exists(self.data_file)
                os.makedirs(os.path.dirname(self.data_file) or ".", exist_ok=True)
                with open(self.data_file, "a", encoding="utf-8-sig", newline="") as f:
                    w = csv.writer(f)
                    if new:
                        w.writerow(["thoi_gian", "o", "hang", "ve", "loai", "so_cap", "gia_truoc", "gia_sau", "so_du_truoc", "so_du_sau", "ve_ton",
                                    "tang_moi_cap", "he_so_gia", "tong_cap_da_nang"])
                    w.writerow(row)
        except Exception:
            pass

    # ---- điều hướng
    def _locate(self, pg: Optional[Page]) -> Optional[int]:
        """Trang pg đang ở ô vị trí nào (theo khoá đã lưu khi quét)? None nếu không khớp ô nào hoặc khớp nhiều ô."""
        if pg is None or not pg.ok:
            return None
        hit = [p for p, k in self.keys.items() if _same_item(pg.key, k)]
        return hit[0] if len(hit) == 1 else None

    @property
    def circular(self) -> bool:
        return bool(self.layout is not None and self.layout.circular and self.n_total > 1)

    def _plan_move(self, target: int):
        """(bước +1/-1, số bước) ngắn nhất để từ ô hiện tại tới target; danh sách xoay vòng thì được đi vòng qua đầu/cuối."""
        d = target - self.pos
        if not self.circular:
            return (1 if d > 0 else -1), abs(d)
        n = self.n_total
        fwd, back = d % n, (-d) % n
        return (1, fwd) if fwd <= back else (-1, back)

    def _advance(self, step: int):
        self.pos = (self.pos - 1 + step) % self.n_total + 1 if self.circular else self.pos + step

    def _dist(self, a: int, b: int) -> int:
        d = abs(a - b)
        return min(d, self.n_total - d) if self.circular else d

    def _goto(self, pg: Page, target: int) -> Page:
        """Tới ô `target`: nhiều ô thì bấm LIÊN TỤC mũi tên (`ui.jump`, nhanh) rồi kiểm khoá trang; lệch thì xác định lại vị trí và đi nốt từng ô."""
        jump = getattr(self.ui, "jump", None)
        step, n = self._plan_move(target)
        if jump is not None and n >= 2 and target in self.keys:
            self._check()
            npg = jump(pg, step, n)
            if npg is not None and npg.ok:
                pg = npg
                if _same_item(npg.key, self.keys[target]):
                    self.pos = target
                    return pg
                found = self._locate(npg)
                if found is None:
                    raise _Stop(f"mất vị trí ô sau khi bấm liên tục {n} lần (cần tới ô {target}) - xem ảnh debug_upgrade/")
                self.log("warn", f"Nâng cấp tối ưu: bấm liên tục lệch (tới ô {found}, cần ô {target}) -> đi nốt từng ô")
                self.pos = found
            else:
                raise _Stop(f"không đọc được trang sau khi bấm liên tục {n} lần")
        while self.pos != target:
            self._check()
            step, _n = self._plan_move(target)
            npg = self.ui.next_item(pg, step)
            if npg is None:
                raise _Stop(f"không sang được ô kế (đang ở ô {self.pos}, cần tới ô {target})")
            pg = npg
            self._advance(step)
        return pg

    def _scan(self) -> Optional[Page]:
        """Lùi về ô đầu, rồi đi sang phải đọc từng ô tới khi hết danh sách. Trả trang cuối (đang đứng), None nếu không đọc được cửa sổ."""
        pg = self.ui.page()
        if pg is None or not pg.ok:
            return None
        circ = bool(pg.layout is not None and pg.layout.circular)
        if circ:
            self.log("info", "Nâng cấp tối ưu: danh sách XOAY VÒNG (ô cuối bấm tiếp = về ô đầu) -> coi ô đang mở là ô 1, đi sang phải tới khi quay lại ô 1")
        if self.rewind and not circ:
            edge = getattr(self.ui, "go_edge", None)
            if edge is not None:
                npg, taps = edge(pg, -1)                # bấm liên tục mũi tên trái tới khi hết mũi tên (nhanh, không đọc từng ô)
                if npg is not None and npg.ok:
                    pg = npg
                if taps:
                    self.log("info", f"Nâng cấp tối ưu: đã bấm mũi tên trái liên tục {taps} lần về ô đầu")
            else:
                back = 0
                while back < self.max_items:
                    self._check()
                    npg = self.ui.next_item(pg, -1)
                    if npg is None:
                        break
                    pg = npg
                    back += 1
                if back:
                    self.log("info", f"Nâng cấp tối ưu: đang đứng giữa danh sách, đã lùi {back} ô về ô đầu")
        self.pos = 1
        self.layout = pg.layout or LAYOUT_A
        if (self.state_file and "{tab}" in self.state_file) or (self.data_file and "{tab}" in self.data_file):
            tab = self._tab_pick(pg.key)
            if self.state_file:
                self.state_file = self.state_file.replace("{tab}", tab)
            if self.data_file:
                self.data_file = self.data_file.replace("{tab}", tab)
            self.log("info", f"Nâng cấp tối ưu: màn hình '{self.layout.label}' - file kết quả: {os.path.basename(self.state_file or self.data_file or '')}")
        self._load_state()
        streak, last_open = 0, 0
        reason = ""
        wrapped = False
        while True:
            self._check()
            self._absorb(pg, self.pos)
            self.keys[self.pos] = pg.key
            self._adopt(self.pos, pg)
            states = []
            for r in sorted(pg.rows, key=lambda r: r.idx):
                if not r.active:
                    states.append("chưa mở/Kích hoạt")
                else:
                    states.append(f"giá {format_amount(r.cost)} " + ("thiếu vé" if r.affordable is False else "bấm được"))
            names = ["trên", "dưới"]
            self.log("info", f"  Ô {self.pos}: " + " | ".join(f"{names[min(r.idx, 1)]}: {t}" for r, t in zip(sorted(pg.rows, key=lambda r: r.idx), states)))
            if self.probe_on_scan and not self.test:
                for r in sorted(pg.rows, key=lambda r: r.idx):     # nâng thử 1 cấp NGAY tại đây để đo mức tăng (khỏi quay lại dò sau)
                    st = self.rows.get(f"{self.pos}#{r.idx}")
                    if st is not None and st.active and st.gain is None and not st.dead and st.affordable is not False:
                        pg = self._press_row(pg, st, 1, None)
            if self._locked(pg):
                streak += 1
            else:
                streak, last_open = 0, self.pos
            if streak >= self.end_locked:
                reason = f"gặp {streak} ô liên tiếp không còn nút 'Tăng cấp'"
                break
            if self.pos >= self.max_items:
                reason = f"đủ max_items={self.max_items}"
                break
            npg = self.ui.next_item(pg, 1)
            if npg is None:
                reason = "hết mũi tên phải (ô cuối)"
                break
            if circ and self.pos >= 2 and _same_item(npg.key, self.keys.get(1, "")):
                reason = "đã quay lại ô 1 (danh sách xoay vòng)"
                wrapped = True
                pg = npg
                break
            pg = npg
            self.pos += 1
        self.n_total, self.n_items = self.pos, last_open
        if wrapped:
            self.pos = 1                                        # thực tế đang đứng ở ô 1 (vừa quay vòng)
        locked = sum(1 for p in range(1, self.n_total + 1) if not any(st.active for st in self.rows.values() if st.pos == p))
        nrows = sum(1 for st in self.rows.values() if st.active)
        self.log("info", f"Nâng cấp tối ưu: QUÉT XONG ({reason}) - đã xem {self.n_total} ô; ô cuối còn nâng được là ô {last_open}; "
                         f"{self.n_total - locked} ô có nút 'Tăng cấp', {locked} ô chưa mở; {nrows} hàng nâng được; vé: "
                 + (", ".join(f"{_tk(k)}={format_amount(v)}" for k, v in sorted(self.balances.items())) or "?")
                 + (f"; dùng lại mức tăng đã lưu của {self.adopted} hàng" if self.adopted else "")
                 + f"; nâng thử trong lúc quét: {self.presses} lần")
        self._save_state()
        return pg

    # ---- chạy
    def run(self) -> bool:
        try:
            return self._run()
        except _Stop as e:
            self.log("info", f"Nâng cấp tối ưu: dừng ({e}) sau {self.presses} lần nâng")
            self._summary()
            return False

    def _run(self) -> bool:
        pg = self._scan()
        if pg is None:
            self.log("warn", "Nâng cấp tối ưu: không đọc được cửa sổ chi tiết (hãy MỞ SẴN 1 ô có 2 hàng 'Tăng cấp'). Xem ảnh debug_upgrade/")
            return False
        if self.n_items <= 0:
            self.log("warn", "Nâng cấp tối ưu: không có ô nào còn nút 'Tăng cấp'")
            return True
        self._table("Bảng hàng sau khi quét")
        if self.test:
            self.log("info", "Nâng cấp tối ưu [TEST]: chỉ đọc, không bấm. Mức tăng chỉ đo được khi nâng THẬT (lượt đầu nâng thử mỗi hàng 1 cấp).")
            return True
        for ps in range(1, self.max_passes + 1):
            self._check()
            before = self.presses
            pg = self._do_pass(ps, pg)
            if self.presses == before:
                break
        self._table("Bảng hàng sau khi nâng")
        self._save_state()
        self._summary()
        return True

    def _table(self, title: str = ""):
        self.log("info", f"--- {title} (ô-hàng | vé | giá lần kế | tăng/lần | hiệu quả = tăng/vé) ---")
        for st in sorted(self.rows.values(), key=lambda r: (r.pos, r.idx)):
            e = st.eff()
            state = "chưa mở" if not st.active else ("thiếu vé" if st.affordable is False else "bấm được")
            if st.dead:
                state += ", BỎ"
            self.log("info", f"  {st.name:<10} vé {_tk(st.ticket):<10} giá {format_amount(st.cost):>8} {state:<18} "
                             f"tăng {format_amount(st.gain):>8} hiệu quả {'?' if e is None else f'{e:.3g}'}"
                             + (f"  (đã nâng {st.presses} lần)" if st.presses else ""))
        for tk in sorted(self.balances):
            self.log("info", f"  Hiệu quả vé {_tk(tk)}: {self._eff_text(tk)}")

    def _summary(self):
        done = sorted((st for st in self.rows.values() if st.presses), key=lambda r: (r.pos, r.idx))
        self.log("info", f"=== TỔNG KẾT: {self.presses} lần nâng ở {len(done)} hàng, thu nhập tăng thêm ~{format_amount(self.gain_total)} (cộng mức tăng đo ở từng lần nâng) ===")
        if self.plan_total:
            self.log("info", f"  Theo kế hoạch (công thức): đã nâng {self.done_total} / dự tính {self.plan_total} cấp")
        if self.prev_presses:
            self.log("info", f"  Cộng cả các lần chạy trước: {self.prev_presses + self.presses} lần nâng")
        if self.state_file and not self.test:
            self.log("info", f"  Đã lưu kết quả đo vào {self.state_file} (lần sau chạy lại/chạy tiếp sẽ dùng, khỏi nâng thử lại)")
        for tk in sorted(self.balances):
            a, b = self.start_balances.get(tk), self.balances.get(tk)
            if a is not None and b is not None:
                self.log("info", f"  Vé {_tk(tk)}: {format_amount(a)} -> {format_amount(b)} (tiêu {format_amount(max(0.0, a - b))}); hiệu quả: {self._eff_text(tk)}")
        if done:
            self.log("info", "  Đã nâng: " + "; ".join(f"{st.name} ×{st.presses}" for st in done))

    def _log_plan(self, ps: int, rows: List[PlanRow], counts: Dict[str, int], cutoff: Dict[str, float], probes: set):
        self.log("info", f"--- LƯỢT {ps}: kế hoạch nâng ---")
        tickets = sorted({self.rows[r.key].ticket for r in rows})
        for tk in tickets:
            cnt = {k: n for k, n in counts.items() if self.rows[k].ticket == tk}
            line = (f"  Vé {_tk(tk)}: dư {format_amount(self.balances.get(tk))}, chừa lại {format_amount(self._reserve_of(tk))} ({self.reserve_pct:g}%) dự phòng sai số "
                    f"-> dùng được {format_amount(max(0.0, (self.balances.get(tk) or 0.0) - self._reserve_of(tk)))}; hiệu quả hiện tại: {self._eff_text(tk)}")
            if cnt:
                tot_cost = sum(self._cost_sum(self.rows[k].cost, self._growth_of(self.rows[k]), n) for k, n in cnt.items())
                tot_gain = sum(n * (self.rows[k].gain or 0.0) for k, n in cnt.items())
                line += (f"; kế hoạch: nâng {sum(cnt.values())} cấp ở {len(cnt)} hàng, tốn ~{format_amount(tot_cost)}, thu nhập tăng ~{format_amount(tot_gain)}"
                         f" (~{(tot_gain / tot_cost if tot_cost else 0):.3g}/vé), ngưỡng biên (hiệu quả thấp nhất vẫn nâng) = {cutoff.get(tk, 0):.3g}/vé")
            else:
                line += "; không nâng hàng nào đã đo"
            self.log("info", line)
            for k, n in sorted(cnt.items(), key=lambda kv: -(self.rows[kv[0]].eff() or 0))[:14]:
                st = self.rows[k]
                g = self._growth_of(st)
                last = (st.gain / (st.cost * g ** (n - 1))) if (st.gain and st.cost) else None
                k10, k1 = self._split10(n)
                self.log("info", f"     {st.name}: nâng {n} cấp ({k10}×x10 + {k1}×1): giá {format_amount(st.cost)} -> {format_amount(st.cost * g ** n)}, "
                                 f"tốn ~{format_amount(self._cost_sum(st.cost, g, n))}, tăng ~{format_amount(n * (st.gain or 0.0))} "
                                 f"({format_amount(st.gain)}/cấp; hiệu quả {(st.eff() or 0):.3g} -> {'?' if last is None else f'{last:.3g}'}/vé, hệ số giá {g:.4f})")
            if len(cnt) > 14:
                self.log("info", f"     ... và {len(cnt) - 14} hàng nữa")
        if probes:
            self.log("info", "  Nâng thử 1 cấp để đo mức tăng (chưa biết): " + ", ".join(sorted((self.rows[k].name for k in probes), key=lambda n: (int(n[1:].split('-')[0]), n))))
        skipped = [st.name for st in self.rows.values() if st.active and st.affordable is False and not st.dead]
        if skipped:
            self.log("info", f"  Bỏ qua vì thiếu vé: {', '.join(sorted(skipped))}")

    def _do_pass(self, ps: int, pg: Page) -> Page:
        rows = self._plan_rows()
        known = [r for r in rows if r.gain is not None]
        usable = {tk: max(0.0, b - self._reserve_of(tk)) for tk, b in self.balances.items()}      # vé dùng được = số dư - phần chừa dự phòng
        counts, cutoff = plan_upgrades(known, usable, 0.0, self.min_eff)
        probes = {r.key for r in rows if r.gain is None and r.can}
        self._log_plan(ps, rows, counts, cutoff, probes)
        plan_cost = {k: self._cost_sum(self.rows[k].cost, self._growth_of(self.rows[k]), n) for k, n in counts.items()}
        plan_gain = {k: n * (self.rows[k].gain or 0.0) for k, n in counts.items()}
        bal0 = dict(self.balances)
        self._pass_stat = {k: {"n": n, "done": 0, "spent": 0.0, "gain": 0.0} for k, n in counts.items()}
        work = {k: counts.get(k, 0) + (1 if k in probes else 0) for k in set(counts) | probes}
        work = {k: n for k, n in work.items() if n > 0 and not self.rows[k].dead}
        if not work:
            self.log("info", f"  Lượt {ps}: không còn hàng nào để nâng")
            return pg
        poss = sorted({self.rows[k].pos for k in work})
        lo, hi = poss[0], poss[-1]
        if self._dist(self.pos, lo) <= self._dist(self.pos, hi):
            first, last, step = lo, hi, 1
        else:
            first, last, step = hi, lo, -1
        self.log("info", f"  Lượt {ps}: đi từ ô {first} tới ô {last} ({len(work)} hàng cần nâng, tổng {sum(work.values())} lần)")
        pg = self._goto(pg, first)
        while True:
            self._check()
            pg = self._visit(pg, work, cutoff)
            if self.pos == last:
                break
            npg = self.ui.next_item(pg, step)
            if npg is None:
                raise _Stop(f"không sang được ô {self.pos + step} khi đang nâng")
            pg = npg
            self.pos += step
        self._pass_report(ps, plan_cost, plan_gain, bal0)
        return pg

    def _pass_report(self, ps: int, plan_cost: Dict[str, float], plan_gain: Dict[str, float], bal0: Dict[str, float]):
        """Cuối mỗi lượt: ĐÃ NÂNG / DỰ TÍNH của từng hàng (số cấp, vé tốn, thu nhập tăng) và từng loại vé (còn lại bao nhiêu, chừa lại bao nhiêu)."""
        if not self._pass_stat:
            return
        self.log("info", f"--- LƯỢT {ps}: ĐÃ NÂNG / DỰ TÍNH ---")
        tot_n = tot_d = 0
        per_tk: Dict[str, List[float]] = {}
        for k in sorted(self._pass_stat, key=lambda k: (self.rows[k].pos, self.rows[k].idx)):
            st, ss = self.rows[k], self._pass_stat[k]
            flag = "" if ss["done"] >= ss["n"] else f"  <-- THIẾU {ss['n'] - ss['done']} cấp"
            self.log("info", f"  {st.name}: đã nâng {ss['done']} / dự tính {ss['n']} cấp | vé tốn {format_amount(ss['spent'])} / dự tính {format_amount(plan_cost.get(k))} | "
                             f"thu nhập tăng ~{format_amount(ss['gain'])} / dự tính ~{format_amount(plan_gain.get(k))}{flag}")
            tot_n += ss["done"]
            tot_d += ss["n"]
            a = per_tk.setdefault(st.ticket, [0.0, 0.0, 0.0, 0.0])
            a[0] += ss["spent"]
            a[1] += plan_cost.get(k, 0.0)
            a[2] += ss["gain"]
            a[3] += plan_gain.get(k, 0.0)
        for tk, a in sorted(per_tk.items()):
            self.log("info", f"  Vé {_tk(tk)}: tốn {format_amount(a[0])} / dự tính {format_amount(a[1])}; số dư {format_amount(bal0.get(tk))} -> {format_amount(self.balances.get(tk))}; "
                             f"chừa lại {format_amount(self._reserve_of(tk))} ({self.reserve_pct:g}% vé lúc bắt đầu) làm sai số; thu nhập tăng ~{format_amount(a[2])} / dự tính ~{format_amount(a[3])}")
        self.log("info", f"  Tổng lượt {ps}: đã nâng {tot_n} / dự tính {tot_d} cấp")
        self.plan_total += tot_d
        self.done_total += tot_n
        self._pass_stat = {}

    def _visit(self, pg: Page, work: Dict[str, int], cutoff: Dict[str, float]) -> Page:
        for r in list(pg.rows):
            k = f"{self.pos}#{r.idx}"
            st = self.rows.get(k)
            if st is None or st.dead:
                continue
            n = work.get(k, 0)
            if n <= 0:
                continue
            if st.gain is None:
                pg = self._press_row(pg, st, 1, None)           # lần đầu của hàng: nâng 1 cấp + đọc mức tăng (cố định cho hàng này, chỉ đo 1 lần)
                if n > 1 and st.gain is not None and not st.dead:
                    pg = self._press_batch(pg, st, n - 1)
            else:
                pg = self._press_batch(pg, st, n)               # đã biết mức tăng: bấm liên tiếp (x10 nếu nhiều), KHÔNG đọc banner
        return pg

    def _press_batch(self, pg: Page, st: RowState, n: int) -> Page:
        """Nâng n cấp 1 hàng đã biết mức tăng: bấm liên tiếp (tích x10 khi n >= x10_min), không đọc banner, rồi đọc lại giá + số dư MỘT lần để kiểm tra."""
        r = pg.row(st.idx)
        if r is None or not r.active or r.cost is None or n <= 0:
            return pg
        bal = pg.balance if pg.balance is not None else self.balances.get(st.ticket)
        g = self._growth_of(st)
        if bal is not None:
            n = self._levels_within(r.cost, g, bal - self._reserve_of(st.ticket), n)       # không bấm quá số vé còn lại SAU KHI chừa dự phòng
        if n <= 0:
            return pg
        k10, k1 = self._split10(n)
        c0, b0 = r.cost, bal
        many = getattr(self.ui, "press_many", None)
        if many is not None:
            new_pg = many(pg, st.idx, k10, k1)
        else:                                                                # giao diện cũ: bấm lẻ từng cấp
            new_pg = pg
            for _ in range(n):
                new_pg, _g = self.ui.press(new_pg, st.idx)
                if new_pg is None:
                    break
        if getattr(self.ui, "x10_dirty", False):
            raise _Stop("không chắc đã bỏ tích 'Nâng cấp x10' - hãy kiểm tra/bỏ tích bằng tay rồi chạy lại")
        if new_pg is None or not new_pg.ok:
            st.dead = True
            self.log("warn", f"Nâng cấp tối ưu: mất cửa sổ sau khi nâng {st.name}")
            return pg
        nr = new_pg.row(st.idx)
        c1 = nr.cost if nr is not None else None
        b1 = new_pg.balance
        spent = (b0 - b1) if (b0 is not None and b1 is not None) else None
        done, g_new = n, None
        if c1 and c0 and c1 > c0:
            gg = (c1 / c0) ** (1.0 / n)
            if 1.0005 <= gg <= 1.5 and (spent is None or (spent > 0 and abs(self._cost_sum(c0, gg, n) / spent - 1.0) < 0.06)):
                g_new = gg                                                   # giá + vé tốn khớp nhau -> đã nâng đủ n cấp, và biết hệ số giá chính xác hơn
        if g_new is None:                                                    # không khớp: chỉ nâng được 1 phần (thiếu vé / bấm hụt) hoặc không ăn
            if spent is not None and spent > 0:
                done = self._levels_within(c0, g, spent * 1.02, n)
            elif c1 is not None and c1 != c0:
                done = max(1, min(n, int(round(math.log(max(c1, 1.0) / c0) / math.log(max(g, 1.0001))))))
            else:
                done = 0
        if g_new is not None and n >= 5 and n >= st.growth_L:
            st.growth, st.growth_precise, st.growth_L = g_new, True, n
        self._absorb(new_pg, st.pos)
        if nr is not None:
            st.cost, st.active, st.affordable = nr.cost, nr.active, nr.affordable
        inc = done * st.gain if st.gain else 0.0
        st.presses += done
        self.presses += done
        st.gain_sum += inc
        self.gain_total += inc
        ps_ = self._pass_stat.get(st.key)
        if ps_ is not None:
            ps_["done"] += done
            ps_["spent"] += spent if (spent and spent > 0) else 0.0
            ps_["gain"] += inc
        if done == 0:
            st.batch_fail += 1
            if st.batch_fail >= 2:
                st.dead = True
        else:
            st.batch_fail = 0
        self._csv(st, "x10" if k10 else "batch", done, c0, c1, b0, b1, st.gain)
        self._save_state()
        e = st.eff()
        self.log("info", f"  {st.name}: nâng {done}/{n} cấp ({k10}×x10 + {k1}×1) | giá {format_amount(c0)} -> {format_amount(c1)} | "
                         f"vé {_tk(st.ticket)} {format_amount(b0)} -> {format_amount(b1)} (tốn {format_amount(spent)}) | "
                         f"thu nhập tăng ~{format_amount(inc)} ({format_amount(st.gain)}/cấp, cố định) | hiệu quả lần kế {'?' if e is None else f'{e:.3g}'}/vé"
                         + ("" if done == n else f" | CHỈ NÂNG ĐƯỢC {done}/{n}" + (" -> bỏ hàng" if st.dead else "")))
        return new_pg

    def _press_row(self, pg: Page, st: RowState, n: int, cut: Optional[float]) -> Page:
        done_n = 0
        for _ in range(n):
            self._check()
            r = pg.row(st.idx)
            if r is None or not r.active or r.cost is None or r.affordable is False:
                break
            bal = pg.balance if pg.balance is not None else self.balances.get(st.ticket)
            if bal is not None and r.cost > bal - self._reserve_of(st.ticket):
                break
            old_cost, old_bal = r.cost, bal
            new_pg, gain = self.ui.press(pg, st.idx)
            if new_pg is None or not new_pg.ok:
                st.dead = True
                self.log("warn", f"Nâng cấp tối ưu: mất cửa sổ sau khi bấm {st.name}")
                break
            nr = new_pg.row(st.idx)
            done = (nr is not None and nr.cost is not None and nr.cost != old_cost) or \
                   (new_pg.balance is not None and old_bal is not None and new_pg.balance < old_bal)
            if not done:
                st.gain_fail += 1
                if st.gain_fail >= 2:
                    st.dead = True
                    self.log("warn", f"Nâng cấp tối ưu: bấm {st.name} 2 lần không ăn -> bỏ hàng này")
                break
            self.presses += 1
            st.presses += 1
            done_n += 1
            if nr is not None and nr.cost is not None and old_cost:
                g = nr.cost / old_cost
                if 1.0 <= g <= 2.0 and st.growth_L < 5:
                    st.growth, st.growth_precise, st.growth_L = g, old_cost < 1e6, 1     # 1 cấp ở giá >= 1tr (3 chữ số) chưa chính xác
            if gain is not None:
                st.gain, st.gain_fail = gain, 0
                st.gain_sum += gain
                self.gain_total += gain
            else:
                st.gain_fail += 1
                if st.gain_fail >= self.gain_fail_limit and st.gain is None:      # đã có mức tăng cũ (đo/lưu trước đó) thì chịu được vài lần đọc hỏng
                    st.dead = True
                    self.log("warn", f"Nâng cấp tối ưu: không đọc được mức tăng của {st.name} {st.gain_fail} lần -> bỏ (xem debug_upgrade/gain_fail_*.png)")
            self._absorb(new_pg, st.pos)
            pg = new_pg
            nr = pg.row(st.idx)
            if nr is not None:
                st.cost, st.active, st.affordable = nr.cost, nr.active, nr.affordable
            this_eff = (gain / old_cost) if (gain is not None and old_cost) else None
            self.log("info", f"  {st.name}: nâng {done_n}/{n} (tổng {st.presses} lần) | giá {format_amount(old_cost)} -> {format_amount(st.cost)} | "
                             f"tăng {format_amount(gain)} | hiệu quả lần này {'?' if this_eff is None else f'{this_eff:.3g}'}/vé, lần kế "
                             f"{'?' if st.eff() is None else f'{st.eff():.3g}'}/vé | vé {_tk(st.ticket)} còn {format_amount(self.balances.get(st.ticket))} | "
                             f"{self._eff_text(st.ticket)}")
            self._csv(st, "probe", 1, old_cost, st.cost, old_bal, self.balances.get(st.ticket), gain)
            self._save_state()
            if st.dead:
                break
            if cut is not None and st.eff() is not None and st.eff() < cut * 0.999:
                self.log("info", f"  {st.name}: hiệu quả lần kế {st.eff():.3g}/vé đã tụt dưới ngưỡng biên {cut:.3g}/vé -> nhường hàng khác")
                break                           # hiệu quả đo được đã tụt dưới ngưỡng cân bằng -> nhường hàng khác
        return pg


# ----------------------------------------------------------------------------
# 6) UI thật qua ADB
# ----------------------------------------------------------------------------
class AdbUI:
    def __init__(self, adb, log=None, sleep=time.sleep, settle_wait=0.2, gain_wait=4.0, arrow_dx=None, arrow_dy=None,
                 debug=False, scale=None, gain_poll=0.3, nav_gap=0.15, burst=4, press_gap=0.2, skills=2):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.sleep = sleep
        self.settle_wait, self.gain_wait = float(settle_wait), float(gain_wait)
        self.gain_poll = max(0.15, float(gain_poll))   # chu kỳ chụp khi chờ số '+tăng' ngừng chạy lên
        self.nav_gap = max(0.05, float(nav_gap))       # khoảng cách giữa 2 lần bấm mũi tên khi bấm liên tục (người dùng xác nhận 0.1-0.2s là được)
        self.burst = max(1, int(burst))                # số lần bấm liên tục giữa 2 lần kiểm tra 'còn mũi tên không'
        self.press_gap = max(0.05, float(press_gap))   # khoảng cách giữa 2 lần bấm 'Tăng cấp' khi bấm LIÊN TIẾP không đọc mức tăng (`press_many`)
        self._layout: Optional[Layout] = None          # kiểu màn hình đã nhận (chốt sau trang đọc được đầu tiên)
        self.skills = max(1, int(skills))              # số biểu tượng kỹ năng (ô 1, 2...) dùng ở kiểu có chọn kỹ năng (Nuôi dưỡng Nghệ Sĩ)
        self.x10_ok = True                             # còn dùng được ô 'Nâng cấp x10' (tự tắt nếu bật không được)
        self.x10_dirty = False                         # nghi ô x10 đang BẬT mà không bỏ tích được -> bot phải dừng
        self.arrow_r = (float(arrow_dx) if arrow_dx is not None else ARROW_R[0], float(arrow_dy) if arrow_dy is not None else ARROW_R[1])
        self.debug, self.scale = bool(debug), scale
        self._shots = 0
        self._dbg_dir = os.path.join("debug_upgrade", _dev_tag(adb))   # ảnh debug theo từng giả lập (chạy nhiều giả lập cùng lúc không lẫn ảnh)
        self._plateau_t = 0.0                       # thời điểm lần đọc mức tăng gần nhất (banner còn hiện ~1-2s sau đó)
        self._last_gain: Optional[float] = None     # mức tăng đọc được ở lần nâng trước (để biết dòng đầu cửa sổ đã cập nhật chưa)
        self._auto_scale: Optional[float] = None   # tỉ lệ giao diện đo từ 2 nút ở lần đọc đầu thành công (scale không đặt tay) - giữ cố định cho các lần sau

    def _frame(self):
        for _ in range(3):
            fr = self.adb.screencap_fast()
            if fr is not None:
                return fr
            self.sleep(0.3)
        return None

    def _save(self, frame, name):
        try:
            os.makedirs(self._dbg_dir, exist_ok=True)
            self._shots += 1
            if self._shots > 200:
                return
            cv2.imencode(".png", frame)[1].tofile(os.path.join(self._dbg_dir, f"{name}.png"))
        except Exception:
            pass

    @staticmethod
    def _still(a, b) -> bool:
        """2 khung chụp liên tiếp gần như giống nhau (hết hoạt ảnh/chuyển mục)?"""
        if a is None or b is None or a.shape != b.shape:
            return False
        sa = cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (96, 160), interpolation=cv2.INTER_AREA).astype(np.int16)
        sb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (96, 160), interpolation=cv2.INTER_AREA).astype(np.int16)
        return float(np.abs(sa - sb).mean()) < 1.5

    def page(self) -> Optional[Page]:
        """Chờ khung ĐỨNG YÊN (2 lần chụp giống nhau) rồi đọc 1 lần."""
        prev = None
        fr = None
        for _ in range(6):
            fr = self._frame()
            if fr is None:
                return None
            if self._still(prev, fr):
                break
            prev = fr
            self.sleep(self.settle_wait)
        pg = self._read(fr)
        if self.debug or not pg.ok:
            self._save(fr, f"page_{'ok' if pg.ok else 'unclear'}_{int(time.time() * 1000) % 10 ** 9}")
        if pg.ok and pg.layout is not None and pg.layout.slots:
            pg = self._merge_slots(pg)                              # kiểu có chọn kỹ năng: bấm lần lượt từng biểu tượng để đọc đủ ô 1, 2...
        return pg

    # ---- kiểu có chọn kỹ năng (Nuôi dưỡng Nghệ Sĩ): mỗi biểu tượng = 1 'hàng'; chỉ hiện giá/nút của biểu tượng đang chọn
    def _n_slots(self, lay: Layout) -> int:
        return min(len(lay.slots), self.skills)

    def _select_slot(self, pg: Page, idx: int) -> bool:
        """Chọn biểu tượng kỹ năng idx (bấm nếu chưa chọn) và kiểm tra vòng sáng đã chuyển sang nó."""
        lay = pg.layout
        if lay is None or not lay.slots or idx >= len(lay.slots):
            return True
        s, n = pg.scale, self._n_slots(lay)
        for attempt in range(2):
            fr = self._frame()
            if fr is None:
                return False
            if _selected_slot(fr, pg.top, s, lay, n) == idx:
                return True
            sx, sy = lay.slots[idx]
            self.adb.tap_px(pg.top[0] + sx * s, pg.top[1] + sy * s)
            self.sleep(0.35)
        fr = self._frame()
        return fr is not None and _selected_slot(fr, pg.top, s, lay, n) == idx

    def _merge_slots(self, pg: Page) -> Page:
        """Đọc đủ các hàng (kỹ năng) của trang: hàng đang chọn đã có; bấm chọn từng biểu tượng còn lại rồi đọc. Cuối cùng chọn lại biểu tượng 1."""
        lay = pg.layout
        rows = {r.idx: r for r in pg.rows}
        for idx in range(self._n_slots(lay)):
            if idx in rows:
                continue
            if not self._select_slot(pg, idx):
                continue                                            # biểu tượng bị khoá / không chọn được -> không có hàng này
            self.sleep(0.15)
            fr = self._frame()
            if fr is None:
                continue
            p = self._read(fr)
            if p.ok and p.rows and p.rows[0].idx == idx:
                rows[idx] = p.rows[0]
        self._select_slot(pg, 0)
        pg.rows = [rows[i] for i in sorted(rows)]
        for r in pg.rows:                                           # cùng 1 số dư -> đủ vé khi số dư >= giá
            if pg.balance is not None and r.cost is not None:
                r.affordable = pg.balance >= r.cost
        return pg

    def _carry_rows(self, old: Page, new: Page) -> Page:
        """Sau khi bấm: trang mới chỉ có hàng đang chọn -> ghép lại các hàng khác của trang cũ (giá không đổi), cập nhật 'đủ vé' theo số dư mới."""
        if old is None or new is None or old.layout is None or not old.layout.slots:
            return new
        have = {r.idx for r in new.rows}
        for r in old.rows:
            if r.idx not in have:
                new.rows.append(r)
        new.rows.sort(key=lambda r: r.idx)
        for r in new.rows:
            if new.balance is not None and r.cost is not None:
                r.affordable = new.balance >= r.cost
        return new

    def _read(self, fr) -> Page:
        """read_page với tỉ lệ: đặt tay (`scale`) > tỉ lệ đã đo ổn định > tự đo từ nút. Chỉ chốt tỉ lệ khi thấy đủ 2 hàng nút."""
        sc = self.scale or self._auto_scale
        pg = read_page(fr, sc, layout=self._layout)
        if pg.rows and any(r.active and r.cost is None for r in pg.rows):
            pg2 = read_page(fr, sc or pg.scale, thorough=True, layout=pg.layout)      # nút bấm được mà không đọc được giá -> đọc kỹ hơn 1 lần
            if pg2.ok:
                pg = pg2
        if pg.ok and self._layout is None:
            self._layout = pg.layout                                # chốt kiểu màn hình cho cả lần chạy
            self.log("info", f"Nâng cấp tối ưu: nhận diện kiểu màn hình '{pg.layout.label}' ({pg.layout.id})")
        if not sc and pg.ok and len(pg.rows) >= 2 and pg.layout.auto_scale:
            self._auto_scale = pg.scale
        return pg

    def _banner(self, fr, pg: Page):
        """Hộp (tuyệt đối) của dòng '<tổng> +<tăng>' nếu banner 'Tăng Thu Nhập' đang hiện, không thì None. Kiểu Ruộng Đồng: so với nút (đã chuẩn); kiểu khác / không thấy: tìm bằng màu."""
        lay = pg.layout or LAYOUT_A
        if lay.banner_box is not None and _banner_visible(fr, pg.top, pg.scale):
            x1, y1, x2, y2 = GAIN_BOX
            return (int(pg.top[0] + x1 * pg.scale), int(pg.top[1] + y1 * pg.scale), int(pg.top[0] + x2 * pg.scale), int(pg.top[1] + y2 * pg.scale))
        return _banner_fixed(fr) or _find_banner(fr)

    def _ocr_gain(self, fr, gb) -> Optional[float]:
        """Đọc '+tăng' từ 1 khung hình (gb = hộp dòng '<tổng> +<tăng>'): nhanh (<=4 lần thử, ~0.2s) trước, không ra mới đọc kỹ (~0.9s)."""
        seg = _gain_segment(_crop_abs(fr, gb))
        if seg is None:
            return None
        a = read_amount(seg, True, False)
        if a.value is None:
            a = read_amount(seg, True, True)
        return a.value

    def press(self, pg: Page, idx: int):
        """Bấm 'Tăng cấp' hàng idx; đọc mức tăng ở banner 'Tăng Thu Nhập'; trả (trang mới, mức tăng | None).
        Bản 5: số '+tăng' CHẠY LÊN ~1.3s rồi đứng yên ~1s (đo trên video: +21k ... +151.7k). Bản 2-4 OCR kỹ (~0.9s) MỖI lần chụp để chờ 2 lần đọc bằng nhau -> chỉ kịp đọc
        1 lần trong đời banner (~2s) nên KHÔNG BAO GIỜ nhận được số ('tăng ?', 4s chờ phí mỗi lần bấm). Nay: chụp liên tục + so chữ ký vùng banner (rẻ, không OCR); 2 lần chụp
        liền không đổi (độ lệch < GAIN_STILL_MAD) = số đã đứng yên -> OCR đúng 1 lần ở khung đó, rồi đọc luôn trang từ khung đó (banner chỉ đè tiêu đề, không che giá/nút)
        nên KHÔNG cần đợi banner tắt. Nếu banner của lần bấm trước còn hiện lúc bấm thì phải thấy số đổi (đếm lại từ +0) trước khi nhận."""
        r = pg.row(idx)
        if pg.layout is not None and pg.layout.slots:
            self._select_slot(pg, idx)                               # kiểu có chọn kỹ năng: chọn đúng biểu tượng trước khi bấm
        need_change = (time.time() - self._plateau_t) < 2.5      # banner lần bấm trước có thể còn hiện
        self.adb.tap_px(r.x + r.w / 2, r.y + r.h / 2)
        t0 = time.time()
        self.sleep(0.15)
        gain, plat, last_vis, seen = None, None, None, False
        prev, stable, changed, ocr_fail = None, 0, not need_change, 0
        fr = None
        while time.time() - t0 < self.gain_wait:
            fr = self._frame()
            if fr is None:
                break
            gb = self._banner(fr, pg)
            if gb is not None:
                seen, last_vis = True, (fr, gb)
                sg = _gain_sig_box(fr, gb)
                if prev is not None:
                    if _sig_diff(prev, sg) >= GAIN_STILL_MAD:
                        changed, stable = True, 0
                    else:
                        stable += 1
                prev = sg
                if stable >= 1 and changed:
                    g = self._ocr_gain(fr, gb)
                    if g is not None:
                        fr2 = self._frame()                     # kiểm lại: nếu số còn đang đổi thì vừa đọc phải số dở dang
                        gb2 = self._banner(fr2, pg) if fr2 is not None else None
                        if gb2 is not None and _sig_diff(sg, _gain_sig_box(fr2, gb2)) >= GAIN_STILL_MAD:
                            prev, stable, fr = _gain_sig_box(fr2, gb2), 0, fr2
                            continue
                        gain, plat = g, fr
                        break
                    ocr_fail += 1
                    stable = 0
                    if ocr_fail >= 3:
                        break
            else:
                prev = None
                if seen:
                    break                                       # banner đã tắt mà chưa đọc được
            self.sleep(0.03)
        why = ""
        if gain is None and last_vis is not None:
            g = self._ocr_gain(last_vis[0], last_vis[1])        # đường lùi: số có thể chưa đứng yên, nhưng vẫn hơn không có
            if g is not None:
                gain, plat = g, last_vis[0]
                why = "chưa chắc số đã đứng yên"
        if fr is None and plat is None:
            return None, None
        if gain is None:
            self._save(last_vis[0] if last_vis is not None else fr, f"gain_fail_{int(time.time() * 1000) % 10 ** 9}")
            self.log("warn", "Nâng cấp tối ưu: không đọc được mức tăng - " + (
                "THẤY banner nhưng OCR không ra số (xem ảnh debug_upgrade/gain_fail_*.png)" if seen else
                f"KHÔNG thấy banner 'Tăng Thu Nhập' sau {self.gain_wait:g}s (bấm không ăn? banner hiện chỗ khác?)"))
        elif why:
            self.log("warn", f"Nâng cấp tối ưu: mức tăng {format_amount(gain)} {why}")
        if plat is not None:
            self._plateau_t = time.time()
            npg = self._read(plat)                              # banner không che giá/nút -> đọc luôn trang từ khung có banner
            if npg.ok:
                return self._carry_rows(pg, npg), gain
        # không có banner / đọc trang lỗi: đợi hết hoạt ảnh rồi đọc
        prev = fr if plat is None else plat
        for _ in range(10):
            self.sleep(0.2)
            fr2 = self._frame()
            if fr2 is None:
                break
            ok = self._still(prev, fr2)
            prev = fr2
            if ok:
                break
        return self._carry_rows(pg, self._read(prev)), gain

    # ---- bấm liên tiếp (không đọc mức tăng) + ô 'Nâng cấp x10'
    def _tap_x10(self, r, s, lay=None):
        lay = lay or self._layout or LAYOUT_A
        self.adb.tap_px(r.x + lay.x10_tap[0] * s, r.y + lay.x10_tap[1] * s)

    def _x10_fail(self, fr, why):
        self.x10_ok = False
        self.log("warn", f"Nâng cấp tối ưu: không dùng được ô 'Nâng cấp x10' ({why}) -> bấm lẻ từng cấp")
        if fr is not None:
            self._save(fr, f"x10_fail_{int(time.time() * 1000) % 10 ** 9}")

    def _x10_on(self, pg: Page, r):
        """Bật ô x10 của hàng r. Trả chữ ký ô tích lúc CHƯA bật (để kiểm tra bỏ tích về sau) hoặc None nếu không bật được (khi đó tắt x10 cho cả lần chạy)."""
        if not self.x10_ok:
            return None
        s, btn = pg.scale, (r.x, r.y, r.w, r.h)
        fr = self._frame()
        if fr is None:
            return None
        lay = pg.layout or LAYOUT_A
        if _x10_dark(fr, btn, s, lay) < 0.8:
            self._x10_fail(fr, "ô x10 không ở trạng thái bỏ tích phẳng - đang tích sẵn? hãy bỏ tích thủ công")
            return None
        ref = _x10_sig(fr, btn, s, lay)
        self._tap_x10(r, s, lay)
        self.sleep(0.3)
        fr2 = self._frame()
        if fr2 is None or _sig_diff(ref, _x10_sig(fr2, btn, s, lay)) < 8:
            self._x10_fail(fr2 if fr2 is not None else fr, "bấm ô x10 mà hình ô tích không đổi")
            return None
        return ref

    def _x10_off(self, pg: Page, r, ref) -> bool:
        """Bỏ tích x10 và kiểm tra ô tích đã về đúng hình lúc chưa bật. Không chắc đã tắt -> x10_dirty (bot dừng, tránh bấm lẻ mà thành x10)."""
        s, btn = pg.scale, (r.x, r.y, r.w, r.h)
        lay = pg.layout or LAYOUT_A
        for _ in range(2):
            self._tap_x10(r, s, lay)
            for _ in range(2):
                self.sleep(0.3)
                fr = self._frame()
                if fr is not None and _sig_diff(ref, _x10_sig(fr, btn, s, lay)) < 5:
                    return True
        self.x10_dirty = True
        self.log("error", "Nâng cấp tối ưu: KHÔNG chắc đã bỏ tích 'Nâng cấp x10' - hãy kiểm tra bằng mắt")
        return False

    def press_many(self, pg: Page, idx: int, k10: int = 0, k1: int = 0) -> Optional[Page]:
        """Bấm 'Tăng cấp' hàng idx LIÊN TIẾP (cách nhau `press_gap`s), KHÔNG đọc mức tăng (mức tăng mỗi hàng cố định, đã đo ở lần nâng thử đầu).
        k10 lần bấm khi đã TÍCH 'Nâng cấp x10' (mỗi lần +10 cấp) rồi bỏ tích, sau đó k1 lần bấm lẻ. Không bật được x10 thì bấm lẻ hết (k1 += 10*k10).
        Trả trang đã đọc lại (giá + số dư mới) hoặc None nếu mất khung hình."""
        r = pg.row(idx)
        if r is None:
            return None
        cx, cy = r.x + r.w / 2, r.y + r.h / 2
        if pg.layout is not None and pg.layout.slots:
            self._select_slot(pg, idx)                               # kiểu có chọn kỹ năng: chọn đúng biểu tượng trước khi bấm
        if k10 > 0:
            ref = self._x10_on(pg, r)
            if ref is None:
                k1, k10 = k1 + 10 * k10, 0
            else:
                for _ in range(k10):
                    self.adb.tap_px(cx, cy)
                    self.sleep(self.press_gap)
                self.sleep(0.2)
                if not self._x10_off(pg, r, ref):
                    return self.page()          # nghi x10 còn bật: KHÔNG bấm lẻ nữa (sẽ thành x10), bot sẽ dừng
        for _ in range(k1):
            self.adb.tap_px(cx, cy)
            self.sleep(self.press_gap)
        self._plateau_t = time.time()
        self.sleep(0.35)
        fr = self._frame()
        if fr is None:
            return None
        npg = self._read(fr)                    # banner chỉ đè tiêu đề, giá/số dư đã cập nhật ngay -> đọc luôn, hỏng mới chờ đứng yên
        if not npg.ok or any(rr.active and rr.cost is None for rr in npg.rows):
            npg = self.page() or npg
        return self._carry_rows(pg, npg)

    def _arrow(self, pg: Page, step: int):
        lay = pg.layout or LAYOUT_A
        if lay.id != LAYOUT_A.id:
            return lay.arrow_r if step > 0 else lay.arrow_l       # kiểu mới: toạ độ đo riêng cho từng kiểu
        ax, ay = self.arrow_r if step > 0 else (-159.0 - self.arrow_r[0], self.arrow_r[1])
        return ax, ay

    def _tap_arrow(self, pg: Page, step: int):
        ax, ay = self._arrow(pg, step)
        self.adb.tap_px(pg.top[0] + ax * pg.scale, pg.top[1] + ay * pg.scale)

    def _key_at(self, fr, pg: Page) -> str:
        return _page_key(fr, pg.top, pg.scale, pg.layout)

    def next_item(self, pg: Page, step: int = 1) -> Optional[Page]:
        """Bấm mũi tên vàng sang ô kế (step=+1 phải, -1 trái). Trả trang mới (đã đứng yên, khác ô cũ) hoặc None nếu không đổi được
        (ô đầu không có mũi tên trái, ô cuối không có mũi tên phải). Bản 3: đợi đổi ô bằng khoá RẺ (`_page_key`, không OCR), chỉ OCR 1 lần khi trang đã đứng yên;
        sau khi bấm chỉ chờ `nav_gap` (0.15s) rồi chụp liên tục - nhanh hơn nhiều so với bản cũ (OCR mỗi lần chụp)."""
        arrow = self._arrow(pg, step)
        for attempt in range(2):
            fr0 = self._frame()
            if fr0 is None:
                return None
            if not _arrow_visible(fr0, pg.top, pg.scale, step, arrow):
                self.sleep(0.25)
                fr0 = self._frame()
                if fr0 is None or not _arrow_visible(fr0, pg.top, pg.scale, step, arrow):
                    return None                 # không có mũi tên = hết danh sách ở phía đó
            self._tap_arrow(pg, step)
            t0 = time.time()
            self.sleep(self.nav_gap)
            prev = None
            while time.time() - t0 < 2.5:
                fr = self._frame()
                if fr is None:
                    return None
                if not _same_item(self._key_at(fr, pg), pg.key):
                    if prev is not None and self._still(prev, fr):      # đã đổi ô + đã hết trượt -> đọc 1 lần
                        npg = self._read(fr)
                        if npg.ok and not _same_item(npg.key, pg.key):
                            if npg.layout is not None and npg.layout.slots:
                                npg = self._merge_slots(npg)        # kiểu có chọn kỹ năng: đọc đủ các hàng (kỹ năng) của ô mới
                            return npg
                    prev = fr
                else:
                    prev = None
                self.sleep(0.05)
        return None

    def go_edge(self, pg: Page, step: int = -1, max_taps: int = 150):
        """Bấm LIÊN TỤC mũi tên (mỗi `nav_gap`s, `burst` lần rồi kiểm tra) tới khi mũi tên biến mất = tới ô đầu (step<0) / ô cuối (step>0).
        Không đọc từng ô nên rất nhanh. Trả (trang tại ô đó đã đọc, số lần bấm) hoặc (None, taps) nếu mất khung hình."""
        arrow = self._arrow(pg, step)
        taps, absent = 0, 0
        while taps < max_taps:
            fr = self._frame()
            if fr is None:
                return None, taps
            if not _arrow_visible(fr, pg.top, pg.scale, step, arrow):
                absent += 1
                if absent >= 2:
                    break
                self.sleep(0.2)
                continue
            absent = 0
            for _ in range(self.burst):
                self._tap_arrow(pg, step)
                taps += 1
                self.sleep(self.nav_gap)
            self.sleep(0.2)
        return self.page(), taps

    def jump(self, pg: Page, step: int, n: int) -> Optional[Page]:
        """Bấm n lần liên tục mũi tên (cách nhau `nav_gap`s) rồi đọc trang đứng yên. Người gọi tự kiểm tra có đúng ô cần tới không."""
        for _ in range(max(0, int(n))):
            self._tap_arrow(pg, step)
            self.sleep(self.nav_gap)
        self.sleep(0.3)
        return self.page()


def _state_path(adb, step) -> Optional[str]:
    """File lưu kết quả đo: mặc định data/upgrade_state_<thiết bị>[__<tài khoản>].json - MỖI GIẢ LẬP (và mỗi tài khoản nếu biết) 1 file riêng nên chạy nhiều giả lập
    cùng lúc không đụng nhau. step['state_file'] = "" thì không lưu."""
    p = step.get("state_file")
    if p == "":
        return None
    if p:
        return str(p)
    name = f"upgrade_state_{_dev_tag(adb, step)}__{{tab}}.json"       # {tab} = kiểu màn hình + số thứ tự danh sách (UpgradeBot._tab_pick chọn khi quét)
    try:
        import paths
        return paths.resolve_data_path(name)
    except Exception:
        return os.path.join("data", name)


def _data_path(adb, step) -> Optional[str]:
    """CSV thu thập dữ liệu (cấp, giá, vé, mức tăng từng lần nâng): data/upgrade_data_<thiết bị>[__<tài khoản>].csv. step['data_file'] = "" thì không ghi."""
    p = step.get("data_file")
    if p == "":
        return None
    if p:
        return str(p)
    name = f"upgrade_data_{_dev_tag(adb, step)}__{{tab}}.csv"
    try:
        import paths
        return paths.resolve_data_path(name)
    except Exception:
        return os.path.join("data", name)


def run_auto_upgrade_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_upgrade` (field xem mục 4 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    ui = AdbUI(adb, log=log, settle_wait=step.get("settle_wait", 0.2), nav_gap=step.get("nav_gap", 0.15), burst=step.get("burst", 4), press_gap=step.get("press_gap", 0.2), skills=step.get("skills", 2), gain_wait=step.get("gain_wait", 4.0), scale=step.get("scale"), gain_poll=step.get("gain_poll", 0.3),
               arrow_dx=step.get("arrow_dx"), arrow_dy=step.get("arrow_dy"), debug=bool(step.get("debug", False)))
    bot = UpgradeBot(ui, log=log, should_stop=should_stop, test=step.get("test", True), max_items=step.get("max_items", 80),
                     max_passes=step.get("max_passes", 30), min_eff=step.get("min_eff", 0.0), reserve=step.get("reserve", 0.0),
                     max_seconds=step.get("max_seconds", 0), cost_growth=step.get("cost_growth"), reserve_pct=step.get("reserve_pct", RESERVE_PCT),
                     gain_fail_limit=step.get("gain_fail_limit", 2), rewind=bool(step.get("rewind", True)),
                     end_locked=step.get("end_locked", 3), probe_on_scan=bool(step.get("probe_on_scan", True)),
                     state_file=_state_path(adb, step), resume=bool(step.get("resume", True)), max_age_hours=step.get("max_age_hours", 0),
                     use_x10=bool(step.get("use_x10", True)), x10_min=step.get("x10_min", 10), data_file=_data_path(adb, step))
    return bot.run()


# ----------------------------------------------------------------------------
# 7) Tự kiểm tra
# ----------------------------------------------------------------------------
def _imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def _selftest():
    """Kiểm tra parse số, bộ tối ưu so với vét cạn, và vòng chạy với game giả (không cần ADB/ảnh)."""
    import itertools
    import tempfile
    assert parse_amount("630.8k") == 630800 and parse_amount("1.3tr") == 1.3e6 and parse_amount("6.55tỷ") == 6.55e9
    assert parse_amount("+461.1k") == 461100 and parse_amount("650000") == 650000 and parse_amount("abc") is None
    assert format_amount(630800) == "630.8k" and format_amount(1.3e6) == "1.3tr" and format_amount(6.55e9) == "6.55tỷ"

    # (a) tham lam == vét cạn khi hiệu quả giảm dần
    import random
    rnd = random.Random(7)
    for trial in range(200):
        rows = [PlanRow(f"r{i}", "blue", rnd.uniform(50, 500), rnd.uniform(10, 400), rnd.uniform(1.0, 1.3)) for i in range(3)]
        budget = rnd.uniform(500, 3000)
        counts, _ = plan_upgrades(rows, {"blue": budget})
        got = sum(counts.get(r.key, 0) * r.gain for r in rows)
        best = 0.0
        for ns in itertools.product(range(0, 25), repeat=3):
            cost = 0.0
            ok = True
            for r, n in zip(rows, ns):
                for j in range(n):
                    cost += r.cost * r.growth ** j
            if cost <= budget:
                best = max(best, sum(n * r.gain for r, n in zip(rows, ns)))
        assert got >= best * 0.999 - 1e-9 or got >= best - 0.5 * max(r.gain for r in rows), (trial, got, best)
    # (b) mỗi loại vé 1 ngân sách riêng
    rows = [PlanRow("a", "blue", 100, 100, 1.0), PlanRow("b", "pink", 100, 1, 1.0)]
    c, _ = plan_upgrades(rows, {"blue": 250, "pink": 250})
    assert c == {"a": 2, "b": 2}, c
    # (c) vòng chạy với game giả (bắt đầu GIỮA danh sách -> phải lùi về ô đầu; cuối có 3 ô chưa mở)
    games = _FakeGame(start=2)
    log = []
    bot = UpgradeBot(games, log=lambda l, m: log.append(m), test=False, max_passes=20, now=lambda: 0.0)
    assert bot.run()
    assert bot.n_items == 4 and bot.n_total == 7, (bot.n_items, bot.n_total)       # 4 ô nâng được + 3 ô chưa mở mới dừng
    text = "\n".join(log)
    assert "QUÉT XONG" in text and "thấp nhất" in text and "cao nhất" in text and "TỔNG KẾT" in text and "Ô1-trên" in text
    assert "liên tục" in text and "về ô đầu" in text, text[:400]
    spent = games.spent
    assert games.presses > 10, games.presses
    start_bal = _FakeGame().balance
    for tk in games.balance:
        assert games.balance[tk] >= 0.05 * start_bal[tk] - 1e-6, (tk, games.balance[tk])      # luôn chừa lại >= 5% vé lúc bắt đầu
    assert "ĐÃ NÂNG / DỰ TÍNH" in "\n".join(log) and "chừa lại" in "\n".join(log) and "Tổng lượt" in "\n".join(log)
    assert bot.done_total == bot.plan_total and bot.plan_total > 0, (bot.done_total, bot.plan_total)
    # tổng thu nhập tăng được phải gần bằng kế hoạch lý tưởng (biết trước mọi mức tăng ngay từ đầu), chỉ chênh phần nâng thử
    ideal = _FakeGame()
    ideal_rows = [PlanRow(k, g.ticket, g.cost, g.gain, g.growth) for k, g in ideal.rows.items()]
    ic, _ = plan_upgrades(ideal_rows, {tk: b * 0.95 for tk, b in ideal.balance.items()})        # chừa lại 5% vé làm sai số
    ideal_gain = sum(n * ideal.rows[k].gain for k, n in ic.items())
    got_gain = sum(g.n * g.gain for g in games.rows.values())
    assert got_gain >= 0.95 * ideal_gain, (got_gain, ideal_gain)
    # các hàng được nâng nhiều lần thì hiệu quả biên cuối phải cân bằng nhau (cùng loại vé)
    for tk in ("blue", "pink"):
        effs = [g.gain / g.cost for g in games.rows.values() if g.ticket == tk and g.n >= 2]
        if len(effs) >= 2:
            assert max(effs) / min(effs) < 2.5, (tk, effs)
    # (L) nhiều kiểu màn hình nâng cấp: tự nhận kiểu theo vị trí nút, đọc 'số dư/giá', tự nhận loại vé theo màu, banner theo màu, tách file theo màn hình
    def fake_frame(btns):
        fr_ = np.full((1280, 720, 3), (200, 235, 253), np.uint8)
        for x_, y_, w_, h_ in btns:
            fr_[y_:y_ + h_, x_:x_ + w_] = (60, 160, 60)
        return fr_
    assert detect_layout(fake_frame([(453, 786, 165, 42), (453, 940, 165, 42)])).id == "ruong"
    assert detect_layout(fake_frame([(480, 769, 165, 42), (480, 928, 165, 42)])).id == "nhatam"
    assert detect_layout(fake_frame([(504, 950, 111, 36)])).id == "nuoiduong"
    assert detect_layout(fake_frame([(100, 100, 165, 42)])) is None
    assert _parse_pair("17.99tr/45.15k") == (17.99e6, 45150.0) and _parse_pair("17.98tr105k") == (17.98e6, 105000.0)
    assert _parse_pair("212.7tr/1.32tr") == (212.7e6, 1.32e6) and _parse_pair("abc") is None
    for nm_, bgr_ in [("red", (30, 30, 200)), ("green", (60, 200, 60)), ("blue", (200, 110, 40)), ("purple", (170, 60, 130)), ("pink", (160, 60, 220)), ("white", (235, 235, 235))]:
        ic_ = np.full((30, 30, 3), bgr_, np.uint8)
        assert _hue_name(ic_) == nm_, (nm_, _hue_name(ic_))
    assert _tk("nuoiduong:purple") == "Nuôi dưỡng/tím" and _tk("blue") == "xanh dương" and _tk("nhatam:white") == "Nhà tắm/trắng"
    bn_ = np.full((1280, 720, 3), (200, 235, 253), np.uint8)
    assert _find_banner(bn_) is None
    bn_[132:250, 146:578] = (150, 170, 40)                          # BGR xanh ngọc (H~88)
    gb_ = _find_banner(bn_)
    assert gb_ is not None and abs(gb_[0] - 279) <= 3 and abs(gb_[1] - 194) <= 3 and abs(gb_[2] - 560) <= 3 and abs(gb_[3] - 231) <= 3, gb_
    # tách file lưu theo màn hình (khoá ô 1): cùng màn hình -> cùng id, màn hình khác -> id mới, file KIỂU CŨ được chuyển sang tên mới
    td_ = tempfile.mkdtemp()
    tm_ = os.path.join(td_, "upgrade_state_dev__{tab}.json")
    b_ = UpgradeBot(_FakeGame(), state_file=tm_, now=lambda: 0.0)
    b_.layout = LAYOUT_B
    k_a, k_b = "0" * 64 + "1" * (STRIP_W * STRIP_H), "1" * 64 + "9" * (STRIP_W * STRIP_H)
    assert b_._tab_pick(k_a) == "nhatam_1"
    json.dump({"keys": {"1": k_a}, "rows": {}}, open(tm_.replace("{tab}", "nhatam_1"), "w"))
    assert b_._tab_pick(k_a) == "nhatam_1" and b_._tab_pick(k_b) == "nhatam_2"
    b_.layout = LAYOUT_A
    json.dump({"keys": {"1": k_a}, "rows": {}}, open(os.path.join(td_, "upgrade_state_dev.json"), "w"))     # file kiểu cũ
    assert b_._tab_pick(k_a) == "ruong_1" and os.path.exists(tm_.replace("{tab}", "ruong_1")) and not os.path.exists(os.path.join(td_, "upgrade_state_dev.json"))
    # (S) biểu tượng kỹ năng (ô 1/2) + banner vị trí cố định + danh sách XOAY VÒNG
    def ring_frame(sel):
        fr_ = np.full((1280, 720, 3), (200, 235, 253), np.uint8)
        if sel is not None:
            sx_, sy_ = LAYOUT_C.slots[sel]
            cv2.circle(fr_, (504 + int(sx_), 950 + int(sy_)), 56, (40, 150, 240), 8)       # BGR cam vàng sáng
        return fr_
    assert _selected_slot(ring_frame(0), (504, 950), 1.0, LAYOUT_C, 2) == 0 and _selected_slot(ring_frame(1), (504, 950), 1.0, LAYOUT_C, 2) == 1
    assert _selected_slot(ring_frame(None), (504, 950), 1.0, LAYOUT_C, 2) is None
    bf_ = np.full((1280, 720, 3), (200, 235, 253), np.uint8)
    assert _banner_fixed(bf_) is None
    bf_[132:250, 146:578] = (150, 170, 40)
    assert _banner_fixed(bf_) == tuple(GAIN_ABS)
    gc_ = _FakeGame(start=1, n_locked=0, circular=True)                  # 4 ô nâng được, xoay vòng, đang đứng giữa danh sách
    logc_ = []
    bc_ = UpgradeBot(gc_, log=lambda l, m: logc_.append(m), state_file=None, max_passes=20, now=lambda: 0.0)
    assert bc_.run()
    assert bc_.n_total == 4 and "xoay vòng" in "\n".join(logc_) and "quay lại ô 1" in "\n".join(logc_), (bc_.n_total, logc_[:6])
    assert bc_.layout.id == "nuoiduong" and bc_.circular
    bc_.pos = 1
    assert bc_._plan_move(4) == (-1, 1) and bc_._plan_move(3) == (1, 2) or bc_._plan_move(3) == (-1, 2)        # vòng: 1 -> 4 đi lùi 1 bước
    assert bc_._dist(1, 4) == 1 and bc_._dist(2, 4) == 2
    for tk_ in gc_.balance:
        assert gc_.balance[tk_] >= 0.05 * _FakeGame().balance[tk_] - 1e-6
    assert bc_.presses > 10 and gc_.presses > 10
    # (c00) công thức: tổng vé nâng N cấp liên tiếp = P0*(r^N-1)/(r-1); hệ số nhân nhanh 10 cấp (ảnh người dùng gửi): r=1.012 -> 10.56, r=1.009 -> 10.41
    assert abs(UpgradeBot._cost_sum(1.0, 1.012, 10) - 10.56) < 0.01 and abs(UpgradeBot._cost_sum(1.0, 1.009, 10) - 10.41) < 0.01
    for c_, g_, b_ in [(100.0, 1.012, 5000.0), (37640.0, 1.012, 15e6), (829900.0, 1.009, 3e6), (50.0, 1.0, 333.0)]:
        k_ = UpgradeBot._levels_within(c_, g_, b_, 10 ** 6)
        assert UpgradeBot._cost_sum(c_, g_, k_) <= b_ < UpgradeBot._cost_sum(c_, g_, k_ + 1), (c_, g_, b_, k_)
    assert UpgradeBot._levels_within(100.0, 1.012, 5000.0, 7) == 7 and UpgradeBot._levels_within(100.0, 1.012, 50.0, 7) == 0
    # (c01) nhiều giả lập/tài khoản chạy cùng lúc: file lưu/CSV/ảnh debug riêng theo thiết bị(+tài khoản); chạy song song nhiều luồng không đụng nhau
    class _A:
        def __init__(self, d, acc=None):
            self.device_id, self.account_key = d, acc
    assert _dev_tag(_A("127.0.0.1:5555")) == "127.0.0.1_5555" and _dev_tag(_A("emulator-5554", "tk 1")) == "emulator-5554__tk_1"
    assert _dev_tag(_A("a"), {"account": "x"}) == "a__x" and _dev_tag(_A(None)) == "default"
    assert _state_path(_A("emu-1"), {}) != _state_path(_A("emu-2"), {}) and _state_path(_A("emu-1"), {"state_file": ""}) is None
    tmp2 = tempfile.mkdtemp()
    results = {}

    def worker(i):
        g_ = _FakeGame(start=i % 3)
        lg_ = []
        b_ = UpgradeBot(g_, log=lambda l, m: lg_.append(m), state_file=os.path.join(tmp2, f"s{i}.json"), data_file=os.path.join(tmp2, f"d{i}.csv"),
                        max_passes=20, now=lambda: 0.0)
        ok_ = b_.run()
        results[i] = (ok_, g_.presses, b_.presses, g_.balance["blue"], g_.balance["pink"])

    ths = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t_ in ths:
        t_.start()
    for t_ in ths:
        t_.join()
    assert len(results) == 6 and all(r[0] for r in results.values()), results
    assert len({r[1:] for r in results.values()}) == 1, results             # cùng kịch bản -> cùng kết quả dù chạy song song
    for i in range(6):
        d_ = json.load(open(os.path.join(tmp2, f"s{i}.json"), encoding="utf-8"))
        assert d_["rows"] and os.path.getsize(os.path.join(tmp2, f"d{i}.csv")) > 100
    # (c0) mức tăng chỉ đo 1 lần/hàng (nâng thử), các cấp sau bấm liên tiếp bằng press_many (có x10), hệ số giá được đo chính xác lại sau các lần nâng nhiều cấp
    assert games.singles == 8 and games.batch_calls > 0 and games.x10_calls > 0, (games.singles, games.batch_calls, games.x10_calls)
    for k, st in bot.rows.items():
        if st.pos > games.n_open:
            continue
        tg = games.rows[f"it{st.pos - 1}#{st.idx}"].growth
        if st.growth_L >= 5:
            assert abs(st.growth / tg - 1) < 1e-6, (k, st.growth, tg)
    assert "×x10" in text and "cố định" in text
    # (c1) nâng thử NGAY lúc quét + lưu kết quả; chạy lại thì dùng kết quả đã lưu, khỏi nâng thử
    tmpd = tempfile.mkdtemp()
    sf = os.path.join(tmpd, "state.json")
    marks = {}

    def mk(tag, g):
        def lg(l, m):
            if "QUÉT XONG" in m:
                marks[tag] = g.presses                      # số lần nâng đã xảy ra NGAY TRONG lúc quét
        return lg
    gA = _FakeGame(start=0)
    bA = UpgradeBot(gA, log=mk("A", gA), state_file=sf, max_passes=20, now=lambda: 0.0)
    assert bA.run() and marks["A"] == 8, marks                 # 8 hàng, mỗi hàng nâng thử 1 cấp ngay khi quét
    assert os.path.exists(sf) and bA.presses >= 8
    gB = _FakeGame(start=0)                                    # game mới (vé/giá lại như ban đầu), cùng danh sách ô
    bB = UpgradeBot(gB, log=mk("B", gB), state_file=sf, max_passes=20, now=lambda: 0.0)
    assert bB.run() and marks["B"] == 0 and bB.adopted == 8, (marks, bB.adopted)    # dùng lại kết quả: quét KHÔNG nâng thử
    assert bB.prev_presses == bA.presses
    gC = _FakeGame(start=0, salt="khac")                       # danh sách ô đã đổi -> bỏ kết quả cũ
    lgC = []
    bC = UpgradeBot(gC, log=lambda l, m: lgC.append(m), state_file=sf, max_passes=20, now=lambda: 0.0)
    assert bC.run() and bC.adopted == 0 and any("KHÁC ô đã lưu" in m for m in lgC)
    gD = _FakeGame(start=0)                                    # resume=False -> đo lại từ đầu
    bD = UpgradeBot(gD, log=mk("D", gD), state_file=sf, resume=False, max_passes=20, now=lambda: 0.0)
    assert bD.run() and marks["D"] == 8 and bD.adopted == 0
    # (c2) bấm liên tục bị nuốt 1 lần bấm -> bot phải tự xác định lại vị trí và vẫn chạy đúng
    g3 = _FakeGame(start=3, drop_next_jump=True)
    log3 = []
    b3 = UpgradeBot(g3, log=lambda l, m: log3.append(m), test=False, max_passes=20, now=lambda: 0.0)
    assert b3.run() and g3.presses > 10
    assert any("lệch" in m for m in log3), log3[:5]
    # (d) TEST không bấm
    g2 = _FakeGame()
    UpgradeBot(g2, log=lambda l, m: None, test=True, now=lambda: 0.0).run()
    assert g2.presses == 0
    # (e) tỉ lệ tự đo từ 2 nút (giao diện thật to 1.26 lần mẫu: nút 165x42, 2 hàng cách 156)
    fake = np.zeros((1280, 720, 3), np.uint8)
    for y in (790, 946):
        fake[y:y + 42, 452:452 + 165] = (60, 160, 60)           # BGR xanh lá
    pgx = read_page(fake)
    assert pgx.top == (452, 790) and 1.22 <= pgx.scale <= 1.30, (pgx.top, pgx.scale)
    assert read_page(fake, 1.0).scale == 1.0                    # đặt tay thì giữ nguyên
    # (f) 2 chữ số DÍNH nhau không bị nhầm là hình tờ vé (lỗi "338.7k" -> "8.7k")
    crop = np.full((40, 215, 3), (200, 235, 253), np.uint8)
    crop[6:32, 20:56] = (150, 120, 220)                           # hình tờ vé (cao 26)
    crop[12:27, 70:81] = (80, 130, 60)
    crop[12:27, 81:92] = (80, 130, 60)                            # "33" dính nhau (rộng 22, cao 15)
    crop[12:27, 100:111] = (80, 130, 60)                          # chữ số thứ 3
    crop[12:27, 125:136] = (80, 130, 60)
    mk = _text_mask(crop, False, 4)
    assert mk is not None and mk.shape[1] >= (136 - 70) * 4 - 8, None if mk is None else mk.shape
    print("selftest OK: nâng", games.presses, "lần, tăng", round(got_gain), "/ lý tưởng", round(ideal_gain), "; vé còn:", {k: round(v) for k, v in games.balance.items()})


class _FakeRow:
    def __init__(self, ticket, cost, gain, growth):
        self.ticket, self.cost, self.gain, self.growth = ticket, cost, gain, growth
        self.n = 0                              # số lần đã nâng


class _FakeGame:
    """Game giả: danh sách TUYẾN TÍNH 4 ô nâng được x 2 hàng + 3 ô chưa mở ở cuối, 2 loại vé, giá tăng theo cấp, mức tăng cố định mỗi hàng. Chỉ dùng cho --selftest."""

    def __init__(self, start=0, n_locked=3, drop_next_jump=False, salt="", circular=False):
        self.salt = salt
        self.circular = circular                # danh sách xoay vòng (như Nuôi dưỡng Nghệ Sĩ): mũi tên luôn hiện, ô cuối bấm tiếp = về ô đầu
        self.drop_next_jump = bool(drop_next_jump)
        self.balance = {"blue": 9000.0, "pink": 3000.0}
        spec = [("blue", 100, 50, 1.05), ("blue", 200, 150, 1.08), ("blue", 60, 20, 1.03), ("blue", 300, 400, 1.10),
                ("pink", 80, 30, 1.04), ("pink", 150, 90, 1.07), ("pink", 500, 100, 1.02), ("blue", 90, 10, 1.01)]
        self.rows = {f"it{i // 2}#{i % 2}": _FakeRow(*s) for i, s in enumerate(spec)}
        self.n_open = 4
        self.n_items = self.n_open + n_locked
        self.cur = start
        self.presses = 0
        self.spent = 0.0
        self.taps = 0
        self.singles = 0                        # số lần gọi press() lẻ (nâng thử + đọc mức tăng)
        self.batch_calls = 0                    # số lần gọi press_many()
        self.x10_calls = 0                      # tổng số lần bấm x10

    def _page(self):
        pg = Page(ok=True, layout=(LAYOUT_C if self.circular else None), key=f"{int(hashlib.md5((str(self.cur) + self.salt).encode()).hexdigest(), 16):0128b}"[:64] + "0" * (STRIP_W * STRIP_H), scale=1.0, top=(0, 0))
        if self.cur >= self.n_open:
            pg.ticket, pg.balance = "blue", self.balance["blue"]
            for i in (0, 1):
                pg.rows.append(RowInfo(i, 0, 0, 1, 1, False, 69e6, None))
            return pg
        pg.ticket = self.rows[f"it{self.cur}#0"].ticket
        pg.balance = self.balance[pg.ticket]
        for i in (0, 1):
            g = self.rows[f"it{self.cur}#{i}"]
            pg.rows.append(RowInfo(i, 0, 0, 1, 1, True, g.cost, g.cost <= self.balance[g.ticket]))
        return pg

    def page(self):
        return self._page()

    def next_item(self, pg, step=1):
        self.taps += 1
        n = self.cur + step
        if self.circular:
            self.cur = n % self.n_items
            return self._page()
        if n < 0 or n >= self.n_items:
            return None
        self.cur = n
        return self._page()

    def go_edge(self, pg, step=-1):
        taps = (self.cur if step < 0 else self.n_items - 1 - self.cur)
        self.cur = 0 if step < 0 else self.n_items - 1
        self.taps += taps
        return self._page(), taps

    def jump(self, pg, step, n):
        if self.drop_next_jump:                 # mô phỏng bấm liên tục bị nuốt 1 lần bấm
            self.drop_next_jump = False
            n -= 1
        self.taps += n
        self.cur = (self.cur + step * n) % self.n_items if self.circular else max(0, min(self.n_items - 1, self.cur + step * n))
        return self._page()

    def press_many(self, pg, idx, k10=0, k1=0):
        self.batch_calls += 1
        self.x10_calls += k10
        g = self.rows[f"it{self.cur}#{idx}"]
        for _ in range(10 * k10 + k1):
            if g.cost > self.balance[g.ticket]:
                break
            self.balance[g.ticket] -= g.cost
            self.spent += g.cost
            g.cost *= g.growth
            g.n += 1
            self.presses += 1
        return self._page()

    def press(self, pg, idx):
        self.singles += 1
        g = self.rows[f"it{self.cur}#{idx}"]
        if g.cost > self.balance[g.ticket]:
            return self._page(), None
        self.balance[g.ticket] -= g.cost
        self.spent += g.cost
        g.cost *= g.growth
        g.n += 1
        self.presses += 1
        return self._page(), g.gain


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "--selftest":
        _selftest()
        sys.exit(0)
    scale = 1.0 if "--crop" in sys.argv else None            # ảnh bị cắt (không phải khung đầy đủ) thì nút vẫn đúng cỡ gốc -> scale 1
    img = _imread(sys.argv[1])
    pg = read_page(img, scale)
    print(f"ok={pg.ok} khoá={pg.key[:12]} vé={pg.ticket} số dư={format_amount(pg.balance)}")
    for r in pg.rows:
        print(f"  hàng {r.idx}: nút ({r.x},{r.y}) {'XANH-bấm được' if r.active else 'XÁM'} giá={format_amount(r.cost)} "
              f"{'đủ vé' if r.affordable else ('THIẾU vé' if r.affordable is False else '?')}")
    if pg.top:
        box = _box(img, pg.top, GAIN_BOX, pg.scale)
        if box is not None:
            g, t, raw = read_gain(box)
            print(f"  dòng mức tăng: tăng={format_amount(g)} tổng={format_amount(t)} thô={raw[:60]}")
