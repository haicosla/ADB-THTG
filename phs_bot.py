# -*- coding: utf-8 -*-
"""
Bot auto "Điện Thoại PHS Mạnh" (game gộp điện thoại/phụ kiện, bàn 5x5) - điều khiển qua ADB, dùng cho bước `auto_phs`.

>>> TRẠNG THÁI: bản 3 - luật gộp/rơi/bảng doanh thu đã theo lời người dùng (14/10). Nhận diện đã thử trên 5 ảnh 720x1280.
>>> Bản 3: sau MỖI lần ấn bot CHỜ BÀN ĐỨNG YÊN (hết hoạt ảnh gộp/rơi) rồi mới đọc + tính + ấn tiếp (trước đây chỉ chờ cố định 0.9s nên
>>> đọc bàn giữa hoạt ảnh và ấn lúc game đang bận -> "ấn mà không ăn"); chấm điểm ưu tiên nước ĂN ĐƯỢC; ấn không có tác dụng thì thử lại / bỏ ô đó.
>>> Chưa chạy thử trên LDPlayer thật (đã thử trên game giả có hoạt ảnh). Bot KHÔNG bấm Mở tiệm: hết bước (hoặc hết nước đi) là DỪNG, người dùng tự mở tiệm.

======================================================================================================
1) GAME LÀ GÌ (người dùng mô tả + suy ra từ ảnh chụp)
======================================================================================================
- Bàn 5x5, mỗi ô là 1 món đồ có CẤP (số ở góc dưới-phải mỗi ô). Mỗi cấp là 1 hình riêng:
      1 = thẻ SIM xanh lá      2 = bao da nâu       3 = pin xanh dương     4 = củ sạc trắng
      5 = tai nghe/vỏ gập hồng 6 = điện thoại vàng  7 = điện thoại xanh-xám (đã thấy, đang có KHOÁ)
  (cấp 8+ chưa có mẫu: thêm bằng `python phs_bot.py anh.png --add-level N hàng cột`).
- ẤN vào 1 món -> món đó tăng 1 cấp (tốn 1 BƯỚC). Món có Ổ KHOÁ (góc trên-phải ô) KHÔNG ấn được.
- GỘP: các món CÙNG CẤP nối liền nhau theo chiều NGANG/DỌC (không chéo) thành nhóm n >= 3 món -> gộp thành 1 món cấp (cấp + n - 2):
  3 cái cấp 3 -> cấp 4, 4 cái cấp 3 -> cấp 5, 4 cái cấp 2 -> cấp 4, 5 cái -> +3 cấp.
- Sau khi gộp, ô trống được món phía trên RƠI XUỐNG theo cột; trên cùng còn thiếu thì rơi thêm món NGẪU NHIÊN (bot không đoán được).
- Cửa hàng cấp 2: món tối thiểu cấp 1, tối đa cấp 8; cửa hàng cấp 4: tối thiểu cấp 3, tối đa cấp 10. Món đạt cấp tối đa mà bị ăn (gộp nhóm >= 3)
  thì BIẾN MẤT. Công thức đoán cho cấp cửa hàng khác: min = cấp-1, max = cấp+6 (field `shop_level`, `min_level`, `max_level`).
- KÉO 1 ô tới khu "quầy điện thoại" phía TRÊN nút "Mở tiệm" = BÁN món đó: ô biến mất (món phía trên rơi xuống, có thể gộp dây chuyền), điểm = V(cấp ô)
  - bằng điểm gộp ra món cấp đó. Mở tiệm xong bàn KHÔNG đổi nên không cần ăn hết, có thể dựng bàn cho ván sau. Người dùng xác nhận 14/10: mỗi lần kéo tốn
  1 BƯỚC như 1 lần ấn; ô KHOÁ cũng kéo được; kéo lúc nào cũng được khi còn bước, hết bước (nút Mở tiệm sáng) thì KHÔNG kéo được (bot đã dừng ở 0 bước).
  Ưu tiên kéo món cấp CAO (người dùng: "kéo cái cao lợi hơn", kéo ô thấp trông tùm lum): `gen_removes` chỉ cho kéo ô thuộc `remove_top` (1) mức cấp cao nhất
  đang có trên bàn và cấp >= `remove_min_level` (3); trong số đó beam search chọn ô kéo + lúc kéo (kéo để món phía trên rơi xuống thành nhóm ăn được cũng được
  tính). `remove_only_stuck` = true: CHỈ kéo khi không còn nước ăn trong số bước còn lại (người dùng gợi ý "hết nước đi mới kéo"; mô phỏng cho thấy bàn
  hầu như luôn còn nước ăn nên gần như không kéo -> điểm tụt về mức chỉ ấn, nên mặc định tắt).
  Mô phỏng 16 ván x 8 vòng (pot 0.2): chỉ ấn 62.9k | kéo mọi ô 91.3k (14% lần kéo là ô cấp <= 2) | kéo ô cao nhất cấp >= 3 84.2k (không kéo ô cấp <= 2,
  cấp TB ô bị kéo 7.2) | 2 mức cao nhất 85.8k | chỉ kéo khi hết nước ăn 62.6k.
- Mỗi lượt có "Số bước" (vòng tròn nâu, vd 6). Về 0 thì nút "Mở tiệm" sáng -> NGƯỜI DÙNG tự bấm (tốn ⚡x1); bàn giữ nguyên cho lượt sau.
- Doanh thu dự kiến = TỔNG doanh thu các lần gộp trong lượt (ảnh: 523 sau 1 bước, 2027 sau hết bước; 3935 khớp "Doanh thu vòng này" lúc mở tiệm).

======================================================================================================
2) BẢNG DOANH THU (người dùng cho) - V(k) = doanh thu khi gộp ra món cấp k từ 3 món
======================================================================================================
- Người dùng cho (14/10): V(1)=10, V(2)=31, V(3)=64, V(4)=177, V(5)=354, V(6)=614, V(7)=979, V(8)=1477, V(9)=2141 (`V_KNOWN`; bảng cũ nội suy
  V(4)=136, V(5)=289 là SAI). Từ cấp 10 ĐOÁN: hiệu V(k)-V(k-1) nhân ~1.33/cấp (`V_DIFF_GROWTH`).
  Nhóm n món cấp L cho (n-2) x V(L+1): 4 cái cấp 1 = 31+31, 4 cái cấp 2 = 64+64 = 128 (khớp lời người dùng). Kéo 1 món cấp k vào Mở tiệm cho V(k).
- Cùng 1 bàn bot chọn chuỗi ấn cho TỔNG doanh thu gộp lớn nhất trong số bước còn lại, cộng thêm 1 chút "tiềm năng" của bàn còn lại
  (`pot_weight`, `pair_bonus`) để lượt sau còn nước tốt.

======================================================================================================
3) HÌNH HỌC + NHẬN DIỆN
======================================================================================================
- Ảnh tham chiếu 720x1280, neo đáy. Vùng 5x5: x 34..688, y 499..1154 (ô ~130.8px). Vòng "Số bước" (503,398)-(572,472); nút Mở tiệm (640,435).
- Cấp (`read_board`): NCC vùng giữa ô (che góc khoá + ô số) với mẫu `templates/phs_lv<N>.png`; điểm < 0.55 -> ô "lạ" (cấp -1) bot không ấn và
  coi như vật cản, lưu crop `debug_phs/unknown_*.png`. Ô trống (cấp 0) = nền nâu đồng màu. Khoá: mẫu `templates/phs_lock.png`.
- Số bước (`read_steps`), thể lực (`read_energy`), cấp cửa hàng (`read_shop_level`, chữ "Cấp Cửa Hàng: N") đọc bằng pytesseract.
- Nút Mở tiệm sáng (`shop_ready`): độ bão hoà vùng nút > 70. Màn hoạt ảnh "Đang mở tiệm" / popup "Mở tiệm thành công" không phải bàn -> `board_ok` false.

======================================================================================================
4) NHỮNG CHỖ VẪN ĐOÁN
======================================================================================================
 a. Món kết quả gộp nằm ở ô vừa ấn (nếu thuộc nhóm), nếu không thì ô trên-trái nhất của nhóm.
 b. Món khoá có tham gia gộp (`locked_merge` = true) và mất khoá sau khi gộp; khoá đi theo món khi rơi.
 c. Gộp dây chuyền sau khi rơi xảy ra tự động và có doanh thu (món NGẪU NHIÊN rơi thêm ở trên cùng thì bot KHÔNG tính vào kế hoạch,
    nên mỗi lần chỉ ấn nước đầu rồi chụp lại).
 d. Doanh thu khi nhóm cấp tối đa biến mất = (n-2) x V(max+1) (ngoại suy); V(4), V(5) nội suy.
 e. Ấn món đang ở cấp tối đa: bot KHÔNG ấn.

======================================================================================================
5) THUẬT TOÁN
======================================================================================================
- `apply_tap()`: +1 cấp -> gộp nhóm (ưu tiên nhóm chứa ô vừa ấn) -> rơi theo cột -> lặp tới ổn định; trả (bàn mới, doanh thu).
- `apply_remove()`: kéo ô vào Mở tiệm -> ô biến mất, +V(cấp) -> rơi theo cột -> gộp dây chuyền. Hành động trong kế hoạch: ấn = (hàng, cột), KÉO = (hàng, cột, "x")
  (`gen_actions`, `apply_action`). Bot kéo bằng `adb.swipe_hold_px` (nhấn -> di chuyển `drag_ms` -> GIỮ YÊN `drag_hold_ms` ở quầy -> nhả; vuốt thường nhả tay khi món chưa tới nơi nên thả hụt) từ tâm ô tới ĐIỂM THẢ ở quầy điện thoại. Điểm thả = KHAY ĐIỆN THOẠI ở quầy (đã đo trên ảnh người dùng khoanh đỏ, nhưng CHƯA thử trên LDPlayer thật): thử lần lượt
  `SHOP_DROP_CANDIDATES` (toạ độ ảnh 720x1280; điểm đầu = tâm khay điện thoại người dùng khoanh đỏ), lần kéo nào làm bàn đổi thì nhớ điểm đó (`_drop_ok`); thử hết các điểm mà không lần nào đổi thì TẮT kéo
  (log cảnh báo). Sau khi điểm thả đã đúng, kéo 1 ô mà bàn + số bước không đổi: thử lại 1 lần, 2 lần liền thì không kéo ô đó nữa; 3 ô thất bại thì TẮT kéo.
  Chốt điểm thả bằng field `drop_xy`; ảnh debug (chế độ TEST) có chữ thập xanh "tha" đánh dấu điểm thả để kiểm tra bằng mắt.
- `beam_search()`: thử chuỗi ấn dài tới `min(số_bước_còn, depth)` giữ `beam` bàn tốt nhất mỗi tầng; điểm = doanh thu đã gộp (nhân `discount`^số nước
  đã ấn trước lúc ăn: ăn sớm được ưu tiên vì sau mỗi lần ăn bàn rơi món NGẪU NHIÊN nên kế hoạch dài hay lệch) + `evaluate()` (tiềm năng cấu trúc bàn:
  cặp kề nhau cùng cấp `pair_bonus`, cặp hơn kém đúng 1 cấp `near_bonus`, cộng rất ít `pot_weight` x giá trị từng món). `pot_weight` cũ 0.3 quá lớn
  làm bot thích ấn tăng cấp ô lẻ hơn là ăn nhóm nhỏ -> hạ còn 0.05 khi chỉ ấn (ván giả 40 ván x 8 vòng: doanh thu +4.6%, tỉ lệ cú ấn ăn được 56% -> 64%).
  Khi có KÉO bán, `pot_weight` = giá trị để dành cho ván sau: mô phỏng 16 ván x 8 vòng: chỉ ấn 62.9k, kéo + pot 0.05 89.6k, pot 0.2 91.3k (tốt nhất),
  pot 0.4 85.6k, 0.6 80.0k, 0.8 55.2k (để dành quá nhiều thì bỏ phí bước) -> mặc định 0.2.
- Mỗi vòng ấn nước ĐẦU rồi CHỜ BÀN ĐỨNG YÊN (`_wait_stable`) rồi chụp lại; DỪNG khi số bước = 0 (hoặc không đọc được số bước mà nút Mở tiệm đã sáng)
  hoặc không còn ô nào ấn được.
- `_wait_stable()`: nghỉ tối thiểu `tap_wait` rồi chụp liên tục tới khi `settle_reads` lần đọc liên tiếp cho cùng 1 bàn VÀ ảnh vùng bàn lệch <= `pix_thr`
  (còn ô trống đang rơi thì đòi gấp đôi). Hạn chờ `settle_max` giây KỂ TỪ LẦN BÀN ĐỔI GẦN NHẤT (chuỗi gộp dây chuyền dài vẫn chờ hết), tổng <= `settle_hard`.
- Kiểm tra cú ấn: sau khi bàn yên mà bàn + số bước KHÔNG đổi -> chờ thêm 1s đọc lại; vẫn không đổi thì ấn lại 1 lần; 2 lần liền không đổi thì coi ô đó
  là ô không ấn được (`_blocked`, như ô khoá) tới khi ô đổi cấp.

======================================================================================================
6) FIELD CỦA BƯỚC `auto_phs` (đều tuỳ chọn)
======================================================================================================
  test (false)        - true = CHỈ chụp 1 lần, nhận diện, tính kế hoạch + doanh thu dự tính, lưu ảnh debug_phs/, KHÔNG bấm
  max_seconds (0)     - giới hạn thời gian (0 = không giới hạn)
  depth (6) / beam (120) - độ sâu / độ rộng beam search
  steps_default (6)   - số bước còn lại giả định khi không đọc được vòng "Số bước"
  shop_level (0)      - cấp cửa hàng (0 = tự đọc OCR, đọc không được thì dùng min_level/max_level)
  min_level / max_level (0) - ghi đè cấp món tối thiểu/tối đa (0 = theo cấp cửa hàng)
  merge_values        - [V2, V3, V4, ...] ghi đè bảng doanh thu (bắt đầu từ V(2))
  pot_weight (0.2 nếu allow_remove, 0.05 nếu không), pair_bonus (0.15), locked_merge (true) - xem mục 4/5
  tap_wait (0.6)      - nghỉ TỐI THIỂU sau mỗi lần ấn (cho hoạt ảnh bắt đầu) rồi mới chờ bàn đứng yên
  settle_max (6)      - chờ bàn đứng yên tối đa bấy nhiêu giây KỂ TỪ LẦN BÀN ĐỔI GẦN NHẤT; settle_hard (60) = trần cứng cho 1 lần chờ
  settle_reads (4)    - số lần chụp liên tiếp phải giống nhau để coi là đứng yên; settle_gap (0.25) = nghỉ giữa 2 lần chụp
  pix_thr (2.0)       - độ lệch ảnh vùng bàn (0..255) tối đa giữa 2 lần chụp để coi là hết hoạt ảnh (tăng nếu bàn có hiệu ứng lấp lánh chạy mãi)
  discount (0.92), near_bonus (0.05) - xem mục 5
  allow_remove (true) - cho phép KÉO ô tới quầy điện thoại để bán (false = chỉ ấn như bản cũ); remove_locked (true) - cho kéo cả ô khoá
  remove_top (1)      - chỉ kéo ô thuộc ngần này mức cấp CAO NHẤT đang có trên bàn (0 = kéo bất kỳ ô nào; 2 = thêm mức nhì, điểm nhỉnh hơn chút)
  remove_min_level (3) - không kéo món cấp thấp hơn mức này;  remove_only_stuck (false) - true = chỉ kéo khi hết nước ăn
  drag_ms (700)       - thời gian di chuyển khi kéo ô; drag_hold_ms (500) - giữ yên tại điểm thả trước khi nhả (0 = nhả ngay); drag_steps (12) - số điểm trung gian
                        (mỗi điểm 1 lệnh adb: nhiều = mượt nhưng chậm hơn); drop_xy ([x, y], toạ độ ảnh 720x1280) - điểm thả cố định (không đặt = tự thử SHOP_DROP_CANDIDATES)
  debug (false)       - lưu ảnh debug_phs/ mỗi nước (test luôn lưu)
  lost_limit (4)      - số lần liên tiếp không thấy bàn thì kết thúc bước

Chạy riêng để kiểm tra:  python phs_bot.py anh.png
Thêm mẫu cấp mới:       python phs_bot.py anh.png --add-level 8 hàng cột     (hàng/cột tính từ 0)
Thêm mẫu khoá:          python phs_bot.py anh.png --add-lock hàng cột
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

# ----------------------------------------------------------------------------
# Hằng số hình học (đo trên ảnh 720x1280)
# ----------------------------------------------------------------------------
REF_W, REF_H = 720, 1280
N = 5                                          # bàn N x N
BOARD_X0, BOARD_X1 = 34.0, 688.0
BOARD_Y0, BOARD_Y1 = 499.0, 1154.0
PITCH = (BOARD_X1 - BOARD_X0) / N              # ~130.8
SHOP_BTN = (640.0, 435.0)
# Điểm THẢ khi kéo ô để bán: KHAY ĐIỆN THOẠI ở quầy (vòng đỏ người dùng khoanh trên ảnh 720x1280 ngày 14/10: x ~335..650, y ~245..408, tâm ~(490, 328)),
# KHÔNG phải nút Mở tiệm (nút chỉ sáng khi hết bước). Điểm đầu = tâm khay; các điểm sau là dự phòng cũng nằm trong khay, dùng khi kéo vào điểm đầu mà bàn
# không đổi (bot thử lần lượt, điểm nào làm bàn đổi thì nhớ dùng tiếp). Đặt field `drop_xy` [x, y] (toạ độ ảnh 720x1280) để chốt 1 điểm.
SHOP_DROP_CANDIDATES = [(490.0, 330.0), (430.0, 340.0), (560.0, 320.0), (480.0, 285.0)]
SHOP_BTN_BOX = (610, 405, 675, 465)
STEPS_BOX = (503, 398, 572, 472)
ENERGY_BOX = (25, 436, 160, 468)
DEBUG_DIR = "debug_phs"
FEAT = 48                                      # cạnh ảnh đặc trưng (vuông)


def _tpl_dir():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    return here if os.path.isdir(here) else "templates"


@dataclass
class Geo:
    s: float
    x0: float
    y0: float
    pitch: float
    sh: float                                  # y_scale để đổi toạ độ tham chiếu -> thực (bằng s)
    y_off: float                               # y_thực = y_ref * s + y_off

    def cx(self, c):
        return self.x0 + (c + 0.5) * self.pitch

    def cy(self, r):
        return self.y0 + (r + 0.5) * self.pitch

    def ref_xy(self, x, y):
        return x * self.s, y * self.s + self.y_off

    def ref_box(self, box):
        x1, y1, x2, y2 = box
        return (int(x1 * self.s), int(y1 * self.s + self.y_off), int(x2 * self.s), int(y2 * self.s + self.y_off))


def make_geo(frame) -> Geo:
    h, w = frame.shape[:2]
    s = w / REF_W
    y_off = h - REF_H * s                      # neo đáy
    return Geo(s=s, x0=BOARD_X0 * s, y0=BOARD_Y0 * s + y_off, pitch=PITCH * s, sh=s, y_off=y_off)


# ----------------------------------------------------------------------------
# 1) Nhận diện
# ----------------------------------------------------------------------------
def _cell_img(frame, geo: Geo, r, c):
    p = geo.pitch
    x, y = geo.x0 + c * p, geo.y0 + r * p
    x1, y1, x2, y2 = int(x), int(y), int(x + p), int(y + p)
    H, W = frame.shape[:2]
    return frame[max(0, y1):min(H, y2), max(0, x1):min(W, x2)]


def _feature(cell_bgr):
    """Ảnh đặc trưng FEATxFEAT xám của vùng giữa ô; che góc trên-phải (khoá) và góc dưới-phải (ô số cấp)."""
    if cell_bgr.size == 0:
        return np.zeros((FEAT, FEAT), np.float32)
    h, w = cell_bgr.shape[:2]
    c = cell_bgr[int(h * 0.06):int(h * 0.94), int(w * 0.06):int(w * 0.94)]
    f = cv2.resize(c, (FEAT, FEAT), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
    m = float(g.mean())
    g[:int(FEAT * 0.42), int(FEAT * 0.62):] = m      # khoá
    g[int(FEAT * 0.60):, int(FEAT * 0.58):] = m      # ô số
    return g


def _tpl_feature(level):
    p = os.path.join(_tpl_dir(), f"phs_lv{level}.png")
    if not os.path.exists(p):
        return None
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if im is None else _feature(im)


_PROTO_CACHE: dict = {}


def load_protos(force=False):
    if force or not _PROTO_CACHE:
        _PROTO_CACHE.clear()
        d = _tpl_dir()
        if os.path.isdir(d):
            for fn in os.listdir(d):
                m = re.fullmatch(r"phs_lv(\d+)\.png", fn)
                if m:
                    f = _tpl_feature(int(m.group(1)))
                    if f is not None:
                        _PROTO_CACHE[int(m.group(1))] = f
    return _PROTO_CACHE


def _ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d > 1e-6 else 0.0


def classify_cell(cell_bgr, min_score=0.55):
    """-> (cấp, điểm). cấp 0 = ô trống, -1 = ô lạ (không khớp mẫu nào)."""
    if cell_bgr.size == 0:
        return 0, 1.0
    h, w = cell_bgr.shape[:2]
    mid = cell_bgr[int(h * 0.2):int(h * 0.8), int(w * 0.2):int(w * 0.8)]
    if float(mid.reshape(-1, 3).std(0).mean()) < 9.0:      # gần đồng màu = nền trống
        return 0, 1.0
    f = _feature(cell_bgr)
    best, bs = -1, -1.0
    for lv, pf in load_protos().items():
        sc = _ncc(f, pf)
        if sc > bs:
            best, bs = lv, sc
    if bs < min_score:
        return -1, bs
    return best, bs


def _lock_tpl():
    p = os.path.join(_tpl_dir(), "phs_lock.png")
    if not os.path.exists(p):
        return None
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def lock_crop(cell_bgr):
    h, w = cell_bgr.shape[:2]
    return cell_bgr[0:int(h * 0.42), int(w * 0.55):w]


def is_locked(cell_bgr, thr=0.6):
    t = _lock_tpl()
    if t is None or cell_bgr.size == 0:
        return False
    reg = lock_crop(cell_bgr)
    if reg.shape[0] < t.shape[0] or reg.shape[1] < t.shape[1]:
        return False
    res = cv2.matchTemplate(reg, t, cv2.TM_CCOEFF_NORMED)
    return float(res.max()) >= thr


def read_board(frame, min_score=0.55, save_unknown=True):
    geo = make_geo(frame)
    lv = [[0] * N for _ in range(N)]
    lk = [[False] * N for _ in range(N)]
    sc = [[0.0] * N for _ in range(N)]
    for r in range(N):
        for c in range(N):
            cell = _cell_img(frame, geo, r, c)
            l, s = classify_cell(cell, min_score)
            lv[r][c], sc[r][c] = l, s
            lk[r][c] = bool(l > 0 and is_locked(cell))
            if l == -1 and save_unknown:
                try:
                    os.makedirs(DEBUG_DIR, exist_ok=True)
                    cv2.imencode(".png", cell)[1].tofile(os.path.join(DEBUG_DIR, f"unknown_r{r}c{c}_{time.strftime('%H%M%S')}.png"))
                except Exception:
                    pass
    return geo, Board(lv, lk, sc)


def board_text(b: Board):
    rows = []
    for r in range(N):
        rows.append(" ".join((f"{b.lv[r][c]:>2}" + ("*" if b.locked[r][c] else " ")) if b.lv[r][c] >= 0 else " ? " for c in range(N)))
    return "\n".join(rows) + "\n(số = cấp, * = khoá, ? = ô lạ, 0 = trống)"


def board_ok(b: Board):
    """Bàn hợp lệ nếu đa số ô nhận ra được (không phải màn hình khác)."""
    known = sum(1 for r in b.lv for v in r if v >= 0)
    return known >= N * N * 0.7


def shop_ready(frame, geo: Geo):
    x1, y1, x2, y2 = geo.ref_box(SHOP_BTN_BOX)
    b = frame[y1:y2, x1:x2]
    if b.size == 0:
        return False
    return float(cv2.cvtColor(b, cv2.COLOR_BGR2HSV)[..., 1].mean()) > 70.0


def _ocr(img, config):
    try:
        import pytesseract
        return pytesseract.image_to_string(img, config=config).strip()
    except Exception:
        return ""


def read_steps(frame, geo: Geo) -> Optional[int]:
    x1, y1, x2, y2 = geo.ref_box(STEPS_BOX)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (12, 70, 170), (40, 255, 255))      # chữ vàng/kem
    ys, xs = np.where(mask > 0)
    if len(xs) < 30:
        return None
    # chỉ giữ phần giữa vòng tròn (bỏ chữ "Số bước" phía dưới)
    h = mask.shape[0]
    mask[int(h * 0.80):, :] = 0
    ys, xs = np.where(mask > 0)
    if len(xs) < 30:
        return None
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = cv2.copyMakeBorder(255 - m, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    m = cv2.resize(m, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    for psm in (7, 8, 10):
        t = _ocr(m, f"--psm {psm} -c tessedit_char_whitelist=0123456789")
        if t.isdigit() and 0 <= int(t) <= 99:
            return int(t)
    return None


def read_energy(frame, geo: Geo) -> Optional[tuple]:
    x1, y1, x2, y2 = geo.ref_box(ENERGY_BOX)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    for im in (th, 255 - th):
        t = _ocr(im, "--psm 7 -c tessedit_char_whitelist=0123456789/")
        m = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", t)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


SHOP_LEVEL_BOX = (55, 343, 200, 373)


def read_shop_level(frame, geo: Geo) -> Optional[int]:
    """Đọc N trong chữ "Cấp Cửa Hàng: N" (dưới lịch bàn góc trái)."""
    x1, y1, x2, y2 = geo.ref_box(SHOP_LEVEL_BOX)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    for im in (th, 255 - th):
        m = re.search(r":\s*(\d{1,2})", _ocr(im, "--psm 7"))
        if m and 1 <= int(m.group(1)) <= 60:
            return int(m.group(1))
    return None


# ----------------------------------------------------------------------------
# 2) Mô phỏng (luật mục 1/2/4 ở docstring)
# ----------------------------------------------------------------------------
# V(k) = điểm khi gộp ra món cấp k = điểm khi KÉO 1 món cấp k vào nút Mở tiệm (người dùng cung cấp 14/10, cấp 1..9).
V_KNOWN = {1: 10.0, 2: 31.0, 3: 64.0, 4: 177.0, 5: 354.0, 6: 614.0, 7: 979.0, 8: 1477.0, 9: 2141.0}
V_RATIO = 2.126                                # chỉ dùng khi `merge_values` ghi đè mà thiếu cấp
V_DIFF_GROWTH = 1.33                           # ĐOÁN cho cấp >= 10: hiệu V(k)-V(k-1) nhân ~1.33 mỗi cấp (hiệu cấp 7..9 = 365, 498, 664)


def default_level_range(shop_level):
    return max(1, shop_level - 1), shop_level + 6            # theo 2 mốc người dùng cho: 2 -> 1..8, 4 -> 3..10


@dataclass
class Rules:
    min_level: int = 1
    max_level: int = 8
    merge_values: Optional[list] = None        # [V2, V3, ...] ghi đè
    pot_weight: float = 0.2                    # giá trị 'để dành' của món trên bàn cho ván sau (có kéo bán: 0.2 tốt nhất trong mô phỏng; không kéo: 0.05; bản đầu 0.3 quá lớn)
    pair_bonus: float = 0.15
    locked_merge: bool = True
    discount: float = 0.92                     # doanh thu gộp ở nước thứ k trong kế hoạch nhân discount^k (ăn sớm chắc hơn ăn muộn vì bàn đổi ngẫu nhiên)
    near_bonus: float = 0.05                   # 2 ô kề nhau hơn kém đúng 1 cấp: ấn ô thấp 1 lần là thành cặp bằng nhau
    allow_remove: bool = True                  # cho phép hành động KÉO 1 ô vào nút Mở tiệm để bán (điểm = V(cấp ô))
    remove_locked: bool = True                 # ô khoá kéo bán được (người dùng xác nhận 14/10)
    remove_top: int = 1                        # chỉ kéo ô thuộc `remove_top` mức cấp CAO NHẤT đang có trên bàn (0 = không giới hạn) - người dùng: "kéo cái cao lợi hơn"
    remove_min_level: int = 3                  # không kéo món thấp hơn cấp này (kéo cấp 1, 2 chỉ được 10-31 điểm mà tốn 1 bước)
    remove_only_stuck: bool = False            # true = CHỈ kéo khi không còn nước ăn được trong số bước còn lại (xem PhsBot.run)
    hole_weight: float = 0.0                   # mỗi ô TRỐNG sau khi gộp/kéo sẽ có điện thoại MỚI rơi vào (miễn phí) -> thưởng hole_weight x V(refill_level) mỗi ô trống
    refill_level: int = 0                      # cấp ước lượng của món mới rơi vào (0 = min_level + 1)

    def V(self, k):
        """Điểm khi gộp 3 món ra món cấp k (cũng là điểm khi kéo 1 món cấp k vào nút Mở tiệm)."""
        if k < 1:
            return 0.0
        if self.merge_values and k >= 2:
            mv = self.merge_values
            if k - 2 < len(mv):
                return float(mv[k - 2])
            return float(mv[-1]) * V_RATIO ** (k - 1 - len(mv))
        if k in V_KNOWN:
            return V_KNOWN[k]
        v, d = V_KNOWN[9], V_KNOWN[9] - V_KNOWN[8]
        for _ in range(9, k):
            d *= V_DIFF_GROWTH
            v += d
        return v

    def pot(self, L):
        return self.V(L) if L >= 2 else self.V(2) / 3.0


@dataclass
class Board:
    lv: list                                   # N x N cấp (0 trống, -1 lạ)
    locked: list                               # N x N bool
    scores: list

    def copy(self):
        return Board([r[:] for r in self.lv], [r[:] for r in self.locked], self.scores)

    def key(self):
        return (tuple(tuple(r) for r in self.lv), tuple(tuple(r) for r in self.locked))


def _components(b: Board, rules: Rules):
    seen = [[False] * N for _ in range(N)]
    comps = []
    for r in range(N):
        for c in range(N):
            L = b.lv[r][c]
            if seen[r][c] or L <= 0:
                continue
            if b.locked[r][c] and not rules.locked_merge:
                continue
            stack, comp = [(r, c)], []
            seen[r][c] = True
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < N and 0 <= nx < N and not seen[ny][nx] and b.lv[ny][nx] == L:
                        if b.locked[ny][nx] and not rules.locked_merge:
                            continue
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            comps.append((L, comp))
    return comps


def _gravity(b: Board, anchor=None):
    """Món rơi xuống theo cột (giữ thứ tự, khoá đi theo món). Trả vị trí mới của anchor."""
    new_anchor = anchor
    for c in range(N):
        items = [(r, b.lv[r][c], b.locked[r][c]) for r in range(N) if b.lv[r][c] != 0]
        for r in range(N):
            b.lv[r][c] = 0
            b.locked[r][c] = False
        for k, (r0, L, lk) in enumerate(reversed(items)):
            r1 = N - 1 - k
            b.lv[r1][c], b.locked[r1][c] = L, lk
            if anchor == (r0, c):
                new_anchor = (r1, c)
    return new_anchor


def resolve_merges(b: Board, rules: Rules, anchor=None):
    """Gộp -> rơi -> gộp... tới ổn định. Trả doanh thu."""
    revenue = 0.0
    for _ in range(60):
        comps = [(L, comp) for L, comp in _components(b, rules) if len(comp) >= 3]
        if not comps:
            break
        comps.sort(key=lambda t: (anchor not in t[1], -t[0]))
        L, comp = comps[0]
        n = len(comp)
        revenue += (n - 2) * rules.V(L + 1)
        pos = anchor if anchor in comp else sorted(comp)[0]
        for y, x in comp:
            b.lv[y][x] = 0
            b.locked[y][x] = False
        if L < rules.max_level:
            b.lv[pos[0]][pos[1]] = min(rules.max_level, L + n - 2)
            anchor = pos
        # L >= max_level: nhóm biến mất
        anchor = _gravity(b, anchor)
    return revenue


def gen_taps(b: Board, rules: Rules):
    return [(r, c) for r in range(N) for c in range(N)
            if 0 < b.lv[r][c] < rules.max_level and not b.locked[r][c]]


def apply_tap(b: Board, rc, rules: Rules):
    """Ấn ô rc. Trả (bàn mới, doanh thu gộp được)."""
    nb = b.copy()
    r, c = rc
    nb.lv[r][c] += 1
    return nb, resolve_merges(nb, rules, anchor=rc)


# Hành động trong kế hoạch: ấn = (hàng, cột); KÉO ô vào nút Mở tiệm = (hàng, cột, "x").
def gen_removes(b: Board, rules: Rules, no_remove=()):
    """Các ô được phép kéo bán: ô có món (khoá tuỳ `remove_locked`), cấp >= `remove_min_level`, và thuộc `remove_top` mức cấp cao nhất đang có."""
    if not rules.allow_remove:
        return []
    cand = [(r, c) for r in range(N) for c in range(N)
            if b.lv[r][c] >= max(1, rules.remove_min_level) and (rules.remove_locked or not b.locked[r][c]) and (r, c) not in no_remove]
    if cand and rules.remove_top > 0:
        top = set(sorted({b.lv[r][c] for r, c in cand}, reverse=True)[:rules.remove_top])
        cand = [(r, c) for r, c in cand if b.lv[r][c] in top]
    return [(r, c, "x") for r, c in cand]


def apply_remove(b: Board, rc, rules: Rules):
    """Kéo ô rc vào nút Mở tiệm: ô biến mất, điểm = V(cấp ô); món phía trên rơi xuống (có thể gộp dây chuyền). Trả (bàn mới, điểm)."""
    nb = b.copy()
    r, c = rc[0], rc[1]
    gain = rules.V(nb.lv[r][c])
    nb.lv[r][c] = 0
    nb.locked[r][c] = False
    _gravity(nb)
    return nb, gain + resolve_merges(nb, rules)


def gen_actions(b: Board, rules: Rules, no_remove=()):
    return gen_taps(b, rules) + gen_removes(b, rules, no_remove)


def apply_action(b: Board, a, rules: Rules):
    return apply_remove(b, a, rules) if len(a) == 3 else apply_tap(b, (a[0], a[1]), rules)


def evaluate(b: Board, rules: Rules):
    tot = 0.0
    for r in range(N):
        for c in range(N):
            L = b.lv[r][c]
            if L > 0:
                tot += rules.pot_weight * rules.pot(L)
                for ny, nx in ((r, c + 1), (r + 1, c)):
                    if ny >= N or nx >= N:
                        continue
                    M = b.lv[ny][nx]
                    if M == L:
                        tot += rules.pair_bonus * rules.pot(L)
                    elif M > 0 and abs(M - L) == 1:
                        low = min(L, M)
                        lo_rc = (r, c) if L < M else (ny, nx)
                        if not b.locked[lo_rc[0]][lo_rc[1]] and low < rules.max_level:
                            tot += rules.near_bonus * rules.pot(low + 1)
    if rules.hole_weight > 0:
        holes = sum(1 for row in b.lv for v in row if v == 0)
        if holes:
            tot += rules.hole_weight * rules.V(rules.refill_level or max(1, rules.min_level + 1)) * holes
    return tot


def beam_search(b: Board, depth=6, beam=120, rules: Optional[Rules] = None, no_remove=()):
    """Trả (chuỗi hành động [(hàng,cột) = ấn | (hàng,cột,"x") = kéo vào Mở tiệm, ...], điểm dự tính của chuỗi).
    `no_remove` = tập ô không được thử kéo (ô kéo mà không có tác dụng).

    Điểm của 1 chuỗi = doanh thu gộp đã CHIẾT KHẤU theo nước (`Rules.discount`^k, k = số nước đã ấn trước lúc ăn) + `evaluate()` bàn cuối.
    Chiết khấu để nước ăn được NGAY hơn nước chuẩn bị rồi mới ăn (vì sau mỗi lần ăn bàn rơi món NGẪU NHIÊN, kế hoạch dài hay lệch).
    Doanh thu trả về vẫn là doanh thu THẬT (không chiết khấu)."""
    rules = rules or Rules()
    g = float(rules.discount)
    # phần tử: (điểm, bàn, đường đi, doanh thu thật, doanh thu chiết khấu)
    frontier = [(evaluate(b, rules), b, [], 0.0, 0.0)]
    best = (-1e18, [], 0.0)
    for d in range(max(1, depth)):
        nxt, seen = [], {}
        w = g ** d
        for _, cur, path, rev, drev in frontier:
            for rc in gen_actions(cur, rules, no_remove):
                nb, gain = apply_action(cur, rc, rules)
                tr = rev + gain
                td = drev + gain * w
                sc = td + evaluate(nb, rules)
                k = nb.key()
                if k in seen and seen[k] >= sc:
                    continue
                seen[k] = sc
                nxt.append((sc, nb, path + [rc], tr, td))
        if not nxt:
            break
        nxt.sort(key=lambda t: -t[0])
        frontier = nxt[:beam]
        if frontier[0][0] > best[0]:
            best = (frontier[0][0], frontier[0][2], frontier[0][3])
    return best[1], best[2]


# ----------------------------------------------------------------------------
# 3) Chạy bước
# ----------------------------------------------------------------------------
class _Stop(Exception):
    pass


ROI_PX = 16                                    # mỗi ô thu nhỏ còn ROI_PX x ROI_PX khi so 2 lần chụp (xem board_roi)


def board_roi(frame, geo: Geo):
    """Ảnh xám thu nhỏ của vùng bàn 5x5 - dùng so 2 lần chụp liên tiếp để biết hoạt ảnh gộp/rơi đã HẾT chưa."""
    H, W = frame.shape[:2]
    x1, y1 = int(max(0, geo.x0)), int(max(0, geo.y0))
    x2, y2 = int(min(W, geo.x0 + N * geo.pitch)), int(min(H, geo.y0 + N * geo.pitch))
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (N * ROI_PX, N * ROI_PX), interpolation=cv2.INTER_AREA).astype(np.float32)


def roi_diff(a, b):
    """Độ lệch trung bình (0..255) giữa 2 ảnh `board_roi`; không so được thì coi là rất khác."""
    if a is None or b is None or a.shape != b.shape:
        return 255.0
    return float(np.abs(a - b).mean())


def save_debug(frame, geo, board: Board, plan=None, tag="phs", drop=None):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        im = frame.copy()
        for r in range(N):
            for c in range(N):
                t = "?" if board.lv[r][c] < 0 else str(board.lv[r][c]) + ("L" if board.locked[r][c] else "")
                cv2.putText(im, t, (int(geo.cx(c)) - 22, int(geo.cy(r)) + 12), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 255), 3)
        for i, a in enumerate(plan or []):
            r, c = a[0], a[1]
            col = (0, 160, 255) if len(a) == 3 else (0, 0, 255)             # cam = KÉO vào nút Mở tiệm, đỏ = ấn
            cv2.circle(im, (int(geo.cx(c)), int(geo.cy(r))), 18 + i * 6, col, 3)
            cv2.putText(im, str(i + 1) + ("x" if len(a) == 3 else ""), (int(geo.cx(c)) - 8, int(geo.cy(r)) - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, col, 3)
        if drop is not None:                                                 # chữ thập xanh = điểm THẢ khi kéo ô để bán
            dx, dy = geo.ref_xy(*drop)
            cv2.drawMarker(im, (int(dx), int(dy)), (255, 255, 0), cv2.MARKER_CROSS, 40, 4)
            cv2.putText(im, "tha", (int(dx) + 24, int(dy) - 12), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 3)
        path = os.path.join(DEBUG_DIR, f"{tag}_{time.strftime('%H%M%S')}.png")
        cv2.imencode(".png", im)[1].tofile(path)
        return path
    except Exception:
        return None


class PhsBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_seconds=0, depth=6, beam=120, steps_default=6,
                 tap_wait=0.6, debug=False, lost_limit=4, shop_level=0, rules: Optional[Rules] = None,
                 min_level=0, max_level=0, sleep=time.sleep, now=time.time,
                 settle_max=6.0, settle_reads=4, settle_gap=0.25, pix_thr=2.0, settle_hard=60.0, drag_ms=700, drop_xy=None, drag_hold_ms=500, drag_steps=12,
                 drag_methods=None, drag_pick_ms=350, drag_slow_ms=1500, drag_tries=6):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test, self.debug = bool(test), bool(debug)
        self.max_seconds = float(max_seconds or 0)
        self.depth, self.beam = int(depth), int(beam)
        self.steps_default = int(steps_default)
        self.tap_wait = float(tap_wait)
        self.lost_limit = int(lost_limit)
        self.shop_level = int(shop_level or 0)
        self.min_level, self.max_level = int(min_level or 0), int(max_level or 0)
        self.rules = rules or Rules()
        self.sleep, self.now = sleep, now
        self.settle_max = float(settle_max)            # chờ bàn đứng yên tối đa bao nhiêu giây KỂ TỪ LẦN BÀN ĐỔI GẦN NHẤT
        self.drag_ms = int(drag_ms)                    # thời gian di chuyển từ ô tới quầy điện thoại (ms)
        self.drag_hold_ms = int(drag_hold_ms)          # GIỮ YÊN tại điểm thả bấy nhiêu ms rồi mới nhả tay (0 = nhả ngay như vuốt thường)
        self.drag_steps = max(1, int(drag_steps))      # số điểm trung gian khi di chuyển (nhiều = mượt, nhưng mỗi điểm là 1 lệnh adb)
        try:
            self._drops = [(float(drop_xy[0]), float(drop_xy[1]))] if drop_xy else list(SHOP_DROP_CANDIDATES)
        except Exception:
            self._drops = list(SHOP_DROP_CANDIDATES)
        if isinstance(drag_methods, str):
            drag_methods = [m.strip() for m in drag_methods.split(",")]
        self._methods = [m for m in (drag_methods or ["hold", "swipe", "dnd"]) if m in ("hold", "swipe", "dnd")] or ["hold"]
        self.drag_pick_ms = int(drag_pick_ms)          # cách "hold": nhấn giữ yên tại ô bấy nhiêu ms để game nhận là NHẤC món lên, rồi mới kéo
        self.drag_slow_ms = int(drag_slow_ms)          # cách "swipe": vuốt liền 1 lệnh adb, chậm để món kịp chạy theo tay
        self.drag_tries = max(1, int(drag_tries))      # số lần kéo thử (đổi cách/điểm thả) mà bàn không đổi thì TẮT kéo
        self._method_idx = 0                           # cách kéo đang dùng (chỉ số trong _methods)
        self._drag_shots = 0                           # số ảnh chẩn đoán kéo đã lưu
        self._drop_idx = 0                             # điểm thả đang dùng (chỉ số trong _drops)
        self._drop_ok = False                          # True khi đã có 1 lần kéo làm bàn đổi -> điểm thả đúng
        self._drop_tries = 0                           # số điểm thả đã thử mà không có tác dụng (khi chưa xác nhận)
        self.settle_hard = float(settle_hard)          # trần cứng tổng thời gian chờ 1 lần (chuỗi gộp dây chuyền dài vẫn được chờ hết)
        self.settle_reads = max(2, int(settle_reads))  # số lần đọc liên tiếp giống nhau để coi là đứng yên
        self.settle_gap = float(settle_gap)            # nghỉ giữa 2 lần chụp khi chờ
        self.pix_thr = float(pix_thr)                  # độ lệch ảnh bàn (0..255) tối đa giữa 2 lần chụp để coi là không còn hoạt ảnh
        self.t0 = now()
        self.taps = 0
        self._ranged = False
        self._warned_unknown = False
        self._blocked = {}                             # {(hàng, cột): cấp lúc bị chặn} - ô ấn 2 lần không có tác dụng
        self._noeff = {}                               # {(hàng, cột): số lần ấn liên tiếp không có tác dụng}
        self._blocked_rm = {}                          # {(hàng, cột): cấp lúc bị chặn} - ô kéo vào Mở tiệm 2 lần không có tác dụng

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

    def _setup_range(self, fr, geo):
        """Đặt min/max cấp món theo field hoặc cấp cửa hàng (đọc OCR 1 lần)."""
        if self._ranged:
            return
        self._ranged = True
        sl = self.shop_level or read_shop_level(fr, geo)
        lo, hi = default_level_range(sl) if sl else (self.rules.min_level, self.rules.max_level)
        self.rules.min_level = self.min_level or lo
        self.rules.max_level = self.max_level or hi
        self.log("info", f"PHS: cấp cửa hàng {sl if sl else '?'} -> món cấp {self.rules.min_level}..{self.rules.max_level}")

    def _wait_stable(self, min_wait=0.0):
        """Chờ bàn ĐỨNG YÊN (hết hoạt ảnh gộp/rơi/sinh món mới) rồi mới trả (frame, geo, board) để tính nước tiếp.

        Đứng yên = `settle_reads` lần chụp liên tiếp cho cùng 1 bàn (cấp + khoá) VÀ ảnh vùng bàn lệch nhau <= `pix_thr`; còn ô trống (đang
        rơi) thì đòi gấp đôi số lần. Hoạt ảnh nhỏ lặp mãi (ảnh bàn không bao giờ yên) thì cho qua khi bàn đọc giống nhau thêm 4 lần mà không
        còn ô trống. Hạn chờ = `settle_max` giây KỂ TỪ LẦN BÀN ĐỔI GẦN NHẤT (bàn còn đang đổi thì cứ chờ, vd chuỗi gộp dây chuyền dài),
        tổng không quá `settle_hard`; hết hạn vẫn chưa yên thì trả bản mới nhất + cảnh báo (không treo)."""
        if min_wait > 0:
            self.sleep(min_wait)
        t_start = self.now()
        deadline = t_start + self.settle_max
        hard = t_start + self.settle_hard
        prev_key = prev_roi = None
        same_board = same_pix = 0
        need = max(1, self.settle_reads - 1)
        while True:
            self._check()
            fr = self._shot()
            geo, board = read_board(fr, save_unknown=False)
            roi = board_roi(fr, geo)
            key = board.key()
            ok = board_ok(board)
            empties = any(v == 0 for row in board.lv for v in row)
            same_board = same_board + 1 if (prev_key is not None and key == prev_key) else 0
            same_pix = same_pix + 1 if (prev_roi is not None and roi_diff(roi, prev_roi) <= self.pix_thr) else 0
            if ok and prev_key is not None and (same_board == 0 or same_pix == 0):
                deadline = min(hard, max(deadline, self.now() + self.settle_max))      # bàn vừa đổi -> gia hạn
            prev_key, prev_roi = key, roi
            need_now = need * 2 if empties else need
            if ok and same_board >= need_now and same_pix >= need_now:
                break
            if ok and not empties and same_board >= need + 4:
                break
            if self.now() >= deadline:
                self.log("warn", f"PHS: chờ {self.now() - t_start:.0f}s mà bàn chưa đứng yên - dùng bản chụp mới nhất")
                break
            self.sleep(self.settle_gap)
        if not self._warned_unknown and any(v < 0 for row in board.lv for v in row):
            read_board(fr)                                      # lưu crop ô lạ vào debug_phs/ (1 lần)
        return fr, geo, board

    def _planning_board(self, board: Board) -> Board:
        """Bàn dùng để tính nước: ô đã bị chặn (ấn 2 lần không có tác dụng) coi như ô khoá. Ô đổi cấp thì bỏ chặn."""
        pb = board.copy()
        for rc, lvl in list(self._blocked.items()):
            if board.lv[rc[0]][rc[1]] == lvl:
                pb.locked[rc[0]][rc[1]] = True
            else:
                del self._blocked[rc]
        return pb

    def _no_remove(self, board: Board):
        """Tập ô không được thử kéo (đã kéo 2 lần không có tác dụng); ô đổi cấp thì bỏ chặn."""
        for rc, lvl in list(self._blocked_rm.items()):
            if board.lv[rc[0]][rc[1]] != lvl:
                del self._blocked_rm[rc]
        return set(self._blocked_rm)

    def _plan(self, board: Board, left):
        """Chọn kế hoạch. `remove_only_stuck`: thử CHỈ ấn trước; có nước ăn được (doanh thu > 0) thì dùng, chưa có mới cho phép kéo."""
        pb, nr = self._planning_board(board), self._no_remove(board)
        depth = min(left, self.depth)
        if self.rules.allow_remove and self.rules.remove_only_stuck:
            self.rules.allow_remove = False
            try:
                plan, rev = beam_search(pb, depth, self.beam, self.rules, nr)
            finally:
                self.rules.allow_remove = True
            if plan and rev > 0:
                return plan, rev
        return beam_search(pb, depth, self.beam, self.rules, nr)

    def _fix_steps(self, steps, pending):
        """Số bước vừa đọc mà LỚN HƠN số bước trước lúc ấn/kéo thì chắc chắn OCR nhầm (vd chữ 1 đọc thành 7: log 14/10 đọc 2 -> 7): coi là trước - 1.
        Trả số bước đã sửa, hoặc None nếu đọc hợp lý."""
        if pending is None or steps is None or pending[2] is None or steps <= pending[2]:
            return None
        fixed = max(0, pending[2] - 1)
        self.log("warn", f"PHS: đọc số bước {steps} nhưng trước đó còn {pending[2]} và vừa ấn/kéo 1 lần -> OCR nhầm, coi là còn {fixed}")
        return fixed

    def _drop_point(self):
        return self._drops[self._drop_idx % len(self._drops)]

    def _drag_to_shop(self, geo: Geo, r, c):
        """Kéo (vuốt) từ tâm ô (r, c) tới điểm thả ở quầy điện thoại (phía trên nút Mở tiệm)."""
        sx, sy = geo.ref_xy(*self._drop_point())
        self._gesture(self._methods[self._method_idx % len(self._methods)], geo.cx(c), geo.cy(r), sx, sy)

    def _method(self):
        return self._methods[self._method_idx % len(self._methods)]

    def _save_shot(self, frame, name):
        """Lưu 1 ảnh chẩn đoán kéo vào debug_phs/ (tối đa 8 ảnh/lần chạy)."""
        if self._drag_shots >= 8 or frame is None:
            return None
        self._drag_shots += 1
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            path = os.path.join(DEBUG_DIR, f"{name}_{time.strftime('%H%M%S')}.png")
            cv2.imencode(".png", frame)[1].tofile(path)
            return path
        except Exception:
            return None

    def _gesture(self, method, x1, y1, x2, y2):
        """Thực hiện 1 cú kéo từ (x1,y1) tới (x2,y2) bằng 1 trong các cách (không chắc cách nào game nhận -> `_methods` thử lần lượt):
        - "hold": nhấn giữ yên `drag_pick_ms` (để game nhận là nhấc món lên) -> di chuyển `drag_ms` qua `drag_steps` điểm -> GIỮ YÊN `drag_hold_ms` ở quầy
          (món chạy theo tay chậm hơn tay, nhả ngay thì thả hụt) -> nhả. Dùng lệnh `input touchscreen motionevent` như `adb.swipe_hold_px`.
          Giữa lúc giữ yên chụp 1 ảnh chẩn đoán (3 lần đầu) để xem món có chạy theo tay không.
        - "swipe": `adb.swipe_px` liền 1 lệnh, chậm `drag_slow_ms`.
        - "dnd": lệnh Android `input draganddrop` (kéo-thả chuẩn, có nhấn giữ lúc đầu)."""
        a = self.adb
        ix1, iy1, ix2, iy2 = (int(round(v)) for v in (x1, y1, x2, y2))
        if method == "swipe":
            a.swipe_px(x1, y1, x2, y2, self.drag_slow_ms)
            return
        if method == "dnd":
            a.run_cmd(["shell", "input", "draganddrop", str(ix1), str(iy1), str(ix2), str(iy2), str(self.drag_slow_ms)],
                      timeout=15 + self.drag_slow_ms / 1000.0)
            return
        ev = lambda kind, x, y: a.run_cmd(["shell", "input", "touchscreen", "motionevent", kind, str(x), str(y)])
        ev("DOWN", ix1, iy1)
        self.sleep(max(0, self.drag_pick_ms) / 1000.0)
        n = max(1, self.drag_steps)
        gap = max(0.001, (self.drag_ms / 1000.0) / n)
        for k in range(1, n + 1):
            self.sleep(gap)
            ev("MOVE", int(ix1 + (ix2 - ix1) * k / n), int(iy1 + (iy2 - iy1) * k / n))
        hold = max(0, self.drag_hold_ms) / 1000.0
        if self._drag_shots < 3 and hold > 0:
            self.sleep(hold / 2)
            try:
                p = self._save_shot(a.screencap_fast(), "drag_mid")
                if p:
                    self.log("info", f"PHS: ảnh chụp GIỮA lúc kéo (đang giữ tay ở quầy): {p}")
            except Exception:
                pass
            self.sleep(hold / 2)
        else:
            self.sleep(hold)
        ev("UP", ix2, iy2)

    def run(self) -> bool:
        lost = 0
        pending = None                    # hành động vừa rồi: (ô, khoá bàn trước, số bước trước, True nếu là KÉO vào Mở tiệm)
        first_wait = 0.0
        try:
            while True:
                self._check()
                # Chờ bàn ĐỨNG YÊN (hoạt ảnh gộp/rơi xong) rồi mới đọc + tính + ấn tiếp: ấn khi game đang chạy hoạt ảnh sẽ không ăn.
                fr, geo, board = self._wait_stable(first_wait)
                first_wait = 0.0
                if not board_ok(board):
                    lost += 1
                    self.log("warn", f"PHS: không thấy bàn 5x5 ({lost}/{self.lost_limit})")
                    if lost >= self.lost_limit:
                        self.log("info", "PHS: không ở màn chơi, kết thúc")
                        return True
                    continue
                lost = 0
                self._setup_range(fr, geo)
                unknown = [(r, c) for r in range(N) for c in range(N) if board.lv[r][c] < 0]
                if unknown and not self._warned_unknown:
                    self._warned_unknown = True
                    self.log("warn", f"PHS: {len(unknown)} ô lạ {unknown} (chưa có mẫu cấp?) - bot không ấn các ô này; ảnh lưu ở {DEBUG_DIR}/unknown_*.png, "
                                     "thêm mẫu bằng: python phs_bot.py anh.png --add-level N hàng cột")
                steps = read_steps(fr, geo)
                ready = shop_ready(fr, geo)
                steps_fix = self._fix_steps(steps, pending)
                if steps == 0 or (steps is None and ready) or (steps_fix == 0 and ready):
                    self.log("info", f"PHS: hết bước ({self.taps} lần ấn) - dừng, bạn tự Mở tiệm")
                    if self.test:
                        save_debug(fr, geo, board)
                    return True
                if pending is not None:
                    cell, key0, steps0, was_rm = pending
                    pending = None
                    what = "kéo ô" if was_rm else "ấn ô"
                    changed = board.key() != key0 or (steps is not None and steps0 is not None and steps != steps0)
                    if not changed:
                        self.log("info", f"PHS: chưa thấy bàn đổi sau khi {what} {cell} - chờ thêm rồi đọc lại")
                        fr, geo, board = self._wait_stable(1.0)
                        steps = read_steps(fr, geo)
                        ready = shop_ready(fr, geo)
                        steps_fix = self._fix_steps(steps, (cell, key0, steps0, was_rm))
                        if steps == 0 or (steps is None and ready) or (steps_fix == 0 and ready):
                            self.log("info", f"PHS: hết bước ({self.taps} lần ấn) - dừng, bạn tự Mở tiệm")
                            return True
                        if not board_ok(board):
                            continue
                        changed = board.key() != key0 or (steps is not None and steps0 is not None and steps != steps0)
                    if changed:
                        self._noeff.clear()
                        if was_rm and not self._drop_ok:
                            self._drop_ok = True
                            self.log("info", f"PHS: kéo được bằng cách '{self._method()}' tại điểm thả {self._drop_point()} (toạ độ ảnh 720x1280) - dùng tiếp cách này")
                    elif was_rm and not self._drop_ok:
                        # chưa có lần kéo nào thành công: nghi SAI CÁCH KÉO hoặc SAI ĐIỂM THẢ -> đổi cách (hold -> swipe -> dnd), hết vòng thì đổi điểm thả
                        self._drop_tries += 1
                        p = self._save_shot(fr, f"drag_fail_{self._method()}")
                        if self._drop_tries >= self.drag_tries:
                            self.rules.allow_remove = False
                            self.log("warn", f"PHS: đã thử {self._drop_tries} lần kéo (các cách {self._methods}, điểm thả {self._drops}) mà không lần nào làm bàn đổi - TẮT hành động kéo "
                                             "(chỉ ấn). Gửi các ảnh drag_*.png trong " + DEBUG_DIR + "/ để chẩn đoán; thử tăng drag_hold_ms/drag_pick_ms, đặt drop_xy [x, y], "
                                             "đổi drag_methods hoặc allow_remove=false" + (f" (ảnh sau lần kéo hụt: {p})" if p else ""))
                        else:
                            self._method_idx += 1
                            if self._method_idx % len(self._methods) == 0:
                                self._drop_idx = (self._drop_idx + 1) % len(self._drops)
                            self.log("warn", f"PHS: kéo ô {cell} không làm bàn đổi - thử cách '{self._method()}' tại điểm thả {self._drop_point()}"
                                             + (f" (ảnh sau lần kéo hụt: {p})" if p else ""))
                    else:
                        nk = (cell[0], cell[1], "x") if was_rm else cell
                        n = self._noeff.get(nk, 0) + 1
                        self._noeff[nk] = n
                        if n >= 2 and was_rm:
                            self._blocked_rm[cell] = board.lv[cell[0]][cell[1]]
                            self.log("warn", f"PHS: kéo ô {cell} tới quầy điện thoại {n} lần mà bàn + số bước không đổi - bỏ qua việc kéo ô này")
                            if len(self._blocked_rm) >= 3 and self.rules.allow_remove:
                                self.rules.allow_remove = False
                                self.log("warn", "PHS: kéo 3 ô khác nhau đều không có tác dụng - TẮT hành động kéo (chỉ ấn). "
                                                 "Kiểm tra điểm thả (field drop_xy) hoặc đặt allow_remove=false")
                        elif n >= 2:
                            self._blocked[cell] = board.lv[cell[0]][cell[1]]
                            self.log("warn", f"PHS: ấn ô {cell} {n} lần mà bàn + số bước không đổi - coi là ô không ấn được, bỏ qua ô này")
                        else:
                            self.log("warn", f"PHS: {what} {cell} không có tác dụng (bàn + số bước không đổi), thử lại 1 lần")
                steps_cur = steps_fix if steps_fix is not None else steps
                left = steps_cur if steps_cur is not None else self.steps_default
                plan, rev = self._plan(board, left)
                if not plan:
                    self.log("info", "PHS: không còn ô nào ấn được - dừng, bạn tự Mở tiệm\n" + board_text(board))
                    return True
                r, c = plan[0][0], plan[0][1]
                is_rm = len(plan[0]) == 3
                if is_rm:
                    self.log("info", f"PHS kéo #{self.taps + 1}: ô ({r},{c}) cấp {board.lv[r][c]} tới quầy điện thoại {self._drop_point()} "
                                     f"(+{self.rules.V(board.lv[r][c]):.0f}; còn {left} bước, kế hoạch {plan}, điểm dự tính ~{rev:.0f})")
                else:
                    self.log("info", f"PHS ấn #{self.taps + 1}: ô ({r},{c}) cấp {board.lv[r][c]}->{board.lv[r][c] + 1} "
                                     f"(còn {left} bước, kế hoạch {plan}, doanh thu dự tính ~{rev:.0f})")
                if self.test or self.debug:
                    p = save_debug(fr, geo, board, plan, drop=self._drop_point())
                    if self.test:
                        self.log("info", f"PHS TEST - bước còn: {steps}, nút Mở tiệm sáng: {ready}\n"
                                         + board_text(board) + (f"\nẢnh debug: {p}" if p else ""))
                        return True
                pending = ((r, c), board.key(), steps_cur, is_rm)
                if is_rm:
                    self._drag_to_shop(geo, r, c)
                else:
                    self.adb.tap_px(geo.cx(c), geo.cy(r))
                self.taps += 1
                first_wait = self.tap_wait            # chờ tối thiểu cho hoạt ảnh bắt đầu, rồi _wait_stable chờ tới khi bàn đứng yên
        except _Stop as e:
            self.log("info", f"PHS: dừng ({e})")
            return False


def run_auto_phs_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_phs` (field xem mục 6 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    allow_remove = bool(step.get("allow_remove", True))
    pw = step.get("pot_weight")
    if pw is None:
        pw = 0.2 if allow_remove else 0.05          # mặc định theo mô phỏng nhiều vòng: có kéo bán 0.2, chỉ ấn 0.05
    rules = Rules(
        merge_values=step.get("merge_values"), pot_weight=float(pw),
        pair_bonus=float(step.get("pair_bonus", 0.15)), locked_merge=bool(step.get("locked_merge", True)),
        discount=float(step.get("discount", 0.92)), near_bonus=float(step.get("near_bonus", 0.05)),
        allow_remove=allow_remove, remove_locked=bool(step.get("remove_locked", True)),
        remove_top=int(step.get("remove_top", 1)), remove_min_level=int(step.get("remove_min_level", 3)),
        remove_only_stuck=bool(step.get("remove_only_stuck", False)),
        hole_weight=float(step.get("hole_weight", 0.3)), refill_level=int(step.get("refill_level", 0)),
    )
    bot = PhsBot(
        adb, log=log, should_stop=should_stop, test=step.get("test", False), max_seconds=step.get("max_seconds", 0),
        depth=step.get("depth", 6), beam=step.get("beam", 120), steps_default=step.get("steps_default", 6),
        tap_wait=step.get("tap_wait", 0.6), debug=step.get("debug", False), lost_limit=step.get("lost_limit", 4),
        shop_level=step.get("shop_level", 0), min_level=step.get("min_level", 0), max_level=step.get("max_level", 0), rules=rules,
        settle_max=step.get("settle_max", 6.0), settle_reads=step.get("settle_reads", 4), settle_gap=step.get("settle_gap", 0.25),
        pix_thr=step.get("pix_thr", 2.0), settle_hard=step.get("settle_hard", 60.0), drag_ms=step.get("drag_ms", 700),
        drop_xy=step.get("drop_xy"), drag_hold_ms=step.get("drag_hold_ms", 500), drag_steps=step.get("drag_steps", 12),
        drag_methods=step.get("drag_methods"), drag_pick_ms=step.get("drag_pick_ms", 350), drag_slow_ms=step.get("drag_slow_ms", 1500),
        drag_tries=step.get("drag_tries", 6),
    )
    return bot.run()


def _imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    img = _imread(sys.argv[1])
    geo = make_geo(img)
    if "--add-level" in sys.argv:
        i = sys.argv.index("--add-level")
        lv, r, c = int(sys.argv[i + 1]), int(sys.argv[i + 2]), int(sys.argv[i + 3])
        os.makedirs(_tpl_dir(), exist_ok=True)
        p = os.path.join(_tpl_dir(), f"phs_lv{lv}.png")
        cv2.imencode(".png", cv2.resize(_cell_img(img, geo, r, c), (96, 96), interpolation=cv2.INTER_AREA))[1].tofile(p)
        print("Đã lưu mẫu cấp", lv, "->", p)
        sys.exit(0)
    if "--add-lock" in sys.argv:
        i = sys.argv.index("--add-lock")
        r, c = int(sys.argv[i + 1]), int(sys.argv[i + 2])
        p = os.path.join(_tpl_dir(), "phs_lock.png")
        cell = _cell_img(img, geo, r, c)
        h, w = cell.shape[:2]
        crop = cell[int(h * 0.03):int(h * 0.32), int(w * 0.66):int(w * 0.97)]
        cv2.imencode(".png", crop)[1].tofile(p)
        print("Đã lưu mẫu khoá ->", p)
        sys.exit(0)
    geo, board = read_board(img)
    print(f"Bàn {N}x{N}, ô {geo.pitch:.1f}px, bàn hợp lệ: {board_ok(board)}")
    print(board_text(board))
    steps = read_steps(img, geo)
    sl = read_shop_level(img, geo)
    print("Số bước:", steps, "| Mở tiệm sáng:", shop_ready(img, geo), "| Thể lực:", read_energy(img, geo), "| Cấp cửa hàng:", sl)
    rules = Rules()
    if sl:
        rules.min_level, rules.max_level = default_level_range(sl)
    t0 = time.time()
    plan, rev = beam_search(board, min(steps if steps else 6, 6), 120, rules)
    print("Kế hoạch ((hàng, cột) = ấn, (hàng, cột, 'x') = kéo vào Mở tiệm):", plan, "| doanh thu gộp dự tính ~%.0f" % rev, "| %.1fs" % (time.time() - t0))
    print("Ảnh debug (chữ thập xanh 'tha' = điểm thả khi kéo ô để bán, thử điểm đầu):", save_debug(img, geo, board, plan, drop=SHOP_DROP_CANDIDATES[0]))
