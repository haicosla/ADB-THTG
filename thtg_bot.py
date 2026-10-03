# -*- coding: utf-8 -*-
"""
Bot auto game "Ngưu Ma Vương" (màn Thất Thánh - Phàn Đầu) qua ADB. Không import tkinter.

Luật (suy từ mô tả + ảnh, các điểm chưa chắc để thành tham số):
- Lưới 7x7, đường đi 8 HƯỚNG, không đi lại ô cũ, bắt đầu từ ô cạnh nhân vật (hàng 0).
- Chỉ nối thú CÙNG LOẠI (ếch/bò/mèo). Kim cương hoặc diệt quái to -> được đổi loại.
- Nối xong phải bấm nút "Chiến" mới đánh. Thanh nộ đầy thì dùng nộ TRƯỚC khi đi.
- Mỗi ô đi qua +1 bước. Quái to số N: cần đủ N bước tích luỹ, bị trừ N, vẫn +1 bước
  vừa đi (vd 10 bước, quái 7 -> 3, cộng 1 = 4).
- Ô LỒNG (khung đỏ/cam nhốt viên ngọc, có số N ở góc): như quái to, cần đủ N bước mới đi qua được (bị trừ N, vẫn +1 bước);
  nhưng đi qua lồng KHÔNG được đổi loại (giữ nguyên loại thú đang nối). Phá lồng xong nó mở khoá thành kim cương thường
  (từ lúc đó mới đổi loại được) và KHÔNG tính là diệt quái (Cell.mtype == "cage").
- THƯỞNG KIM CƯƠNG: đi đủ 10 bước thưởng ngẫu nhiên 1 kim cương, 20 bước thưởng 2, 30 bước thưởng 3... (steps // 10).
  Kim cương chủ yếu để TẠO LỐI ĐI (đổi loại thú), không cần ăn hết: mỗi viên dùng bị trừ điểm (SolverParams.w_diamond < 0),
  mỗi mốc 10 bước được cộng điểm (w_reward) -> ưu tiên đi TRÒN mốc 10 bước và chỉ dùng kim cương khi cần làm cầu nối /
  để chạm mốc (vd 33 bước dùng 3 viên là hợp lý; 31 bước thì dùng 2 viên thôi, chừa 1 viên).
- Mỗi lượt các ô đã đi biến mất, quái mới rơi từ trên xuống (không đoán được) nên chỉ
  tối ưu từng lượt. Nhân vật đứng lại ở ô CUỐI đường đi nên bước cuối bị phạt (`_EndEval`) nếu: dồn vào góc/mép, hoặc sau khi
  các ô rơi xuống mà quanh nhân vật gần như không còn ô đi vào được (quái to/lồng/đá chặn) -> lượt sau bị kẹt không có đường.
  Không phạt khi đường đi diệt nốt quái to cuối cùng.
- Bấm lần lượt từng ô là nối được (không cần vuốt).

Chạy riêng để kiểm tra nhận diện + đường đi trên ảnh chụp:
    python thtg_bot.py anh.png [beam]     -> in bàn cờ, đường đi, lưu thtg_debug.png
    python thtg_bot.py --add-monster anh.png HÀNG CỘT  -> lưu ô đó thành mẫu quái mới (templates/thtg_monster_N.png)
"""

from __future__ import annotations

import glob
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import cv2

ROWS = COLS = 7
ANIMALS = {0: "Ếch", 1: "Bò", 2: "Mèo", 3: "Heo"}
ANIMAL_CH = {0: "F", 1: "O", 2: "C", 3: "P"}

_DIRS8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


# =====================================================================================
# 1) Mô hình bàn cờ
# =====================================================================================
@dataclass
class Cell:
    kind: str = "empty"        # animal | diamond | monster | stone | hero | empty
    color: int = -1            # 0 ếch, 1 bò, 2 mèo (kind == animal)
    n: int = 0                 # số bước cần (kind == monster)
    fire: bool = False         # có lửa
    boss: bool = False         # quái to có skill (hết lượt không diệt -> mất máu)
    mtype: str = "boss"        # loại quái to (khoá của SolverParams.monster_weights); thêm loại mới = thêm 1 dòng ở đó
    turns: int = 0             # số LƯỢT còn lại trước khi quái dùng skill làm mất máu (số bên trái quái; 0 = không có/không rõ)


@dataclass
class Board:
    cells: list                # cells[r][c] -> Cell
    hero: tuple = (0, 3)       # nhân vật đứng ở ô bất kỳ (sau mỗi lượt đứng ở cuối đường đi)

    def at(self, r, c):
        return self.cells[r][c]

    def pretty(self) -> str:
        out = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                x = self.cells[r][c]
                if (r, c) == self.hero:
                    row.append(" H ")
                elif x.kind == "animal":
                    row.append(f" {ANIMAL_CH[x.color]}{'*' if x.fire else ' '}")
                elif x.kind == "diamond":
                    row.append(" D ")
                elif x.kind == "monster":
                    row.append(("L" if x.mtype == "cage" else "M") + f"{x.n}" + (f"/{x.turns}" if x.turns else "") + " ")
                elif x.kind == "stone":
                    row.append(" # ")
                else:
                    row.append(" ? ")
            out.append("".join(row))
        return "\n".join(out)


def board_from_strings(rows, monsters: Optional[dict] = None, hero=(0, 3)) -> Board:
    """Dựng Board từ chuỗi để test. F/O/C/P = ếch/bò/mèo/heo (thêm * sau chữ = có lửa), D = kim cương,
    M = quái to, L = ô lồng (số bước lấy từ monsters[(r,c)]), # = đá, H = nhân vật."""
    monsters = monsters or {}
    cells = []
    for r, line in enumerate(rows):
        row = []
        toks = line.split()
        for c, t in enumerate(toks):
            ch = t[0]
            fire = t.endswith("*")
            if ch in "FOCP":
                row.append(Cell("animal", "FOCP".index(ch), fire=fire))
            elif ch == "D":
                row.append(Cell("diamond"))
            elif ch == "M":
                mv = monsters.get((r, c), 7)
                n_, t_ = (mv if isinstance(mv, tuple) else (mv, 0))
                row.append(Cell("monster", n=n_, turns=t_, boss=True))
            elif ch == "L":                      # ô lồng (số bước lấy từ monsters[(r,c)])
                mv = monsters.get((r, c), 5)
                row.append(Cell("monster", n=(mv[0] if isinstance(mv, tuple) else mv), mtype="cage"))
            elif ch == "#":
                row.append(Cell("stone"))
            elif ch == "H":
                row.append(Cell("hero"))
                hero = (r, c)
            else:
                row.append(Cell("empty"))
        cells.append(row)
    return Board(cells, hero)


# =====================================================================================
# 2) Tìm đường (beam search)
# =====================================================================================
@dataclass
class SolverParams:
    beam: int = 5000
    w_kill: float = 1000.0         # mỗi quái to diệt được (LUÔN lớn hơn tổng điểm bước tối đa 49*w_step -> diệt quái là ưu tiên số 1)
    w_boss: float = 500.0          # cộng thêm nếu là quái to có skill (dùng khi loại quái không có trong monster_weights)
    # Điểm CỘNG THÊM theo loại quái to (ngoài w_kill). Loại nào quan trọng hơn thì để số lớn hơn. Sau này có nhiều
    # loại quái: detector gán Cell.mtype, ở đây thêm 1 dòng, ví dụ "elite": 900.0.
    monster_weights: dict = field(default_factory=lambda: {"boss": 500.0})
    w_cage: float = 200.0          # điểm cộng khi đi qua (mở khoá) 1 ô lồng: thấp hơn diệt quái (w_kill) nhưng cao hơn kim cương; 0 = chỉ qua khi làm cầu nối
    w_step: float = 10.0           # mỗi bước (nạp nộ)
    # Kim cương CHỦ YẾU để tạo lối đi (đổi loại), không cần ăn: mỗi viên đi qua bị TRỪ w_diamond điểm (số ÂM); đổi lại mỗi mốc
    # reward_every bước đi được thưởng 1 viên (cộng w_reward điểm) -> đường tròn mốc 10/20/30 bước lời hơn, dùng kim cương
    # chỉ khi cần cầu nối hoặc để chạm mốc. (Bản cũ: +15 mỗi viên -> bot cứ ăn kim cương cho bằng hết.)
    w_diamond: float = -40.0
    w_reward: float = 60.0         # giá trị 1 viên kim cương thưởng (mỗi reward_every bước)
    reward_every: int = 10         # cứ đủ chừng này bước thưởng 1 kim cương (10 -> 1, 20 -> 2, 30 -> 3...)
    w_fire: float = 0.0            # ăn con có lửa (chưa rõ tác dụng, mặc định 0)
    w_region: float = 6.0          # phụ: vùng ô cùng loại còn nối tiếp được (để ăn hết cụm ở cuối)
    w_pull: float = 1.0            # phụ: kéo về phía quái chưa diệt
    count_step_first: bool = False # True: cần (bước+1) >= N; False: cần bước >= N
    # 0 = KHÔNG giới hạn thời gian: kết quả chỉ phụ thuộc bàn cờ, không phụ thuộc máy nhanh/chậm (trước đây hết 3s là
    # cắt giữa chừng -> đường đi ngắn, bỏ sót quái, mỗi lần chạy một kiểu). >0 chỉ nên dùng khi test.
    time_limit: float = 0.0
    # Chạy beam nhiều lần với bộ trọng số phụ khác nhau (w_region, w_pull) rồi lấy đường tốt nhất; thứ tự cố định.
    variants: tuple = ((None, None), (0.0, 4.0), (14.0, 0.0))   # None = dùng w_region/w_pull ở trên
    # Chạy THÊM beam "nhắm" riêng từng quái to (kéo đường đi về đúng quái đó + thưởng khi gom đủ bước cần để diệt nó),
    # chỉ chạy khi các beam thường chưa diệt hết quái. Thứ tự cố định -> kết quả vẫn xác định.
    target_beams: bool = True
    w_target: float = 12.0         # kéo về quái được nhắm (mỗi ô khoảng cách)
    w_need: float = 8.0            # thưởng mỗi bước gom được hướng tới số bước cần của quái được nhắm
    max_len: int = ROWS * COLS
    # --- Tránh KẸT ở lượt sau (nhân vật đứng lại ở ô cuối đường đi). Phạt điểm vị trí cuối; tắt: end_safety=False.
    # Ô bị phạt tính SAU KHI các ô đã đi biến mất và ô phía trên rơi xuống (fall_down), ô mới rơi vào coi là đi được.
    end_safety: bool = True
    fall_down: bool = True         # True: ô rơi xuống theo cột (mới rơi từ trên); False: coi ô đã đi thành ô mới tại chỗ
    # phạt theo SỐ ô kề nhân vật đi vào được ở bước đầu lượt sau (thú/kim cương; quái to/lồng/đá không vào được vì chưa có bước)
    # chỉ số = số ô vào được: 0 = KẸT HẲN (phạt rất nặng), 1, 2, 3; từ 4 trở lên không phạt.
    open_pen: tuple = (2500.0, 400.0, 150.0, 50.0)
    w_corner: float = 150.0        # kết thúc ở GÓC bàn cờ
    w_edge: float = 40.0           # kết thúc ở MÉP (không phải góc)
    reach_min: int = 8             # vùng đi vào được liền nhau quanh nhân vật nhỏ hơn mức này thì phạt thêm (lượt sau đường ngắn)
    w_reach: float = 25.0          # phạt mỗi ô thiếu so với reach_min
    # Quái có đếm ngược: còn ít lượt thì phải diệt NGAY lượt này (hết lượt nó dùng skill làm mất máu) -> cộng thêm điểm.
    # Khoá = số lượt còn lại (1 = hết lượt này là nó đánh).
    urgency: dict = field(default_factory=lambda: {1: 4000.0, 2: 1500.0, 3: 600.0})
    # Bộ giải CHÍNH XÁC (thtg_solver.py, nhánh-cận): chạy trước; nếu chứng minh được là tối ưu thì khỏi chạy beam.
    use_exact: bool = True
    exact_nodes: int = 400_000     # giới hạn SỐ NÚT (không phải giây) -> kết quả xác định, không phụ thuộc máy nhanh/chậm

    def monster_extra(self, x) -> float:
        """Điểm cộng thêm khi diệt quái x (ngoài w_kill): theo loại quái + mức khẩn cấp theo số lượt đếm ngược."""
        if x.mtype in self.monster_weights:
            base = float(self.monster_weights[x.mtype])
        else:
            base = self.w_boss if x.boss else 0.0
        return base + float(self.urgency.get(getattr(x, "turns", 0), 0.0))


@dataclass
class Plan:
    path: list = field(default_factory=list)   # [(r, c), ...] không gồm ô nhân vật
    score: float = 0.0
    kills: int = 0
    steps: int = 0
    diamonds: int = 0
    killed: list = field(default_factory=list)
    final_balance: int = 0
    optimal: bool = False          # True = bộ giải chính xác đã CHỨNG MINH đường này tối ưu
    reward: int = 0                # số kim cương được thưởng (steps // reward_every)
    end_pen: float = 0.0           # điểm phạt vị trí cuối (kẹt/góc/mép), 0 = an toàn hoặc đã diệt hết quái
    solver: str = ""               # "exact" | "beam" | "exact+beam"


_W = 8                                   # bàn cờ đặt trong lưới bit rộng 8 (cột 7 là đệm)
_BOARD = sum(0x7F << (_W * r) for r in range(ROWS))


def _bit(r, c):
    return 1 << (r * _W + c)


def _popcount(x):
    try:
        return x.bit_count()
    except AttributeError:        # Python < 3.10
        return bin(x).count("1")


def _dil(m):
    """Nở 1 ô theo 8 hướng."""
    d = m | (m << 1) | (m >> 1)
    d |= (d << _W) | (d >> _W)
    return d & _BOARD


def _flood(tip_bit, allowed):
    """Các ô trong `allowed` nối liền (8 hướng) với ô tip - cận trên số bước còn đi tiếp được."""
    reg = _dil(tip_bit) & allowed
    while True:
        n = _dil(reg) & allowed
        if n == reg:
            return reg
        reg = n


class _EndEval:
    """Phạt VỊ TRÍ KẾT THÚC của một đường đi (nhân vật đứng lại ở ô cuối, lượt sau bắt đầu từ đó) để lượt sau không bị kẹt.
    Mô phỏng: các ô đã đi (mask, gồm cả ô xuất phát của nhân vật) biến mất, ô còn lại rơi xuống theo cột, ô mới ở phía trên
    chưa biết nên coi là ĐI ĐƯỢC. Đầu lượt sau chưa có bước nào nên chỉ vào được thú/kim cương (quái to, lồng, đá thì không).
    Điểm phạt (>= 0): theo số ô kề đi vào được (0 = kẹt hẳn) + góc/mép + vùng đi vào được quanh nhân vật quá nhỏ.
    Đã diệt hết quái to thì không phạt (thắng). Kết quả chỉ phụ thuộc (ô cuối, mask) nên bộ giải chính xác dùng được."""

    def __init__(self, board: Board, p: SolverParams):
        self.p = p
        self.on = bool(p.end_safety)
        self.real_mon = 0
        self.ok_cols = [[False] * ROWS for _ in range(COLS)]      # ok_cols[c][r]: ô (r,c) đi vào được ở đầu lượt sau
        self.ok_bits = 0
        for r in range(ROWS):
            for c in range(COLS):
                x = board.cells[r][c]
                if x.kind == "monster" and x.mtype != "cage":
                    self.real_mon |= _bit(r, c)
                if (r, c) != board.hero and x.kind in ("animal", "diamond"):
                    self.ok_cols[c][r] = True
                    self.ok_bits |= _bit(r, c)

    def open_bits(self, mask):
        """Mặt nạ các ô đi vào được SAU KHI ô đã đi biến mất + ô rơi xuống."""
        if not self.p.fall_down:
            return (self.ok_bits & ~mask) | (mask & _BOARD)         # ô đã đi (và ô xuất phát) thành ô mới tại chỗ
        bits = 0
        for c in range(COLS):
            col = self.ok_cols[c]
            rem = [col[r] for r in range(ROWS) if not (mask >> (r * _W + c)) & 1]
            k = ROWS - len(rem)                                      # số ô mới rơi vào đầu cột (chưa biết -> đi được)
            for r in range(k):
                bits |= 1 << (r * _W + c)
            for i, v in enumerate(rem):
                if v:
                    bits |= 1 << ((k + i) * _W + c)
        return bits

    def penalty(self, tip, mask) -> float:
        """tip = r*_W + c của ô cuối; mask = các ô đã đi (gồm ô xuất phát). Trả điểm phạt >= 0."""
        if not self.on or (self.real_mon and not (self.real_mon & ~mask)):     # đã diệt nốt quái to cuối cùng -> khỏi phạt
            return 0.0
        p = self.p
        r, c = tip >> 3, tip & 7
        tb = 1 << tip
        bits = self.open_bits(mask) & ~tb
        nbr = _popcount(_dil(tb) & bits)
        pen = float(p.open_pen[nbr]) if nbr < len(p.open_pen) else 0.0
        if r in (0, ROWS - 1) and c in (0, COLS - 1):
            pen += p.w_corner
        elif r in (0, ROWS - 1) or c in (0, COLS - 1):
            pen += p.w_edge
        if nbr and p.w_reach > 0:
            reach = _popcount(_flood(tb, bits))
            if reach < p.reach_min:
                pen += p.w_reach * (p.reach_min - reach)
        return pen


def _step(board: Board, p: SolverParams, r, c, a, b, color, bal, killed_bits):
    """Thử đi từ (r,c) sang (a,b). Trả (color_mới, bal_mới, dkill, ddiam, dboss, dfire) hoặc None."""
    x = board.cells[a][b]
    if x.kind == "animal":
        if color != -1 and x.color != color:
            return None
        return x.color, bal + 1, 0, 0, 0, 1 if x.fire else 0
    if x.kind == "diamond":
        return -1, bal + 1, 0, 1, 0, 0
    if x.kind == "monster":
        need = x.n - (1 if p.count_step_first else 0)
        if bal < need:
            return None
        if x.mtype == "cage":              # lồng: cần đủ số bước như quái, KHÔNG đổi loại (giữ `color`), không tính diệt;
            return color, bal + 1 - x.n, 0, 0, p.w_cage, 0     # phá xong lồng thành kim cương (chỉ có tác dụng từ lượt sau)
        return -1, bal + 1 - x.n, 1, 0, p.monster_extra(x), 0
    return None   # đá / nhân vật / ô trống không đi được


def solve_beam(board: Board, params: Optional[SolverParams] = None) -> Plan:
    """(Heuristic) Tìm đường đi 1 lượt bằng beam search. Thứ tự ưu tiên: diệt quái to (nhiều nhất, quái nặng điểm trước) > số bước > kim cương.
    KẾT QUẢ XÁC ĐỊNH: cùng bàn cờ + cùng tham số luôn ra đúng 1 đường đi (không phụ thuộc tốc độ máy)."""
    p = params or SolverParams()
    t0 = time.time()
    hr, hc = board.hero
    monsters = []
    colmask = {k: 0 for k in ANIMALS}
    dia_mask = mon_mask = 0
    for r in range(ROWS):
        for c in range(COLS):
            x = board.cells[r][c]
            if x.kind == "monster":
                if x.mtype != "cage":          # lồng không phải mục tiêu diệt (chỉ là cầu nối)
                    monsters.append((r, c))
                mon_mask |= _bit(r, c)
            elif x.kind == "diamond":
                dia_mask |= _bit(r, c)
            elif x.kind == "animal":
                colmask[x.color] |= _bit(r, c)
    free_extra = dia_mask | mon_mask
    endev = _EndEval(board, p) if p.end_safety else None
    rew_every = max(1, int(p.reward_every))

    def region(a, b, mask, color):
        """Số ô còn có thể nối tiếp từ (a,b): cùng loại `color` (hoặc kim cương/quái làm cầu nối).
        color == -1 (đổi loại tự do): lấy loại có vùng lớn nhất."""
        tip = _bit(a, b)
        free = ~mask & _BOARD
        if color >= 0:
            return _popcount(_flood(tip, free & (colmask[color] | free_extra)))
        best_ = 0
        for k in colmask:
            best_ = max(best_, _popcount(_flood(tip, free & (colmask[k] | free_extra))))
        return best_

    def run_beam(w_region, w_pull, target=None, bal_need=0):
        def pull(r, c, mask, bal=0):
            alive = [(a, b) for a, b in monsters if not (mask >> (a * _W + b)) & 1]
            if not alive:
                return 0.0
            if target is not None:
                ta, tb = target
                if (mask >> (ta * _W + tb)) & 1:      # quái nhắm đã diệt -> quay về kiểu thường
                    return -w_pull * min(max(abs(a - r), abs(b - c)) for a, b in alive)
                d = max(abs(ta - r), abs(tb - c))
                return -p.w_target * d + p.w_need * min(bal, bal_need)
            return -w_pull * min(max(abs(a - r), abs(b - c)) for a, b in alive)

        # state: (heur, r, c, mask, color, bal, kills, bossExtra, diam, fire, parent_node, steps)
        root = (0.0, hr, hc, _bit(hr, hc), -1, 0, 0, 0.0, 0, 0, None, 0)
        beam = [root]
        best = (-1e18, None)      # điểm có thể ÂM (kim cương trừ điểm, phạt kẹt) nhưng vẫn phải chọn 1 đường nếu có
        for _ in range(p.max_len):
            if p.time_limit > 0 and time.time() - t0 > p.time_limit:
                break
            nxt, seen = [], set()
            for st in beam:
                _, r, c, mask, color, bal, kills, boss, diam, fire, _par, steps = st
                for dr, dc in _DIRS8:
                    a, b = r + dr, c + dc
                    if not (0 <= a < ROWS and 0 <= b < COLS):
                        continue
                    bit = _bit(a, b)
                    if mask & bit:
                        continue
                    res = _step(board, p, r, c, a, b, color, bal, mask)
                    if res is None:
                        continue
                    ncol, nbal, dk, dd, dbo, dfi = res
                    nm = mask | bit
                    key = (a, b, nm, ncol, nbal)
                    if key in seen:
                        continue
                    seen.add(key)
                    nk, nb_, nd, nf, ns = kills + dk, boss + dbo, diam + dd, fire + dfi, steps + 1
                    final = (p.w_kill * nk + nb_ + p.w_step * ns
                             + p.w_diamond * nd + p.w_fire * nf + p.w_reward * (ns // rew_every))
                    heur = final + w_region * region(a, b, nm, ncol) + pull(a, b, nm, nbal)
                    node = (heur, a, b, nm, ncol, nbal, nk, nb_, nd, nf, (st, (a, b)), ns)
                    nxt.append(node)
                    if final > best[0]:
                        tot = final - (endev.penalty(a * _W + b, nm) if endev else 0.0)
                        if tot > best[0]:
                            best = (tot, node)
            if not nxt:
                break
            # sắp xếp ỔN ĐỊNH + khoá phụ cố định -> hoà điểm vẫn ra cùng 1 thứ tự ở mọi lần chạy
            nxt.sort(key=lambda s_: (-s_[0], s_[1], s_[2], s_[3]))
            beam = nxt[: p.beam]
        return best

    best = (-1e18, None)
    for vr, vp in (p.variants or ((None, None),)):
        cand = run_beam(p.w_region if vr is None else vr, p.w_pull if vp is None else vp)
        if cand[1] is not None and cand[0] > best[0]:     # hoà điểm -> giữ bộ trọng số đứng trước (thứ tự cố định)
            best = cand

    if p.target_beams and monsters and (best[1] is None or best[1][6] < len(monsters)):
        for (ta, tb) in monsters:                       # thứ tự quét cố định
            need = board.cells[ta][tb].n
            cand = run_beam(p.w_region, 0.0, target=(ta, tb), bal_need=need)
            if cand[1] is not None and cand[0] > best[0]:
                best = cand

    final, node = best
    if node is None:
        return Plan()
    path = []
    cur = node
    while cur is not None and cur[10] is not None:
        parent, cell = cur[10]
        path.append(cell)
        cur = parent
    path.reverse()
    killed = [q for q in path if board.cells[q[0]][q[1]].kind == "monster" and board.cells[q[0]][q[1]].mtype != "cage"]
    return Plan(path=path, score=final, kills=node[6], steps=node[11], diamonds=node[8],
                killed=killed, final_balance=node[5], solver="beam",
                reward=node[11] // rew_every, end_pen=(endev.penalty(node[1] * _W + node[2], node[3]) if endev else 0.0))


def evaluate_path(board: Board, path, p: SolverParams):
    """Điểm của 1 đường theo ĐÚNG hàm mục tiêu của solver (None nếu vi phạm luật). Dùng để so beam với exact."""
    ok, _, _ = validate_path(board, path, p)
    if not ok:
        return None
    r, c = board.hero
    color, bal, sc = -1, 0, 0.0
    mask = _bit(r, c)
    for (a, b) in path:
        color, bal, dk, dd, dbo, dfi = _step(board, p, r, c, a, b, color, bal, 0)
        sc += p.w_kill * dk + dbo + p.w_diamond * dd + p.w_fire * dfi + p.w_step
        mask |= _bit(a, b)
        r, c = a, b
    sc += p.w_reward * (len(path) // max(1, int(p.reward_every)))
    if path and p.end_safety:
        sc -= _EndEval(board, p).penalty(r * _W + c, mask)
    return sc


def _plan_from_path(board: Board, path, p: SolverParams, solver: str, optimal=False) -> Plan:
    r, c = board.hero
    color, bal, kills, diam = -1, 0, 0, 0
    for (a, b) in path:
        color, bal, dk, dd, _dbo, _dfi = _step(board, p, r, c, a, b, color, bal, 0)
        kills += dk
        diam += dd
        r, c = a, b
    killed = [q for q in path if board.cells[q[0]][q[1]].kind == "monster" and board.cells[q[0]][q[1]].mtype != "cage"]
    sc = evaluate_path(board, path, p)
    end_pen = 0.0
    if path and p.end_safety:
        mask = _bit(*board.hero)
        for (a, b) in path:
            mask |= _bit(a, b)
        end_pen = _EndEval(board, p).penalty(path[-1][0] * _W + path[-1][1], mask)
    return Plan(path=list(path), score=0.0 if sc is None else sc, kills=kills, steps=len(path),
                diamonds=diam, killed=killed, final_balance=bal, optimal=optimal, solver=solver,
                reward=len(path) // max(1, int(p.reward_every)), end_pen=end_pen)


def _to_exact_grid(board: Board, p: SolverParams):
    g = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            x = board.cells[r][c]
            if (r, c) == board.hero:
                row.append(("H", -1, 0, 0))
            elif x.kind == "animal":
                row.append(("A", x.color, 0, 0))
            elif x.kind == "diamond":
                row.append(("D", -1, 0, 0))
            elif x.kind == "monster":
                row.append(("L", -1, x.n, p.w_cage) if x.mtype == "cage"
                           else ("M", -1, x.n, p.w_kill + p.monster_extra(x)))
            elif x.kind == "stone":
                row.append(("S", -1, 0, 0))
            else:
                row.append(("E", -1, 0, 0))
        g.append(row)
    return g


def solve(board: Board, params: Optional[SolverParams] = None) -> Plan:
    """Tìm đường đi tốt nhất 1 lượt. Thứ tự ưu tiên: diệt quái to (quái sắp đánh trước) > số bước (nạp nộ) > kim cương.
    1) Bộ giải chính xác (nhánh-cận, thtg_solver.py): thường CHỨNG MINH được đường tối ưu trong chưa tới 1 giây.
    2) Nếu bàn quá khó (hết số nút): chạy thêm beam rồi lấy đường tốt hơn, thử cải thiện tiếp bằng exact xuất phát từ nó.
    KẾT QUẢ XÁC ĐỊNH (cùng bàn cờ + cùng tham số -> cùng đường, không phụ thuộc tốc độ máy)."""
    p = params or SolverParams()
    ex_path, ex_info = None, None
    endev = _EndEval(board, p) if p.end_safety else None
    end_fn = (lambda tip, mask: -endev.penalty(tip, mask)) if endev else None       # thưởng/phạt vị trí cuối (<= 0)
    if p.use_exact and p.w_fire == 0:
        try:
            from thtg_solver import solve_exact
            grid = _to_exact_grid(board, p)
            ex_path, _sc, ex_info = solve_exact(grid, board.hero, p.w_step, p.w_diamond, p.count_step_first,
                                                node_limit=p.exact_nodes, w_reward=p.w_reward,
                                                reward_every=p.reward_every, end_fn=end_fn)
        except Exception:
            ex_path, ex_info = None, None
    if ex_info is not None and ex_info.get("complete") and ex_path:
        return _plan_from_path(board, ex_path, p, "exact", optimal=True)
    beam_plan = solve_beam(board, p)
    if ex_path is None or ex_info is None:
        return beam_plan
    sb = evaluate_path(board, beam_plan.path, p)
    se = evaluate_path(board, ex_path, p)
    sb = -1e18 if sb is None else sb
    se = -1e18 if se is None else se
    best_path, best_sc = (ex_path, se) if se >= sb else (beam_plan.path, sb)
    try:
        grid = _to_exact_grid(board, p)
        path2, _s2, info2 = solve_exact(grid, board.hero, p.w_step, p.w_diamond, p.count_step_first,
                                        node_limit=p.exact_nodes, seed_path=best_path, seed_score=best_sc,
                                        w_reward=p.w_reward, reward_every=p.reward_every, end_fn=end_fn)
        s2 = evaluate_path(board, path2, p)
        s2 = -1e18 if s2 is None else s2
        if path2 and s2 > best_sc:
            best_path, best_sc = path2, s2
        opt = bool(info2.get("complete"))
    except Exception:
        opt = False
    return _plan_from_path(board, best_path, p, "exact+beam", optimal=opt)


def validate_path(board: Board, path, params: Optional[SolverParams] = None):
    """Mô phỏng lại 1 đường đi theo luật. Trả (hợp lệ, kills, balance)."""
    p = params or SolverParams()
    r, c = board.hero
    color, bal, kills, seen = -1, 0, 0, {(r, c)}
    for (a, b) in path:
        if (a, b) in seen or max(abs(a - r), abs(b - c)) != 1:
            return False, kills, bal
        res = _step(board, p, r, c, a, b, color, bal, 0)
        if res is None:
            return False, kills, bal
        color, bal, dk = res[0], res[1], res[2]
        kills += dk
        seen.add((a, b))
        r, c = a, b
    return True, kills, bal


# =====================================================================================
# 3) Nhận diện bàn cờ từ ảnh chụp
# =====================================================================================
_TPL_DIR = "templates"
HERO_DX, HERO_DY = 7.0, 9.5      # tâm mẫu nhân vật lệch so với tâm ô (px, ảnh 671 rộng)
TPL_PITCH = 93.0                 # cạnh ô lúc cắt mẫu kim cương/quái to


def _imread(path):
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


@dataclass
class Geometry:
    cx0: float      # tâm cột 0
    cy0: float      # tâm hàng 0
    pitch: float    # cạnh 1 ô

    def center(self, r, c):
        return self.cx0 + self.pitch * c, self.cy0 + self.pitch * r


def _span(p, thr, minrun):
    """Đoạn [đầu, cuối) rộng nhất bao các đoạn liên tục p>thr dài >= minrun."""
    on = p > thr
    segs, i, n = [], 0, len(on)
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            if j - i >= minrun:
                segs.append((i, j))
            i = j
        else:
            i += 1
    return (segs[0][0], segs[-1][1]) if segs else None


def find_board_rect(frame):
    """Khung 7x7 dò theo màu nền ô be (cửa sổ LDPlayer có thể bị cắt/tỉ lệ khác nhau nên không
    dùng tỉ lệ cố định). Trả (trái, trên, cạnh_ô) hoặc None."""
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 24) & (hsv[:, :, 1] >= 25)
         & (hsv[:, :, 1] <= 110) & (hsv[:, :, 2] >= 150)).astype(np.float32)
    k = np.ones(3) / 3
    for thr in (0.18, 0.12, 0.08):
        cs = _span(np.convolve(m.mean(0), k, "same"), thr, max(10, w // 22))
        if cs is None or not (0.85 * w < cs[1] - cs[0] < 1.0 * w):
            continue
        rs = _span(np.convolve(m[:, cs[0]:cs[1]].mean(1), k, "same"), thr, max(10, w // 22))
        if rs is None:
            continue
        pitch = (cs[1] - cs[0]) / 7.0
        return float(cs[0]), float(rs[0]) + 3.0, pitch
    return None


def find_geometry(frame, hero_tpl=None):
    """Trả (Geometry, (hàng, cột) nhân vật) hoặc None. Nhân vật ĐỨNG Ở Ô BẤT KỲ (đầu trận ở giữa
    hàng trên hoặc dưới, sau mỗi lượt đứng ở cuối đường đi) nên tìm mẫu trên TOÀN BỘ bàn cờ."""
    h, w = frame.shape[:2]
    rect = find_board_rect(frame)
    if rect is None:
        return None
    left, top, pitch = rect
    k = pitch / TPL_PITCH
    if hero_tpl is None:
        hero_tpl = _imread(os.path.join(_TPL_DIR, "thtg_hero.png"))
    if hero_tpl is None:
        return None
    x1, y1 = int(max(0, left - pitch * 0.2)), int(max(0, top - pitch * 0.2))
    x2, y2 = int(min(w, left + 7.2 * pitch)), int(min(h, top + 7.2 * pitch))
    roi = frame[y1:y2, x1:x2]
    best = None
    for sc in (0.92, 1.0, 1.08):
        tpl = cv2.resize(hero_tpl, None, fx=k * sc, fy=k * sc, interpolation=cv2.INTER_AREA)
        if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
            continue
        res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if best is None or mx > best[0]:
            best = (mx, x1 + loc[0] + tpl.shape[1] / 2, y1 + loc[1] + tpl.shape[0] / 2)
    if best is None or best[0] < 0.33:
        return None
    hx, hy = best[1] - HERO_DX * k, best[2] - HERO_DY * k
    hc = int((hx - left) // pitch)
    hr = int((hy - top) // pitch)
    if not (0 <= hr < ROWS and 0 <= hc < COLS):
        return None
    return Geometry(cx0=left + pitch / 2, cy0=top + pitch / 2, pitch=pitch), (hr, hc)


def _load_tpl(name):
    return _imread(os.path.join(_TPL_DIR, name))


def _match(cell_img, tpl, pitch):
    """Điểm khớp cao nhất của mẫu (cắt ở cạnh ô TPL_PITCH) trong ảnh ô, co giãn theo pitch."""
    if tpl is None:
        return 0.0
    k = pitch / TPL_PITCH
    t = cv2.resize(tpl, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    if t.shape[0] > cell_img.shape[0] or t.shape[1] > cell_img.shape[1]:
        return 0.0
    return float(cv2.matchTemplate(cell_img, t, cv2.TM_CCOEFF_NORMED).max())


class BoardDetector:
    def __init__(self, diamond_thr=0.55, monster_thr=0.5):
        self.tpl_diamond = _load_tpl("thtg_diamond.png")
        # Mẫu quái to: templates/thtg_monster_*.png (mỗi loại quái/màu hào quang 1 file; thêm quái mới = thả thêm 1 file,
        # hoặc chạy `python thtg_bot.py --add-monster anh.png HÀNG CỘT`). Không có thì dùng mẫu cũ thtg_bigmonster.png.
        self.tpl_monsters = []
        for f in sorted(glob.glob(os.path.join(_TPL_DIR, "thtg_monster_*.png"))):
            t = _imread(f)
            if t is not None:
                self.tpl_monsters.append(t)
        if not self.tpl_monsters:
            t = _load_tpl("thtg_bigmonster.png")
            if t is not None:
                self.tpl_monsters.append(t)
        self.diamond_thr = diamond_thr
        self.monster_thr = monster_thr
        self.last_raw = {}

    def classify(self, frame, geo: Geometry, r, c):
        p = geo.pitch
        x, y = geo.center(r, c)
        half = int(p * 0.52)
        x, y = int(x), int(y + p * 0.11)
        H, W = frame.shape[:2]
        cell = frame[max(0, y - half): min(H, y + half), max(0, x - half): min(W, x + half)]
        if cell.size == 0:
            return Cell("empty")
        # 1) quái to: khớp mẫu (nhiều mẫu) HOẶC có huy hiệu số (chữ số đỏ trên nền kem ở góc dưới - quái nào cũng có,
        #    nên quái MỚI chưa có mẫu vẫn nhận ra được); kim cương bằng mẫu.
        m_mon = max([_match(cell, t, p) for t in self.tpl_monsters] or [0.0])
        m_dia = _match(cell, self.tpl_diamond, p)
        if _badge_red_px(frame, geo, r, c) >= 60 and _is_cage(frame, geo, r, c):
            return Cell("monster", n=0, mtype="cage")         # lồng: không phải quái, không có đếm ngược
        if m_mon >= self.monster_thr and m_mon >= m_dia:
            return Cell("monster", n=0, boss=True)
        if _badge_red_px(frame, geo, r, c) >= 60:
            return Cell("monster", n=0, boss=True)
        if m_dia >= self.diamond_thr:
            return Cell("diamond")
        # 2) thú theo màu chủ đạo (HSV), vùng giữa ô
        k = int(p * 0.28)
        yc = y + int(p * 0.10)          # thân con vật nằm thấp hơn tâm ô một chút
        core = frame[max(0, yc - k): yc + k, max(0, x - k): x + k]
        hsv = cv2.cvtColor(core, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        h_, s_, v_ = hsv[:, 0].astype(int), hsv[:, 1].astype(int), hsv[:, 2].astype(int)
        # đá: gần như toàn màu đá be/nâu nhạt (đo: đá >= 0.90, thú <= 0.26) - đá có thể rộng 2 ô nên mỗi ô đều là đá
        if float(((h_ >= 13) & (h_ <= 22) & (s_ >= 60) & (s_ <= 135) & (v_ >= 140)).mean()) >= 0.75:
            return Cell("stone")
        sat = (s_ > 70) & (v_ > 70)
        n_green = int((sat & (h_ >= 25) & (h_ <= 55)).sum())
        n_blue = int((sat & (h_ >= 92) & (h_ <= 125)).sum())
        n_ox = int((sat & (h_ >= 5) & (h_ <= 16)).sum())
        n_pig = int((sat & ((h_ >= 165) | (h_ <= 4))).sum())     # heo đỏ/hồng (map "Phàn giữa")
        counts = {0: n_green, 1: n_ox, 2: n_blue, 3: n_pig}
        col = max(counts, key=counts.get)
        if counts[col] < 0.08 * len(hsv):
            return Cell("empty")
        # lửa: nhiều điểm VÀNG sáng phía trên đầu con vật (đo: có lửa >= 0.14, không lửa <= 0.04)
        top = frame[max(0, y - int(p * (0.58 if r > 0 else 0.46))): y - int(p * 0.20), max(0, x - int(p * 0.25)): x + int(p * 0.25)]
        fire = False
        if top.size:
            th = cv2.cvtColor(top, cv2.COLOR_BGR2HSV).reshape(-1, 3)
            yel = ((th[:, 0] >= 14) & (th[:, 0] <= 32) & (th[:, 1] > 120) & (th[:, 2] > 220)).mean()
            fire = yel > 0.08
        return Cell("animal", color=col, fire=bool(fire))

    def signature(self, frame):
        """Chữ ký nhẹ của bàn cờ (không OCR số quái): (tuple loại ô, số ô trống) hoặc None nếu chưa thấy bàn cờ.
        Dùng để biết hoạt ảnh/quái rơi đã XONG chưa (đủ 49 ô nhận diện được + các lần chụp liên tiếp giống hệt),
        thay cho việc chờ cả màn hình đứng yên (nhân vật/quái luôn có hoạt ảnh nghỉ nên hầu như không bao giờ đứng yên)."""
        g = find_geometry(frame)
        if g is None:
            return None
        geo, hero = g
        sig, empty = [], 0
        for r in range(ROWS):
            for c in range(COLS):
                if (r, c) == hero:
                    sig.append(("hero", -1))
                    continue
                x = self.classify(frame, geo, r, c)
                if x.kind == "empty":
                    empty += 1
                sig.append((x.kind, x.color))
        return tuple(sig), empty

    def detect(self, frame, adb=None, monster_default=7):
        self.last_raw = {}          # (hàng, cột) -> (số bước đọc thô, số lượt đọc thô, đọc chắc?) của khung này; 0 = không đọc được
        g = find_geometry(frame)
        if g is None:
            return None, None
        geo, hero = g
        cells = [[self.classify(frame, geo, r, c) for c in range(COLS)] for r in range(ROWS)]
        cells[hero[0]][hero[1]] = Cell("hero")
        for r in range(ROWS):
            for c in range(COLS):
                x = cells[r][c]
                if x.kind == "monster":
                    n_raw, n_ok = _number_votes(frame, geo, r, c)
                    if x.mtype == "cage":                 # lồng không có đồng hồ cát -> khỏi đọc lượt (tránh đọc nhầm)
                        t_raw, t_ok = 0, True
                    else:
                        t_raw, t_ok = _turns_votes(frame, geo, r, c)
                    self.last_raw[(r, c)] = (n_raw, t_raw, n_ok and t_ok)
                    x.n = n_raw or monster_default
                    x.turns = t_raw
        return Board(cells, hero), geo


def _is_cage(frame, geo: Geometry, r, c) -> bool:
    """Ô LỒNG (khung đỏ/cam nhốt viên ngọc) hay quái? Lồng có thanh khung hồng/cam chạy NGANG gần hết ô ở phía trên và
    nhiều thanh dọc cùng màu; quái (chuột...) thì không. Đo trên ảnh thật: lồng thanh trên 0.90-0.93 + 24-27 cột,
    quái 0.00 + 0 cột. Chỉ gọi cho ô đã có huy hiệu số."""
    x, y = geo.center(r, c)
    h = int(geo.pitch * 0.46)
    cell = frame[max(0, int(y - h)):int(y + h), max(0, int(x - h)):int(x + h)]
    if cell.size == 0:
        return False
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    h_, s_, v_ = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    m = (((h_ >= 165) | (h_ <= 24)) & (s_ >= 100) & (v_ >= 170))
    top = float(m.mean(axis=1)[: max(1, int(len(m) * 0.4))].max())
    cols = int((m.mean(axis=0) > 0.35).sum())
    return top >= 0.6 and cols >= 12


def _badge_red_px(frame, geo: Geometry, r, c) -> int:
    """Số điểm đỏ nằm TRONG huy hiệu màu kem ở góc dưới-phải ô (chữ số bước của quái). Thú thường ~0-20, quái >= 100."""
    x, y = geo.center(r, c)
    p = geo.pitch
    x0, y0, x1, y1 = int(x + p * .18), int(y + p * .10), int(x + p * .64), int(y + p * .58)
    crop = frame[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return 0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    cream = ((h >= 8) & (h <= 30) & (s <= 110) & (v >= 190)).astype(np.uint8)
    cream = cv2.morphologyEx(cream, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(cream)
    if n <= 1:
        return 0
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    blob = (lab == i).astype(np.uint8)
    cnts, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(blob)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    filled = cv2.erode(filled, np.ones((3, 3), np.uint8))
    red = ((((h >= 160) | (h <= 10)) & (s >= 80) & (v >= 90)).astype(np.uint8)) & filled
    return int(red.sum())


def _turns_votes(frame, geo: Geometry, r, c):
    """Số LƯỢT đếm ngược của quái (đồng hồ cát đỏ bên trái, chữ số ở giữa). Quái không có đếm ngược -> 0.
    Cách đọc: tìm đồng hồ cát (2 nửa đỏ, nối lại theo chiều dọc), lấy phần giữa (chỉ ~14x14px nên phóng 8x), nhị phân hoá
    nhiều kiểu (Otsu + 3 ngưỡng tối, có/không co mỏng) rồi Tesseract 3 chế độ BỎ PHIẾU; chỉ nhận 1 chữ số 1-9 (trước đây
    chấp nhận cả '13', '31', '58' do nhiễu nên lượt đếm ngược bị đọc sai -> mức khẩn cấp sai)."""
    try:
        import pytesseract
    except Exception:
        return 0, True
    x, y = geo.center(r, c)
    p = geo.pitch
    x0, y0, x1, y1 = int(x - p * .55), int(y + p * .05), int(x + p * .02), int(y + p * .62)
    crop = frame[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return 0, True
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    red = (((h >= 170) | (h <= 8)) & (s >= 150) & (v >= 140)).astype(np.uint8)
    merged = cv2.morphologyEx(red, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 15)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(merged)
    if n <= 1:
        return 0, True                              # không có đồng hồ cát = quái không đếm ngược
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    bx, by, bw, bh, _area = st[i]
    if bw < 8 or bh < 14 or bh < bw * 0.9:          # đồng hồ cát cao hơn rộng
        return 0, True
    reg = crop[by + int(bh * .25): by + int(bh * .75), bx + int(bw * .18): bx + int(bw * .82)]
    if reg.size == 0:
        return 0, False
    g = cv2.cvtColor(reg, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
    outs = [cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]]
    for t_ in (80, 110, 140):
        outs.append(((g < t_) * 255).astype(np.uint8))
    votes = {}
    for b in outs:
        for thin in (False, True):
            bb = cv2.erode(b, np.ones((5, 5), np.uint8)) if thin else b
            img = cv2.copyMakeBorder(255 - bb, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
            for psm in (10, 8, 13):
                try:
                    t = pytesseract.image_to_string(
                        img, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789").strip()
                except Exception:
                    return 0, False
                if t.isdigit() and 1 <= int(t) <= 9:
                    votes[int(t)] = votes.get(int(t), 0) + 1
                    top = sorted(votes.values(), reverse=True) + [0]
                    if top[0] >= 3 and top[1] == 0:        # 3 lần đọc đều ra cùng 1 số -> dừng sớm (nhanh gấp nhiều lần)
                        return int(t), True
    if not votes:
        return 0, False
    top = sorted(votes.values(), reverse=True) + [0]
    best = max(votes, key=votes.get)
    return best, (top[0] >= 3 and top[0] >= 3 * top[1])


def read_monster_turns(frame, geo: Geometry, r, c) -> int:
    """Số lượt đếm ngược của quái (xem _turns_votes). Quái không có đếm ngược / không đọc được -> 0."""
    return _turns_votes(frame, geo, r, c)[0]


def _number_votes(frame, geo: Geometry, r, c):
    """Số bước cần của quái to: chữ số ĐỎ trên huy hiệu màu KEM ở góc dưới-phải ô. Cách đọc: tìm mảng kem (huy hiệu),
    lấp đầy, chỉ lấy điểm đỏ NẰM TRONG huy hiệu (loại hào quang hồng/móng vuốt quanh quái), bỏ các đốm nhỏ, cắt sát chữ
    số rồi chuẩn hoá cao 48px; OCR (Tesseract) 3 độ dày nét x 4 chế độ rồi BỎ PHIẾU (kết quả đúng số chữ số được tính
    gấp đôi). Đo trên ảnh thật (huy hiệu '5', 7 cỡ ảnh 0.8-1.25x + ảnh nền tối): bản cũ đúng 14/30 (đọc ra 3, 8, 45,
    58, 0...) -> bản này 30/30. Không đọc được -> 0 (bên gọi dùng monster_default). Không cần adb (giữ tham số để
    tương thích)."""
    try:
        import pytesseract
    except Exception:
        return 0, False
    x, y = geo.center(r, c)
    p = geo.pitch
    x0, y0, x1, y1 = int(x + p * .18), int(y + p * .10), int(x + p * .64), int(y + p * .58)
    crop = frame[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return 0, False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    cream = ((h >= 8) & (h <= 30) & (s <= 110) & (v >= 190)).astype(np.uint8)
    cream = cv2.morphologyEx(cream, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(cream)
    if n <= 1:
        return 0, False
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    if st[i, cv2.CC_STAT_AREA] < 0.06 * crop.shape[0] * crop.shape[1]:
        return 0, False
    blob = (lab == i).astype(np.uint8)
    cnts, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(blob)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    filled = cv2.erode(filled, np.ones((3, 3), np.uint8))
    red = ((((h >= 160) | (h <= 10)) & (s >= 80) & (v >= 90)).astype(np.uint8)) & filled
    if int(red.sum()) < 12:
        return 0, False
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(red)
    if n2 <= 1:
        return 0, False
    areas = st2[1:, cv2.CC_STAT_AREA]
    keep = [1 + k for k, a in enumerate(areas) if a >= max(8, 0.2 * areas.max())]     # bỏ đốm nhỏ (nhiễu)
    if not keep:
        return 0, False
    m = np.isin(lab2, keep).astype(np.uint8)
    ys, xs = np.where(m)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    base = cv2.resize(m * 255, None, fx=48.0 / m.shape[0], fy=48.0 / m.shape[0], interpolation=cv2.INTER_CUBIC)
    base = (base > 100).astype(np.uint8) * 255
    want_len = min(len(keep), 2)
    votes = {}
    for k in (0, 1, -1):                       # nét nguyên / dày / mỏng
        v_ = cv2.dilate(base, np.ones((3, 3), np.uint8)) if k == 1 else (
            cv2.erode(base, np.ones((3, 3), np.uint8)) if k == -1 else base)
        img = cv2.copyMakeBorder(255 - v_, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
        for psm in (10, 8, 7, 13):
            try:
                t = pytesseract.image_to_string(
                    img, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789").strip()
            except Exception:
                return 0, False
            if t.isdigit() and 1 <= int(t) <= 99:
                votes[int(t)] = votes.get(int(t), 0) + (2 if len(t) == want_len else 1)
                top = sorted(votes.values(), reverse=True) + [0]
                if top[0] >= 4 and top[1] == 0:            # >= 2 lần đọc đúng số chữ số, không có số nào khác -> dừng sớm
                    return int(t), True
    if not votes:
        return 0, False
    top = sorted(votes.values(), reverse=True) + [0]
    return max(votes, key=votes.get), (top[0] >= 4 and top[0] >= 3 * top[1])


def read_monster_number(frame, geo: Geometry, r, c, adb=None) -> int:
    """Số bước cần của quái to (xem _number_votes). Không đọc được -> 0 (bên gọi dùng monster_default)."""
    return _number_votes(frame, geo, r, c)[0]


# =====================================================================================
# 4) Thực thi
# =====================================================================================
class _Stop(Exception):
    pass


class THTGBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_turns=50,
                 params: Optional[SolverParams] = None, tap_delay=0.12, settle_max=8.0,
                 use_skill=True, monster_default=7, save_debug=None, debug_dir="debug_thtg",
                 press_attack=True, attack_xy=(0.87, 0.96), attack_delay=0.6, rage_xy=(0.18, 0.93),
                 attack_wait_base=1.5, attack_wait_per_step=0.15, attack_wait_per_kill=1.2, skill_wait=4.0,
                 settle_stable=3, rage_portrait=True, rage_delay=0.5, ready_first_wait=0.6, vote_frames=3):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.test = test
        self.max_turns = max_turns
        self.params = params or SolverParams()
        self.tap_delay = tap_delay
        self.settle_max = settle_max
        self.use_skill = use_skill
        self.monster_default = monster_default
        self.press_attack = press_attack      # bấm nút "Chiến" sau khi nối xong đường đi (không bấm thì không đánh)
        self.attack_xy = attack_xy            # vị trí nút Chiến, tỉ lệ theo ảnh (x/w, y/h)
        self.attack_delay = attack_delay      # nghỉ sau khi bấm ô cuối rồi mới bấm Chiến
        self.rage_xy = rage_xy                # nơi bấm để DÙNG NỘ khi thanh nộ đầy (mặc định: ảnh nhân vật)
        # Bấm Chiến xong nhân vật phải CHẠY dọc đường đi và đánh từng con (mất vài giây, càng nhiều bước/quái càng lâu)
        # rồi quái mới mới rơi xuống: nghỉ tối thiểu base + per_step*số bước + per_kill*số quái rồi mới chờ bàn cờ yên.
        self.attack_wait_base = attack_wait_base
        self.attack_wait_per_step = attack_wait_per_step
        self.attack_wait_per_kill = attack_wait_per_kill
        self.skill_wait = skill_wait          # nghỉ tối thiểu sau khi dùng nộ (nhân vật chạy đi đánh từng con)
        self.settle_stable = settle_stable    # số lần chụp liên tiếp thấy bàn cờ đứng yên mới coi là xong
        self.rage_portrait = rage_portrait    # true: bấm ảnh nhân vật (rage_xy) RỒI bấm Chiến để dùng nộ (false = chỉ bấm Chiến)
        self.rage_delay = rage_delay          # nghỉ giữa bấm ảnh nhân vật (nộ) và bấm Chiến
        self.ready_first_wait = ready_first_wait   # nghỉ tối thiểu trước khi bắt đầu kiểm tra bàn cờ đã sẵn sàng
        self.vote_frames = vote_frames        # số khung chụp để bỏ phiếu số bước/lượt của quái (1 = chỉ khung đầu)
        self._pending_wait = 0.0
        self._rage_raw = []
        self._rage_fail_logs = 0
        self.det = BoardDetector()
        self.save_debug = test if save_debug is None else save_debug   # TEST: luôn lưu đường đi thử
        self.debug_dir = debug_dir
        self._turn = 0

    def _save(self, name, img, text=None):
        """Lưu ảnh (và ghi chú) vào debug_thtg/. Không bao giờ ném lỗi."""
        try:
            os.makedirs(self.debug_dir, exist_ok=True)
            ok, buf = cv2.imencode(".png", img)
            if ok:
                buf.tofile(os.path.join(self.debug_dir, name + ".png"))
            if text:
                with open(os.path.join(self.debug_dir, name + ".txt"), "w", encoding="utf-8") as f:
                    f.write(text)
            return os.path.join(self.debug_dir, name + ".png")
        except Exception:
            return None

    def _check(self):
        if self.should_stop():
            raise _Stop()

    def _shot(self):
        return self.adb.screencap_fast()

    def _sleep(self, secs):
        end = time.time() + secs
        while time.time() < end:
            self._check()
            time.sleep(min(0.2, max(0.0, end - time.time())))

    def _settle(self, min_wait=0.0):
        """Chờ bàn cờ SẴN SÀNG: (1) nghỉ tối thiểu max(min_wait, ready_first_wait) (nhân vật chạy dọc đường đi và đánh từng
        con), (2) đủ 49 ô nhận diện được (không còn ô trống do đang rơi) và `settle_stable` lần chụp liên tiếp giống hệt
        nhau (chữ ký bàn cờ `BoardDetector.signature`), (3) nhận lại được nhân vật (đang chạy/đánh thì không thấy).
        Nhanh hơn nhiều so với chờ cả màn hình đứng yên và tránh nhận diện giữa chừng hoạt ảnh (bàn cờ thiếu ô -> đường
        đi 1-3 bước). `settle_max` tính từ sau lúc nghỉ tối thiểu."""
        self._sleep(max(min_wait, self.ready_first_wait))
        t0 = time.time()
        need_same = max(1, self.settle_stable - 1)       # settle_stable lần chụp giống nhau = settle_stable-1 lần "bằng"
        prev, same, last = None, 0, None
        while True:
            self._check()
            f = self._shot()
            if f is not None:
                last = f
                res = self.det.signature(f)
                if res is not None:
                    sig, empty = res
                    same = same + 1 if sig == prev else 0
                    prev = sig
                    if same >= need_same and empty == 0:
                        break
                    if same >= 8:          # bàn cờ có ô trống thật (không phải đang rơi) -> đừng chờ mãi
                        break
                else:
                    prev, same = None, 0
            if time.time() - t0 > self.settle_max:
                break
            time.sleep(0.12)
        self.log("info", f"Ngưu Ma Vương: chờ bàn cờ sẵn sàng {time.time() - t0:.1f}s")
        return last if last is not None else self._shot()

    @staticmethod
    def _parse_rage(txt):
        """'2685/1000' / '26851000' (OCR hay làm rơi dấu '/') -> (2685, 1000); không hiểu -> None."""
        txt = str(txt).strip()
        if "/" in txt:
            left, right = txt.split("/", 1)
            left = "".join(ch for ch in left if ch.isdigit())
            right = "".join(ch for ch in right if ch.isdigit())
            if right != "1000" or not left:
                return None
            return (1000 if left in ("1000", "000") else int(left)), 1000
        digits = "".join(ch for ch in txt if ch.isdigit())
        if len(digits) >= 5 and digits.endswith("1000"):
            left = digits[:-4]
            return (1000 if left in ("1000", "000") else int(left)), 1000
        return None

    @staticmethod
    def _rage_white_ocr(crop):
        """Chữ trên thanh nộ màu TRẮNG trên nền cam: Otsu thường làm mất chữ (đọc ra rỗng) nên tách riêng các điểm trắng
        (độ bão hoà thấp + rất sáng) thành chữ đen trên nền trắng rồi mới OCR. Thử vài ngưỡng bão hoà."""
        import pytesseract
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        out = []
        for smax in (125, 110, 140):          # đo: chữ trắng trên nền cam có độ bão hoà tới ~110 (do viền mờ)
            m = ((hsv[:, :, 1] < smax) & (hsv[:, :, 2] > 190)).astype(np.uint8) * 255
            m = 255 - cv2.resize(m, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
            m = cv2.GaussianBlur(m, (3, 3), 0)
            m = cv2.copyMakeBorder(m, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
            out.append(pytesseract.image_to_string(
                m, config="--psm 7 -c tessedit_char_whitelist=0123456789/"))
        return out

    def read_rage(self, frame):
        """Đọc 'x/y' ở thanh nộ bằng OCR. Trả (x, y) hoặc None. Thử lần lượt: tách chữ trắng (đúng với thanh nộ cam),
        OCR của adb, Tesseract thường; 2 vùng đọc (vùng chuẩn rồi vùng cao hơn). x có thể LỚN HƠN 1000 (vd 2685/1000 = đầy).
        Chữ số đầu của x hay bị ngọn lửa che nên chỉ nhận "đầy" khi x là 1000 hoặc 000 (ba số 0 sau khi mất số 1) hoặc >= 1000."""
        h, w = frame.shape[:2]
        boxes = [(int(w * 0.19), int(h * 0.963), int(w * 0.40), int(h * 0.985)),
                 (int(w * 0.19), int(h * 0.945), int(w * 0.40), int(h * 0.995))]
        self._rage_raw = []
        for box in boxes:
            crop = frame[box[1]:box[3], box[0]:box[2]]
            if crop.size == 0:
                continue
            txts = []
            try:
                txts += self._rage_white_ocr(crop)
            except Exception:
                pass
            if hasattr(self.adb, "ocr_text_in_box"):
                try:
                    txts.append(str(self.adb.ocr_text_in_box(frame, box, lang="eng", charset="digits")))
                except Exception:
                    pass
            try:
                import pytesseract
                g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                g = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
                txts.append(pytesseract.image_to_string(
                    g, config="--psm 7 -c tessedit_char_whitelist=0123456789/"))
            except Exception:
                pass
            for t in txts:
                self._rage_raw.append(str(t).strip())
                res = self._parse_rage(t)
                if res is not None:
                    return res
        return None

    def _tap_ratio(self, frame, xy):
        h, w = frame.shape[:2]
        self.adb.tap_px(w * xy[0], h * xy[1])

    def _press_skill(self, frame):
        """DÙNG NỘ khi thanh nộ đầy: bấm ẢNH NHÂN VẬT (rage_xy, góc trái trên thanh nộ) RỒI bấm Chiến thì nộ mới được dùng
        (rage_portrait=false: chỉ bấm Chiến). Chế độ TEST chỉ ghi log, không bấm. Sau đó nhân vật chạy đi đánh từng con
        nên bên gọi phải chờ (skill_wait) rồi mới đi tiếp."""
        self.log("info", "Ngưu Ma Vương: nộ đầy -> " + ("bấm ảnh nhân vật rồi bấm Chiến để dùng nộ"
                                                       if self.rage_portrait else "bấm Chiến để dùng nộ"))
        if self.test:
            return
        if self.rage_portrait:
            self._tap_ratio(frame, self.rage_xy)
            self._sleep(self.rage_delay)
        self._tap_ratio(frame, self.attack_xy)

    def _press_attack(self, frame):
        """Bấm nút Chiến để thực hiện đường đi vừa nối (phải bấm thì mới đánh)."""
        self.log("info", "Ngưu Ma Vương: bấm Chiến")
        self._tap_ratio(frame, self.attack_xy)

    def _vote_monsters(self, board, geo, frame):
        """Số bước cần / số lượt đếm ngược của quái đọc bằng OCR nên thỉnh thoảng sai 1 khung (sai số bước = bot tưởng quái
        không ăn nổi -> bỏ quái). Quái nào khung đầu đọc CHƯA chắc (không ra số, hoặc các lần đọc không thống nhất) thì chụp
        thêm tới `vote_frames` khung, đọc lại rồi lấy số xuất hiện NHIỀU NHẤT (hoà thì giữ số khung đầu); quái đọc chắc thì
        khỏi tốn thêm thời gian. Luôn ghi log số đã dùng; không đọc được hẳn thì dùng monster_default."""
        mons = [(r, c) for r in range(ROWS) for c in range(COLS) if board.cells[r][c].kind == "monster"]
        if not mons:
            return
        reads = {rc: [self.det.last_raw.get(rc, (0, 0, False))[:2]] for rc in mons}
        unsure = [rc for rc in mons if not self.det.last_raw.get(rc, (0, 0, False))[2]]
        for _ in range(max(0, self.vote_frames - 1)):
            if not unsure:
                break
            try:
                self._check()
                time.sleep(0.15)
                f2 = self._shot()
                if f2 is None:
                    continue
                still = []
                for (r, c) in unsure:
                    n_, n_ok = _number_votes(f2, geo, r, c)
                    if board.cells[r][c].mtype == "cage":
                        t_, t_ok = 0, True
                    else:
                        t_, t_ok = _turns_votes(f2, geo, r, c)
                    reads[(r, c)].append((n_, t_))
                    if not (n_ok and t_ok):
                        still.append((r, c))
                unsure = still
            except _Stop:
                raise
            except Exception:
                break
        parts = []
        for (r, c) in mons:
            x = board.cells[r][c]
            for idx, name in ((0, "n"), (1, "turns")):
                vals = [v[idx] for v in reads[(r, c)] if v[idx]]
                if vals:
                    best = max(set(vals), key=lambda k: (vals.count(k), k == vals[0]))
                    setattr(x, name, best)
                elif idx == 0:
                    x.n = self.monster_default
                else:
                    x.turns = 0
            note = ""
            if not any(v[0] for v in reads[(r, c)]):
                note = " (KHÔNG đọc được -> dùng mặc định)"
            elif any(v[0] != x.n for v in reads[(r, c)]):
                note = f" (các khung đọc: {[v[0] for v in reads[(r, c)]]})"
            if x.mtype == "cage":
                parts.append(f"({r},{c}) LỒNG cần {x.n}{note}")
            else:
                parts.append(f"({r},{c}) cần {x.n}, đếm ngược {x.turns}{note}")
        self.log("info", "Ngưu Ma Vương: quái to/lồng: " + "; ".join(parts))

    def play_turn(self, frame):
        board, geo = self.det.detect(frame, self.adb, self.monster_default)
        stamp = time.strftime("%H%M%S")
        if board is None:
            where = self._save(f"{stamp}_khong_thay_ban_co", frame)
            self.log("warn", "Ngưu Ma Vương: không thấy nhân vật/bàn cờ (hết trận?)"
                     + (f" - đã lưu ảnh: {where}" if where else ""))
            return None
        self._vote_monsters(board, geo, frame)
        plan = solve(board, self.params)
        self.log("info", f"Ngưu Ma Vương: kế hoạch {plan.steps} bước, diệt {plan.kills} quái to, "
                         f"dùng {plan.diamonds} kim cương, thưởng {plan.reward} (ròng {plan.reward - plan.diamonds:+d}), "
                         f"điểm {plan.score:.0f}"
                         + (" [tối ưu đã chứng minh]" if plan.optimal else f" [{plan.solver}]"))
        if plan.path:
            er, ec = plan.path[-1]
            if plan.end_pen > 0:
                self.log("info", f"Ngưu Ma Vương: nhân vật sẽ đứng ở ({er},{ec}) - vị trí cuối bị phạt {plan.end_pen:.0f} điểm "
                                 f"(góc/mép/ít ô đi tiếp) nhưng đã là lựa chọn tốt nhất")
            else:
                self.log("info", f"Ngưu Ma Vương: nhân vật sẽ đứng ở ({er},{ec}) - vị trí cuối an toàn")
        self._turn += 1
        n_cage = sum(1 for (r, c) in plan.path if board.cells[r][c].mtype == "cage" and board.cells[r][c].kind == "monster")
        if n_cage:
            self.log("info", f"Ngưu Ma Vương: đường đi mở khoá {n_cage} ô lồng (lồng thành kim cương, không tính là diệt quái)")
        suspicious = plan.steps <= 4 and not self.save_debug
        if self.save_debug or suspicious:
            txt = (board.pretty() + f"\nNhân vật: hàng {board.hero[0]}, cột {board.hero[1]}\n"
                   f"Đường đi ({plan.steps} bước): {plan.path}\n"
                   f"Quái to (hàng, cột, số bước cần, số lượt đếm ngược): {[(r, c, board.cells[r][c].n, board.cells[r][c].turns) for r in range(ROWS) for c in range(COLS) if board.cells[r][c].kind == 'monster' and board.cells[r][c].mtype != 'cage']}\n"
                   f"Lồng (hàng, cột, số bước cần): {[(r, c, board.cells[r][c].n) for r in range(ROWS) for c in range(COLS) if board.cells[r][c].kind == 'monster' and board.cells[r][c].mtype == 'cage']}\n"
                   f"Bộ giải: {plan.solver}{' (tối ưu đã chứng minh)' if plan.optimal else ''}, diệt {plan.kills} quái, dùng {plan.diamonds} kim cương, thưởng {plan.reward}\n"
                   f"Phạt vị trí cuối (kẹt/góc/mép): {plan.end_pen:.0f}\n")
            where = self._save(f"{stamp}_luot{self._turn}", draw_plan(frame, geo, board, plan), txt)
            if where:
                self.log("info", f"Ngưu Ma Vương: đã lưu {'ảnh kế hoạch ngắn bất thường' if suspicious else 'đường đi thử'}: {where}")
        if not plan.path:
            self.log("warn", "Ngưu Ma Vương: không có đường đi")
            return plan
        if self.test:
            return plan
        for (r, c) in plan.path:
            self._check()
            x, y = geo.center(r, c)
            self.adb.tap_px(x, y)
            time.sleep(self.tap_delay)
        if self.press_attack:
            self._check()
            time.sleep(self.attack_delay)
            self._press_attack(frame)
            self._pending_wait = (self.attack_wait_base + self.attack_wait_per_step * plan.steps
                                  + self.attack_wait_per_kill * plan.kills)
        return plan

    def run(self) -> bool:
        turns = 0
        rage_tries = 0
        try:
            while turns < self.max_turns:
                self._check()
                frame = self._settle(self._pending_wait) if turns else self._shot()
                self._pending_wait = 0.0
                if frame is None:
                    self.log("error", "Ngưu Ma Vương: không chụp được màn hình")
                    return False
                if self.use_skill and not self.test and rage_tries < 2:
                    rage = self.read_rage(frame)
                    if rage is None and self._rage_fail_logs < 3:
                        self._rage_fail_logs += 1
                        hh, ww = frame.shape[:2]
                        where = self._save(f"{time.strftime('%H%M%S')}_khong_doc_duoc_no",
                                           frame[int(hh * 0.90):, :int(ww * 0.5)], f"OCR thô: {self._rage_raw}")
                        self.log("warn", f"Ngưu Ma Vương: không đọc được thanh nộ (OCR thô: {self._rage_raw})"
                                         + (f" - đã lưu ảnh: {where}" if where else ""))
                    if rage and rage[0] >= rage[1]:
                        rage_tries += 1
                        self._press_skill(frame)
                        self._pending_wait = self.skill_wait
                        turns += 1
                        continue            # đầu vòng sau tự chờ bàn cờ sẵn sàng rồi tính đường
                    rage_tries = 0
                elif self.use_skill and self.test:
                    rage = self.read_rage(frame)
                    if rage and rage[0] >= rage[1]:
                        self.log("info", "Ngưu Ma Vương: [TEST] nộ đầy -> sẽ bấm " + (
                            "ảnh nhân vật rồi bấm Chiến" if self.rage_portrait else "Chiến"))
                if rage_tries >= 2:
                    self.log("warn", "Ngưu Ma Vương: bấm nộ 2 lần mà thanh nộ vẫn đầy - kiểm tra field rage_xy "
                                     "(và rage_portrait); lượt này bỏ qua nộ")
                    rage_tries = 0
                plan = self.play_turn(frame)
                if plan is None:
                    return turns > 0
                turns += 1
                if self.test:
                    self.log("info", "Ngưu Ma Vương: chế độ TEST - dừng sau 1 lượt, không bấm gì")
                    return True
        except _Stop:
            self.log("info", "Ngưu Ma Vương: đã dừng")
            return False
        self.log("info", f"Ngưu Ma Vương: xong {turns} lượt")
        return True


def run_auto_thtg_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """
    Field của bước (đều tuỳ chọn):
      test (false)           - true: chỉ nhận diện + tính đường, KHÔNG bấm gì
      max_turns (50)         - số lượt tối đa
      beam (5000)            - độ rộng beam search (tối thiểu 5000)
      tap_delay (0.12)       - nghỉ giữa 2 lần bấm ô (giây)
      use_skill (true)       - nộ đầy thì bấm Chiến
      monster_default (7)    - số bước quái to khi OCR không đọc được
      save_debug (null)      - lưu ảnh đường đi vào debug_dir; null = chỉ khi test (true/false để ép)
      debug_dir (debug_thtg) - thư mục lưu ảnh/ghi chú đường đi
      count_step_first (false) - true: cần (bước+1) >= N để diệt quái N
      press_attack (true)    - nối xong thì bấm nút Chiến để đánh (false = chỉ nối, tự bấm Chiến)
      attack_xy ([0.87,0.96]) - vị trí nút Chiến theo tỉ lệ ảnh [x/w, y/h]
      attack_delay (0.6)     - nghỉ (giây) giữa ô cuối và lúc bấm Chiến
      rage_xy ([0.18,0.93])  - ảnh nhân vật góc trái trên thanh nộ: nộ đầy thì bấm vào đây RỒI bấm Chiến (khi rage_portrait=true)
      rage_portrait (true)   - dùng nộ: true = bấm ảnh nhân vật rồi bấm Chiến, false = chỉ bấm Chiến
      rage_delay (0.5)       - nghỉ (giây) giữa bấm ảnh nhân vật và bấm Chiến khi dùng nộ
      vote_frames (3)        - số khung chụp để bỏ phiếu số bước/lượt đếm ngược của quái (OCR hay sai 1 khung; 1 = tắt)
      ready_first_wait (0.6) - nghỉ tối thiểu rồi mới kiểm tra bàn cờ đã rơi xong chưa (sau Chiến vẫn nghỉ attack_wait_* nếu lâu hơn)
      attack_wait_base (1.5) / attack_wait_per_step (0.15) / attack_wait_per_kill (1.2)
                             - sau khi bấm Chiến nghỉ tối thiểu base + per_step*số bước + per_kill*số quái (nhân vật chạy đi
                               đánh từng con) rồi mới chờ bàn cờ yên và đi tiếp
      skill_wait (4.0)       - nghỉ tối thiểu sau khi dùng nộ
      settle_stable (3)      - số lần chụp liên tiếp thấy bàn cờ (đủ 49 ô, giống hệt nhau) mới coi là xong hoạt ảnh
      settle_max (20.0)      - chờ hoạt ảnh tối đa bao nhiêu giây
      diamond_cost (40)      - điểm TRỪ mỗi kim cương phải đi qua (kim cương để tạo lối đi, không cần ăn hết; 0 = không trừ)
      diamond_reward (60)    - điểm CỘNG cho mỗi kim cương được thưởng (cứ đủ 10 bước thưởng 1 viên) -> ưu tiên đi tròn mốc 10/20/30 bước
      reward_every (10)      - số bước để được thưởng 1 kim cương
      end_safety (true)      - phạt bước cuối đi vào góc/mép/chỗ lượt sau bị kẹt (false = tắt)
      fall_down (true)       - mô phỏng ô rơi xuống theo cột khi tính chỗ kẹt (false = coi ô đã đi thành ô mới tại chỗ)
      w_corner (150) / w_edge (40) - điểm phạt kết thúc ở góc / mép
      use_exact (true)       - dùng bộ giải chính xác thtg_solver.py trước (false = chỉ beam)
      exact_nodes (400000)   - giới hạn số nút của bộ giải chính xác (không phải giây -> kết quả xác định)
    """
    # beam < 5000 từng khiến ~1/8 bàn bị bỏ sót đường tốt hơn (đo 40 bàn ngẫu nhiên: 5000 = 0 bàn thua beam 12000, ~0.12s/bàn)
    # nên coi 5000 là mức tối thiểu, kể cả kịch bản cũ đã lưu beam=2000.
    params = SolverParams(beam=max(5000, int(step.get("beam", 5000))),
                          use_exact=bool(step.get("use_exact", True)),
                          exact_nodes=int(step.get("exact_nodes", 400000)),
                          count_step_first=bool(step.get("count_step_first", False)),
                          w_diamond=-abs(float(step.get("diamond_cost", 40.0))),
                          w_reward=float(step.get("diamond_reward", 60.0)),
                          reward_every=max(1, int(step.get("reward_every", 10))),
                          end_safety=bool(step.get("end_safety", True)),
                          fall_down=bool(step.get("fall_down", True)),
                          w_corner=float(step.get("w_corner", 150.0)),
                          w_edge=float(step.get("w_edge", 40.0)))
    bot = THTGBot(adb, log=log, should_stop=should_stop, test=bool(step.get("test", False)),
                  max_turns=int(step.get("max_turns", 50)), params=params,
                  tap_delay=float(step.get("tap_delay", 0.12)),
                  use_skill=bool(step.get("use_skill", True)),
                  monster_default=int(step.get("monster_default", 7)),
                  save_debug=step.get("save_debug"), debug_dir=step.get("debug_dir", "debug_thtg"),
                  press_attack=bool(step.get("press_attack", True)),
                  attack_xy=tuple(step.get("attack_xy", (0.87, 0.96))),
                  attack_delay=float(step.get("attack_delay", 0.6)),
                  rage_xy=tuple(step.get("rage_xy", (0.18, 0.93))),
                  attack_wait_base=float(step.get("attack_wait_base", 1.5)),
                  attack_wait_per_step=float(step.get("attack_wait_per_step", 0.15)),
                  attack_wait_per_kill=float(step.get("attack_wait_per_kill", 1.2)),
                  skill_wait=float(step.get("skill_wait", 4.0)),
                  settle_stable=int(step.get("settle_stable", 3)),
                  rage_portrait=bool(step.get("rage_portrait", True)),
                  rage_delay=float(step.get("rage_delay", 0.5)),
                  ready_first_wait=float(step.get("ready_first_wait", 0.6)),
                  vote_frames=max(1, int(step.get("vote_frames", 3))),
                  settle_max=float(step.get("settle_max", 20.0)))
    return bot.run()


def draw_plan(frame, geo: Geometry, board: Board, plan: Plan):
    img = frame.copy()
    pts = [geo.center(*board.hero)] + [geo.center(r, c) for r, c in plan.path]
    for i in range(len(pts) - 1):
        cv2.line(img, tuple(int(v) for v in pts[i]), tuple(int(v) for v in pts[i + 1]), (0, 0, 255), 4)
    for i, (x, y) in enumerate(pts[1:], 1):
        cv2.putText(img, str(i), (int(x) - 8, int(y) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return img


def add_monster_template(img_path, row, col):
    """Cắt ô (row, col) của ảnh chụp thành mẫu quái mới: templates/thtg_monster_<n>.png (hàng/cột đếm từ 0)."""
    im = _imread(img_path)
    g = find_geometry(im) if im is not None else None
    if g is None:
        print("Không thấy bàn cờ trong ảnh.")
        return None
    geo, _hero = g
    x, y = geo.center(row, col)
    h = int(geo.pitch * 0.42 * 1.0)
    k = TPL_PITCH / geo.pitch                      # quy về cạnh ô chuẩn 93px như các mẫu khác
    crop = im[int(y) - h:int(y) + h, int(x) - h:int(x) + h]
    crop = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    os.makedirs(_TPL_DIR, exist_ok=True)
    n = len(glob.glob(os.path.join(_TPL_DIR, "thtg_monster_*.png"))) + 1
    out = os.path.join(_TPL_DIR, f"thtg_monster_{n}.png")
    ok, buf = cv2.imencode(".png", crop)
    if ok:
        buf.tofile(out)
    print("Đã lưu mẫu quái:", out)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "--add-monster" and len(sys.argv) >= 5:
        add_monster_template(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        sys.exit(0)
    frame = _imread(sys.argv[1])
    prm = SolverParams(beam=int(sys.argv[2]) if len(sys.argv) > 2 else 5000)
    bd = BoardDetector()
    brd, geo = bd.detect(frame)
    if brd is None:
        print("Không thấy nhân vật trong ảnh.")
        sys.exit(1)
    print(brd.pretty())
    t = time.time()
    pl = solve(brd, prm)
    print(f"{pl.steps} bước, diệt {pl.kills} quái, dùng {pl.diamonds} kim cương, thưởng {pl.reward}, phạt cuối {pl.end_pen:.0f}, "
          f"còn {pl.final_balance} bước, {time.time()-t:.2f}s")
    print(pl.path)
    cv2.imwrite("thtg_debug.png", draw_plan(frame, geo, brd, pl))
