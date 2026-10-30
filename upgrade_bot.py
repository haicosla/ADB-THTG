# -*- coding: utf-8 -*-
"""
Bot auto "Nâng Cấp Tối Ưu" (Hợp Tác Xã Nghiên Cứu Công Nghệ Sản Xuất: nâng cấp bằng VÉ để tăng thu nhập) - điều khiển qua ADB, dùng cho bước `auto_upgrade`.

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
- Đi qua các mục bằng 2 MŨI TÊN vàng hai bên cửa sổ (sang phải đến khi quay lại mục đầu, hoặc không đổi được nữa thì dừng). Bot KHÔNG tự mở Hợp Tác Xã/chọn tab: hãy mở
  sẵn 1 mục bất kỳ của tab cần nâng (cửa sổ chi tiết có 2 hàng "Tăng cấp") rồi mới chạy bước; muốn nâng nhiều tab thì xếp nhiều bước (bấm tab/thẻ bằng bước thường) + nhiều bước auto_upgrade.

======================================================================================================
3) ĐỌC MÀN HÌNH (mọi toạ độ tính theo nút "Tăng cấp" HÀNG TRÊN, nhân tỉ lệ s = rộng_khung / 720)
======================================================================================================
- Nút: ô xanh lá 132x33 = "Tăng cấp" (bấm được), ô xám cùng cỡ = "Kích hoạt" (chưa bấm được).
- Giá: số trên mỗi nút (khung `COST_BOX`), CHỮ XANH = đủ vé, CHỮ ĐỎ = thiếu vé. Số dư vé: viên thuốc tối phía trên hàng 1 (`PILL_BOX`), loại vé nhận bằng màu hình tờ vé trong viên thuốc.
- Số có đơn vị k / tr / tỷ ("630.8k", "1.3tr", "6.55tỷ"): tesseract hay RỚT dấu chấm hoặc chữ đơn vị với chữ nhỏ này, nên `read_amount` bỏ hình tờ vé, đọc nhiều biến thể rồi BỎ PHIẾU,
  chèn lại dấu chấm theo chấm nhỏ trên ảnh, và đơn vị lấy từ biến thể nào đọc ra được chữ. Đọc không chắc (thiếu đơn vị) -> trả None, bot KHÔNG đoán.
- Mục hiện tại nhận bằng dHash hình minh hoạ (`KEY_BOX`); hết vòng khi gặp lại mục đã đi qua.
- Mức tăng thu nhập: đọc dòng "<tổng> +<tăng>" ở đầu cửa sổ (`GAIN_BOX`) SAU khi nâng. ĐOÁN: các trang Nhân Tài / Nghệ Sĩ chưa có ảnh sau-khi-nâng nên chưa chắc có dòng này; không đọc được
  thì mục đó coi là chưa đo (bot lưu ảnh `debug_upgrade/gain_fail_*.png`, dừng nâng thử mục đó sau `gain_fail_limit` lần để không phí vé).

======================================================================================================
4) FIELD CỦA BƯỚC `auto_upgrade`
======================================================================================================
test (True = chỉ đọc + liệt kê, KHÔNG bấm), max_items (80), max_passes (30), min_eff (0 = nâng tới hết vé; đơn vị thu nhập/vé), reserve (số vé giữ lại mỗi loại, 0),
max_seconds (0 = không giới hạn), cost_growth (1.02: hệ số giá mỗi cấp khi chưa đo được), gain_fail_limit (2), settle_wait (0.45s), gain_wait (2.0s),
arrow_dx / arrow_dy (186 / -173: vị trí mũi tên PHẢI so với nút Tăng cấp hàng trên, ở khung 720 rộng; mũi tên trái = -345), debug (False).
"""
import hashlib
import heapq
import os
import re
import sys
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
GAIN_BOX = (-150, -480, 120, -446)              # dòng "<tổng thu nhập> +<tăng>" ở đầu cửa sổ
ARROW_R = (186, -173)                           # tâm mũi tên phải (so với góc trái-trên nút hàng trên)
ARROW_L = (-345, -173)

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
        for i in range(1, nl):
            x, y, w, h, a = st[i]
            if w >= 18 * s_up and h >= 14 * s_up and a > 150 * s_up * s_up / 4:
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


def read_amount(crop, light_on_dark=False, thorough=False) -> Amount:
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
    mant, unit = _vote(cands, dot_left)
    out.mant, out.unit = mant, unit
    if mant and unit:
        out.value = parse_amount(mant + unit)
    out.green = _ink_green(crop, light_on_dark)
    return out


def _gain_of(c: str):
    m = re.match(r"^.*?\+(\d[\d.]*)([a-zỷ]*)$", c)
    if not m:
        return None
    mant, unit = _split(m.group(1) + m.group(2)) or (None, None)
    return (mant, unit) if mant else None


def read_gain(crop) -> Tuple[Optional[float], Optional[float], str]:
    """Đọc dòng '<tổng> +<tăng>' ở đầu cửa sổ. Trả (mức tăng, tổng, chuỗi thô). Không có đơn vị của mức tăng -> (None, ...)."""
    cands: List[str] = []
    g0 = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    for s_up, blur, psm in [(4, 0, 7), (5, 1, 7), (5, 0, 7), (4, 1, 7), (6, 1, 7), (3, 0, 7), (5, 1, 13), (6, 0, 7)]:
        g = cv2.resize(g0, None, fx=s_up, fy=s_up, interpolation=cv2.INTER_CUBIC)
        if blur:
            g = cv2.GaussianBlur(g, (0, 0), 1.0)
        _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        b = cv2.copyMakeBorder(255 - b, 30, 30, 40, 40, cv2.BORDER_CONSTANT, value=255)
        c = _tess(b, 7).replace(" ", "")
        if c:
            cands.append(c)
            if len(cands) >= 2:
                a1, a2 = _gain_of(cands[-1]), _gain_of(cands[-2])
                if a1 and a1 == a2 and a1[1]:
                    break                       # 2 lần đọc liền nhau giống hệt và có đơn vị -> chắc
    gains, totals = [], []
    for c in cands:
        m = re.match(r"^(.*?)\+(\d[\d.]*)([a-zỷ]*)$", c)
        if not m:
            continue
        gains.append((m.group(2), m.group(3)))
        tm = re.match(r"^(\d[\d.]*)([a-zỷ]*)$", m.group(1))
        if tm:
            totals.append(tm.group(1) + tm.group(2))
    if not gains:
        return None, None, "|".join(cands)
    mant, unit = _vote([a + b for a, b in gains], None)
    gain = parse_amount(mant + unit) if (mant and unit) else None
    total = None
    if totals:
        tm, tu = _vote(totals, None)
        total = parse_amount(tm + tu) if (tm and tu) else None
    return gain, total, "|".join(cands)


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
        if 100 * s <= w <= 170 * s and 22 * s <= h <= 48 * s and 3.0 <= w / max(h, 1) <= 5.0:
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


def _dhash(img) -> str:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return "".join("1" if b else "0" for b in bits)


def _hamming(a, b):
    return sum(x != y for x, y in zip(a, b))


def read_page(frame, scale=None, thorough=False) -> Page:
    """Đọc cửa sổ chi tiết 1 mục: nút, giá, số dư vé + loại vé, khoá nhận mục. scale mặc định = rộng khung / 720."""
    h, w = frame.shape[:2]
    s = float(scale) if scale else w / REF_W
    pg = Page(scale=s)
    btns = find_buttons(frame, s)
    if not btns:
        return pg
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
    key_img = _box(frame, top, KEY_BOX, s)
    pg.key = _dhash(key_img) if key_img is not None else ""
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

    def eff(self):
        if self.gain and self.cost:
            return self.gain / self.cost
        return None


class _Stop(Exception):
    pass


class UpgradeBot:
    """ui cần có: page() -> Page | None, press(page, idx) -> (Page | None, gain | None), next_item(page) -> bool (đã chuyển sang mục khác)."""

    def __init__(self, ui, log=None, should_stop=None, test=False, max_items=80, max_passes=30, min_eff=0.0, reserve=0.0,
                 max_seconds=0, cost_growth=1.02, gain_fail_limit=2, now=time.time):
        self.ui = ui
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test = bool(test)
        self.max_items, self.max_passes = int(max_items), int(max_passes)
        self.min_eff, self.reserve = float(min_eff), float(reserve)
        self.max_seconds = float(max_seconds or 0)
        self.cost_growth = float(cost_growth)
        self.gain_fail_limit = int(gain_fail_limit)
        self.now = now
        self.t0 = now()
        self.rows: Dict[str, RowState] = {}
        self.balances: Dict[str, float] = {}
        self.items: List[str] = []
        self.presses = 0

    # ---- tiện ích
    def _check(self):
        if self.should_stop():
            raise _Stop("stop")
        if self.max_seconds and self.now() - self.t0 > self.max_seconds:
            raise _Stop("timeout")

    def _canon(self, key: str) -> str:
        """Khoá mục chuẩn hoá: dHash lệch <= 6 bit so với 1 mục đã biết thì coi là CÙNG mục (ảnh chụp có nhiễu nhẹ)."""
        for k in self.items:
            if k == key or (len(k) == len(key) and _hamming(k, key) <= 6):
                return k
        return key

    def _absorb(self, pg: Page):
        """Cập nhật trạng thái các hàng + số dư vé từ 1 trang vừa đọc."""
        if pg.ticket != "?" and pg.balance is not None:
            self.balances[pg.ticket] = pg.balance
        ck = self._canon(pg.key)
        for r in pg.rows:
            k = f"{ck}#{r.idx}"
            st = self.rows.get(k)
            if st is None:
                st = self.rows[k] = RowState(k, pg.key, r.idx)
            st.ticket = pg.ticket if pg.ticket != "?" else st.ticket
            if r.cost is not None:
                st.cost = r.cost
            st.active, st.affordable = r.active, r.affordable
        if ck not in self.items:
            self.items.append(ck)

    def _cycle(self, visit):
        """Đi 1 vòng các mục (mũi tên phải) tới khi gặp lại mục đầu / không đổi được / quá max_items. visit(page) chạy ở mỗi mục."""
        seen: List[str] = []
        pg = self.ui.page()
        n = 0
        while pg is not None and pg.ok and n < self.max_items:
            self._check()
            if self._canon(pg.key) in seen:
                break
            seen.append(self._canon(pg.key))
            self._absorb(pg)
            pg = visit(pg) or pg
            n += 1
            if not self.ui.next_item(pg):
                break
            pg = self.ui.page()
        return seen

    def _plan_rows(self) -> List[PlanRow]:
        out = []
        for st in self.rows.values():
            if st.dead or st.cost is None or not st.active:
                continue
            out.append(PlanRow(st.key, st.ticket, st.cost, st.gain, st.growth or self.cost_growth,
                               can=(st.affordable is not False)))
        return out

    # ---- chạy
    def run(self) -> bool:
        try:
            return self._run()
        except _Stop as e:
            self.log("info", f"Nâng cấp tối ưu: dừng ({e}) sau {self.presses} lần nâng")
            return False

    def _run(self) -> bool:
        seen = self._cycle(lambda pg: None)
        if not seen:
            self.log("warn", "Nâng cấp tối ưu: không đọc được cửa sổ chi tiết (hãy MỞ SẴN 1 mục có 2 hàng 'Tăng cấp'). Xem ảnh debug_upgrade/")
            return False
        self.log("info", f"Nâng cấp tối ưu: thấy {len(seen)} mục, {len(self.rows)} hàng; vé: " +
                 ", ".join(f"{k}={format_amount(v)}" for k, v in sorted(self.balances.items())))
        self._table()
        if self.test:
            self.log("info", "Nâng cấp tối ưu [TEST]: chỉ đọc, không bấm. Mức tăng chỉ đo được khi nâng THẬT (lượt đầu nâng thử mỗi hàng 1 cấp).")
            return True
        for ps in range(1, self.max_passes + 1):
            self._check()
            before = self.presses
            self._do_pass(ps)
            if self.presses == before:
                break
        self._table()
        self.log("info", f"Nâng cấp tối ưu: xong, {self.presses} lần nâng")
        return True

    def _table(self):
        for st in sorted(self.rows.values(), key=lambda r: r.key):
            e = st.eff()
            self.log("info", f"  {st.key[:8]}#{st.idx} vé={st.ticket} giá={format_amount(st.cost)} "
                             f"{'bấm được' if st.active else 'chưa mở'} {'đủ vé' if st.affordable else ('thiếu vé' if st.affordable is False else '')} "
                             f"tăng={format_amount(st.gain)} hiệu quả={'?' if e is None else f'{e:.3g}'}")

    def _do_pass(self, ps):
        rows = self._plan_rows()
        known = [r for r in rows if r.gain is not None]
        counts, cutoff = plan_upgrades(known, self.balances, self.reserve, self.min_eff)
        probes = {r.key for r in rows if r.gain is None and r.can}
        self.log("info", f"Lượt {ps}: kế hoạch {sum(counts.values())} lần nâng + {len(probes)} lần nâng thử; ngưỡng biên: " +
                 (", ".join(f"{k}={v:.3g}" for k, v in cutoff.items()) or "-"))
        if not counts and not probes:
            return

        def visit(pg: Page):
            for r in list(pg.rows):
                k = f"{self._canon(pg.key)}#{r.idx}"
                st = self.rows.get(k)
                if st is None or st.dead:
                    continue
                n = counts.get(k, 0) + (1 if k in probes else 0)
                if n <= 0:
                    continue
                pg = self._press_row(pg, st, n, cutoff.get(st.ticket))
            return pg

        self._cycle(visit)

    def _press_row(self, pg: Page, st: RowState, n: int, cut: Optional[float]) -> Page:
        for _ in range(n):
            self._check()
            r = pg.row(st.idx)
            if r is None or not r.active or r.cost is None or r.affordable is False:
                break
            bal = pg.balance if pg.balance is not None else self.balances.get(st.ticket)
            if bal is not None and r.cost > bal - self.reserve:
                break
            old_cost, old_bal = r.cost, bal
            new_pg, gain = self.ui.press(pg, st.idx)
            if new_pg is None or not new_pg.ok:
                st.dead = True
                self.log("warn", f"Nâng cấp tối ưu: mất cửa sổ sau khi bấm {st.key[:8]}#{st.idx}")
                break
            nr = new_pg.row(st.idx)
            done = (nr is not None and nr.cost is not None and nr.cost != old_cost) or \
                   (new_pg.balance is not None and old_bal is not None and new_pg.balance < old_bal)
            if not done:
                st.gain_fail += 1
                if st.gain_fail >= 2:
                    st.dead = True
                    self.log("warn", f"Nâng cấp tối ưu: bấm {st.key[:8]}#{st.idx} 2 lần không ăn -> bỏ hàng này")
                break
            self.presses += 1
            st.presses += 1
            if nr is not None and nr.cost is not None and old_cost:
                g = nr.cost / old_cost
                if 1.0 <= g <= 2.0:
                    st.growth = g
            if gain is not None:
                st.gain, st.gain_fail = gain, 0
            else:
                st.gain_fail += 1
                if st.gain_fail >= self.gain_fail_limit:
                    st.dead = True
                    self.log("warn", f"Nâng cấp tối ưu: không đọc được mức tăng của {st.key[:8]}#{st.idx} {st.gain_fail} lần -> bỏ (xem debug_upgrade/gain_fail_*.png)")
            self._absorb(new_pg)
            pg = new_pg
            nr = pg.row(st.idx)
            if nr is not None:
                st.cost, st.active, st.affordable = nr.cost, nr.active, nr.affordable
            if st.dead:
                break
            if cut is not None and st.eff() is not None and st.eff() < cut * 0.999:
                break                           # hiệu quả đo được đã tụt dưới ngưỡng cân bằng -> nhường hàng khác
        return pg


# ----------------------------------------------------------------------------
# 6) UI thật qua ADB
# ----------------------------------------------------------------------------
class AdbUI:
    def __init__(self, adb, log=None, sleep=time.sleep, settle_wait=0.45, gain_wait=2.0, arrow_dx=None, arrow_dy=None,
                 debug=False, scale=None):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.sleep = sleep
        self.settle_wait, self.gain_wait = float(settle_wait), float(gain_wait)
        self.arrow_r = (float(arrow_dx) if arrow_dx is not None else ARROW_R[0], float(arrow_dy) if arrow_dy is not None else ARROW_R[1])
        self.debug, self.scale = bool(debug), scale
        self._shots = 0
        self._dbg_dir = "debug_upgrade"
        self._last_gain: Optional[float] = None     # mức tăng đọc được ở lần nâng trước (để biết dòng đầu cửa sổ đã cập nhật chưa)

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
        pg = read_page(fr, self.scale)
        if self.debug or not pg.ok:
            self._save(fr, f"page_{'ok' if pg.ok else 'unclear'}_{int(time.time() * 1000) % 10 ** 9}")
        return pg

    def press(self, pg: Page, idx: int):
        """Bấm 'Tăng cấp' hàng idx; đợi dòng đầu cửa sổ cập nhật rồi đọc mức tăng; trả (trang mới, mức tăng | None)."""
        r = pg.row(idx)
        self.adb.tap_px(r.x + r.w / 2, r.y + r.h / 2)
        t0 = time.time()
        gain = None
        fr = None
        while True:
            self.sleep(self.settle_wait)
            fr = self._frame()
            if fr is None:
                break
            box = _box(fr, pg.top, GAIN_BOX, pg.scale)
            if box is not None:
                g, _total, _raw = read_gain(box)
                # cùng giá trị với lần nâng trước: có thể là CHƯA cập nhật, đợi tới 1 giây rồi mới nhận (mức tăng phẳng lặp lại là bình thường)
                if g is not None and (g != self._last_gain or time.time() - t0 >= 1.0):
                    gain = g
                    break
            if time.time() - t0 > self.gain_wait:
                break
        if fr is None:
            return None, None
        if gain is None:
            self._save(fr, f"gain_fail_{int(time.time() * 1000) % 10 ** 9}")
        else:
            self._last_gain = gain
        # chờ hết hoạt ảnh rồi đọc trang
        prev = fr
        for _ in range(4):
            self.sleep(0.25)
            fr2 = self._frame()
            if fr2 is None:
                break
            ok = self._still(prev, fr2)
            prev = fr2
            if ok:
                break
        return read_page(prev, self.scale), gain

    def next_item(self, pg: Page) -> bool:
        s = pg.scale
        self.adb.tap_px(pg.top[0] + self.arrow_r[0] * s, pg.top[1] + self.arrow_r[1] * s)
        self.sleep(0.5)
        for _ in range(5):
            fr = self._frame()
            if fr is None:
                return False
            npg = read_page(fr, self.scale)
            if npg.ok and len(npg.key) == len(pg.key) and _hamming(npg.key, pg.key) > 6:
                return True
            self.sleep(0.4)
        return False


def run_auto_upgrade_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_upgrade` (field xem mục 4 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    ui = AdbUI(adb, log=log, settle_wait=step.get("settle_wait", 0.45), gain_wait=step.get("gain_wait", 2.0),
               arrow_dx=step.get("arrow_dx"), arrow_dy=step.get("arrow_dy"), debug=bool(step.get("debug", False)))
    bot = UpgradeBot(ui, log=log, should_stop=should_stop, test=step.get("test", True), max_items=step.get("max_items", 80),
                     max_passes=step.get("max_passes", 30), min_eff=step.get("min_eff", 0.0), reserve=step.get("reserve", 0.0),
                     max_seconds=step.get("max_seconds", 0), cost_growth=step.get("cost_growth", 1.02),
                     gain_fail_limit=step.get("gain_fail_limit", 2))
    return bot.run()


# ----------------------------------------------------------------------------
# 7) Tự kiểm tra
# ----------------------------------------------------------------------------
def _imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def _selftest():
    """Kiểm tra parse số, bộ tối ưu so với vét cạn, và vòng chạy với game giả (không cần ADB/ảnh)."""
    import itertools
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
    # (c) vòng chạy với game giả
    games = _FakeGame()
    log = []
    bot = UpgradeBot(games, log=lambda l, m: log.append(m), test=False, max_passes=20, now=lambda: 0.0)
    assert bot.run()
    spent = games.spent
    assert games.presses > 10, games.presses
    for tk in games.balance:
        assert games.balance[tk] >= 0
    # tổng thu nhập tăng được phải gần bằng kế hoạch lý tưởng (biết trước mọi mức tăng ngay từ đầu), chỉ chênh phần nâng thử
    ideal = _FakeGame()
    ideal_rows = [PlanRow(k, g.ticket, g.cost, g.gain, g.growth) for k, g in ideal.rows.items()]
    ic, _ = plan_upgrades(ideal_rows, dict(ideal.balance))
    ideal_gain = sum(n * ideal.rows[k].gain for k, n in ic.items())
    got_gain = sum(g.n * g.gain for g in games.rows.values())
    assert got_gain >= 0.95 * ideal_gain, (got_gain, ideal_gain)
    # các hàng được nâng nhiều lần thì hiệu quả biên cuối phải cân bằng nhau (cùng loại vé)
    for tk in ("blue", "pink"):
        effs = [g.gain / g.cost for g in games.rows.values() if g.ticket == tk and g.n >= 2]
        if len(effs) >= 2:
            assert max(effs) / min(effs) < 2.5, (tk, effs)
    # (d) TEST không bấm
    g2 = _FakeGame()
    UpgradeBot(g2, log=lambda l, m: None, test=True, now=lambda: 0.0).run()
    assert g2.presses == 0
    print("selftest OK: nâng", games.presses, "lần, tăng", round(got_gain), "/ lý tưởng", round(ideal_gain), "; vé còn:", {k: round(v) for k, v in games.balance.items()})


class _FakeRow:
    def __init__(self, ticket, cost, gain, growth):
        self.ticket, self.cost, self.gain, self.growth = ticket, cost, gain, growth
        self.n = 0                              # số lần đã nâng


class _FakeGame:
    """Game giả: 4 mục x 2 hàng, 2 loại vé, giá tăng theo cấp, mức tăng cố định mỗi hàng. Chỉ dùng cho --selftest."""

    def __init__(self):
        self.balance = {"blue": 9000.0, "pink": 3000.0}
        spec = [("blue", 100, 50, 1.05), ("blue", 200, 150, 1.08), ("blue", 60, 20, 1.03), ("blue", 300, 400, 1.10),
                ("pink", 80, 30, 1.04), ("pink", 150, 90, 1.07), ("pink", 500, 100, 1.02), ("blue", 90, 10, 1.01)]
        self.rows = {f"it{i // 2}#{i % 2}": _FakeRow(*s) for i, s in enumerate(spec)}
        self.n_items = 4
        self.cur = 0
        self.presses = 0
        self.spent = 0.0

    def _page(self):
        pg = Page(ok=True, key=f"{int(hashlib.md5(str(self.cur).encode()).hexdigest(), 16):0128b}"[:64], scale=1.0, top=(0, 0))
        pg.ticket = self.rows[f"it{self.cur}#0"].ticket
        pg.balance = self.balance[pg.ticket]
        for i in (0, 1):
            g = self.rows[f"it{self.cur}#{i}"]
            pg.rows.append(RowInfo(i, 0, 0, 1, 1, True, g.cost, g.cost <= self.balance[g.ticket]))
        return pg

    def page(self):
        return self._page()

    def next_item(self, pg):
        self.cur = (self.cur + 1) % self.n_items
        return True

    def press(self, pg, idx):
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
