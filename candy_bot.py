# -*- coding: utf-8 -*-
"""
Bot auto "Cửa Hàng Kỳ Thú" (game xếp hình 3 kiểu Candy Crush, có ĐƠN HÀNG KHÁCH) - điều khiển qua ADB, dùng cho bước `auto_candy`.

>>> TRẠNG THÁI: nhận diện + chọn nước đã thử trên 2 ảnh chụp 720x1280 (đúng 84/84 ô, kiểm tra chéo giữa 2 ảnh: 0 lỗi).
>>> Luật bom/mũi tên/combo, sinh bom (4 bánh) / mũi tên (5 bánh), bánh rơi ngẫu nhiên, đơn giới hạn 10 nước: NGƯỜI DÙNG XÁC NHẬN (mục 4).
>>> Chưa chạy thử trên LDPlayer thật -> chạy `test: true` trước, rồi chạy thật vài nước xem log.

======================================================================================================
1) GAME LÀ GÌ (người dùng nói + suy ra từ 2 ảnh chụp 720x1280)
======================================================================================================
- Tiêu đề "Cửa Hàng Kỳ Thú". Bàn 7 CỘT x 6 HÀNG, ô gần vuông (~94px). Chạm vào 1 bánh rồi VUỐT sang ô kề (trái/phải/trên/dưới)
  để ĐỔI CHỖ 2 bánh; xếp được 3 bánh giống nhau trở lên thành hàng ngang/dọc thì ăn (biến mất), bánh trên rơi xuống, bánh mới rơi vào.
- 4 loại bánh thường: BÁNH QUY (cookie, nâu cam có hạt chocolate) = 'C', SÔ-CÔ-LA trong cốc xanh = 'B', BÁNH MACARON XANH LÁ = 'G',
  KẸO ĐỎ hình múi cam = 'R'.
- 2 loại ĐẶC BIỆT thấy trên bàn: BOM đen (dây ngòi, viền vàng) = 'X' và BÁNH MŨI TÊN 4 HƯỚNG sọc đỏ-vàng = 'A'.
- Phía trên có "Đơn hàng khách hàng": tối đa 3 loại bánh cần ăn, mỗi loại hiện "đã ăn/cần" (vd 0/10, 4/15) hoặc DẤU TÍCH XANH khi xong;
  góc phải là phần thưởng hoàn thành đơn. => ưu tiên ăn đúng loại bánh còn thiếu trong đơn.
- Khác: thể lực (54/60, hồi 1 điểm / vài phút), 2 nút x8 / x16 (chưa rõ, bot KHÔNG bấm), cuốn sách "Làm giàu" x5 góc dưới phải
  (chưa rõ, bot KHÔNG bấm), nút mũi tên quay lại góc dưới trái (bot KHÔNG bấm).

======================================================================================================
2) HÌNH HỌC (toạ độ THAM CHIẾU ảnh 720x1280; bot co giãn theo kích thước ảnh: x theo w/720, y theo h/1280)
======================================================================================================
- Tâm ô (hàng r, cột c): x = 73 + 94.0*c, y = 630 + 94.1*r. Nền ô trống màu đỏ sẫm (BGR ~57,56,132 / 66,69,148).
- Đơn hàng: 3 biểu tượng ở x = 37 / 110 / 183, y ~ 430; chữ "a/b" (đỏ) hoặc dấu tích xanh ngay bên dưới ở y ~ 473.

======================================================================================================
3) NHẬN DIỆN (`classify_cell`, `read_grid`, `read_orders`)
======================================================================================================
- Mỗi ô: cắt mảng 68x68 quanh tâm, đếm tỉ lệ điểm ảnh theo 7 dải màu HSV (xanh lá, đỏ-hồng, xanh dương của cốc, cam-nâu, tối, vàng kim,
  trắng) -> vector 7 số -> gần tâm cụm nào nhất (CENTROIDS lấy từ 2 ảnh). Ô không có bánh (nền trơn) hoặc không khớp cụm nào = '?'
  (đang chạy hiệu ứng) -> bot chờ rồi chụp lại cho tới khi bàn đứng yên (2 lần đọc giống hệt nhau, không còn '?').
- Đơn hàng: biểu tượng phân loại bằng `classify_icon` (đếm điểm ảnh xanh lá/đỏ/xanh cốc/cam-nâu, vì nền bảng màu kem); dấu tích = có
  điểm ảnh xanh lá-ngọc (H 60-80) dưới biểu tượng; số "a/b" đọc bằng tesseract (pytesseract, whitelist 0123456789/); không đọc được thì coi là còn thiếu
  `default_need` (10) cái. Tesseract/pytesseract lỗi cũng KHÔNG làm bot dừng.

======================================================================================================
4) NHỮNG CHỖ ĐANG ĐOÁN - CẦN NGƯỜI DÙNG XÁC NHẬN
======================================================================================================
 LUẬT NGƯỜI DÙNG XÁC NHẬN (2026-10-14):
 a. Kéo BOM sang ô kề: nổ 3x3 quanh vị trí mới. Kéo MŨI TÊN sang ô kề: xoá cả HÀNG và CỘT của nó.
 b. Kéo bánh đặc biệt vào bánh đặc biệt (tâm hiệu ứng = ô đích, `_combo_cells`): BOM+BOM nổ 5x5; MŨI TÊN+MŨI TÊN xoá 3 hàng + 3 cột;
    BOM+MŨI TÊN xoá 3 hàng/cột THEO CHIỀU KÉO + 1 đường còn lại (kéo ngang: 3 hàng + 1 cột; kéo dọc: 3 cột + 1 hàng).
 c. Ăn ĐÚNG 4 bánh thẳng hàng -> sinh BOM; ăn >= 5 -> sinh MŨI TÊN. Ngoài ra KHÔNG có bánh đặc biệt nào khác sinh ra (bánh rơi
    xuống luôn là bánh thường; hình L/T không sinh gì - đó là cách mình hiểu câu "không có sinh bánh đặc biệt" khác).
    ĐOÁN: bánh đặc biệt sinh ở ô vừa kéo nằm trong đoạn (không thì giữa đoạn).
 d. Bánh mới rơi xuống NGẪU NHIÊN (mô phỏng: đều 4 loại thường - ĐOÁN tỉ lệ đều).
 e. Mỗi ĐƠN giới hạn 10 NƯỚC (`order_moves`). Xong đơn lại có đơn mới ngay.
 f. Thao tác = vuốt từ ô này sang ô kề (`swipe_px`, `drag_ms`).
 CHƯA BIẾT: màn hình có chỗ hiện số nước còn lại không (bot tự đếm: đặt lại về 10 khi thấy đơn mới); nước tính vào đơn có tính cả
 bánh bị bom/mũi tên xoá không (bot đang coi là CÓ).

======================================================================================================================================================================================================
5) THUẬT TOÁN (v2: Monte Carlo nhìn sâu, có tính bánh rơi ngẫu nhiên + giới hạn 10 nước)
======================================================================================================
- Mô phỏng đầy đủ (`apply_swap`/`resolve` với rng): đổi chỗ, ăn, SINH bom/mũi tên (luật c), combo (luật b), rơi, bánh mới NGẪU NHIÊN, ăn dây chuyền.
- Bước 1 (tham lam, bánh mới chưa biết): xếp hạng ~71 nước bằng `score_move` -> giữ `top_k` (10) nước tốt nhất + mọi combo 2 bánh đặc biệt.
- Bước 2 (`plan_moves`): với mỗi nước giữ lại chạy nhiều MẪU `rollout`: đi nước đó (bánh mới rơi ngẫu nhiên), rồi chơi tiếp tham lam
  tới `depth` (4) nước hoặc tới hết số nước còn lại của đơn (`moves_left`). Điểm mẫu = thưởng chiết khấu (bánh đúng đơn còn thiếu `w_need`,
  bánh khác `w_other`, dây chuyền `w_combo`, bánh đặc biệt dùng `w_special` / sinh ra `w_made`) + `w_done` mỗi nước tiết kiệm khi XONG ĐƠN SỚM
  + chất lượng bàn cuối (`w_future` số nước còn đi được, `w_board_special` bom/mũi tên còn giữ để ghép combo). Lấy điểm TRUNG BÌNH nhiều mẫu
  cho từng nước, chọn nước kỳ vọng cao nhất. Chạy tới hết `think_s` giây (mặc định 2s, ~800 mẫu trên máy thử; ~3ms/mẫu).
- Số nước còn lại của đơn (`moves_left`): bot tự đếm (bắt đầu `order_moves`=10 hoặc `moves_left_start`), giảm 1 mỗi nước, ĐẶT LẠI 10 khi thấy ĐƠN MỚI
  (đổi loại bánh / từ 'xong' sang 'chưa xong' / số cần tăng >= 5 khi OCR đọc được) - nên bot ưu tiên khác nhau khi còn nhiều nước và khi sắp hết.
- Thử trên ván giả (bánh rơi đều ngẫu nhiên, 10 nước, cần 36+36+36): tham lam cũ xong đơn 14/20 ván, còn thiếu TB 2.4 bánh;
  Monte Carlo 1s/nước xong 19/20 ván, còn thiếu TB 0.7. (Ván giả dễ hơn game thật nhiều vì mô phỏng của mình cho dây chuyền dễ - chỉ dùng so sánh tương đối.)

======
6) FIELD CỦA BƯỚC `auto_candy` (đều tuỳ chọn)
======================================================================================================
  test (false)         - true = CHẾ ĐỘ TEST: chụp 1 lần, nhận diện, chọn nước, lưu ảnh debug_candy/, KHÔNG bấm
  max_moves (0)        - số nước tối đa (0 = chạy tới khi hết/ bị Dừng)
  max_seconds (0)      - giới hạn thời gian (0 = không giới hạn)
  settle_s (1.4)       - chờ sau mỗi nước trước khi chụp lại (hoạt ảnh ăn/rơi)
  stable_timeout (8)   - tối đa bao nhiêu giây chờ bàn đứng yên
  drag_ms (180)        - thời gian vuốt
  stop_when_done (false) - true = dừng khi cả đơn hàng đã đủ (đủ dấu tích)
  default_need (10)    - số cần thêm khi không đọc được "a/b"
  think_s (2.0)        - số giây suy nghĩ mỗi nước (Monte Carlo); 0 = tham lam 1 nước, nhanh nhưng yếu hơn
  depth (4)            - số nước nhìn trước trong mỗi mẫu; top_k (10) - số nước đưa vào Monte Carlo; max_samples (600) - trần số vòng mẫu
  order_moves (10)     - giới hạn số nước của 1 đơn; moves_left_start - số nước còn lại LÚC BẮT ĐẦU (nếu bật bot giữa chừng 1 đơn)
  bomb_radius (1)      - bán kính nổ của bom (1 = 3x3)
  use_specials (true)  - false = KHÔNG đi nước có đụng bom/mũi tên (an toàn khi chưa chắc luật bánh đặc biệt)
  w_need (100) w_other (10) w_combo (25) w_special (15) w_made (20) w_future (4) w_low (0.3) w_done (60) w_board_special (12)
  debug (false)        - lưu ảnh debug_candy/ mỗi nước (test luôn lưu)
  lost_limit (4)       - số lần liên tiếp không thấy bàn thì kết thúc bước

Chạy riêng kiểm tra nhận diện + nước đi trên ảnh chụp màn hình:  python candy_bot.py anh.png
"""

from __future__ import annotations

import os
import random
import re
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

# ----------------------------------------------------------------------------
# Hằng số hình học (đo trên ảnh 720x1280)
# ----------------------------------------------------------------------------
REF_W, REF_H = 720, 1280
COLS, ROWS = 7, 6
X0, PX = 73.0, 94.0          # tâm cột 0, bước cột
Y0, PY = 630.0, 94.1         # tâm hàng 0, bước hàng
HALF = 34                    # nửa cạnh mảng cắt quanh tâm ô
ORDER_X = (37.0, 110.0, 183.0)
ORDER_ICON_Y = 430.0
ORDER_TEXT_Y = 473.0
DEBUG_DIR = "debug_candy"

KINDS = "CBGR"               # 4 loại bánh thường
SPECIALS = "XA"              # bom, mũi tên
NAMES = {"C": "bánh quy", "B": "sô-cô-la", "G": "macaron xanh", "R": "kẹo đỏ", "X": "bom", "A": "mũi tên"}

# Tâm cụm đặc trưng (xanh lá, đỏ-hồng, xanh cốc, cam-nâu, tối, vàng kim, trắng) - lấy từ 2 ảnh chụp
CENTROIDS = {
    "C": (0.000, 0.001, 0.000, 0.617, 0.000, 0.037, 0.000),
    "B": (0.000, 0.058, 0.257, 0.341, 0.000, 0.000, 0.010),
    "G": (0.251, 0.000, 0.000, 0.011, 0.000, 0.065, 0.026),
    "R": (0.000, 0.458, 0.000, 0.000, 0.000, 0.000, 0.002),
    "X": (0.000, 0.000, 0.000, 0.136, 0.027, 0.098, 0.073),
    "A": (0.000, 0.140, 0.000, 0.212, 0.001, 0.079, 0.085),
}
MAX_DIST = 0.22              # xa hơn mức này so với mọi cụm -> '?'
BG_COLORS = ((57, 56, 132), (66, 69, 148), (74, 142, 214))   # BGR nền ô (và viền) - dùng phát hiện ô trống


@dataclass
class Geo:
    sx: float
    sy: float

    def cx(self, c):
        return (X0 + PX * c) * self.sx

    def cy(self, r):
        return (Y0 + PY * r) * self.sy


def make_geo(frame) -> Geo:
    h, w = frame.shape[:2]
    return Geo(sx=w / REF_W, sy=h / REF_H)


# ----------------------------------------------------------------------------
# 1) Nhận diện
# ----------------------------------------------------------------------------
def _features(patch_bgr, simple=False):
    hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    H, S, V = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    n = max(1, len(H))
    f = [
        ((H >= 35) & (H <= 50) & (S > 90) & (V > 90)).sum() / n,
        (((H <= 6) | (H >= 165)) & (S > 110) & (V > 170)).sum() / n,
        ((H >= 92) & (H <= 112) & (S > 80) & (V > 120)).sum() / n,
        ((H >= 7) & (H <= 19) & (S > 60) & (V > 110)).sum() / n,
        (V < 70).sum() / n,
        ((H >= 18) & (H <= 30) & (S > 120) & (V > 200)).sum() / n,
        ((S < 60) & (V > 190)).sum() / n,
    ]
    if simple:                     # nền kem của bảng đơn hàng: bỏ tối/vàng kim/trắng
        f[4] = f[5] = f[6] = 0.0
    return np.array(f, np.float32)


def _is_empty(patch_bgr) -> bool:
    px = patch_bgr.reshape(-1, 3).astype(np.float32)
    near = np.zeros(len(px), bool)
    for bg in BG_COLORS:
        near |= (np.abs(px - np.array(bg, np.float32)).sum(1) < 45)
    return near.mean() > 0.80


def classify_cell(patch_bgr, simple=False, kinds=None):
    """-> (nhãn 'C','B','G','R','X','A' hoặc '?', khoảng cách tới cụm gần nhất)."""
    if patch_bgr.size == 0:
        return "?", 9.0
    if not simple and _is_empty(patch_bgr):
        return "?", 9.0
    f = _features(patch_bgr, simple)
    best, bd = "?", 9.0
    for k, cen in CENTROIDS.items():
        if kinds and k not in kinds:
            continue
        c = np.array(cen, np.float32)
        if simple:
            c = c.copy()
            c[4:] = 0.0
        d = float(np.sqrt(((f - c) ** 2).sum()))
        if d < bd:
            best, bd = k, d
    return (best if bd <= MAX_DIST else "?"), bd


def read_grid(frame):
    geo = make_geo(frame)
    hx, hy = int(HALF * geo.sx), int(HALF * geo.sy)
    grid = []
    for r in range(ROWS):
        row = []
        y = int(geo.cy(r))
        for c in range(COLS):
            x = int(geo.cx(c))
            patch = frame[max(0, y - hy):y + hy, max(0, x - hx):x + hx]
            row.append(classify_cell(patch)[0])
        grid.append(row)
    return geo, grid


def grid_text(grid):
    return "\n".join("".join(row) for row in grid)


def unknown_count(grid):
    return sum(1 for row in grid for k in row if k == "?")


# ----- đơn hàng -----
def _tess_digits(img_gray):
    try:
        import pytesseract
        big = cv2.resize(img_gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        big = cv2.copyMakeBorder(big, 24, 24, 48, 48, cv2.BORDER_CONSTANT, value=255)   # chữ sát mép trái dễ bị mất số đầu
        txt = pytesseract.image_to_string(big, config="--psm 7 -c tessedit_char_whitelist=0123456789/")
        return txt.strip()
    except Exception:
        return ""


def classify_icon(patch_bgr):
    """Biểu tượng bánh nhỏ trên nền kem của bảng đơn hàng: đếm điểm ảnh từng dải màu (xanh lá > đỏ > xanh cốc > cam-nâu)."""
    if patch_bgr.size == 0:
        return "?"
    hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    H, S, V = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    n = max(1, len(H))
    green = ((H >= 35) & (H <= 50) & (S > 90) & (V > 90)).sum() / n
    red = (((H <= 6) | (H >= 165)) & (S > 110) & (V > 170)).sum() / n
    blue = ((H >= 92) & (H <= 112) & (S > 80) & (V > 120)).sum() / n
    orange = ((H >= 7) & (H <= 19) & (S > 60) & (V > 110)).sum() / n
    th = 0.05
    if green > th:
        return "G"
    if red > th:
        return "R"
    if blue > th:
        return "B"
    if orange > 0.10:
        return "C"
    return "?"


def read_orders(frame, default_need=10, use_ocr=True):
    """-> list tối đa 3 phần tử {kind, done(bool), need(int hoặc None), text}. Loại bánh dựa biểu tượng; kind None = ô đơn không có."""
    geo = make_geo(frame)
    out = []
    for ox in ORDER_X:
        x, y = int(ox * geo.sx), int(ORDER_ICON_Y * geo.sy)
        icon = frame[max(0, y - int(26 * geo.sy)):y + int(26 * geo.sy), max(0, x - int(26 * geo.sx)):x + int(26 * geo.sx)]
        kind = classify_icon(icon)
        ty = int(ORDER_TEXT_Y * geo.sy)
        reg = frame[max(0, ty - int(24 * geo.sy)):ty + int(24 * geo.sy), max(0, x - int(40 * geo.sx)):x + int(40 * geo.sx)]
        hsv = cv2.cvtColor(reg, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        tick = int(((hsv[:, 0] >= 60) & (hsv[:, 0] <= 80) & (hsv[:, 1] > 70) & (hsv[:, 2] > 110)).sum())
        done = tick > 0.02 * len(hsv)
        need, text, ocr_ok = None, "", False
        if kind == "?":
            out.append({"kind": None, "done": False, "need": None, "text": "", "ocr": False})
            continue
        if not done:
            if use_ocr:
                b, g, r = reg[:, :, 0].astype(int), reg[:, :, 1].astype(int), reg[:, :, 2].astype(int)
                mask = ((r - g > 30) & (g < 150)).astype(np.uint8) * 255      # chữ đỏ sẫm
                text = _tess_digits(255 - mask)
                m = re.search(r"(\d*)\s*/\s*(\d+)", text)
                if m:
                    # tesseract hay làm mất số 0 đầu của "0/10" -> thiếu số bên trái coi là 0
                    need = max(0, int(m.group(2)) - int(m.group(1) or 0))
                    ocr_ok = True
            if need is None:
                need = int(default_need)
        else:
            need = 0
        out.append({"kind": kind, "done": done, "need": need, "text": text, "ocr": ocr_ok or done})
    return out


def orders_text(orders):
    parts = []
    for o in orders:
        if not o["kind"]:
            continue
        parts.append(f"{NAMES[o['kind']]}: " + ("✔" if o["done"] else f"còn {o['need']}"))
    return ", ".join(parts) or "(không thấy đơn)"


# ----------------------------------------------------------------------------
# 2) Mô phỏng (luật người dùng xác nhận - xem mục 4 docstring)
# ----------------------------------------------------------------------------
Grid = List[List[str]]


def _runs(g: Grid):
    """Mọi đoạn >= 3 bánh THƯỜNG cùng loại liền nhau (ngang + dọc) -> list (list_ô, loại)."""
    out = []
    for r in range(ROWS):
        c = 0
        while c < COLS:
            k = g[r][c]
            if k not in KINDS:
                c += 1
                continue
            e = c
            while e + 1 < COLS and g[r][e + 1] == k:
                e += 1
            if e - c + 1 >= 3:
                out.append(([(r, x) for x in range(c, e + 1)], k))
            c = e + 1
    for c in range(COLS):
        r = 0
        while r < ROWS:
            k = g[r][c]
            if k not in KINDS:
                r += 1
                continue
            e = r
            while e + 1 < ROWS and g[e + 1][c] == k:
                e += 1
            if e - r + 1 >= 3:
                out.append(([(x, c) for x in range(r, e + 1)], k))
            r = e + 1
    return out


def find_matches(g: Grid):
    """Tập ô thuộc hàng/cột >= 3 bánh cùng loại THƯỜNG (ô '.', '?', bánh đặc biệt không tạo hàng)."""
    hit = set()
    for cells, _ in _runs(g):
        hit.update(cells)
    return hit


def _blast_cells(g: Grid, r, c, bomb_radius=1):
    k = g[r][c]
    cells = set()
    if k == "X":
        for dr in range(-bomb_radius, bomb_radius + 1):
            for dc in range(-bomb_radius, bomb_radius + 1):
                if 0 <= r + dr < ROWS and 0 <= c + dc < COLS:
                    cells.add((r + dr, c + dc))
    elif k == "A":
        cells.update((r, x) for x in range(COLS))
        cells.update((y, c) for y in range(ROWS))
    return cells


def _gravity(g: Grid):
    for c in range(COLS):
        col = [g[r][c] for r in range(ROWS) if g[r][c] != "."]
        col = ["."] * (ROWS - len(col)) + col
        for r in range(ROWS):
            g[r][c] = col[r]


def _refill(g: Grid, rng):
    """Bánh mới rơi xuống NGẪU NHIÊN (đều 4 loại thường) vào mọi ô trống."""
    for r in range(ROWS):
        for c in range(COLS):
            if g[r][c] == ".":
                g[r][c] = rng.choice(KINDS)


def resolve(g: Grid, first_extra=None, bomb_radius=1, rng=None, swapped=()):
    """Ăn + (sinh bánh đặc biệt) + rơi + (bánh mới ngẫu nhiên nếu có rng) + ăn dây chuyền.
    - Đoạn đúng 4 bánh thẳng hàng -> sinh BOM; đoạn >= 5 -> sinh MŨI TÊN (luật người dùng). Chỗ sinh = ô vừa kéo (swapped) nằm trong
      đoạn, không thì giữa đoạn (ĐOÁN). Hình L/T không sinh gì.
    - first_extra = tập ô đã bị bánh đặc biệt kích hoạt ở tầng đầu.
    - rng None = chỉ tính phần đã biết (ô trống bên trên giữ nguyên trống).
    -> (grid_mới, {loại: số bánh ăn}, số_tầng, số_bánh_đặc_biệt_dùng, hàng_trung_bình_vùng_ăn, số_bánh_đặc_biệt_sinh_ra)."""
    g = [row[:] for row in g]
    counts = {}
    layers = specials_used = made = 0
    row_sum = 0.0
    n_cleared = 0
    extra = set(first_extra or ())
    swapped = set(swapped)
    while layers < 14:
        hit = set()
        spawn = {}
        for cells, _k in _runs(g):
            hit.update(cells)
            n = len(cells)
            if n >= 4:
                sp = "X" if n == 4 else "A"
                pick = [x for x in cells if x in swapped]
                cell = pick[0] if pick else cells[n // 2]
                if spawn.get(cell) != "A":
                    spawn[cell] = sp
        swapped = set()
        hit |= extra
        extra = set()
        # bánh đặc biệt nằm trong vùng ăn cũng nổ (dây chuyền)
        stack = list(hit)
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


def _combo_cells(ka, kb, a, b, bomb_radius=1):
    """Kéo 2 bánh đặc biệt vào nhau (a = ô bị kéo, b = ô đích, tâm hiệu ứng = b). Luật người dùng xác nhận:
    bom+bom = nổ 5x5; mũi tên+mũi tên = xoá 3 hàng + 3 cột; bom+mũi tên = 3 hàng/cột THEO CHIỀU KÉO + 1 đường còn lại
    (kéo ngang: 3 hàng + 1 cột; kéo dọc: 3 cột + 1 hàng)."""
    rb, cb_ = b
    horizontal = (a[0] == b[0])
    cells = set()

    def rows(r0, r1):
        for r in range(max(0, r0), min(ROWS, r1 + 1)):
            cells.update((r, x) for x in range(COLS))

    def cols(c0, c1):
        for c in range(max(0, c0), min(COLS, c1 + 1)):
            cells.update((y, c) for y in range(ROWS))

    if ka == "X" and kb == "X":
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                if 0 <= rb + dr < ROWS and 0 <= cb_ + dc < COLS:
                    cells.add((rb + dr, cb_ + dc))
    elif ka == "A" and kb == "A":
        rows(rb - 1, rb + 1)
        cols(cb_ - 1, cb_ + 1)
    else:                                   # bom + mũi tên
        if horizontal:
            rows(rb - 1, rb + 1)
            cols(cb_, cb_)
        else:
            cols(cb_ - 1, cb_ + 1)
            rows(rb, rb)
    return cells


def apply_swap(g: Grid, a, b, bomb_radius=1, rng=None):
    """Kéo bánh ở ô a sang ô kề b rồi mô phỏng. Trả None nếu nước vô hiệu (không ăn được gì). rng != None = có bánh mới rơi."""
    (r1, c1), (r2, c2) = a, b
    if g[r1][c1] in ("?", ".") or g[r2][c2] in ("?", "."):
        return None
    if g[r1][c1] == g[r2][c2] and g[r1][c1] not in SPECIALS:
        return None
    if g[r1][c1] in SPECIALS and g[r2][c2] in SPECIALS:
        cells = _combo_cells(g[r1][c1], g[r2][c2], a, b, bomb_radius)
        ng = [row[:] for row in g]
        ng[r1][c1] = ng[r2][c2] = "."       # 2 bánh đã dùng vào combo, không nổ thêm kiểu đơn
        res = resolve(ng, cells, bomb_radius, rng)
        return (res[0], res[1], res[2], res[3] + 2, res[4], res[5])
    ng = [row[:] for row in g]
    ng[r1][c1], ng[r2][c2] = ng[r2][c2], ng[r1][c1]
    extra = set()
    # luật người dùng xác nhận: kéo bánh đặc biệt sang ô kề = kích hoạt nó tại vị trí MỚI
    for (r, c) in (a, b):
        if ng[r][c] in SPECIALS:
            extra.add((r, c))
    if not extra and not find_matches(ng):
        return None
    return resolve(ng, extra, bomb_radius, rng, swapped=(a, b))


def neighbor_pairs():
    for r in range(ROWS):
        for c in range(COLS):
            if c + 1 < COLS:
                yield (r, c), (r, c + 1)
            if r + 1 < ROWS:
                yield (r, c), (r + 1, c)


def count_future_moves(g: Grid, cap=6):
    n = 0
    for a, b in neighbor_pairs():
        (r1, c1), (r2, c2) = a, b
        if g[r1][c1] in KINDS + SPECIALS and g[r2][c2] in KINDS + SPECIALS and (g[r1][c1] != g[r2][c2] or g[r1][c1] in SPECIALS):
            ng = [row[:] for row in g]
            ng[r1][c1], ng[r2][c2] = ng[r2][c2], ng[r1][c1]
            if find_matches(ng) or ng[r1][c1] in SPECIALS or ng[r2][c2] in SPECIALS:
                n += 1
                if n >= cap:
                    break
    return n


@dataclass
class Weights:
    w_need: float = 100.0          # mỗi bánh đúng loại còn thiếu trong đơn
    w_other: float = 10.0          # bánh khác / đã đủ đơn
    w_combo: float = 25.0          # mỗi tầng ăn dây chuyền thêm
    w_special: float = 15.0        # mỗi bánh đặc biệt đã dùng (nổ)
    w_made: float = 20.0           # mỗi bánh đặc biệt SINH RA (ăn 4 = bom, 5 = mũi tên)
    w_future: float = 4.0          # số nước còn ăn được trên bàn (tối đa 6)
    w_low: float = 0.3             # thưởng nhẹ ăn gần đáy (chỉ dùng cho xếp hạng tham lam)
    w_done: float = 60.0           # thưởng mỗi nước TIẾT KIỆM được khi xong đơn sớm
    w_board_special: float = 12.0  # thưởng mỗi bánh đặc biệt còn trên bàn cuối đoạn mô phỏng (để dành combo)


def score_move(res, need, w: Weights, board_after: Grid, with_future=True):
    g2, counts, layers, spec, avg_row, made = res
    s = 0.0
    for k, n in counts.items():
        want = need.get(k, 0)
        useful = min(n, want)
        s += w.w_need * useful + w.w_other * (n - useful)
    s += w.w_combo * max(0, layers - 1) + w.w_special * spec + w.w_made * made
    s += w.w_low * avg_row
    if with_future:
        s += w.w_future * count_future_moves(board_after)
    return s


def candidate_moves(g: Grid, need: dict, w: Optional[Weights] = None, bomb_radius=1, use_specials=True, with_future=True):
    """Chỉ tính phần đã biết (không bánh mới). -> list (điểm, ô a, ô b, counts) sắp xếp giảm dần (a = ô bị kéo, b = ô đích)."""
    w = w or Weights()
    out = []
    for a, b in neighbor_pairs():
        if not use_specials and (g[a[0]][a[1]] in SPECIALS or g[b[0]][b[1]] in SPECIALS):
            continue
        pairs = [(a, b)]
        if g[a[0]][a[1]] in SPECIALS and g[b[0]][b[1]] in SPECIALS:
            pairs.append((b, a))             # combo: tâm hiệu ứng = ô đích nên 2 chiều kéo khác nhau
        for x, y in pairs:
            res = apply_swap(g, x, y, bomb_radius)
            if res is None:
                continue
            out.append((score_move(res, need, w, res[0], with_future), x, y, res[1]))
    out.sort(key=lambda t: -t[0])
    return out


# ----------------------------------------------------------------------------
# 2b) Bộ lập kế hoạch: Monte Carlo nhìn sâu (bánh mới rơi ngẫu nhiên, đơn giới hạn số nước)
# ----------------------------------------------------------------------------
def _use_need(counts, nd):
    useful = other = 0
    for k, n in counts.items():
        u = min(n, nd.get(k, 0))
        useful += u
        other += n - u
        if u:
            nd[k] -= u
    return useful, other


def rollout(grid: Grid, need: dict, first, horizon, moves_left, w: Weights, bomb_radius, use_specials, rng, gamma=0.92):
    """1 mẫu: đi nước `first` (có bánh mới rơi NGẪU NHIÊN), rồi chơi tiếp tham lam tới `horizon` nước (bánh mới vẫn ngẫu nhiên).
    Điểm = tổng thưởng chiết khấu (bánh đúng đơn, dây chuyền, bánh đặc biệt sinh ra/dùng) + thưởng xong đơn sớm + chất lượng bàn cuối."""
    nd = {k: v for k, v in need.items() if v > 0}
    had_need = bool(nd)
    g = grid
    total, scale = 0.0, 1.0
    for t in range(horizon):
        if t == 0:
            mv = first
        else:
            cands = candidate_moves(g, nd, w, bomb_radius, use_specials, with_future=False)
            if not cands:
                total -= 150.0 * scale      # kẹt không còn nước ăn
                break
            mv = (cands[0][1], cands[0][2])
        res = apply_swap(g, mv[0], mv[1], bomb_radius, rng)
        if res is None:
            break
        g = res[0]
        useful, other = _use_need(res[1], nd)
        total += scale * (w.w_need * useful + w.w_other * other + w.w_combo * max(0, res[2] - 1)
                          + w.w_special * res[3] + w.w_made * res[5])
        scale *= gamma
        if had_need and all(v <= 0 for v in nd.values()):
            total += w.w_done * max(0, moves_left - (t + 1))
            break
    specials_left = sum(row.count("X") + row.count("A") for row in g)
    total += scale * (w.w_future * count_future_moves(g) + w.w_board_special * specials_left)
    return total


def plan_moves(grid: Grid, need: dict, moves_left: int, w: Weights, bomb_radius=1, use_specials=True, rng=None,
               think_s=2.0, depth=4, top_k=10, max_samples=600, min_rounds=3, now=time.time):
    """-> (list xếp hạng [(điểm_kỳ_vọng, a, b, counts)], số_mẫu, giây). think_s <= 0 = chỉ tham lam 1 nước (nhanh)."""
    rng = rng or random.Random()
    t0 = now()
    det = candidate_moves(grid, need, w, bomb_radius, use_specials)
    if len(det) <= 1 or think_s <= 0:
        return det, 0, now() - t0
    cands = list(det[:top_k])
    for m in det[top_k:]:                                   # luôn giữ combo 2 bánh đặc biệt
        if grid[m[1][0]][m[1][1]] in SPECIALS and grid[m[2][0]][m[2][1]] in SPECIALS:
            cands.append(m)
    horizon = max(1, min(int(moves_left), int(depth)))
    sums = [0.0] * len(cands)
    cnts = [0] * len(cands)
    rounds = 0
    total = 0
    while rounds < max_samples:
        for i, m in enumerate(cands):
            sums[i] += rollout(grid, need, (m[1], m[2]), horizon, moves_left, w, bomb_radius, use_specials, rng)
            cnts[i] += 1
            total += 1
        rounds += 1
        if rounds >= min_rounds and now() - t0 >= think_s:
            break
    ranked = [(sums[i] / cnts[i], m[1], m[2], m[3]) for i, m in enumerate(cands)]
    ranked.sort(key=lambda t: -t[0])
    return ranked, total, now() - t0


# ----------------------------------------------------------------------------
# 3) Chạy bước
# ----------------------------------------------------------------------------
class _Stop(Exception):
    pass


def save_debug(frame, geo, grid, move=None, tag="candy"):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        im = frame.copy()
        for r in range(ROWS):
            for c in range(COLS):
                cv2.putText(im, grid[r][c], (int(geo.cx(c)) - 8, int(geo.cy(r)) + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
        if move:
            (r1, c1), (r2, c2) = move
            cv2.arrowedLine(im, (int(geo.cx(c1)), int(geo.cy(r1))), (int(geo.cx(c2)), int(geo.cy(r2))), (0, 0, 255), 4)
        path = os.path.join(DEBUG_DIR, f"{tag}_{time.strftime('%H%M%S')}.png")
        cv2.imencode(".png", im)[1].tofile(path)
        return path
    except Exception:
        return None


def _order_sig(orders):
    return tuple(sorted((o["kind"] or "", bool(o["done"])) for o in orders if o["kind"]))


class CandyBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_moves=0, max_seconds=0, settle_s=1.4,
                 stable_timeout=8.0, drag_ms=180, stop_when_done=False, default_need=10, bomb_radius=1, use_specials=True,
                 weights=None, debug=False, lost_limit=4, think_s=2.0, depth=4, top_k=10, max_samples=600,
                 order_moves=10, moves_left_start=None, seed=None, sleep=time.sleep, now=time.time):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test, self.debug = bool(test), bool(debug)
        self.max_moves, self.max_seconds = int(max_moves or 0), float(max_seconds or 0)
        self.settle_s, self.stable_timeout = float(settle_s), float(stable_timeout)
        self.drag_ms = int(drag_ms)
        self.stop_when_done = bool(stop_when_done)
        self.default_need = int(default_need)
        self.bomb_radius = int(bomb_radius)
        self.use_specials = bool(use_specials)
        self.w = weights or Weights()
        self.lost_limit = int(lost_limit)
        self.think_s, self.depth, self.top_k, self.max_samples = float(think_s), int(depth), int(top_k), int(max_samples)
        self.order_moves = max(1, int(order_moves))
        self.moves_left = self.order_moves if moves_left_start is None else max(1, int(moves_left_start))
        self.sleep, self.now = sleep, now
        self.t0 = now()
        self.moves = 0
        self.rng = random.Random(seed)
        self._sig = None
        self._total_need = None

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

    def _stable_read(self):
        """Chụp lặp tới khi bàn đứng yên (2 lần đọc giống nhau, không còn '?'). -> (frame, geo, grid, ổn_định?)."""
        t_end = self.now() + self.stable_timeout
        prev = None
        while True:
            self._check()
            fr = self._shot()
            geo, grid = read_grid(fr)
            if unknown_count(grid) == 0 and prev is not None and grid == prev:
                return fr, geo, grid, True
            prev = grid
            if self.now() >= t_end:
                return fr, geo, grid, False
            self.sleep(0.35)

    def _do_swap(self, geo, a, b):
        (r1, c1), (r2, c2) = a, b
        self.adb.swipe_px(geo.cx(c1), geo.cy(r1), geo.cx(c2), geo.cy(r2), self.drag_ms)

    def _track_order(self, orders):
        """Đơn giới hạn `order_moves` nước: thấy ĐƠN MỚI (đổi loại bánh, hoặc từ 'xong' sang 'chưa xong', hoặc số cần tăng rõ rệt
        khi đọc OCR được) thì đặt lại số nước còn lại."""
        sig = _order_sig(orders)
        ocr_ok = all(o.get("ocr") for o in orders if o["kind"] and not o["done"])
        total = sum(o["need"] or 0 for o in orders if o["kind"] and not o["done"]) if ocr_ok else None
        new = False
        if self._sig is not None:
            kinds_prev = {k for k, _ in self._sig}
            kinds_now = {k for k, _ in sig}
            all_done_prev = bool(self._sig) and all(d for _, d in self._sig)
            all_done_now = bool(sig) and all(d for _, d in sig)
            if kinds_prev != kinds_now or (all_done_prev and not all_done_now):
                new = True
            elif total is not None and self._total_need is not None and total >= self._total_need + 5:
                new = True
        if new:
            self.moves_left = self.order_moves
            self.log("info", f"Candy: thấy ĐƠN MỚI ({orders_text(orders)}), đặt lại {self.order_moves} nước")
        self._sig = sig
        if total is not None:
            self._total_need = total

    def run(self) -> bool:
        lost = 0
        try:
            while True:
                self._check()
                if self.max_moves and self.moves >= self.max_moves:
                    self.log("info", f"Candy: đủ {self.moves} nước, dừng")
                    return True
                fr, geo, grid, stable = self._stable_read()
                unk = unknown_count(grid)
                if unk > ROWS * COLS * 0.4:
                    lost += 1
                    self.log("warn", f"Candy: không thấy bàn rõ ({unk}/{ROWS * COLS} ô lạ) ({lost}/{self.lost_limit})")
                    if lost >= self.lost_limit:
                        self.log("info", "Candy: coi như đã hết lượt/thoát bàn, kết thúc")
                        return True
                    self.sleep(0.8)
                    continue
                lost = 0
                if not stable:
                    self.log("warn", f"Candy: bàn chưa đứng yên sau {self.stable_timeout:.0f}s ({unk} ô lạ), vẫn thử đi")
                orders = read_orders(fr, self.default_need)
                self._track_order(orders)
                need = {o["kind"]: o["need"] for o in orders if o["kind"] and not o["done"]}
                if self.stop_when_done and orders and all(o["done"] for o in orders if o["kind"]) and any(o["kind"] for o in orders):
                    self.log("info", "Candy: đơn hàng đã đủ, dừng (stop_when_done)")
                    return True
                ranked, nsamp, dt = plan_moves(grid, need, self.moves_left, self.w, self.bomb_radius, self.use_specials, self.rng,
                                               self.think_s, self.depth, self.top_k, self.max_samples, now=self.now)
                if not ranked:
                    self.log("warn", "Candy: không có nước ăn nào trên bàn nhìn thấy (có thể bàn tự xáo)")
                    if self.test:
                        save_debug(fr, geo, grid)
                        return False
                    self.sleep(1.0)
                    lost += 1
                    if lost >= self.lost_limit:
                        return False
                    continue
                sc, a, b, counts = ranked[0]
                desc = ", ".join(f"{NAMES[k]} x{n}" for k, n in counts.items()) or "bánh đặc biệt"
                self.log("info", f"Candy nước {self.moves + 1} (còn {self.moves_left}/{self.order_moves}): kéo ({a[0]},{a[1]}) -> ({b[0]},{b[1]}) "
                                 f"ăn chắc {desc} | kỳ vọng {sc:.0f}, {nsamp} mẫu/{dt:.1f}s | đơn: {orders_text(orders)}")
                if self.test or self.debug:
                    p = save_debug(fr, geo, grid, (a, b))
                    if self.test:
                        top5 = [(round(m[0], 1), m[1], m[2]) for m in ranked[:5]]
                        self.log("info", "Candy TEST - bàn nhận diện:\n" + grid_text(grid) + f"\n5 nước tốt nhất: {top5}" + (f"\nẢnh debug: {p}" if p else ""))
                        return True
                self._do_swap(geo, a, b)
                self.moves += 1
                self.moves_left -= 1
                if self.moves_left <= 0:
                    self.moves_left = self.order_moves     # hết nước mà chưa thấy đơn mới: coi như vòng mới
                self.sleep(self.settle_s)
        except _Stop as e:
            self.log("info", f"Candy: dừng ({e})")
            return False


def run_auto_candy_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_candy` (field xem mục 6 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    d = Weights()
    w = Weights(**{f: float(step.get(f, getattr(d, f))) for f in d.__dataclass_fields__})
    bot = CandyBot(
        adb, log=log, should_stop=should_stop,
        test=step.get("test", False), max_moves=step.get("max_moves", 0), max_seconds=step.get("max_seconds", 0),
        settle_s=step.get("settle_s", 1.4), stable_timeout=step.get("stable_timeout", 8), drag_ms=step.get("drag_ms", 180),
        stop_when_done=step.get("stop_when_done", False), default_need=step.get("default_need", 10),
        bomb_radius=step.get("bomb_radius", 1), use_specials=step.get("use_specials", True), weights=w,
        debug=step.get("debug", False), lost_limit=step.get("lost_limit", 4),
        think_s=step.get("think_s", 2.0), depth=step.get("depth", 4), top_k=step.get("top_k", 10),
        max_samples=step.get("max_samples", 600), order_moves=step.get("order_moves", 10),
        moves_left_start=step.get("moves_left_start", None),
    )
    return bot.run()


if __name__ == "__main__":
    # Kiểm tra nhận diện + nước đi trên ảnh chụp màn hình: python candy_bot.py anh.png
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    img = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
    geo, grid = read_grid(img)
    print(f"Bàn {COLS}x{ROWS}. Ô: C=bánh quy B=sô-cô-la G=macaron R=kẹo đỏ X=bom A=mũi tên ?=lạ")
    print(grid_text(grid))
    orders = read_orders(img)
    print("Đơn hàng:", orders_text(orders), "|", [(o["kind"], o["done"], o["need"], o["text"]) for o in orders])
    need = {o["kind"]: o["need"] for o in orders if o["kind"] and not o["done"]}
    ranked, nsamp, dt = plan_moves(grid, need, 10, Weights(), think_s=float(sys.argv[2]) if len(sys.argv) > 2 else 2.0)
    print(f"{len(ranked)} nước xét ({nsamp} mẫu, {dt:.1f}s). Top 5 (điểm kỳ vọng, ô kéo, ô đích, bánh ăn chắc):")
    for m in ranked[:5]:
        print("  ", round(m[0], 1), m[1], m[2], m[3])
    print("Ảnh debug:", save_debug(img, geo, grid, (ranked[0][1], ranked[0][2]) if ranked else None))
