# -*- coding: utf-8 -*-
"""
Bot auto "Cờ Tướng - Đối Thủ Ngang Tài" (game xe sinh tồn) - điều khiển qua ADB, dùng cho bước `auto_xiangqi`.

>>> TRẠNG THÁI: KHUNG SƯỜN ĐẦU TIÊN. Chạy được từ đầu đến cuối nhưng LUẬT GAME CÒN NHIỀU CHỖ ĐOÁN (xem mục 5).
>>> Người dùng sẽ cung cấp luật chính xác rồi chỉnh từng phần. Chưa chạy thử trên LDPlayer thật.

======================================================================================================
1) GAME LÀ GÌ (những điều người dùng đã nói)
======================================================================================================
- Màn hình tiêu đề trong game: "Đối Thủ Ngang Tài". Dạng cờ tướng nhưng NGƯỜI CHƠI CHỈ CÓ 1 CON XE (chữ ĐỎ: 車).
  (Trang web cùng kiểu: https://www.wesane.com/game/209/ tên "Chinese Chess Fighting", chạy Flash. Chưa chắc cùng luật
  với bản mobile trong ảnh, và công cụ của AI không xem được nội dung bên trong - chỉ thấy màn loading.)
- Mục tiêu: ĂN quân địch và SỐNG LÂU mà không bị ăn. Ảnh có chữ "Điều kiện vượt ải: Còn N vòng" -> sống đủ số vòng
  yêu cầu thì qua ải (ảnh 1 còn 95 vòng, ảnh 2 còn 1 vòng). Có "Điểm" (870, 2900...) cộng khi ăn quân.
- "1 vòng" = 1 lượt đi của người chơi (người dùng xác nhận).
- Mỗi lượt: người chơi đi xe 1 nước -> sau đó 1 quân địch NGẪU NHIÊN tự đi. Nếu quân đó ăn được xe thì THUA.
  Địch THƯỜNG CHẠY những quân đang bị xe chiếu (người dùng nói "thường nó sẽ chạy mấy con đang bị chiếu").
- Khay phía trên bàn có các quân CHỜ (ảnh 1: 3 quân tốt 卒) và đồng hồ cát với 1 con số (ảnh 1: 3). Con số là số LƯỢT
  ĐI cho tới khi các quân trên khay XUẤT HIỆN trên bàn ở vị trí NGẪU NHIÊN (người dùng xác nhận). Loại quân biết trước
  (nhìn khay), vị trí thì không. Ảnh 2: khay trống + "Còn 1 vòng" (đợt cuối).
- Điểm từng loại quân KHI ĂN: CHƯA BIẾT.
- Có các nút ở dưới màn hình: "Cường hóa" (có số 2), "Đặc quyền thay thế" (ổ khóa, có hình xe mờ), nút quay lại. Chưa rõ tác dụng.

======================================================================================================
2) HÌNH HỌC BÀN CỜ (đo trên 2 ảnh chụp: 922x2048 và 720x1600)
======================================================================================================
- Bàn có 8 CỘT x 9 HÀNG GIAO ĐIỂM (không phải 9x10 như cờ tướng thật), quân đặt TRÊN giao điểm, ô VUÔNG
  (bước ngang = bước dọc: 111.4px ở ảnh 922 rộng, 87px ở ảnh 720 rộng). Không thấy cung hay sông.
- Vạch lưới màu ĐỎ; khung bàn gỗ. Tỉ lệ ngang theo bề rộng ảnh khá ổn định (đường biên trái ~0.076, phải ~0.922 bề rộng)
  nhưng toạ độ DỌC phụ thuộc tỉ lệ màn hình, nên bot DÒ lưới từ vạch đỏ (`find_grid`) chứ không dùng toạ độ cứng.
- Quân là ĐĨA gỗ tròn (bán kính ~0.30-0.44 bước lưới) với 1 chữ Hán. Trên mỗi đĩa có hình "ma" xanh mờ (linh thú) đè lên
  phía trên đĩa. Quân của người chơi (xe) có chữ ĐỎ + khung chọn xanh lá; quân địch chữ XANH LỤC đậm.
- Khi xe được chọn, game vẽ các DẤU NGOẶC XANH LÁ ở mọi ô xe đi/ăn được (xem ảnh 2) -> luật đi của xe đúng cờ tướng:
  đi thẳng ngang/dọc, gặp quân thì ăn quân đầu tiên và dừng. Có thể dùng dấu này để KIỂM TRA nước đi hợp lệ (chưa làm).
- Chữ trên quân địch đã thấy: 卒(tốt) 士(sĩ) 車(xe) 炮(pháo) 馬(mã) 象(tượng) 将(tướng). Quân của mình: 車 đỏ.
  Quân địch có thể ở BẤT KỲ chỗ nào trên bàn (sĩ, tượng, tướng nằm cả giữa bàn) nên mô phỏng coi như KHÔNG có cung/sông.

======================================================================================================
3) NHẬN DIỆN (đã thử trên 2 ảnh người dùng gửi)
======================================================================================================
- `find_grid`: lọc điểm ảnh ĐỎ, chiếu theo hàng/cột, rồi khớp dãy cách đều (9 hàng, 8 cột, ô vuông). Quân che mất vạch dọc
  nên bước ngang lấy theo bước dọc. Kết quả thử: đúng cả 2 ảnh.
- `read_board`: HoughCircles tìm đĩa quân tại các giao điểm. Thử: ảnh thưa tìm đúng 2/2 quân, ảnh đông tìm đúng 26/26.
- MÀU CHỮ: đỏ = quân của mình, xanh lục = địch (phân biệt rất rõ trong thử nghiệm).
- LOẠI QUÂN: khớp MẪU MỰC CHỮ (mặt nạ 40x40 sau khi nhị phân Otsu trong hình tròn, lấy mẫu giống nhất - 1-NN) với
  `templates/xq_kinds.json` (26 mẫu: 25 cắt từ ảnh 720 rộng + 1 sĩ từ ảnh 922 rộng). Thử leave-one-out (bỏ chính nó ra
  khỏi tập mẫu): ĐÚNG 24/26 (92%); khi dùng mẫu TRUNG BÌNH mỗi loại chỉ 22/26 nên chọn 1-NN. Hay nhầm 車/卒/象 với nhau.
  Mới thử trên 2 ảnh nên CẦN THÊM NHIỀU MẪU (nhất là mỗi loại ở nhiều độ phân giải/nền sáng-tối). Thêm mẫu bằng:
      python xiangqi_bot.py anh.png <hàng> <cột> <loại: r c n p b a k>      (hàng/cột đếm từ 0, từ trên-trái)
  Quân không nhận ra (điểm khớp thấp) được coi là loại `unknown_as` (mặc định 'r' = nguy hiểm nhất, để xe né cho chắc).
- CHƯA LÀM: đọc khay (loại quân chờ), đọc số đồng hồ cát, đọc "Còn N vòng", đọc điểm bằng OCR. Hiện: bot không biết đã
  tới lượt quân xuất hiện hay chưa nên lượt nào cũng trừ 1 ít điểm rủi ro (`spawn_risk_every_turn`).

======================================================================================================
4) THUẬT TOÁN (đã thử trong bộ mô phỏng riêng xe_sim.py của cuộc trò chuyện, 150 ván, mục tiêu 95 vòng)
======================================================================================================
Mô phỏng dùng luật ĐOÁN ở mục 5 nên số liệu chỉ để SO SÁNH các cách chơi, không phải dự đoán điểm thật:
    đi ngẫu nhiên             ~2% qua ải
    chỉ tránh ô bị chiếu      65%
    + ăn quân + giữ đường thoát   67%
    + tính rủi ro quân mới hiện   75%   <- hàm `choose_move` bên dưới làm đúng việc này
    tìm kiếm lấy mẫu (chậm 15x)   67% (điểm cao hơn nhưng không sống lâu hơn)
Phát hiện quan trọng: ~88% ván thua xảy ra khi xe đang đứng ô AN TOÀN, do quân MỚI hiện ra đúng ô chiếu xe rồi được chọn đi ăn.
Vì thế chấm điểm mỗi nước đi (`choose_move`):
  1. LOẠI nước đi vào ô đang bị quân địch chiếu (tính sau khi quân bị ăn đã biến mất). Hết nước an toàn: chọn nước ít bị chiếu nhất.
  2. + giá trị quân ăn được (`VALUE`, ĐOÁN) + 1.5 x số đường thoát an toàn sau nước đi (tối đa 8).
  3. - LOSS x xác suất mất xe vì quân mới hiện ra chiếu xe (`spawn_risk`).
Ý tưởng chiến thuật (chưa chứng minh trên game thật): chỉ 1 quân địch đi mỗi lượt và địch hay chạy quân bị chiếu, nên xe CHIẾU ĐÔI
(chiếu >=2 quân cùng lúc) thì lượt sau chắc ăn được quân còn lại; chiếu 1 quân thì quân đó chạy mất. Mã là mồi ngon vì xe
chiếu thẳng thì mã không đánh trả (cản chân/đi chữ L).

======================================================================================================
5) NHỮNG CHỖ ĐANG ĐOÁN - CẦN NGƯỜI DÙNG XÁC NHẬN / CUNG CẤP LUẬT
======================================================================================================
 a. Điểm từng quân khi ăn (`VALUE` bên dưới là số tự đặt: tốt 10, sĩ/tượng 20, mã 40, pháo 45, xe 90, tướng 100).
 b. Quân địch đi thế nào: hiện coi sĩ/tượng/tướng đi tự do KHÔNG giới hạn cung/sông; tốt tiến 1 ô xuống (về hàng lớn hơn),
    đi ngang từ hàng 5 trở đi; mã có cản chân, tượng có cản mắt, pháo cần đúng 1 ngòi để ăn. Hướng tiến của tốt chưa kiểm chứng.
 c. Cách địch chọn quân đi: hiện coi ngẫu nhiên, quân bị xe chiếu được chọn nhiều gấp ~3 lần và ưu tiên chạy ra khỏi tầm xe.
 d. Quân được chọn mà ăn được xe thì có LUÔN ăn không (hiện: có).
 e. Quân mới hiện ra: có ăn xe NGAY trong lượt hiện không, hay phải đợi tới lượt địch đi (hiện: đợi). Số quân/loại quân mỗi đợt.
 f. Số quân lúc bắt đầu ván, số vòng yêu cầu mỗi ải, điều kiện thua khác (hết giờ? hết nước?).
 g. "Cường hóa" / "Đặc quyền thay thế" làm gì (có thể đổi xe bằng quân khác?). Bot hiện KHÔNG đụng tới.
 h. Thao tác điều khiển: hiện giả định CHẠM xe (chọn) rồi CHẠM ô đích (`input_mode` = "tap_tap"). Nếu game dùng KÉO THẢ thì
    đặt `input_mode` = "drag".
 i. Bàn 8x9 có chắc là kích thước mọi ải không.

======================================================================================================
6) FIELD CỦA BƯỚC `auto_xiangqi` (đều tuỳ chọn)
======================================================================================================
  test (false)        - true = CHẾ ĐỘ TEST: chụp 1 lần, nhận diện, tính nước đi, lưu ảnh debug, KHÔNG bấm
  max_rounds (0)      - số lượt đi tối đa (0 = chạy tới khi hết ván / bị Dừng)
  max_seconds (0)     - giới hạn thời gian (0 = không giới hạn)
  settle_s (1.3)      - chờ sau mỗi nước (hoạt ảnh địch đi/quân hiện)
  input_mode ("tap_tap") - "tap_tap" (chạm xe rồi chạm ô đích) hoặc "drag" (kéo từ xe tới ô đích)
  unknown_as ("r")    - loại quân coi là gì khi không nhận ra chữ
  min_match (0.55)    - điểm khớp mẫu tối thiểu để chấp nhận loại quân
  spawn_risk_every_turn (0.3) - hệ số rủi ro quân mới hiện ra cộng mỗi lượt khi chưa đọc được đồng hồ khay
  debug (false)       - lưu ảnh debug_xiangqi/ mỗi lượt (test luôn lưu)
  lost_limit (4)      - số lần liên tiếp không thấy bàn/xe thì kết thúc bước (ván đã xong hoặc đã thoát bàn)

Chạy riêng để kiểm tra nhận diện + nước đi trên 1 ảnh chụp màn hình:  python xiangqi_bot.py anh.png
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

# ----------------------------------------------------------------------------
# Hằng số
# ----------------------------------------------------------------------------
ROWS, COLS = 9, 8
MASK_S = 40                                   # kích thước mặt nạ mẫu chữ
TEMPLATE_FILE = os.path.join("templates", "xq_kinds.json")
DEBUG_DIR = "debug_xiangqi"
LOSS = 1000.0

# r=xe c=pháo n=mã p=tốt b=tượng a=sĩ k=tướng ; 'X' = xe của người chơi
KIND_NAMES = {"r": "車", "c": "炮", "n": "馬", "p": "卒", "b": "象", "a": "士", "k": "将", "X": "車(ta)"}


@dataclass
class Config:
    pawn_dir: int = 1                 # ĐOÁN: tốt địch tiến về phía hàng lớn hơn
    pawn_side_from_row: int = 5       # ĐOÁN: từ hàng này tốt đi ngang được
    value: dict = field(default_factory=lambda: {"p": 10, "a": 20, "b": 20, "n": 40, "c": 45, "r": 90, "k": 100})  # ĐOÁN


# ----------------------------------------------------------------------------
# 1) Dò lưới từ vạch đỏ
# ----------------------------------------------------------------------------
@dataclass
class Grid:
    xs: list          # toạ độ x (px) của 8 cột
    ys: list          # toạ độ y (px) của 9 hàng
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


def find_grid(frame) -> Optional[Grid]:
    h, w = frame.shape[:2]
    b, g, r = [frame[:, :, i].astype(int) for i in range(3)]
    red = ((r - g > 60) & (r - b > 60) & (r > 110) & (r < 230) & (g < 110)).astype(np.uint8)
    row_pk = _peaks(red.sum(1), w * 0.30)
    fy = _fit_lattice(row_pk, ROWS)
    if not fy or fy[2] < 6:
        return None
    oy, py, _ = fy
    ys = [oy + i * py for i in range(ROWS)]
    # chỉ xét các hàng điểm ảnh trong vùng bàn khi dò cột
    y0, y1 = int(max(0, ys[0] - py * 0.3)), int(min(h, ys[-1] + py * 0.3))
    col_pk = _peaks(red[y0:y1].sum(0), (y1 - y0) * 0.25)
    fx = _fit_lattice(col_pk, COLS, pitch=py, tol=0.15)
    if not fx or fx[2] < 2:
        return None
    ox = fx[0]
    xs = [ox + i * py for i in range(COLS)]
    if xs[-1] > w or xs[0] < 0:
        return None
    return Grid(xs=xs, ys=ys, pitch=float(py))


# ----------------------------------------------------------------------------
# 2) Nhận diện quân
# ----------------------------------------------------------------------------
_YY, _XX = np.mgrid[0:MASK_S, 0:MASK_S]
_CM = (((_YY - MASK_S / 2 + .5) ** 2 + (_XX - MASK_S / 2 + .5) ** 2) <= (MASK_S * 0.42) ** 2)


def _patch(frame, x, y, pitch):
    R = int(pitch * 0.36)
    p = frame[int(y - R):int(y + R), int(x - R):int(x + R)]
    if p.size == 0:
        return None
    return cv2.resize(p, (MASK_S, MASK_S), interpolation=cv2.INTER_AREA)


def ink_mask(patch) -> np.ndarray:
    g = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    vals = g[_CM].reshape(-1, 1).astype(np.uint8)
    t, _ = cv2.threshold(vals, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return ((g < t) & _CM).astype(np.float32)


def red_score(patch):
    """(số điểm ảnh đỏ trong đĩa, số điểm ảnh xanh lục). Xe của mình = chữ ĐỎ rõ; quân địch có thể có quầng đỏ nhạt."""
    b, g, r = [patch[:, :, i].astype(int) for i in range(3)]
    red = int(((r > 110) & (r - g > 60) & (r - b > 50) & _CM).sum())
    grn = int(((g > r + 8) & (g > b - 10) & (r < 100) & _CM).sum())
    return red, grn


def ink_is_red(patch) -> bool:
    red, grn = red_score(patch)
    return red > max(60, 2 * grn)


_TEMPLATES = None


def load_templates(path=TEMPLATE_FILE):
    """{loại: [mặt nạ float32 40x40, ...]} đọc từ templates/xq_kinds.json (rỗng nếu chưa có)."""
    global _TEMPLATES
    if _TEMPLATES is not None:
        return _TEMPLATES
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for s in data.get("samples", []):
            m = np.array([int(ch) for ch in s["mask"]], np.float32).reshape(MASK_S, MASK_S)
            out.setdefault(s["kind"], []).append(m)
    except Exception:
        pass
    _TEMPLATES = out
    return out


def add_template(kind, mask, path=TEMPLATE_FILE):
    global _TEMPLATES
    data = {"size": MASK_S, "samples": []}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["samples"].append({"kind": kind, "mask": "".join("1" if v > 0.5 else "0" for v in mask.reshape(-1))})
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    _TEMPLATES = None


def classify_kind(mask, templates=None):
    """-> (loại, điểm). Lấy mẫu GIỐNG NHẤT (1-NN, TM_CCOEFF_NORMED) trong mọi mẫu đã lưu; điểm thấp = không chắc."""
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
    board: dict                       # {(hàng, cột): loại}; xe của mình = 'X'
    rook: Optional[tuple]
    low_conf: list = field(default_factory=list)   # [(ô, loại đoán, điểm)]


def detect_discs(frame, grid):
    gray = cv2.medianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 5)
    p = grid.pitch
    c = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=p * 0.6, param1=120, param2=28,
                         minRadius=int(p * 0.30), maxRadius=int(p * 0.44))
    cells = set()
    if c is not None:
        for x, y, _ in c[0]:
            ci = int(round((x - grid.xs[0]) / p))
            ri = int(np.argmin([abs(y - yy) for yy in grid.ys]))
            if 0 <= ci < COLS and abs(x - grid.xs[ci]) < p * 0.3 and abs(y - grid.ys[ri]) < p * 0.3:
                cells.add((ri, ci))
    return sorted(cells)


def read_board(frame, grid, unknown_as="r", min_match=0.55) -> BoardState:
    board, rook, low = {}, None, []
    found = []                                      # (ô, patch, điểm đỏ)
    for (r, c) in detect_discs(frame, grid):
        x, y = grid.px(r, c)
        patch = _patch(frame, x, y, grid.pitch)
        if patch is not None:
            found.append(((r, c), patch, red_score(patch)))
    # xe của mình = đĩa có chữ ĐỎ rõ nhất (quân địch có thể có quầng đỏ nhạt nên chỉ lấy 1 ô cao nhất)
    cand = [f for f in found if ink_is_red(f[1])]
    rook = max(cand, key=lambda f: f[2][0])[0] if cand else None
    for (r, c), patch, _ in found:
        if (r, c) == rook:
            board[(r, c)] = "X"
            continue
        kind, score = classify_kind(ink_mask(patch))
        if kind is None or score < min_match:
            low.append(((r, c), kind, round(score, 2)))
            kind = unknown_as
        board[(r, c)] = kind
    return BoardState(board=board, rook=rook, low_conf=low)


# ----------------------------------------------------------------------------
# 3) Luật + solver (xem mục 4-5 ở docstring; luật quân địch là ĐOÁN)
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
        if dr == cfg.pawn_dir and dc == 0:
            return True
        return dr == 0 and abs(dc) == 1 and r >= cfg.pawn_side_from_row
    if kind == "b":
        return abs(dr) == 2 and abs(dc) == 2 and (r + dr // 2, c + dc // 2) not in b
    if kind == "a":
        return abs(dr) == 1 and abs(dc) == 1
    if kind == "k":
        return abs(dr) + abs(dc) == 1
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


def choose_move(board, rook, cfg, tray=None, spawn_scale=0.3):
    """Chọn nước đi cho xe. tray=None: chưa biết khay -> dùng quân giả định ['n','c','r'] nhân `spawn_scale`.
    Trả (ô_đích, ô_bị_ăn_loại, điểm) hoặc None nếu xe không có nước nào."""
    opts = []
    for d, cap in rook_moves(board, rook):
        nb = after_move(board, rook, d)
        opts.append((d, cap, nb, is_attacked(nb, d, cfg)))
    if not opts:
        return None
    safe = [o for o in opts if not o[3]]
    if not safe:                                    # hết đường: chọn nước ít bị chiếu nhất
        best = min(opts, key=lambda o: count_attackers(o[2], o[0], cfg))
        return best[0], best[1], -LOSS
    kinds, scale = (tray, 1.0) if tray else (["n", "c", "r"], spawn_scale)
    best, bv = None, -1e18
    for d, cap, nb, _ in safe:
        v = cfg.value.get(cap, 0) + 1.5 * min(exits(nb, d, cfg), 8) - LOSS * spawn_risk(nb, d, kinds, cfg, scale)
        if v > bv:
            best, bv = (d, cap), v
    return best[0], best[1], bv


# ----------------------------------------------------------------------------
# 4) Chạy bước
# ----------------------------------------------------------------------------
class _Stop(Exception):
    pass


def board_text(st: BoardState):
    rows = []
    for r in range(ROWS):
        rows.append(" ".join((st.board.get((r, c)) or ".").ljust(1) for c in range(COLS)))
    return "\n".join(rows)


def save_debug(frame, grid, st, move=None, tag="xq"):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        im = frame.copy()
        for (r, c), k in st.board.items():
            x, y = grid.px(r, c)
            col = (0, 0, 255) if k == "X" else (0, 160, 0)
            cv2.circle(im, (int(x), int(y)), int(grid.pitch * 0.4), col, 2)
            cv2.putText(im, k, (int(x) - 8, int(y) + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
        if move:
            x, y = grid.px(*move)
            cv2.circle(im, (int(x), int(y)), int(grid.pitch * 0.46), (255, 0, 0), 3)
        path = os.path.join(DEBUG_DIR, f"{tag}_{time.strftime('%H%M%S')}.png")
        cv2.imencode(".png", im)[1].tofile(path)
        return path
    except Exception:
        return None


class XiangqiBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_rounds=0, max_seconds=0, settle_s=1.3,
                 input_mode="tap_tap", unknown_as="r", min_match=0.55, spawn_risk_every_turn=0.3, debug=False,
                 lost_limit=4, sleep=time.sleep, now=time.time):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test, self.debug = bool(test), bool(debug)
        self.max_rounds = int(max_rounds or 0)
        self.max_seconds = float(max_seconds or 0)
        self.settle_s = float(settle_s)
        self.input_mode = input_mode
        self.unknown_as, self.min_match = unknown_as, float(min_match)
        self.spawn_scale = float(spawn_risk_every_turn)
        self.lost_limit = int(lost_limit)
        self.sleep, self.now = sleep, now
        self.cfg = Config()
        self.t0 = now()
        self.rounds = 0

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
        grid = find_grid(fr)
        if grid is None:
            return fr, None, None
        return fr, grid, read_board(fr, grid, self.unknown_as, self.min_match)

    def _do_move(self, grid, src, dst):
        sx, sy = grid.px(*src)
        dx, dy = grid.px(*dst)
        if self.input_mode == "drag":
            self.adb.swipe_px(sx, sy, dx, dy, 250)
        else:
            self.adb.tap_px(sx, sy)
            self.sleep(0.2)
            self.adb.tap_px(dx, dy)

    def run(self) -> bool:
        lost = 0
        try:
            while True:
                self._check()
                if self.max_rounds and self.rounds >= self.max_rounds:
                    self.log("info", f"Xiangqi: đủ {self.rounds} lượt, dừng")
                    return True
                fr, grid, st = self._read()
                if grid is None or st is None or st.rook is None:
                    lost += 1
                    self.log("warn", f"Xiangqi: không thấy bàn/xe ({lost}/{self.lost_limit})")
                    if lost >= self.lost_limit:
                        self.log("info", "Xiangqi: coi như ván đã xong/đã thoát bàn, kết thúc")
                        return True
                    self.sleep(0.8)
                    continue
                lost = 0
                if st.low_conf:
                    self.log("warn", "Xiangqi: quân không chắc loại (ô, đoán, điểm): " + str(st.low_conf[:6]))
                mv = choose_move(st.board, st.rook, self.cfg, tray=None, spawn_scale=self.spawn_scale)
                if mv is None:
                    self.log("warn", "Xiangqi: xe không có nước đi")
                    return False
                dst, cap, score = mv
                self.log("info", f"Xiangqi lượt {self.rounds + 1}: xe {st.rook} -> {dst}"
                                 + (f" ăn {KIND_NAMES.get(cap, cap)}" if cap else "") + f" (điểm {score:.1f}, {len(st.board) - 1} quân địch)")
                if self.test or self.debug:
                    p = save_debug(fr, grid, st, dst)
                    if self.test:
                        self.log("info", "Xiangqi TEST - bàn nhận diện:\n" + board_text(st) + (f"\nẢnh debug: {p}" if p else ""))
                        return True
                self._do_move(grid, st.rook, dst)
                self.rounds += 1
                self.sleep(self.settle_s)
        except _Stop as e:
            self.log("info", f"Xiangqi: dừng ({e})")
            return False


def run_auto_xiangqi_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_xiangqi` (field xem mục 6 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    bot = XiangqiBot(
        adb, log=log, should_stop=should_stop,
        test=step.get("test", False), max_rounds=step.get("max_rounds", 0), max_seconds=step.get("max_seconds", 0),
        settle_s=step.get("settle_s", 1.3), input_mode=step.get("input_mode", "tap_tap"),
        unknown_as=step.get("unknown_as", "r"), min_match=step.get("min_match", 0.55),
        spawn_risk_every_turn=step.get("spawn_risk_every_turn", 0.3), debug=step.get("debug", False),
        lost_limit=step.get("lost_limit", 4),
    )
    return bot.run()


if __name__ == "__main__":
    # python xiangqi_bot.py anh.png                      -> kiểm nhận diện + nước đi
    # python xiangqi_bot.py anh.png <hàng> <cột> <loại>  -> thêm 1 mẫu chữ vào templates/xq_kinds.json
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    img = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
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
    print(board_text(s))
    print("Xe của mình:", s.rook, "| quân không chắc loại:", s.low_conf)
    if s.rook:
        print("Nước đi chọn:", choose_move(s.board, s.rook, Config()))
