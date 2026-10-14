# -*- coding: utf-8 -*-
"""
Bot auto "Thế Giới Động Vật" (game xếp thanh trượt kiểu Neko Sliding) - điều khiển qua ADB, dùng cho bước `auto_animal`.

>>> TRẠNG THÁI: KHUNG SƯỜN ĐẦU TIÊN. Luật game CHƯA ĐƯỢC XÁC NHẬN (xem mục 4), nhận diện mới thử trên 1 ảnh chụp.
>>> Người dùng sẽ cung cấp luật chính xác rồi chỉnh từng phần. Chưa chạy thử trên LDPlayer thật.

======================================================================================================
1) GAME LÀ GÌ (người dùng nói + suy ra từ 1 ảnh chụp 566x960)
======================================================================================================
- Người dùng mô tả (cho game giống Neko Sliding: Cat Puzzle của Gearhead Games): "chỉ di chuyển từng khối theo chiều NGANG
  thôi, trống bên dưới thì RƠI, đầy hàng thì ĂN".
- Trong game thật (Neko Sliding) kéo mèo bằng tay để chúng rơi vào chỗ, xếp đủ 1 hàng thì hàng biến mất và được điểm; có
  mèo đặc biệt xóa hàng theo cách riêng; có nhiều thử thách + bảng xếp hạng. (Thông tin từ trang game, chưa chắc áp dụng
  cho bản "Thế Giới Động Vật".)
- Ảnh chụp bản "Thế Giới Động Vật" cho thấy:
    * Tiêu đề "Thế Giới Động Vật", "Điểm ván này" = 114514, nhãn "Hiệp 500" ở góc trên phải (có hình đầu trâu đỏ).
    * Thanh "Kỹ Năng" (hình sư tử) hiển thị 7610/5000, màu xanh lá, có nút "+" -> có KỸ NĂNG dùng được, đang đầy.
      Tác dụng kỹ năng: CHƯA BIẾT.
    * Dải chữ đỏ "Vòng này sắp kết thúc" phủ lên hàng trên cùng của bàn -> có khái niệm VÒNG (hiệp) với giới hạn nào đó
      (số nước? số lượt?) và đang gần hết. Khi dải này hiện, hàng trên cùng bị che nên đọc màu hàng đó KHÔNG đáng tin.
    * Thanh tiến độ nhỏ (vàng) ở đáy bàn, chưa rõ ý nghĩa (có thể là tiến độ vòng).
    * Nút mũi tên quay lại ở góc dưới trái; huy hiệu "18" góc trái (cảnh báo độ tuổi, không liên quan).

======================================================================================================
2) HÌNH HỌC BÀN (đo trên ảnh 566x960)
======================================================================================================
- Bàn 9 CỘT x 11 HÀNG ô (bước ngang ~50.1px, bước dọc ~52.3px - gần vuông, ô chữ nhật hơi cao). Viền khung cam. Nền ô trống màu
  NÂU (khoảng RGB 157,100,52) có kẻ ô mờ.
- Mỗi "con vật" là 1 THANH NGANG dài 1..5 ô, đầu thú ở bên TRÁI thanh, thân là dải màu. Màu ~ loài:
    ĐỎ    = trâu    (RGB ~233,92,74)      VÀNG = sư tử (RGB ~255,179,41)
    XANH  = voi     (RGB ~140,190,217)    TRẮNG-ĐEN = ngựa vằn (nền trắng ~236,217,219, có vằn đen)
  Độ dài thanh KHÔNG cố định theo loài (trâu đã thấy dài 1,2,3,4,5; voi 1,3; sư tử 3; ngựa vằn 2,3).
- Mỗi hàng có thể có nhiều thanh, cách nhau bằng ô trống (vd hàng 1: trâu 3 ô, voi 1 ô, trâu 3 ô liền nhau).
- Toạ độ trong file là toạ độ THAM CHIẾU của ảnh 566x960; bot co giãn theo bề rộng ảnh và NEO ĐÁY (giả định bố cục tựa đáy).
  Với tỉ lệ màn hình khác có thể lệch -> kiểm tra bằng:  python animal_bot.py anh.png  (lưu ảnh debug_animal/).

======================================================================================================
3) NHẬN DIỆN (`read_grid`)
======================================================================================================
- Mỗi ô: lấy màu trung vị ở mảng nhỏ quanh tâm ô, gán nhãn gần nhất trong bảng màu (ô trống / đỏ / vàng / xanh / vằn).
- Ghép các ô LIỀN NHAU cùng màu trong 1 hàng thành 1 thanh. HẠN CHẾ: 2 thanh CÙNG MÀU nằm SÁT NHAU sẽ bị gộp thành 1
  (cần nhận ĐẦU THÚ để tách; chưa làm, người dùng cho biết cách tách hoặc cung cấp mẫu đầu thú).
- Ô ĐẦU THÚ: mặt thú che màu thân (vd sư tử) nên ô đầu bị đọc thành ô trống; bot gán lại theo màu thân thanh ngay bên phải
  (đầu thú luôn ở đầu TRÁI thanh) khi ô đó KHÔNG phải nền nâu thuần.
- KẾT QUẢ THỬ trên ảnh 566x960 (so với bản người đọc tay từng hàng): hàng 1..10 khớp 10/10 về ô có/không có thanh và màu;
  chỗ sai duy nhất là hàng 2 hai thanh trâu sát nhau bị gộp thành 1 thanh dài 6 (hạn chế đã nêu). Hàng 0 bị dải đỏ
  "Vòng này sắp kết thúc" che nên đọc ra 8 ô đỏ (SAI) - cần bỏ qua/xử lý hàng 0 khi dải này hiện (chưa làm).
- Không đọc điểm/hiệp/kỹ năng bằng OCR (chưa cần để chạy, sẽ làm khi biết luật).

======================================================================================================
4) NHỮNG CHỖ ĐANG ĐOÁN - CẦN NGƯỜI DÙNG XÁC NHẬN / CUNG CẤP LUẬT
======================================================================================================
 a. Thao tác: coi là KÉO NGANG 1 thanh từ tâm thanh sang ô mong muốn (`swipe_px`). Có thể game dùng chạm-rồi-chạm.
 b. Một thanh dời được tối đa bao nhiêu ô mỗi lượt, có đi xuyên qua thanh khác không (hiện: KHÔNG, chỉ trượt qua ô trống liên tiếp).
 c. Rơi: thanh rơi KHI TOÀN BỘ các ô bên dưới nó đều trống, rơi cả thanh (cứng) tới khi chạm; rơi nhiều tầng (hiện: đúng).
 d. Ăn hàng: hàng đầy đủ 9 ô thì các thanh trong hàng đó biến mất; sau đó phần phía trên rơi tiếp, ăn dây chuyền (combo).
 e. Cách tính điểm (nhiều hàng cùng lúc? combo? theo loài/độ dài thanh?). Hiện mô phỏng chỉ ĐẾM số hàng ăn.
 f. Hàng mới sinh thế nào (đẩy từ dưới lên? từ trên rơi xuống? khi nào? có xem trước không?) và "vòng" kết thúc ra sao.
 g. Kỹ năng (thanh Kỹ Năng) làm gì, khi nào nên dùng.
 h. Điều kiện thua (bàn đầy? hết lượt?).
 i. Có mèo/thú đặc biệt với hiệu ứng riêng không (như Neko Sliding).

======================================================================================================
5) THUẬT TOÁN (đã dựng, chưa chỉnh)
======================================================================================================
- `settle()`: mô phỏng rơi + ăn hàng đến khi ổn định (luật mục 4c, 4d).
- `gen_moves()`: mọi nước dời 1 thanh sang trái/phải qua các ô trống liên tiếp.
- `beam_search()`: tìm chuỗi `depth` nước (mặc định 2) giữ `beam` trạng thái tốt nhất mỗi tầng, hàm chấm `evaluate()`:
  thưởng lớn cho hàng ăn được, thưởng độ đầy của hàng, phạt LỖ TRỐNG nằm dưới thanh (khó lấp), phạt chiều cao cột.
  Trọng số là số TỰ ĐẶT, chưa tinh chỉnh (nên viết bộ mô phỏng và chơi thử hàng nghìn ván như đã làm với game xe).
- Vì hàng mới chưa biết sinh thế nào nên chưa tính vào tìm kiếm (chỉ tối ưu bàn hiện tại).

======================================================================================================
6) FIELD CỦA BƯỚC `auto_animal` (đều tuỳ chọn)
======================================================================================================
  test (false)        - true = CHẾ ĐỘ TEST: chụp 1 lần, nhận diện, tính chuỗi nước, lưu ảnh debug, KHÔNG bấm
  max_moves (0)       - số nước tối đa (0 = chạy tới khi hết nước / bị Dừng)
  max_seconds (0)     - giới hạn thời gian (0 = không giới hạn)
  depth (2) / beam (40) - độ sâu và độ rộng beam search
  settle_s (1.2)      - chờ sau mỗi nước (hoạt ảnh rơi/ăn hàng)
  drag_ms (220)       - thời gian kéo
  debug (false)       - lưu ảnh debug_animal/ mỗi nước (test luôn lưu)
  lost_limit (4)      - số lần liên tiếp không thấy bàn thì kết thúc bước

Chạy riêng để kiểm tra nhận diện + nước đi trên 1 ảnh chụp màn hình:  python animal_bot.py anh.png
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# ----------------------------------------------------------------------------
# Hằng số hình học (đo trên ảnh 566x960)
# ----------------------------------------------------------------------------
REF_W, REF_H = 566, 960
COLS, ROWS = 9, 11
BOARD_X0, BOARD_X1 = 57.0, 508.0               # mép trái/phải vùng ô
BOARD_Y1 = 906.0                               # mép DƯỚI của hàng cuối (neo đáy)
PITCH_X = (BOARD_X1 - BOARD_X0) / COLS         # ~50.1
PITCH_Y = 52.3
DEBUG_DIR = "debug_animal"

# Bảng màu (RGB) lấy mẫu từ ảnh chụp
PROTO = {
    ".": (157, 100, 52),    # ô trống
    "R": (233, 92, 74),     # trâu
    "Y": (255, 179, 41),    # sư tử
    "B": (140, 190, 217),   # voi
    "W": (236, 217, 219),   # ngựa vằn (nền trắng)
}
NAMES = {"R": "trâu", "Y": "sư tử", "B": "voi", "W": "ngựa vằn"}


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


def make_geo(frame) -> Geo:
    h, w = frame.shape[:2]
    s = w / REF_W
    return Geo(sx=s, x0=BOARD_X0 * s, pitch_x=PITCH_X * s, y_bottom=h - (REF_H - BOARD_Y1) * s, pitch_y=PITCH_Y * s)


# ----------------------------------------------------------------------------
# 1) Nhận diện
# ----------------------------------------------------------------------------
def classify_cell(patch_bgr):
    """(nhãn ô '.', 'R', 'Y', 'B', 'W', tỉ lệ nền nâu). Đếm điểm ảnh gần từng màu mẫu trên CẢ ô (ô đầu thú có mặt thú ở giữa nên không thể
    chỉ lấy màu ở tâm), lấy màu chiếm nhiều nhất; ô trống = nền nâu chiếm chủ yếu."""
    px = patch_bgr.reshape(-1, 3).astype(np.float32)
    if px.size == 0:
        return ".", 1.0
    rgb = px[:, ::-1]
    counts = {}
    for k, col in PROTO.items():
        d = np.sqrt(((rgb - np.array(col, np.float32)) ** 2).sum(1))
        counts[k] = int((d < 48).sum())
    bars = {k: v for k, v in counts.items() if k != "."}
    kb = max(bars, key=bars.get)
    if bars[kb] >= 0.22 * len(px) and bars[kb] >= counts["."] * 0.8:
        return kb, counts["."] / len(px)
    return ".", counts["."] / len(px)


def read_cells(frame, geo: Geo):
    """-> list ROWS x COLS nhãn ô. Ô ĐẦU THÚ (mặt thú che màu thân, vd sư tử) bị đọc thành '.' nhưng KHÔNG phải nền nâu
    -> gán theo màu thân thanh ngay bên phải (đầu thú luôn ở đầu TRÁI thanh)."""
    hx, hy = int(geo.pitch_x * 0.40), int(geo.pitch_y * 0.40)
    grid, brown = [], []
    for r in range(ROWS):
        row, brow = [], []
        y = int(geo.cy(r))
        for c in range(COLS):
            x = int(geo.cx(c))
            patch = frame[max(0, y - hy):y + hy, max(0, x - hx):x + hx]
            lab, bf = classify_cell(patch)
            row.append(lab)
            brow.append(bf)
        grid.append(row)
        brown.append(brow)
    for r in range(ROWS):
        for c in range(COLS - 1):
            if grid[r][c] == "." and brown[r][c] < 0.6 and grid[r][c + 1] != ".":
                grid[r][c] = grid[r][c + 1]
    return grid


@dataclass(frozen=True)
class Bar:
    row: int
    col: int
    length: int
    kind: str                       # 'R' 'Y' 'B' 'W'


def bars_from_cells(cells):
    bars = []
    for r in range(ROWS):
        c = 0
        while c < COLS:
            k = cells[r][c]
            if k == ".":
                c += 1
                continue
            e = c
            while e + 1 < COLS and cells[r][e + 1] == k:
                e += 1
            bars.append(Bar(r, c, e - c + 1, k))
            c = e + 1
    return bars


def read_grid(frame):
    geo = make_geo(frame)
    cells = read_cells(frame, geo)
    return geo, cells, bars_from_cells(cells)


def cells_text(cells):
    return "\n".join("".join(row) for row in cells)


# ----------------------------------------------------------------------------
# 2) Mô phỏng (luật mục 4 ở docstring là ĐOÁN)
# ----------------------------------------------------------------------------
def occupancy(bars):
    occ = {}
    for i, b in enumerate(bars):
        for c in range(b.col, b.col + b.length):
            occ[(b.row, c)] = i
    return occ


def settle(bars):
    """Rơi + ăn hàng tới khi ổn định. Trả (bars_mới, số_hàng_đã_ăn, số_thanh_biến_mất)."""
    bars = list(bars)
    cleared_rows = removed = 0
    while True:
        changed = False
        # ăn hàng đầy
        occ = occupancy(bars)
        full = [r for r in range(ROWS) if all((r, c) in occ for c in range(COLS))]
        if full:
            keep = [b for b in bars if b.row not in full]
            removed += len(bars) - len(keep)
            cleared_rows += len(full)
            bars = keep
            changed = True
        # rơi (xử lý từ dưới lên)
        moved = True
        while moved:
            moved = False
            occ = occupancy(bars)
            for i in sorted(range(len(bars)), key=lambda j: -bars[j].row):
                b = bars[i]
                if b.row + 1 < ROWS and all((b.row + 1, c) not in occ for c in range(b.col, b.col + b.length)):
                    bars[i] = Bar(b.row + 1, b.col, b.length, b.kind)
                    moved = changed = True
                    break
        if not changed:
            return bars, cleared_rows, removed


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


def apply_move(bars, i, new_col):
    nb = list(bars)
    b = nb[i]
    nb[i] = Bar(b.row, new_col, b.length, b.kind)
    return settle(nb)


@dataclass
class Weights:
    clear_row: float = 1000.0
    row_fill: float = 6.0          # thưởng độ đầy (bình phương) của các hàng chưa đầy
    hole: float = 5.0              # phạt ô trống nằm DƯỚI một thanh (khó lấp)
    height: float = 1.0            # phạt độ cao của khối


def evaluate(bars, cleared, w: Weights):
    occ = occupancy(bars)
    score = cleared * w.clear_row
    for r in range(ROWS):
        n = sum((r, c) in occ for c in range(COLS))
        score += w.row_fill * (n / COLS) ** 2 * COLS
    holes = 0
    top = ROWS
    for c in range(COLS):
        seen = False
        for r in range(ROWS):
            if (r, c) in occ:
                seen = True
                top = min(top, r)
            elif seen:
                holes += 1
    return score - w.hole * holes - w.height * (ROWS - top if bars else 0)


def beam_search(bars, depth=2, beam=40, w: Optional[Weights] = None):
    """Trả danh sách nước [(chỉ số thanh trong bars GỐC... ) ] dạng [(row, col_cũ, length, col_mới), ...] và điểm."""
    w = w or Weights()
    frontier = [(0.0, bars, [], 0)]
    best = (-1e18, [])
    for _ in range(depth):
        nxt = []
        for _, cur, path, cleared_total in frontier:
            for i, nc in gen_moves(cur):
                b = cur[i]
                nb, cl, _ = apply_move(cur, i, nc)
                tot = cleared_total + cl
                sc = evaluate(nb, tot, w)
                nxt.append((sc, nb, path + [(b.row, b.col, b.length, nc)], tot))
        if not nxt:
            break
        nxt.sort(key=lambda t: -t[0])
        frontier = nxt[:beam]
        if frontier[0][0] > best[0]:
            best = (frontier[0][0], frontier[0][2])
    return best[1], best[0]


# ----------------------------------------------------------------------------
# 3) Chạy bước
# ----------------------------------------------------------------------------
class _Stop(Exception):
    pass


def save_debug(frame, geo, cells, move=None, tag="an"):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        im = frame.copy()
        for r in range(ROWS):
            for c in range(COLS):
                k = cells[r][c]
                if k != ".":
                    cv2.putText(im, k, (int(geo.cx(c)) - 6, int(geo.cy(r)) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        if move:
            r, c0, ln, nc = move
            cv2.arrowedLine(im, (int(geo.cx(c0) + (ln - 1) * geo.pitch_x / 2), int(geo.cy(r))),
                            (int(geo.cx(nc) + (ln - 1) * geo.pitch_x / 2), int(geo.cy(r))), (0, 0, 255), 3)
        path = os.path.join(DEBUG_DIR, f"{tag}_{time.strftime('%H%M%S')}.png")
        cv2.imencode(".png", im)[1].tofile(path)
        return path
    except Exception:
        return None


class AnimalBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_moves=0, max_seconds=0, depth=2, beam=40,
                 settle_s=1.2, drag_ms=220, debug=False, lost_limit=4, sleep=time.sleep, now=time.time):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test, self.debug = bool(test), bool(debug)
        self.max_moves, self.max_seconds = int(max_moves or 0), float(max_seconds or 0)
        self.depth, self.beam = int(depth), int(beam)
        self.settle_s, self.drag_ms = float(settle_s), int(drag_ms)
        self.lost_limit = int(lost_limit)
        self.sleep, self.now = sleep, now
        self.t0 = now()
        self.moves = 0

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

    def run(self) -> bool:
        lost = 0
        try:
            while True:
                self._check()
                if self.max_moves and self.moves >= self.max_moves:
                    self.log("info", f"Animal: đủ {self.moves} nước, dừng")
                    return True
                fr = self._shot()
                geo, cells, bars = read_grid(fr)
                if not bars:
                    lost += 1
                    self.log("warn", f"Animal: không thấy thanh nào ({lost}/{self.lost_limit})")
                    if lost >= self.lost_limit:
                        self.log("info", "Animal: coi như đã hết ván/thoát bàn, kết thúc")
                        return True
                    self.sleep(0.8)
                    continue
                lost = 0
                path, score = beam_search(bars, self.depth, self.beam)
                if not path:
                    self.log("warn", "Animal: không có nước đi nào")
                    return False
                r, c0, ln, nc = path[0]
                self.log("info", f"Animal nước {self.moves + 1}: thanh hàng {r} cột {c0} (dài {ln}) -> cột {nc} (điểm {score:.0f}, {len(bars)} thanh)")
                if self.test or self.debug:
                    p = save_debug(fr, geo, cells, path[0])
                    if self.test:
                        self.log("info", "Animal TEST - bàn nhận diện:\n" + cells_text(cells) + f"\nChuỗi nước: {path}" + (f"\nẢnh debug: {p}" if p else ""))
                        return True
                half = (ln - 1) * geo.pitch_x / 2.0
                self.adb.swipe_px(geo.cx(c0) + half, geo.cy(r), geo.cx(nc) + half, geo.cy(r), self.drag_ms)
                self.moves += 1
                self.sleep(self.settle_s)
        except _Stop as e:
            self.log("info", f"Animal: dừng ({e})")
            return False


def run_auto_animal_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_animal` (field xem mục 6 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    bot = AnimalBot(
        adb, log=log, should_stop=should_stop,
        test=step.get("test", False), max_moves=step.get("max_moves", 0), max_seconds=step.get("max_seconds", 0),
        depth=step.get("depth", 2), beam=step.get("beam", 40), settle_s=step.get("settle_s", 1.2),
        drag_ms=step.get("drag_ms", 220), debug=step.get("debug", False), lost_limit=step.get("lost_limit", 4),
    )
    return bot.run()


if __name__ == "__main__":
    # Kiểm tra nhận diện + nước đi trên ảnh chụp màn hình: python animal_bot.py anh.png
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    img = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
    geo, cells, bars = read_grid(img)
    print(f"Bàn {COLS}x{ROWS}, ô {geo.pitch_x:.1f}x{geo.pitch_y:.1f}px. Ô: .=trống R=trâu Y=sư tử B=voi W=ngựa vằn")
    print(cells_text(cells))
    print(f"{len(bars)} thanh:", [(b.row, b.col, b.length, b.kind) for b in bars][:12], "...")
    path, score = beam_search(bars)
    print("Chuỗi nước (hàng, cột cũ, dài, cột mới):", path, "điểm", round(score, 1))
    print("Ảnh debug:", save_debug(img, geo, cells, path[0] if path else None))
