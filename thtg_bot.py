# -*- coding: utf-8 -*-
"""
Bot auto game "Ngưu Ma Vương" (màn Thất Thánh - Phàn Đầu) qua ADB. Không import tkinter.

Luật (suy từ mô tả + ảnh, các điểm chưa chắc để thành tham số):
- Lưới 7x7, đường đi 8 HƯỚNG, không đi lại ô cũ, bắt đầu từ ô cạnh nhân vật (hàng 0).
- Chỉ nối thú CÙNG LOẠI (ếch/bò/mèo). Kim cương hoặc diệt quái to -> được đổi loại.
- Nối xong phải bấm nút "Chiến" mới đánh. Thanh nộ đầy thì dùng nộ TRƯỚC khi đi.
- Mỗi ô đi qua +1 bước. Quái to số N: cần đủ N bước tích luỹ, bị trừ N, vẫn +1 bước
  vừa đi (vd 10 bước, quái 7 -> 3, cộng 1 = 4).
- Ô LỒNG CÓ MÀU (khung xanh/hồng-đỏ/cam/lục tương ứng mèo/heo/bò/ếch; `Cell.color` của ô lồng): đang nối con màu nào thì CHỈ đi qua lồng CÙNG màu
  (đỏ -> lồng đỏ), đi qua xong vẫn giữ màu đó nối tiếp. Lồng màu không rõ (color = -1) thì qua được mọi màu.
- Ô LỒNG (khung nhốt viên ngọc, có số ở góc): luôn cần ĐÚNG 5 bước (`CAGE_STEPS`, không đọc số bằng OCR vì hay sai): như quái to, cần đủ 5 bước mới đi qua được (bị trừ 5, vẫn +1 bước);
  nhưng đi qua lồng KHÔNG được đổi loại (giữ nguyên loại thú đang nối). Phá lồng xong nó mở khoá thành kim cương thường
  (từ lúc đó mới đổi loại được) và KHÔNG tính là diệt quái (Cell.mtype == "cage").
- THƯỞNG KIM CƯƠNG: nối được N bước rồi bấm Chiến thì LƯỢT SAU có N // 10 ô thú con biến thành kim cương (10-19 bước -> 1,
  20-29 -> 2, 30-39 -> 3...; vd 23 bước -> 2 viên). Kim cương chủ yếu để TẠO LỐI ĐI (đổi loại thú), không cần ăn hết: mỗi viên dùng bị trừ điểm (SolverParams.w_diamond < 0),
  mỗi mốc 10 bước được cộng điểm (w_reward) -> ưu tiên đi TRÒN mốc 10 bước và chỉ dùng kim cương khi cần làm cầu nối /
  để chạm mốc (vd 33 bước dùng 3 viên là hợp lý; 31 bước thì dùng 2 viên thôi, chừa 1 viên).
- "Hiệp còn lại" (vòng tròn góc trái trên) = số LƯỢT ĐI còn lại; về 0 mà chưa diệt hết quái to là THUA. Bot đọc số này mỗi lượt
  (`read_turns_left`, tự đếm lùi khi OCR không chắc): lượt CUỐI (còn 1) thì kim cương thưởng/chống kẹt vô nghĩa nên tắt hết,
  dồn toàn lực diệt quái; còn <= 2 hiệp mà chưa diệt hết thì ghi cảnh báo.
- Mỗi lượt các ô đã đi biến mất, quái mới rơi từ trên xuống (không đoán được) nên chỉ
  tối ưu từng lượt. Nhân vật đứng lại ở ô CUỐI đường đi nên bước cuối bị phạt (`_EndEval`) nếu: dồn vào góc/mép, hoặc sau khi
  các ô rơi xuống mà quanh nhân vật gần như không còn ô đi vào được (quái to/lồng/đá chặn) -> lượt sau bị kẹt không có đường.
  Không phạt khi đường đi diệt nốt quái to cuối cùng.
- Ô GỖ (map mới, hộp gỗ úp lên 1 con thú) có 2 trạng thái: ĐÓNG (hộp cao che gần hết con thú, chỉ lòi cái đầu) = như ĐÁ,
  không đi vào được (Cell.kind == "stone", Cell.box == "closed"); MỞ (hộp thấp, con thú lộ ra) = như ô thú con BÌNH THƯỜNG
  (Cell.kind == "animal", Cell.box == "open"). Trạng thái đọc lại từ ảnh MỖI LƯỢT, và ô gỗ ĐỔI XEN KẼ mỗi lượt (đóng -> mở -> đóng...):
  khi tính vị trí kết thúc (`_EndEval`) bot coi ô gỗ đang ĐÓNG sẽ MỞ ở lượt sau (đi vào được) và ô đang MỞ sẽ ĐÓNG (không vào được).
- NHỆN (map mới, quái to có mạng nhện ở nền ô, tóc/cánh tím đen, chỉ có số bước ở góc, KHÔNG có đồng hồ cát đếm ngược; Cell.mtype == "spider"):
  CÒN NHỆN trên bàn thì thanh nộ bị KHOÁ (hiện ổ khoá) - bot VẪN đọc/bấm nộ như bình thường (khoá thì bấm cũng không ảnh hưởng gì;
  tuỳ chọn `spider_lock_rage` = true mới bỏ qua nộ) và chỉ khác là ưu tiên TIÊU DIỆT TOÀN BỘ NHỆN trước mọi quái khác (`SolverParams.monster_weights["spider"]` = w_spider, mặc định 5000 -> nhện 6000 điểm, hơn 3 quái thường không khẩn cấp cộng lại 3x1500=4500);
  hết nhện thì nộ mở khoá, bot lại dùng nộ như cũ. Nhận diện: mẫu `templates/thtg_spider_*.png` (thêm bằng `--add-spider`) HOẶC tỉ lệ pixel
  tím-đen (tóc/cánh) lớn trong ô quái (`_spider_purple`; đo: nhện 0.29, quái/thú khác <= 0.05).
- Bấm lần lượt từng ô là nối được (không cần vuốt).

Chạy riêng để kiểm tra nhận diện + đường đi trên ảnh chụp:
    python thtg_bot.py anh.png [beam]     -> in bàn cờ, đường đi, lưu thtg_debug.png
    python thtg_bot.py --add-num anh.png HÀNG CỘT SỐ  -> lưu mẫu chữ số bước của quái (templates/thtg_num_N_k.png; có sẵn 4,5,6,7)
    python thtg_bot.py --add-turns anh.png CHỮ_SỐ     -> lưu mẫu chữ số 'Hiệp còn lại' (templates/thtg_turn_N.png; có sẵn 5 và 9)
    python thtg_bot.py --add-monster anh.png HÀNG CỘT  -> lưu ô đó thành mẫu quái mới (templates/thtg_monster_N.png)
    python thtg_bot.py --add-spider anh.png HÀNG CỘT   -> lưu ô đó thành mẫu NHỆN (templates/thtg_spider_N.png; không bắt buộc, có cách nhận bằng màu)
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
CAGE_STEPS = 5                   # ô LỒNG luôn cần đúng 5 bước (game không có số khác) -> KHÔNG đọc số của lồng bằng OCR nữa (hay đọc sai)
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
    mtype: str = "boss"        # loại quái to (khoá của SolverParams.monster_weights): boss | spider (nhện: khoá nộ, ưu tiên diệt) | cage; thêm loại mới = thêm 1 dòng ở đó
    turns: int = 0             # số LƯỢT còn lại trước khi quái dùng skill làm mất máu (số bên trái quái; 0 = không có/không rõ)
    box: str = ""              # ô GỖ: "closed" (đóng, kind = stone, không đi được) | "open" (mở, kind = animal, đi như thú thường) | "" = không phải ô gỗ


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
                    row.append(f" {ANIMAL_CH[x.color]}{'*' if x.fire else ('_' if x.box == 'open' else ' ')}")
                elif x.kind == "diamond":
                    row.append(" D ")
                elif x.kind == "monster":
                    row.append(("L" if x.mtype == "cage" else ("S" if x.mtype == "spider" else "M")) + f"{x.n}" + (f"/{x.turns}" if x.turns else "") + " ")
                elif x.kind == "stone":
                    row.append(" B " if x.box == "closed" else " # ")
                else:
                    row.append(" ? ")
            out.append("".join(row))
        return "\n".join(out)


def board_from_strings(rows, monsters: Optional[dict] = None, hero=(0, 3)) -> Board:
    """Dựng Board từ chuỗi để test. F/O/C/P = ếch/bò/mèo/heo (thêm * sau chữ = có lửa), D = kim cương,
    M = quái to, S = NHỆN (số bước lấy từ monsters[(r,c)], mặc định 5), L = ô lồng (số bước lấy từ monsters[(r,c)]), # = đá, B = ô gỗ ĐÓNG (như đá), thêm _ sau chữ thú = ô gỗ MỞ
    (vd F_ = ếch trong ô gỗ mở, đi như thú thường), H = nhân vật."""
    monsters = monsters or {}
    cells = []
    for r, line in enumerate(rows):
        row = []
        toks = line.split()
        for c, t in enumerate(toks):
            ch = t[0]
            fire = t.endswith("*") or t.endswith("*_")
            if ch in "FOCP":
                row.append(Cell("animal", "FOCP".index(ch), fire=fire, box="open" if t.endswith("_") else ""))
            elif ch == "D":
                row.append(Cell("diamond"))
            elif ch == "M":
                mv = monsters.get((r, c), 7)
                n_, t_ = (mv if isinstance(mv, tuple) else (mv, 0))
                row.append(Cell("monster", n=n_, turns=t_, boss=True))
            elif ch == "S":                      # NHỆN: quái to đặc biệt (khoá nộ, ưu tiên diệt)
                mv = monsters.get((r, c), 5)
                n_, t_ = (mv if isinstance(mv, tuple) else (mv, 0))
                row.append(Cell("monster", n=n_, turns=t_, boss=True, mtype="spider"))
            elif ch == "L":                      # ô lồng (số bước lấy từ monsters[(r,c)]); LF/LO/LC/LP = lồng màu ếch/bò/mèo/heo, L = màu không rõ
                mv = monsters.get((r, c), 5)
                lc = "FOCP".index(t[1]) if len(t) > 1 and t[1] in "FOCP" else -1
                row.append(Cell("monster", color=lc, n=(mv[0] if isinstance(mv, tuple) else mv), mtype="cage"))
            elif ch == "#":
                row.append(Cell("stone"))
            elif ch == "B":                      # ô gỗ ĐÓNG: như đá
                row.append(Cell("stone", box="closed"))
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
    monster_weights: dict = field(default_factory=lambda: {"boss": 500.0, "spider": 5000.0})   # nhện 5000 (+w_kill 1000 = 6000 > 3 quái thường 3x1500): diệt nhện (mở khoá nộ) trước quái thường
    w_cage: float = 200.0          # điểm cộng khi đi qua (mở khoá) 1 ô lồng: thấp hơn diệt quái (w_kill) nhưng cao hơn kim cương; 0 = chỉ qua khi làm cầu nối
    w_step: float = 10.0           # mỗi bước (nạp nộ)
    # Kim cương CHỦ YẾU để tạo lối đi (đổi loại), không cần ăn: mỗi viên đi qua bị TRỪ w_diamond điểm (số ÂM); đổi lại mỗi mốc
    # reward_every bước đi được thưởng 1 viên (cộng w_reward điểm) -> đường tròn mốc 10/20/30 bước lời hơn, dùng kim cương
    # chỉ khi cần cầu nối hoặc để chạm mốc. (Bản cũ: +15 mỗi viên -> bot cứ ăn kim cương cho bằng hết.)
    w_diamond: float = 0.0         # MẶC ĐỊNH 0: kim cương không quan trọng (chỉ để tạo lối đi); đặt âm = tiết kiệm kim cương
    w_reward: float = 0.0          # MẶC ĐỊNH 0: không ưu tiên đi tròn mốc 10 bước; đặt dương (vd 60) nếu muốn thưởng kim cương
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
    open_pen: tuple = (2500.0, 250.0, 80.0, 25.0)
    box_alternate: bool = True     # ô gỗ đổi xen kẽ mỗi lượt: đang đóng -> lượt sau mở (đi được), đang mở -> lượt sau đóng (như đá); False = coi ô gỗ giữ nguyên
    w_corner: float = 60.0         # kết thúc ở GÓC bàn cờ (~6 bước; nhẹ để không làm mất bước)
    w_edge: float = 8.0            # kết thúc ở MÉP (không phải góc)
    reach_min: int = 8             # vùng đi vào được liền nhau quanh nhân vật nhỏ hơn mức này thì phạt thêm (lượt sau đường ngắn)
    w_reach: float = 25.0          # phạt mỗi ô thiếu so với reach_min
    # Quái có đếm ngược: còn ít lượt thì phải diệt NGAY lượt này (hết lượt nó dùng skill làm mất máu) -> cộng thêm điểm.
    # Khoá = số lượt còn lại (1 = hết lượt này là nó đánh).
    urgency: dict = field(default_factory=lambda: {1: 4000.0, 2: 1500.0, 3: 600.0})
    # Bộ giải CHÍNH XÁC (thtg_solver.py, nhánh-cận): chạy trước; nếu chứng minh được là tối ưu thì khỏi chạy beam.
    use_exact: bool = True
    exact_nodes: int = 400_000     # giới hạn SỐ NÚT (không phải giây) -> kết quả xác định, không phụ thuộc máy nhanh/chậm

    # Số hiệp (lượt đi) còn lại, 0 = không biết. Còn 1 = lượt cuối: kim cương thưởng và vị trí cuối không còn giá trị.
    turns_left: int = 0

    def effective(self):
        """Bản tham số đã chỉnh theo số hiệp còn lại (lượt cuối: bỏ thưởng/trừ kim cương và chống kẹt). Gọi nhiều lần vẫn an toàn."""
        if self.turns_left == 1:
            from dataclasses import replace
            return replace(self, w_diamond=0.0, w_reward=0.0, end_safety=False)
        return self

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
                if (r, c) == board.hero:
                    continue
                ok = x.kind in ("animal", "diamond")
                if x.box and p.box_alternate:            # ô gỗ đổi trạng thái sau lượt này: đóng -> mở (vào được), mở -> đóng (không vào được)
                    ok = (x.box == "closed")
                if ok:
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
            if color != -1 and x.color != -1 and x.color != color:
                return None                # lồng khác màu con đang nối -> không đi qua được
            return color, bal + 1 - x.n, 0, 0, p.w_cage, 0     # phá xong lồng thành kim cương (chỉ có tác dụng từ lượt sau)
        return -1, bal + 1 - x.n, 1, 0, p.monster_extra(x), 0
    return None   # đá / nhân vật / ô trống không đi được


def solve_beam(board: Board, params: Optional[SolverParams] = None) -> Plan:
    """(Heuristic) Tìm đường đi 1 lượt bằng beam search. Thứ tự ưu tiên: diệt quái to (nhiều nhất, quái nặng điểm trước) > số bước > kim cương.
    KẾT QUẢ XÁC ĐỊNH: cùng bàn cờ + cùng tham số luôn ra đúng 1 đường đi (không phụ thuộc tốc độ máy)."""
    p = (params or SolverParams()).effective()
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
                row.append(("L", x.color, x.n, p.w_cage) if x.mtype == "cage"
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
    p = (params or SolverParams()).effective()
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


def _segs(p, thr, minrun):
    """Mọi đoạn [đầu, cuối) liên tục p>thr dài >= minrun (cùng cách tính với _span nhưng trả đủ danh sách)."""
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
    return segs


def find_board_rect(frame):
    """Khung 7x7 dò theo màu nền ô be (cửa sổ LDPlayer có thể bị cắt/tỉ lệ khác nhau nên không
    dùng tỉ lệ cố định). Trả (trái, trên, cạnh_ô) hoặc None.
    Map mới (nền sa mạc/trời màu be ở PHÍA TRÊN bàn cờ) làm cách dò cũ lấy luôn cả vùng trời (bàn cờ bị đo cao gấp đôi,
    trên = 3) -> khi khung đo ra không gần hình vuông thì dò lại: lấy cụm hàng be CUỐI CÙNG (bàn cờ nằm dưới trời) rồi mới dò cột."""
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 24) & (hsv[:, :, 1] >= 25)
         & (hsv[:, :, 1] <= 110) & (hsv[:, :, 2] >= 150)).astype(np.float32)
    k = np.ones(3) / 3
    minrun = max(10, w // 22)
    cand = None            # kết quả cách cũ chỉ "gần" hình vuông (lệch 3-12%): giữ làm phương án cuối nếu cách dự phòng không dò được
    for thr in (0.18, 0.12, 0.08):
        cs = _span(np.convolve(m.mean(0), k, "same"), thr, minrun)
        if cs is not None and 0.85 * w < cs[1] - cs[0] < 1.0 * w:
            rs = _span(np.convolve(m[:, cs[0]:cs[1]].mean(1), k, "same"), thr, minrun)
            if rs is not None:
                pitch = (cs[1] - cs[0]) / 7.0
                dev = abs((rs[1] - rs[0]) - 7.0 * pitch)
                if dev <= 0.03 * 7.0 * pitch:                                      # gần như đúng hình vuông -> cách cũ đúng
                    return float(cs[0]), float(rs[0]) + 3.0, pitch
                # Map NHỆN (nền trời be sát trên bàn cờ, cách 1 vạch khung ~2px): khung đo ra cao hơn 7 ô ~6% nhưng vẫn lọt ngưỡng
                # 12% cũ -> hàng 0 bị lệch ~1/2 ô, bấm trượt hết. Lệch > 3% thì thử cách dự phòng (lấy cụm be CUỐI = bàn cờ) trước.
                if dev <= 0.12 * 7.0 * pitch and cand is None:
                    cand = (float(cs[0]), float(rs[0]) + 3.0, pitch)
        # cách dự phòng (nền be phía trên bàn cờ): hàng trước (chỉ lấy phần giữa bề ngang), cột sau
        segs = _segs(np.convolve(m[:, int(w * 0.08):int(w * 0.92)].mean(1), k, "same"), thr, minrun)
        if not segs:
            continue
        bot = segs[-1][1]
        keep = [s for s in segs if s[0] >= bot - w]                  # bàn cờ vuông, rộng <= bề ngang ảnh
        r0 = keep[0][0]
        cs = _span(np.convolve(m[r0:bot].mean(0), k, "same"), thr, minrun)
        if cs is None or not (0.85 * w < cs[1] - cs[0] < 1.0 * w):
            continue
        pitch = (cs[1] - cs[0]) / 7.0
        if abs((bot - r0) - 7.0 * pitch) > 0.12 * 7.0 * pitch:
            continue
        return float(cs[0]), float(r0) + 3.0, pitch
    return cand


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


SPIDER_PURPLE_MIN = 0.12        # tỉ lệ pixel tím-đen (tóc + cánh nhện) trong nửa trên ô quái từ mức này là NHỆN (đo: nhện 0.29, thỏ 0.02, chuột 0.00, thú thường <= 0.05)


def _spider_purple(frame, geo: Geometry, r, c) -> float:
    """Tỉ lệ pixel TÍM-ĐEN (tóc + cánh nhện: V thấp, H 100-165, có chút bão hoà) ở nửa trên ô. Chỉ gọi cho ô ĐÃ là quái to.
    Cách này không cần mẫu ảnh; ngoài ra còn có mẫu `thtg_spider_*.png` (`BoardDetector.tpl_spiders`)."""
    x, y = geo.center(r, c)
    p = geo.pitch
    x0, x1 = int(x - p * 0.5 + p * 0.08), int(x - p * 0.5 + p * 0.92)
    y0, y1 = int(y - p * 0.5 + p * 0.05), int(y - p * 0.5 + p * 0.70)
    crop = frame[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
    if crop.size == 0:
        return 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(int)
    m = (hsv[:, 2] < 120) & (hsv[:, 1] >= 25) & (hsv[:, 0] >= 100) & (hsv[:, 0] <= 165)
    return float(m.mean())


class BoardDetector:
    def __init__(self, diamond_thr=0.55, monster_thr=0.5, ocr_workers=None, spider_thr=0.6):
        self.ocr_workers = ocr_workers      # số luồng đọc số quái song song (None = OCR_WORKERS)
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
        # Mẫu NHỆN (tuỳ chọn): templates/thtg_spider_*.png (`python thtg_bot.py --add-spider anh.png HÀNG CỘT`). Không có mẫu thì
        # nhận nhện bằng màu tím-đen (`_spider_purple`).
        self.tpl_spiders = []
        for f in sorted(glob.glob(os.path.join(_TPL_DIR, "thtg_spider_*.png"))):
            t = _imread(f)
            if t is not None:
                self.tpl_spiders.append(t)
        self.spider_thr = spider_thr
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
        badge_px = _badge_red_px(frame, geo, r, c)
        if badge_px >= 25:                       # khung lồng đủ rõ thì chỉ cần dấu hiệu số mờ (số bị che bớt); ô không có lồng thì badge ~0-1
            is_cage, cage_col = _cage_info(frame, geo, r, c)
            if is_cage:
                return Cell("monster", color=cage_col, n=CAGE_STEPS, mtype="cage")         # lồng: không phải quái, không có đếm ngược, luôn cần CAGE_STEPS bước
        m_spi = max([_match(cell, t, p) for t in self.tpl_spiders] or [0.0])
        is_mon = m_mon >= self.monster_thr and m_mon >= m_dia
        if not is_mon and badge_px >= 60:
            is_mon = True
        if is_mon or m_spi >= self.spider_thr:
            # NHỆN (khoá nộ, ưu tiên diệt): khớp mẫu nhện HOẶC nhiều pixel tím-đen; quái khác vẫn là "boss"
            spider = m_spi >= self.spider_thr or _spider_purple(frame, geo, r, c) >= SPIDER_PURPLE_MIN
            return Cell("monster", n=0, boss=True, mtype="spider" if spider else "boss")
        if m_dia >= self.diamond_thr:
            return Cell("diamond")
        # 1b) ô GỖ: hộp gỗ úp lên con thú. ĐÓNG = hộp cao che kín (coi như đá); MỞ = hộp thấp, thú lộ ra (coi như thú thường)
        box_state = _box_state(frame, geo, r, c)
        if box_state == "closed":
            return Cell("stone", box="closed")
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
        return Cell("animal", color=col, fire=bool(fire), box=box_state)

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
        todo = []
        for r in range(ROWS):
            for c in range(COLS):
                x = cells[r][c]
                if x.kind == "monster":
                    if x.mtype == "cage":                 # lồng: số bước CỐ ĐỊNH = CAGE_STEPS, không có đồng hồ cát -> khỏi đọc số/lượt (tránh đọc nhầm)
                        x.n, x.turns = CAGE_STEPS, 0
                        self.last_raw[(r, c)] = (CAGE_STEPS, 0, True)
                        continue
                    todo.append((r, c))
        _num_templates()                                  # nạp trước (tránh nhiều luồng cùng nạp)

        def _read(rc):
            if cells[rc[0]][rc[1]].mtype == "spider":         # nhện không có đồng hồ cát đếm ngược -> khỏi đọc lượt (đỡ đọc nhầm + nhanh hơn)
                return _number_votes(frame, geo, *rc) + (0, True)
            return _number_votes(frame, geo, *rc) + _turns_votes(frame, geo, *rc)
        for (r, c), (n_raw, n_ok, t_raw, t_ok) in zip(todo, _pmap(_read, todo, self.ocr_workers)):
            self.last_raw[(r, c)] = (n_raw, t_raw, n_ok and t_ok)
            cells[r][c].n = n_raw or monster_default
            cells[r][c].turns = t_raw
        return Board(cells, hero), geo


def _box_bands(frame, geo: Geometry, r, c):
    """Tỉ lệ điểm màu GỖ/đá be (HSV giống ô đá) theo 10 dải ngang của ô (trên -> dưới), chỉ xét 60% bề ngang giữa ô."""
    p = geo.pitch
    cx, cy = geo.center(r, c)
    H, W = frame.shape[:2]
    x0, x1 = max(0, int(cx - 0.3 * p)), min(W, int(cx + 0.3 * p))
    top = cy - p / 2.0
    out = []
    for k in range(10):
        y0, y1 = max(0, int(top + k * p / 10.0)), min(H, int(top + (k + 1) * p / 10.0))
        reg = frame[y0:y1, x0:x1]
        if reg.size == 0:
            out.append(0.0)
            continue
        hsv = cv2.cvtColor(reg, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        h_, s_, v_ = hsv[:, 0].astype(int), hsv[:, 1].astype(int), hsv[:, 2].astype(int)
        out.append(float(((h_ >= 13) & (h_ <= 22) & (s_ >= 60) & (s_ <= 135) & (v_ >= 140)).mean()))
    return out


def _box_state(frame, geo: Geometry, r, c) -> str:
    """Ô GỖ: "closed" (hộp CAO che kín con thú, chỉ lòi cái đầu), "open" (hộp THẤP ở đáy ô, thú lộ rõ) hoặc "" (không phải ô gỗ).
    Đo trên ảnh thật (map Phàn Đầu, 723x1276): phần giữa-dưới ô (dải 5-8 trong 10 dải) - hộp đóng 0.83-0.87, hộp mở 0.35 (chỉ có
    nắp thấp ở 2 dải cuối: dải 8 >= 0.85), ô thú thường <= 0.30 (dải 8 <= 0.45). Ô ĐÁ cũng ra 'closed' (cùng không đi được nên không sao).
    'open' CHỈ để ghi log/vẽ debug: ô vẫn là thú bình thường nên nhận sai cũng không ảnh hưởng đường đi."""
    b = _box_bands(frame, geo, r, c)
    m58 = sum(b[5:9]) / 4.0
    if m58 >= 0.65:
        return "closed"
    # Ô gỗ ĐÓNG ở ĐÁY cột gỗ (vd hàng 4 của cột gỗ hàng 2-4) bị cắt/thon nên gỗ chỉ phủ ~0.50-0.60 mà phủ ĐỀU từ dải 2 tới dải 8
    # (ảnh thật: 0.57, dải nhỏ nhất 0.51) -> cũ không nhận ra, bot coi là bò và ĐI XUYÊN qua cột gỗ. Ô thú thường: dải 5-8 <= 0.23, dải nhỏ nhất <= 0.10;
    # hộp mở có 2 dải giữa trống (<= 0.30) nên không dính điều kiện "đều".
    if m58 >= 0.45 and min(b[2:9]) >= 0.35:
        return "closed"
    if b[8] >= 0.80 and b[5] <= 0.30 and b[6] <= 0.30:
        return "open"
    return ""


def _cage_info(frame, geo: Geometry, r, c):
    """Ô LỒNG (khung nhốt viên ngọc) hay quái? Trả (là_lồng, màu_thú) - màu 0 ếch / 1 bò / 2 mèo / 3 heo, -1 = không rõ.
    Lồng có thanh khung NGANG gần hết ô ở phía trên và nhiều thanh dọc cùng màu; quái (chuột...) thì không. Màu khung = màu thú
    của lồng (xanh dương = mèo, hồng/đỏ = heo, cam = bò, lục = ếch): chỉ lồng CÙNG màu con đang nối mới đi qua được.
    Đo trên ảnh thật: lồng hồng thanh trên 0.90-0.93 + 24-27 cột; lồng XANH DƯƠNG 0.80-0.91 + 29-34 cột (bản cũ chỉ dò hồng/cam nên lồng xanh
    bị nhận nhầm là quái to -> bot tưởng \"diệt quái\" được đổi màu tự do); quái 0.00 + 0-1 cột. Chỉ gọi cho ô đã có huy hiệu số."""
    x, y = geo.center(r, c)
    h = int(geo.pitch * 0.46)
    cell = frame[max(0, int(y - h)):int(y + h), max(0, int(x - h)):int(x + h)]
    if cell.size == 0:
        return False, -1
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    h_, s_, v_ = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)

    def bars(m):
        top = float(m.mean(axis=1)[: max(1, int(len(m) * 0.4))].max())
        cols = int((m.mean(axis=0) > 0.35).sum())
        return top >= 0.6 and cols >= 12, cols
    warm = (((h_ >= 165) | (h_ <= 24)) & (s_ >= 100) & (v_ >= 170))
    blue = ((h_ >= 85) & (h_ <= 125) & (s_ >= 60) & (v_ >= 150))
    green = ((h_ >= 30) & (h_ <= 80) & (s_ >= 50) & (v_ >= 140))      # thanh lồng xanh lá NHẠT (đo: 0.92 + 24 cột; quái có hào quang xanh <= 0.2 + 6 cột)
    best = (False, -1, 0)
    for col, m in ((2, blue), (0, green), (-2, warm)):          # -2 = nhóm hồng/đỏ/cam, tách heo/bò bên dưới
        ok, cols = bars(m)
        if ok and cols > best[2]:
            best = (True, col, cols)
    if not best[0]:
        return False, -1
    col = best[1]
    if col == -2:
        wm = warm.sum()
        orange = int((warm & (h_ >= 9) & (h_ <= 24)).sum())
        col = 1 if wm and orange > 0.6 * wm else 3
    return True, col


def _is_cage(frame, geo: Geometry, r, c) -> bool:
    """Giữ tên cũ: ô này có phải lồng không (xem _cage_info)."""
    return _cage_info(frame, geo, r, c)[0]


def _num_glyph(frame, cx, cy, p):
    """Tìm CHỮ SỐ ĐỎ bước cần của quái ở góc dưới-phải ô tâm (cx,cy), cạnh ô p. Không phụ thuộc vào việc tâm ô chính xác
    (lệch +-5px vẫn tìm được) và không bị hào quang hồng / thanh lồng / cột đánh lừa: nét chữ số là điểm ĐỎ có viền KEM
    ở cả hai phía (trái-phải hoặc trên-dưới); thanh/cột đỏ lớn không có viền kem hai phía nên bị loại. Trả (mặt nạ 0/1 đã cắt
    sát, số ký tự) hoặc None nếu ô không có chữ số."""
    H_, W_ = frame.shape[:2]
    x0, y0 = max(0, int(cx + p * .02)), max(0, int(cy - p * .02))
    x1, y1 = min(W_, int(cx + p * .72)), min(H_, int(cy + p * .72))
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, s, v = [hsv[..., i].astype(int) for i in range(3)]
    red = (((h >= 174) | (h <= 8)) & (s >= 85) & (v >= 105)).astype(np.uint8)       # đỏ thuần (hào quang hồng là h ~ 160)
    cream = ((h >= 6) & (h <= 34) & (s <= 130) & (v >= 180)).astype(np.uint8)

    def _shift(m, dx, dy, k):
        out = np.zeros_like(m)
        for t in range(1, k + 1):
            out |= cv2.warpAffine(m, np.float32([[1, 0, dx * t], [0, 1, dy * t]]), (m.shape[1], m.shape[0]),
                                  flags=cv2.INTER_NEAREST, borderValue=0)
        return out
    k = max(2, int(round(p * .035)))
    L, R, U, D = _shift(cream, 1, 0, k), _shift(cream, -1, 0, k), _shift(cream, 0, 1, k), _shift(cream, 0, -1, k)
    stroke = cv2.morphologyEx((red & ((L & R) | (U & D))).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(stroke)
    ex, ey = (cx + p * .41) - x0, (cy + p * .34) - y0                                # vị trí kỳ vọng của chữ số
    cands = []
    for i in range(1, n):
        bx, by, bw, bh, a = st[i]
        if bh < p * .14 or bh > p * .36 or bw < p * .05 or bw > p * .28 or a < p * p * .003:
            continue
        if bw > bh * 1.15 or bw < bh * .28:
            continue
        if x0 + cen[i][0] > cx + p * .50:        # chữ số nằm NGOÀI mép phải ô = số lượt (đồng hồ cát) của quái ô bên phải, không phải số của ô này
            continue
        cands.append((float(np.hypot(cen[i][0] - ex, cen[i][1] - ey) / p), i))
    if not cands:
        return None
    cands.sort()
    if cands[0][0] > .30:
        return None
    i0 = cands[0][1]
    bx0, by0, bw0, bh0, _a = st[i0]
    keep = [i0]
    for d, i in cands[1:]:                                                            # chữ số thứ 2 (số 10+)
        bx, by, bw, bh, a = st[i]
        if (abs((by + bh / 2) - (by0 + bh0 / 2)) < bh0 * .35 and abs(bh - bh0) < bh0 * .3
                and (bx - (bx0 + bw0) < p * .15 and bx0 - (bx + bw) < p * .15)):
            keep.append(i)
    keep = keep[:2]
    xa = max(0, min(st[i][0] for i in keep) - 1); ya = max(0, min(st[i][1] for i in keep) - 1)
    xb = min(crop.shape[1], max(st[i][0] + st[i][2] for i in keep) + 1)
    yb = min(crop.shape[0], max(st[i][1] + st[i][3] for i in keep) + 1)
    g = hsv[ya:yb, xa:xb]
    gh, gs, gv = [g[..., i].astype(int) for i in range(3)]
    full = (((gh >= 172) | (gh <= 9)) & (gs >= 70) & (gv >= 100)).astype(np.uint8)    # màu đỏ ĐẦY ĐỦ (nét mảnh không bị đứt)
    m = (full & cv2.dilate(stroke[ya:yb, xa:xb], np.ones((3, 3), np.uint8))).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    ys, xs = np.where(m)
    if len(ys) < 12:
        return None
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # cắt bằng cửa sổ đúng cỡ chữ số (cao ~0.195p, rộng ~0.135p/chữ số): bỏ phần thanh lồng/cột hồng dính sát chữ số
    th, tw = int(round(p * .195)), int(round(p * .135 * (1 if len(keep) == 1 else 2.1)))
    if m.shape[0] > th or m.shape[1] > tw:
        th, tw = min(th, m.shape[0]), min(tw, m.shape[1])
        ii = cv2.integral(m)
        best, pos = -1, (0, 0)
        for yy in range(0, m.shape[0] - th + 1):
            for xx in range(0, m.shape[1] - tw + 1):
                val = ii[yy + th, xx + tw] - ii[yy, xx + tw] - ii[yy + th, xx] + ii[yy, xx]
                if val > best:
                    best, pos = val, (yy, xx)
        sub = m[pos[0]:pos[0] + th, pos[1]:pos[1] + tw]
        ys, xs = np.where(sub)
        if len(ys):
            m = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return m, len(keep)


_NUM_TPL_B64 = {
    7: "iVBORw0KGgoAAAANSUhEUgAAABAAAAAYCAAAAADWyyLQAAAAWElEQVQYGVXBwWGEMAAEMU3/RW98wTyQmq/mq/lqvvKaf3nNT3nNT3kNkWsIuYaQawhhrpB55ci8cmReOXLMkX85hjxyDHnkGPIIc+QRhlxhyBWGXGHI9QeB+BgUIwXNYgAAAABJRU5ErkJggg==",
    5: "iVBORw0KGgoAAAANSUhEUgAAABAAAAAYCAAAAADWyyLQAAAAU0lEQVQYGVXBiWGDQAAEMU3/Ra9J/HBIYQ6Zh8xD5lSG/GTklpFbRm7NIZqHmoeaS5h/DXkbchhyGHIYchga+Rga+Rga8jY0l/yZS+ZU5lSYr3gBdpYeDOS/ywsAAAAASUVORK5CYII=",
    4: "iVBORw0KGgoAAAANSUhEUgAAABAAAAAYCAAAAADWyyLQAAAAW0lEQVQYGVXBgXGDQAAEMW3/RV/AmPxYyjGU19zKa27laz7KYx7lMY/yMV/lNq9yGWIoDGEoDGEoDGEoQ25DzSW3oeYW5lLzq/mVf3Mpx1COoRxDOYZyDOUY+gMJSR8XeElEhwAAAABJRU5ErkJggg==",
    6: "iVBORw0KGgoAAAANSUhEUgAAABAAAAAYCAAAAADWyyLQAAAAXUlEQVQYGVXBiRHCAAAEIbb/os98ThTCvMqcYk6ZU5hDc8hlaMhtaMhjNOQxGvJqXqH5U/On5hLm0JDb0JDHaMhjNPI1GvkaDbkNDbkNDbkNmVPmkvlV5lc5zC18ANK9KAlhp5ZHAAAAAElFTkSuQmCC",
}
_num_tpls = None


def _num_norm(m):
    return (cv2.resize(m * 255, (16, 24), interpolation=cv2.INTER_AREA) > 100).astype(np.uint8)


def _num_corr(a, b):
    fa = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 1.0).ravel()
    fb = cv2.GaussianBlur(b.astype(np.float32), (0, 0), 1.0).ravel()
    fa -= fa.mean()
    fb -= fb.mean()
    return float(fa @ fb / (np.linalg.norm(fa) * np.linalg.norm(fb) + 1e-9))


def _num_templates():
    """Mẫu chữ số 1 ký tự: 4,5,6,7 nhúng sẵn (từ ảnh thật); thêm số khác (1,2,3,8,9...) bằng
    `python thtg_bot.py --add-num anh.png HÀNG CỘT SỐ` -> templates/thtg_num_<số>.png (có thể có nhiều file mỗi số: thtg_num_<số>_<k>.png)."""
    global _num_tpls
    if _num_tpls is None:
        import base64
        _num_tpls = []
        for d, b in _NUM_TPL_B64.items():
            img = cv2.imdecode(np.frombuffer(base64.b64decode(b), np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                _num_tpls.append((d, (img > 100).astype(np.uint8)))
        for f in sorted(glob.glob(os.path.join(_TPL_DIR, "thtg_num_*.png"))):
            try:
                d = int(os.path.basename(f)[len("thtg_num_"):-4].split("_")[0])
            except ValueError:
                continue
            img = _imread(f)
            if img is not None:
                g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _num_tpls.append((d, (cv2.resize(g, (16, 24), interpolation=cv2.INTER_AREA) > 100).astype(np.uint8)))
    return _num_tpls


def _badge_red_px(frame, geo: Geometry, r, c) -> int:
    """Ô có CHỮ SỐ ĐỎ của quái/lồng (huy hiệu số ở góc dưới-phải) không? Trả số lớn (>= 60 = có) hay 0. Thú thường ~0.
    Dùng bộ định vị chữ số `_num_glyph` (chịu lệch hình học vài px); nếu không thấy mới dùng cách đếm điểm đỏ trong
    huy hiệu kem (cách cũ, giữ để không mất quái mà bộ mới bỏ sót)."""
    x, y = geo.center(r, c)
    if _num_glyph(frame, x, y, geo.pitch) is not None:
        return 200
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


OCR_WORKERS = 3          # số luồng đọc số quái song song (mỗi lần OCR là 1 tiến trình tesseract riêng nên song song được)


def _tess_batch(imgs, psm, whitelist="0123456789"):
    """OCR NHIỀU ảnh bằng ĐÚNG 1 lần chạy tesseract (truyền danh sách ảnh, tesseract in các trang cách nhau bằng \\f).
    Mỗi lần gọi `pytesseract.image_to_string` là 1 tiến trình tesseract.exe mới (Windows + antivirus: ~0.3-1s/lần); bản cũ gọi
    tới 24 lần cho MỖI quái nên 8-9 quái mất 50-90s mỗi lượt. Trả list chuỗi (đã strip) cùng thứ tự ảnh; None nếu lô lỗi
    (bên gọi tự rơi về cách cũ từng ảnh một nên không bao giờ kém hơn cũ)."""
    if not imgs:
        return []
    try:
        import pytesseract, tempfile, subprocess, shutil
        cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", None) or "tesseract"
        d = tempfile.mkdtemp(prefix="thtg_ocr_")
        try:
            lines = []
            for i, im in enumerate(imgs):
                ok, buf = cv2.imencode(".png", im)
                if not ok:
                    return None
                fp = os.path.join(d, f"{i:03d}.png")
                buf.tofile(fp)
                lines.append(fp.replace("\\", "/"))
            lst = os.path.join(d, "list.txt")
            with open(lst, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            kw = {}
            if os.name == "nt":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                kw = {"startupinfo": si, "creationflags": 0x08000000}
            r = subprocess.run([cmd, lst, "stdout", "--psm", str(psm), "-c", f"tessedit_char_whitelist={whitelist}"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, **kw)
            if r.returncode != 0:
                return None
            pages = r.stdout.decode("utf-8", "ignore").split("\f")
            if len(pages) < len(imgs):
                return None
            return [t.strip() for t in pages[:len(imgs)]]
        finally:
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        return None


def _tess_digits(imgs, psm, whitelist="0123456789"):
    """OCR 1 lô ảnh cùng chế độ psm: thử 1 lần chạy (_tess_batch), lỗi thì rơi về từng ảnh một như bản cũ."""
    out = _tess_batch(imgs, psm, whitelist)
    if out is not None:
        return out
    import pytesseract
    res = []
    for im in imgs:
        try:
            res.append(pytesseract.image_to_string(im, config=f"--psm {psm} -c tessedit_char_whitelist={whitelist}").strip())
        except Exception:
            res.append("")
    return res


def _pmap(fn, items, workers=None):
    """map song song (giữ thứ tự). 1 phần tử / workers<=1 thì chạy thẳng, không tạo luồng."""
    items = list(items)
    w = OCR_WORKERS if workers is None else int(workers)
    if len(items) <= 1 or w <= 1:
        return [fn(x) for x in items]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(w, len(items))) as ex:
        return list(ex.map(fn, items))


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
    imgs = []
    for b in outs:
        for thin in (False, True):
            bb = cv2.erode(b, np.ones((5, 5), np.uint8)) if thin else b
            imgs.append(cv2.copyMakeBorder(255 - bb, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255))
    votes = {}

    def _count(texts):
        for t in texts:
            if t.isdigit() and 1 <= int(t) <= 9:
                votes[int(t)] = votes.get(int(t), 0) + 1
    _count(_tess_digits(imgs, 10))                      # lần 1 (1 tiến trình cho cả 8 biến thể ảnh)
    top = sorted(votes.values(), reverse=True) + [0]
    if top[0] >= 3 and top[1] == 0:                      # >=3 lần đọc đều ra cùng 1 số -> dừng sớm
        return max(votes, key=votes.get), True
    _count(_tess_digits(imgs, 8))
    _count(_tess_digits(imgs, 13))
    if not votes:
        return 0, False
    top = sorted(votes.values(), reverse=True) + [0]
    best = max(votes, key=votes.get)
    return best, (top[0] >= 3 and top[0] >= 3 * top[1])


def read_monster_turns(frame, geo: Geometry, r, c) -> int:
    """Số lượt đếm ngược của quái (xem _turns_votes). Quái không có đếm ngược / không đọc được -> 0."""
    return _turns_votes(frame, geo, r, c)[0]


def _number_votes(frame, geo: Geometry, r, c):
    """Số bước cần của quái to / lồng: chữ số ĐỎ ở góc dưới-phải ô. Bản cũ cắt cửa sổ cố định quanh tâm ô rồi chọn mảng kem
    lớn nhất nên chỉ cần tâm ô lệch vài px (hoặc hào quang hồng / thanh lồng dính chữ) là đọc ra 0/2/3/45...; đo trên ảnh
    thật với lệch +-5px: đúng 574/825 (70%). Bản này: (1) `_num_glyph` định vị chính xác chữ số (đúng 100% khi lệch +-4px,
    không nhận nhầm ô thường), (2) so khớp MẪU hình dạng (tương quan, 4/5/6/7 nhúng sẵn, thêm số khác bằng --add-num) -
    nhanh và ổn định, (3) chỉ khi không khớp mẫu mới OCR Tesseract trên mặt nạ sạch, bỏ phiếu, kiểm chéo với mẫu.
    Trả (số, chắc_chắn); không đọc được -> (0, False) (bên gọi dùng monster_default)."""
    x, y = geo.center(r, c)
    g = _num_glyph(frame, x, y, geo.pitch)
    if g is None:
        return 0, False
    m, nd = g
    tpl_best = None
    if nd == 1:
        sc = {}
        nm = _num_norm(m)
        for d, t in _num_templates():
            sc[d] = max(sc.get(d, -1.0), _num_corr(nm, t))
        if sc:
            rank = sorted(((v, d) for d, v in sc.items()), reverse=True)
            top, dig = rank[0]
            margin = top - (rank[1][0] if len(rank) > 1 else 0.0)
            if top >= 0.75 and margin >= 0.15:
                return dig, True                                 # khớp mẫu rất rõ: khỏi OCR
            if top >= 0.55 and margin >= 0.10:
                tpl_best = dig
    try:
        import pytesseract
    except Exception:
        return (tpl_best, False) if tpl_best else (0, False)
    base = cv2.resize(m * 255, None, fx=48.0 / m.shape[0], fy=48.0 / m.shape[0], interpolation=cv2.INTER_CUBIC)
    base = (base > 90).astype(np.uint8) * 255
    votes = {}
    imgs = []
    for k in (1, 2, 0):                                          # nét mảnh nên ưu tiên làm dày
        v_ = cv2.dilate(base, np.ones((3, 3), np.uint8), iterations=k) if k else base
        imgs.append(cv2.copyMakeBorder(255 - v_, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255))
    for psm in (10, 8, 7, 13):                                   # mỗi psm 1 tiến trình cho cả 3 ảnh (trước: 12 tiến trình)
        for t in _tess_digits(imgs, psm):
            if t.isdigit() and 1 <= int(t) <= 99 and (len(t) == nd or nd == 1 and len(t) == 1):
                votes[int(t)] = votes.get(int(t), 0) + 1
    if not votes:
        return (tpl_best, False) if tpl_best else (0, False)
    top = sorted(votes.items(), key=lambda kv: -kv[1])
    second = top[1][1] if len(top) > 1 else 0
    ocr_ok = top[0][1] >= 3 and top[0][1] >= 2 * second
    if tpl_best is not None:
        if top[0][0] == tpl_best or not ocr_ok:
            return tpl_best, True                                # mẫu khá khớp và OCR đồng ý (hoặc OCR không chắc)
        return top[0][0], False                                  # OCR chắc chắn một số khác: nghi ngờ -> báo chưa chắc (bỏ phiếu nhiều khung)
    return top[0][0], ocr_ok


def add_number_template(img_path, row, col, digit):
    """Lưu chữ số bước của quái ở ô (row, col) trong ảnh chụp thành mẫu: templates/thtg_num_<digit>_<k>.png (hàng/cột từ 0).
    Dùng cho chữ số chưa có mẫu sẵn (có sẵn 4,5,6,7) hoặc khi đọc sai."""
    frame = _imread(img_path)
    brd, geo = BoardDetector().detect(frame)
    if geo is None:
        raise ValueError("không dựng được hình học bàn cờ từ ảnh")
    x, y = geo.center(row, col)
    g = _num_glyph(frame, x, y, geo.pitch)
    if g is None:
        raise ValueError(f"không thấy chữ số ở ô ({row},{col})")
    os.makedirs(_TPL_DIR, exist_ok=True)
    k = 1
    while os.path.exists(os.path.join(_TPL_DIR, f"thtg_num_{int(digit)}_{k}.png")):
        k += 1
    out = os.path.join(_TPL_DIR, f"thtg_num_{int(digit)}_{k}.png")
    cv2.imwrite(out, _num_norm(g[0]) * 255)
    return out


def read_monster_number(frame, geo: Geometry, r, c, adb=None) -> int:
    """Số bước cần của quái to (xem _number_votes). Không đọc được -> 0 (bên gọi dùng monster_default)."""
    return _number_votes(frame, geo, r, c)[0]


# ---------------------------------------------------------------- "Hiệp còn lại" (số lượt đi còn lại)
# Vòng tròn nâu ở góc trái trên, số vàng nghiêng. Ưu tiên so khớp MẪU hình dạng (chữ nghiêng lạ nên Tesseract hay đọc sai,
# vd 9 -> 7), sau đó mới OCR có kiểm tra số lỗ của chữ số. Mẫu có sẵn: 5 và 9; thêm mẫu số khác:
#   python thtg_bot.py --add-turns anh.png CHỮ_SỐ   -> lưu templates/thtg_turn_<số>.png
_TURN_TPL_B64 = {
    5: "iVBORw0KGgoAAAANSUhEUgAAABwAAAAkCAAAAAC/TwWIAAAArklEQVQ4EW3BiWGDQAADMHn/oV3uSeBIpViKUFNMsdQhhtjqEJfY6hCX2OoQl1hqCkpMsdQQh5hqikNMNcUhhlriEJf6iKcY6hBLUG8xBfUjhqB+xSXUf4JQH0EtQagpplqCUEMstYVQQyy1hVBDLLWFUJdY6iOEIpb6CkGJqW4hHuohxK0egviqh7jEpd5iCOotpqBeYgnqFFuoQ3yFeopbULd4iKG2eIqppjj8Ad4xLiWOJvRyAAAAAElFTkSuQmCC",
    9: "iVBORw0KGgoAAAANSUhEUgAAABwAAAAkCAAAAAC/TwWIAAAAo0lEQVQ4EW3BAYJDQBRAsbz7H/ovhm2LJD/GLku+jCVLPsaSUy7jklMuIwa55DTCkH85DDI2+ZfDkLHJR3ZDxi4f2Q0Zm3zJbpzyLbux5Ed2Y8mPHMYuv7IMcpNlkJscBrnLYZC77AZ5yGaQpzDIizDIizDkTRjyJpvJw0ReDZE3Q8iLQcjD2GSThyGH3IxNDvk1NllyM8iSmyGn3Aw55Wbk8gdGWyslco7XzQAAAABJRU5ErkJggg==",
}
_TURN_HOLES = {0: (1,), 1: (0,), 2: (0,), 3: (0,), 4: (0, 1), 5: (0,), 6: (1,), 7: (0,), 8: (2,), 9: (1,)}
_turn_tpls = None


def _turn_digit_mask(frame):
    """Mặt nạ nhị phân (0/255) của chữ số vàng trong vòng 'Hiệp còn lại', hoặc None."""
    h, w = frame.shape[:2]
    x0, x1, y0, y1 = int(w * 0.095), int(w * 0.19), int(h * 0.055), int(h * 0.122)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    H, S, V = [hsv[..., i].astype(int) for i in range(3)]
    m = ((H >= 12) & (H <= 38) & (S >= 70) & (V >= 200)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = [i for i in range(1, n) if st[i, 3] >= max(10, 0.2 * crop.shape[0]) and st[i, 4] >= 60]
    if not keep:
        return None
    keep.sort(key=lambda i: st[i, 0])
    keep = keep[:2]                                   # tối đa 2 chữ số
    mm = np.isin(lab, keep).astype(np.uint8)
    ys, xs = np.where(mm)
    return mm[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255


def _turn_deskew(mm):
    """Chữ nghiêng: thử nhiều góc shear, chọn góc làm chữ hẹp nhất theo chiều ngang."""
    h, w = mm.shape
    best = (1e9, mm)
    for sh in np.linspace(-0.5, 0.5, 21):
        pad = int(abs(sh) * h) + 2
        M = np.float32([[1, sh, -sh * h / 2 + pad], [0, 1, 0]])
        out = cv2.warpAffine(mm, M, (w + 2 * pad, h), flags=cv2.INTER_LINEAR)
        xs = np.where(out.max(axis=0) > 100)[0]
        if len(xs) and xs.max() - xs.min() < best[0]:
            best = (xs.max() - xs.min(), out[:, xs.min():xs.max() + 1])
    return best[1]


def _turn_norm(mm):
    """Chuẩn hoá chữ số về 36x28 nhị phân (đã bỏ nghiêng, căn giữa) để so khớp mẫu."""
    d = _turn_deskew(mm)
    ys, xs = np.where(d > 100)
    d = d[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    s = 36.0 / d.shape[0]
    r = cv2.resize(d, (max(1, int(round(d.shape[1] * s))), 36), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((36, 28), np.uint8)
    rw = min(28, r.shape[1])
    x0 = (28 - rw) // 2
    canvas[:, x0:x0 + rw] = r[:, :rw]
    return (canvas > 90).astype(np.uint8)


def _turn_templates():
    global _turn_tpls
    if _turn_tpls is None:
        import base64
        _turn_tpls = {}
        for d, b in _TURN_TPL_B64.items():
            img = cv2.imdecode(np.frombuffer(base64.b64decode(b), np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                _turn_tpls[d] = (img > 100).astype(np.uint8)
        for f in sorted(glob.glob(os.path.join(_TPL_DIR, "thtg_turn_*.png"))):
            try:
                d = int(os.path.basename(f)[len("thtg_turn_"):-4].split("_")[0])
            except ValueError:
                continue
            img = _imread(f)
            if img is not None:
                g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _turn_tpls[d] = (cv2.resize(g, (28, 36)) > 100).astype(np.uint8)
    return _turn_tpls


def _turn_iou(a, b):
    a2 = cv2.dilate(a, np.ones((3, 3), np.uint8))
    b2 = cv2.dilate(b, np.ones((3, 3), np.uint8))
    return float(((a & b2).sum() + (b & a2).sum()) / max(1, a.sum() + b.sum()))


def _turn_holes(mm):
    cnts, hier = cv2.findContours((mm > 100).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return 0
    return sum(1 for hh, c in zip(hier[0], cnts) if hh[3] >= 0 and cv2.contourArea(c) >= 12)


def read_turns_left(frame):
    """Đọc số 'Hiệp còn lại'. Trả int hoặc None nếu không chắc (khi đó bot tự đếm lùi). 1 chữ số: so khớp mẫu rồi OCR;
    2 chữ số (10+): OCR có kiểm tra."""
    try:
        mm = _turn_digit_mask(frame)
        if mm is None:
            return None
        if mm.shape[1] <= 1.1 * mm.shape[0]:                       # 1 chữ số (rộng xấp xỉ cao)
            nm = _turn_norm(mm)
            sc = sorted(((_turn_iou(nm, t), d) for d, t in _turn_templates().items()), reverse=True)
            if sc and sc[0][0] >= 0.80 and (len(sc) < 2 or sc[0][0] - sc[1][0] >= 0.10):
                return sc[0][1]
        import pytesseract
        holes = _turn_holes(mm)
        votes = {}
        imgs = []
        for sk in (False, True):
            m0 = _turn_deskew(mm) if sk else mm
            base = cv2.resize(m0, None, fx=48.0 / m0.shape[0], fy=48.0 / m0.shape[0], interpolation=cv2.INTER_CUBIC)
            base = ((base > 100) * 255).astype(np.uint8)
            for k in (0, 1, -1):
                v = (cv2.dilate(base, np.ones((3, 3), np.uint8)) if k == 1
                     else cv2.erode(base, np.ones((3, 3), np.uint8)) if k == -1 else base)
                imgs.append(cv2.copyMakeBorder(255 - v, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255))
        for psm in (10, 8, 7, 13):                                 # mỗi psm 1 tiến trình cho cả 6 ảnh (trước: 24 tiến trình)
            for t in _tess_digits(imgs, psm):
                if t.isdigit() and 0 <= int(t) <= 99:
                    if len(t) == 1 and holes not in _TURN_HOLES[int(t)]:
                        continue                                   # số lỗ không khớp -> bỏ phiếu (vd 7 có 0 lỗ)
                    votes[int(t)] = votes.get(int(t), 0) + 1
        if not votes:
            return None
        top = sorted(votes.items(), key=lambda kv: -kv[1])
        second = top[1][1] if len(top) > 1 else 0
        if top[0][1] >= 3 and top[0][1] >= 2 * second:
            return top[0][0]
    except Exception:
        pass
    return None


def add_turns_template(img_path, digit):
    """Lưu chữ số trong ảnh chụp thành mẫu: templates/thtg_turn_<digit>.png."""
    frame = _imread(img_path)
    mm = None if frame is None else _turn_digit_mask(frame)
    if mm is None:
        raise ValueError("không thấy chữ số 'Hiệp còn lại' trong ảnh")
    os.makedirs(_TPL_DIR, exist_ok=True)
    out = os.path.join(_TPL_DIR, f"thtg_turn_{int(digit)}.png")
    cv2.imwrite(out, _turn_norm(mm) * 255)
    return out


# =====================================================================================
# 4) Thực thi
# =====================================================================================
STEPS_BOX = (0.74, 0.855, 0.88, 0.90)     # (trái, trên, phải, dưới) theo tỉ lệ ảnh: SỐ BƯỚC đã nối, chữ vàng ngay trên nút Chiến (20 = đã nối 20 ô)


def read_step_counter(frame):
    """Đọc SỐ BƯỚC đang hiển thị trên nút Chiến (số vàng phía trên nút, tổng số ô đã nối kể cả ô quái/lồng; đo trên ảnh thật:
    nối 20 ô -> '20', nối đủ kế hoạch 26 ô -> '26'). Trả int hoặc None (không có số / OCR không thống nhất).
    Tách chữ vàng bằng HSV rồi OCR bỏ phiếu 3 kiểu nét x 3 psm (3 tiến trình tesseract, không phải 9)."""
    try:
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = STEPS_BOX
        crop = frame[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]
        if crop.size == 0:
            return None
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hh, ss, vv = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
        m = (((hh >= 15) & (hh <= 35) & (ss >= 70) & (vv >= 225)).astype(np.uint8)) * 255
        m = cv2.resize(m, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        m = cv2.GaussianBlur(m, (5, 5), 0)
        _, m = cv2.threshold(m, 128, 255, cv2.THRESH_BINARY)
        if int((m > 0).sum()) < 2000:                      # đo: có số ~9000+ px, không có số ~100
            return None
        imgs = []
        for v in (m, cv2.dilate(m, np.ones((3, 3), np.uint8)), cv2.erode(m, np.ones((3, 3), np.uint8))):
            imgs.append(cv2.copyMakeBorder(255 - v, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255))
        votes = {}
        for psm in (7, 8, 13):
            for t in _tess_digits(imgs, psm):
                if t.isdigit() and 1 <= int(t) <= 99:
                    votes[int(t)] = votes.get(int(t), 0) + 1
        if not votes:
            return None
        ranked = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
        if ranked[0][1] < 3 or (len(ranked) > 1 and ranked[1][1] == ranked[0][1]):
            return None
        return ranked[0][0]
    except Exception:
        return None


class _Stop(Exception):
    pass


class THTGBot:
    def __init__(self, adb, log=None, should_stop=None, test=False, max_turns=50,
                 params: Optional[SolverParams] = None, tap_delay=0.12, settle_max=8.0,
                 use_skill=True, monster_default=7, save_debug=None, debug_dir="debug_thtg",
                 press_attack=True, attack_xy=(0.87, 0.96), attack_delay=0.6, rage_xy=(0.18, 0.93),
                 attack_wait_base=1.5, attack_wait_per_step=0.15, attack_wait_per_kill=1.2, skill_wait=4.0,
                 settle_stable=3, rage_portrait=True, rage_delay=0.5, ready_first_wait=0.6, vote_frames=3,
                 read_turns=True, start_turns=0, save_shots=True, shots_keep=40, exit_when_gone=True, gone_frames=3,
                 spider_lock_rage=False, verify_steps=True, verify_retries=2, kill_tap_delay=0.7):
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
        self.read_turns = read_turns          # đọc 'Hiệp còn lại' mỗi lượt (false = không dùng; cần cho chế độ lượt cuối)
        self.turns_left = int(start_turns) or None   # số hiệp còn lại (None = chưa biết); start_turns: đặt tay số hiệp ban đầu
        self.exit_when_gone = bool(exit_when_gone)   # không thấy nhân vật, ô nộ lẫn khung bàn cờ => đã thoát bàn cờ: kết thúc ngay
        self.gone_frames = max(1, int(gone_frames))   # số khung chụp liên tiếp phải 'thoát bàn cờ' mới kết luận
        # NHỆN: mặc định (false) vẫn đọc/bấm nộ như bình thường (nộ bị khoá thì bấm cũng không ảnh hưởng gì); true = còn nhện/thấy ổ khoá thì bỏ qua nộ
        self.spider_lock_rage = bool(spider_lock_rage)
        # Bấm quái to/lồng thì game chạy hoạt ảnh diệt (số sát thương hiện ra) và BỎ QUA các lần bấm đến quá sớm -> sau khi bấm 1 ô quái
        # nghỉ thêm `kill_tap_delay`; nối xong thì đọc số bước trên nút Chiến, thiếu (bấm rớt) thì bấm bù phần còn lại (tối đa `verify_retries` lần)
        self.verify_steps = bool(verify_steps)
        self.verify_retries = max(0, int(verify_retries))
        self.kill_tap_delay = max(0.0, float(kill_tap_delay))
        self._rage_locked = False              # trạng thái khoá nộ đã ghi log lần gần nhất (chỉ log khi đổi trạng thái)
        self._left_board = False
        self._tm = {}                          # thời gian từng giai đoạn của lượt hiện tại (giây) -> in 1 dòng log để biết lượt mất thời gian ở đâu
        self._pending_wait = 0.0
        self._rage_raw = []
        self._rage_fail_logs = 0
        self.det = BoardDetector()
        self.save_debug = test if save_debug is None else save_debug   # TEST: luôn lưu đường đi thử
        self.debug_dir = debug_dir
        self.save_shots = bool(save_shots)    # luôn lưu ảnh kiểm tra (đường đi + số đọc được) trước khi bấm Chiến
        self.shots_keep = max(0, int(shots_keep))   # giữ tối đa N lượt gần nhất trong debug_dir (0 = không xoá)
        self._turn = 0
        self._turn_read_warned = False

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

    def _trim_shots(self):
        """Xoá bớt ảnh kiểm tra cũ: giữ `shots_keep` lượt gần nhất (mỗi lượt <= 3 file). Không bao giờ ném lỗi."""
        try:
            if not self.shots_keep:
                return
            fs = [os.path.join(self.debug_dir, f) for f in os.listdir(self.debug_dir) if "_luot" in f]
            fs.sort(key=os.path.getmtime)
            for f in fs[: max(0, len(fs) - self.shots_keep * 3)]:
                os.remove(f)
        except Exception:
            pass

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

    @staticmethod
    def _attack_button_visible(f):
        """Nút Chiến (góc dưới phải, cam-vàng rực) còn trên màn hình? Dấu hiệu rẻ để biết CÒN trong trận khi OCR thanh nộ trượt
        (ngọn lửa che số). Đo trên ảnh thật: ~0.39 điểm cam bão hoà; chỉ dùng để KHÔNG kết luận thoát nhầm (thêm bằng chứng 'còn trong trận')."""
        h, w = f.shape[:2]
        crop = f[int(h * 0.90):int(h * 0.995), int(w * 0.75):int(w * 0.99)]
        if crop.size == 0:
            return False
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        m = (hsv[:, :, 0] >= 5) & (hsv[:, :, 0] <= 30) & (hsv[:, :, 1] >= 150) & (hsv[:, :, 2] >= 170)
        return float(m.mean()) >= 0.20

    @staticmethod
    def _rage_lock_visible(f):
        """Ổ KHOÁ trên ảnh nhân vật ở thanh nộ (đĩa xám sáng ~ (0.270w, 0.938h), bán kính ~0.039w) có hiện không? Đo trên ảnh thật:
        tâm đĩa 0.82 điểm xám sáng (S < 45, V 130-235), cách xa 0.2 -> ngưỡng 0.6. Dấu hiệu PHỤ: nhận nhện mới là căn cứ chính (xem _count_spiders)."""
        h, w = f.shape[:2]
        cx, cy, rad = int(w * 0.270), int(h * 0.938), max(4, int(w * 0.034))
        crop = f[max(0, cy - rad):cy + rad, max(0, cx - rad):cx + rad]
        if crop.size == 0:
            return False
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        yy, xx = np.ogrid[:crop.shape[0], :crop.shape[1]]
        disc = (yy - crop.shape[0] / 2.0) ** 2 + (xx - crop.shape[1] / 2.0) ** 2 <= rad ** 2
        px = hsv[disc].astype(int)
        if px.size == 0:
            return False
        grey = (px[:, 1] < 45) & (px[:, 2] >= 130) & (px[:, 2] <= 235)
        return float(grey.mean()) >= 0.6

    def _count_spiders(self, frame):
        """Số NHỆN còn trên bàn cờ ở khung này (chỉ phân loại 49 ô, không OCR). Không thấy bàn cờ -> 0."""
        try:
            g = find_geometry(frame)
            if g is None:
                return 0
            geo, hero = g
            n = 0
            for r in range(ROWS):
                for c in range(COLS):
                    if (r, c) == hero:
                        continue
                    x = self.det.classify(frame, geo, r, c)
                    if x.kind == "monster" and x.mtype == "spider":
                        n += 1
            return n
        except Exception:
            return 0

    def _battle_gone(self, f):
        """Khung này có phải đã THOÁT bàn cờ không? Chỉ True khi KHÔNG thấy nhân vật, KHÔNG đọc được thanh nộ và KHÔNG thấy cả
        khung bàn cờ 7x7 và KHÔNG thấy nút Chiến. (Đang bấm Chiến thì nhân vật chạy đi nên vắng 1 lúc - nhưng khung bàn cờ/thanh nộ/nút Chiến vẫn còn, nên chưa tính là thoát.)
        Kiểm theo thứ tự rẻ -> đắt (OCR thanh nộ cuối cùng) để không làm chậm vòng chờ."""
        try:
            if find_geometry(f) is not None:
                return False
            if find_board_rect(f) is not None:
                return False
            if self._attack_button_visible(f):
                return False
            if self._rage_lock_visible(f):          # nộ bị khoá (có nhện): thanh nộ hiện ổ khoá nên OCR không đọc được, nhưng vẫn đang trong trận
                return False
            if self.read_rage(f) is not None:
                return False
        except Exception:
            return False
        return True

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
        gone = 0
        while True:
            self._check()
            f = self._shot()
            if f is not None:
                last = f
                res = self.det.signature(f)
                if res is None and self.exit_when_gone:
                    gone = gone + 1 if self._battle_gone(f) else 0
                    if gone >= self.gone_frames:
                        self._left_board = True
                        self.log("info", "Ngưu Ma Vương: không thấy nhân vật, thanh nộ và bàn cờ -> đã thoát bàn cờ, kết thúc")
                        return f
                else:
                    gone = 0
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
        imgs = []
        for smax in (125, 110, 140):          # đo: chữ trắng trên nền cam có độ bão hoà tới ~110 (do viền mờ)
            m = ((hsv[:, :, 1] < smax) & (hsv[:, :, 2] > 190)).astype(np.uint8) * 255
            m = 255 - cv2.resize(m, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
            m = cv2.GaussianBlur(m, (3, 3), 0)
            imgs.append(cv2.copyMakeBorder(m, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255))
        return _tess_digits(imgs, 7, "0123456789/")       # 1 tiến trình cho cả 3 ảnh

    def read_rage(self, frame):
        """Đọc 'x/y' ở thanh nộ bằng OCR. Trả (x, y) hoặc None. Thử lần lượt: tách chữ trắng (đúng với thanh nộ cam),
        OCR của adb, Tesseract thường; 2 vùng đọc (vùng chuẩn rồi vùng cao hơn). x có thể LỚN HƠN 1000 (vd 2685/1000 = đầy).
        Chữ số đầu của x hay bị ngọn lửa che nên chỉ nhận "đầy" khi x là 1000 hoặc 000 (ba số 0 sau khi mất số 1) hoặc >= 1000."""
        h, w = frame.shape[:2]
        boxes = [(int(w * 0.19), int(h * 0.963), int(w * 0.40), int(h * 0.985)),
                 (int(w * 0.19), int(h * 0.945), int(w * 0.40), int(h * 0.995))]
        self._rage_raw = []

        def _sources(crop, box):
            """Lần lượt từng nguồn OCR (rẻ trước); bên gọi dừng ở nguồn đầu tiên đọc ra được."""
            yield lambda: self._rage_white_ocr(crop)
            if hasattr(self.adb, "ocr_text_in_box"):
                yield lambda: [str(self.adb.ocr_text_in_box(frame, box, lang="eng", charset="digits"))]

            def _plain():
                import pytesseract
                g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                g = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
                return [pytesseract.image_to_string(g, config="--psm 7 -c tessedit_char_whitelist=0123456789/")]
            yield _plain
        for box in boxes:
            crop = frame[box[1]:box[3], box[0]:box[2]]
            if crop.size == 0:
                continue
            for src in _sources(crop, box):
                try:
                    txts = src()
                except Exception:
                    continue
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
        for r in range(ROWS):
            for c in range(COLS):
                if board.cells[r][c].kind == "monster" and board.cells[r][c].mtype == "cage":
                    board.cells[r][c].n, board.cells[r][c].turns = CAGE_STEPS, 0       # lồng luôn CAGE_STEPS bước, không vote/đọc
        mons = [(r, c) for r in range(ROWS) for c in range(COLS)
                if board.cells[r][c].kind == "monster" and board.cells[r][c].mtype != "cage"]
        if not mons:
            if any(x.kind == "monster" for row in board.cells for x in row):
                self.log("info", f"Ngưu Ma Vương: lồng luôn cần {CAGE_STEPS} bước (không đọc số)")
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
                def _reread(rc):
                    n_, n_ok = _number_votes(f2, geo, *rc)
                    if board.cells[rc[0]][rc[1]].mtype in ("cage", "spider"):
                        t_, t_ok = 0, True
                    else:
                        t_, t_ok = _turns_votes(f2, geo, *rc)
                    return n_, n_ok, t_, t_ok
                still = []
                for (r, c), (n_, n_ok, t_, t_ok) in zip(unsure, _pmap(_reread, unsure, self.det.ocr_workers)):
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
            elif x.mtype == "spider":
                parts.append(f"({r},{c}) NHỆN cần {x.n}{note}")
            else:
                parts.append(f"({r},{c}) cần {x.n}, đếm ngược {x.turns}{note}")
        n_cage = sum(1 for row in board.cells for x in row if x.kind == "monster" and x.mtype == "cage")
        if n_cage:
            parts.append(f"{n_cage} lồng (luôn cần {CAGE_STEPS} bước)")
        self.log("info", "Ngưu Ma Vương: quái to/lồng: " + "; ".join(parts))

    def _update_turns_left(self, frame):
        """Cập nhật self.turns_left từ ảnh: chỉ nhận số đọc được nếu hợp lý với số đang đếm (hiệp chỉ giảm, mỗi lượt giảm 1);
        đọc lệch/không chắc thì giữ số đang đếm lùi. Lần đầu chưa biết thì nhận số đọc được."""
        if not self.read_turns:
            return self.turns_left
        got = read_turns_left(frame)
        prev = self.turns_left
        if got is not None:
            if prev is None or (prev - 2 <= got <= prev):
                self.turns_left = got
            else:
                self.log("warn", f"Ngưu Ma Vương: đọc 'Hiệp còn lại' = {got} không khớp số đang đếm ({prev}), bỏ qua")
        elif prev is None and not self._turn_read_warned:
            self._turn_read_warned = True
            self.log("warn", "Ngưu Ma Vương: chưa đọc được 'Hiệp còn lại' (chế độ lượt cuối chưa hoạt động; có thể đặt start_turns). "
                              "Thêm mẫu số: python thtg_bot.py --add-turns anh.png CHỮ_SỐ")
        return self.turns_left

    def _tap_path(self, cells, geo, board):
        """Bấm lần lượt các ô. Ô quái to/lồng: game chạy hoạt ảnh diệt (hiện sát thương) và bỏ qua các lần bấm đến quá sớm
        (ảnh thật: nối được 20/26 ô rồi dừng ngay sau khi diệt chuột, 6 ô sau không ăn) -> nghỉ thêm `kill_tap_delay` sau ô đó."""
        for (r, c) in cells:
            self._check()
            x, y = geo.center(r, c)
            self.adb.tap_px(x, y)
            time.sleep(self.tap_delay)
            if self.kill_tap_delay > 0 and board.cells[r][c].kind == "monster":
                self._sleep(self.kill_tap_delay)

    def _stable_step_counter(self):
        """Số bước trên nút Chiến, chỉ tin khi 2 khung chụp liên tiếp đọc GIỐNG NHAU (tránh bấm bù nhầm làm lùi đường đã nối)."""
        prev = None
        for _ in range(3):
            self._check()
            f = self._shot()
            got = read_step_counter(f) if f is not None else None
            if got is not None and got == prev:
                return got
            prev = got
            time.sleep(0.25)
        return None

    def _verify_steps(self, plan, geo, board):
        """Nối xong đọc số bước trên nút Chiến: thiếu so với kế hoạch (bấm rớt) thì bấm bù đúng phần còn lại; thừa thì chỉ cảnh báo."""
        want = len(plan.path)
        if want < 1:
            return
        for attempt in range(self.verify_retries + 1):
            time.sleep(0.4 if attempt == 0 else 0.6)         # chờ hoạt ảnh diệt quái cuối xong rồi mới đọc
            got = self._stable_step_counter()
            if got is None:
                self.log("info" if want < 10 else "warn",
                         f"Ngưu Ma Vương: không đọc được số bước trên nút Chiến (kế hoạch {want} bước) - bỏ qua kiểm tra")
                return
            if got == want:
                self.log("info", f"Ngưu Ma Vương: số bước trên nút Chiến = {got}, khớp kế hoạch" + (" (đã bấm bù)" if attempt else ""))
                return
            if got > want:
                self.log("warn", f"Ngưu Ma Vương: số bước trên nút Chiến = {got} NHIỀU hơn kế hoạch {want} - không bấm thêm")
                return
            if attempt >= self.verify_retries:
                self.log("warn", f"Ngưu Ma Vương: số bước trên nút Chiến = {got} vẫn THIẾU so với kế hoạch {want} sau {attempt} lần bấm bù - đánh với phần đã nối")
                return
            miss = plan.path[got:]
            self.log("warn", f"Ngưu Ma Vương: số bước trên nút Chiến = {got} < kế hoạch {want} (bấm rớt) - bấm bù {len(miss)} ô từ {miss[0]}")
            self._tap_path(miss, geo, board)

    def play_turn(self, frame):
        t_ = time.perf_counter()
        board, geo = self.det.detect(frame, self.adb, self.monster_default)
        self._tm["nhận diện+đọc số quái"] = time.perf_counter() - t_
        stamp = time.strftime("%H%M%S")
        if board is None:
            where = self._save(f"{stamp}_khong_thay_ban_co", frame)
            self.log("warn", "Ngưu Ma Vương: không thấy nhân vật/bàn cờ (hết trận?)"
                     + (f" - đã lưu ảnh: {where}" if where else ""))
            return None
        t_ = time.perf_counter()
        self._vote_monsters(board, geo, frame)
        self._tm["bỏ phiếu quái"] = time.perf_counter() - t_
        t_ = time.perf_counter()
        tl = self._update_turns_left(frame)
        self._tm["đọc hiệp"] = time.perf_counter() - t_
        n_big = sum(1 for r in range(ROWS) for c in range(COLS)
                    if board.cells[r][c].kind == "monster" and board.cells[r][c].mtype != "cage")
        spiders = [(r, c) for r in range(ROWS) for c in range(COLS)
                   if board.cells[r][c].kind == "monster" and board.cells[r][c].mtype == "spider"]
        if spiders:
            self.log("info", f"Ngưu Ma Vương: còn {len(spiders)} NHỆN {spiders} -> ưu tiên diệt hết nhện "
                             f"(điểm ưu tiên nhện {self.params.monster_weights.get('spider', 0):.0f})")
        if tl is not None:
            from dataclasses import replace as _dc_replace
            prm = _dc_replace(self.params, turns_left=tl)
            msg = f"Ngưu Ma Vương: còn {tl} hiệp (hết hiệp mà còn quái to là thua), {n_big} quái to trên bàn"
            if tl == 1:
                msg += " - LƯỢT CUỐI: bỏ thưởng kim cương/chống kẹt, dồn diệt quái"
            self.log("warn" if tl <= 2 and n_big else "info", msg)
        else:
            prm = self.params
        t_ = time.perf_counter()
        plan = solve(board, prm)
        self._tm["giải"] = time.perf_counter() - t_
        if tl is not None and tl <= 2 and n_big and plan.kills < n_big:
            self.log("warn", f"Ngưu Ma Vương: CẢNH BÁO còn {tl} hiệp mà kế hoạch chỉ diệt {plan.kills}/{n_big} quái to trong lượt này")
        if spiders:
            sp_kill = sum(1 for q in plan.killed if board.cells[q[0]][q[1]].mtype == "spider")
            if sp_kill >= len(spiders):
                self.log("info", f"Ngưu Ma Vương: kế hoạch diệt HẾT {sp_kill}/{len(spiders)} nhện trong lượt này -> nộ sẽ mở khoá")
            else:
                self.log("warn", f"Ngưu Ma Vương: kế hoạch chỉ diệt {sp_kill}/{len(spiders)} nhện trong lượt này (nhện còn lại lượt sau tiếp tục ưu tiên)")
        skipped = [(q, board.cells[q[0]][q[1]]) for q in [(r, c) for r in range(ROWS) for c in range(COLS)]
                   if board.cells[q[0]][q[1]].kind == "monster" and board.cells[q[0]][q[1]].mtype != "cage"
                   and q not in set(map(tuple, plan.killed))]
        if skipped and plan.path:
            self.log("info", "Ngưu Ma Vương: quái BỎ lại lượt này: " + "; ".join(
                f"({q[0]},{q[1]}) cần {x.n}{' NHỆN' if x.mtype == 'spider' else ''}"
                f"{'' if self.det.last_raw.get(q, (0, 0, True))[2] else ' [đọc số CHƯA chắc]'}" for q, x in skipped)
                + (" [bộ giải đã chứng minh không ăn thêm được]" if plan.optimal else " [bộ giải chưa chứng minh tối ưu]"))
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
        box_closed = [(r, c) for r in range(ROWS) for c in range(COLS) if board.cells[r][c].box == "closed"]
        box_open = [(r, c) for r in range(ROWS) for c in range(COLS) if board.cells[r][c].box == "open"]
        if box_closed or box_open:
            self.log("info", f"Ngưu Ma Vương: ô gỗ ĐÓNG {len(box_closed)} (như đá, không đi vào) {box_closed}, "
                             f"ô gỗ MỞ {len(box_open)} (như thú thường) {box_open}")
        n_cage = sum(1 for (r, c) in plan.path if board.cells[r][c].mtype == "cage" and board.cells[r][c].kind == "monster")
        if n_cage:
            self.log("info", f"Ngưu Ma Vương: đường đi mở khoá {n_cage} ô lồng (lồng thành kim cương, không tính là diệt quái)")
        suspicious = plan.steps <= 4 and not (self.save_debug or self.save_shots)
        unsure_rc = {rc for rc in [(r, c) for r in range(ROWS) for c in range(COLS)]
                     if board.cells[rc[0]][rc[1]].kind == "monster" and not self.det.last_raw.get(rc, (0, 0, True))[2]}
        draw_info = {"title": f"LUOT {self._turn}" + (f" | con {tl} hiep" if tl is not None else ""), "unsure": unsure_rc}
        if self.save_debug or self.save_shots or suspicious:
            txt = (board.pretty() + f"\nNhân vật: hàng {board.hero[0]}, cột {board.hero[1]}\n"
                   f"Đường đi ({plan.steps} bước): {plan.path}\n"
                   f"Quái to (hàng, cột, số bước cần, số lượt đếm ngược): {[(r, c, board.cells[r][c].n, board.cells[r][c].turns) for r in range(ROWS) for c in range(COLS) if board.cells[r][c].kind == 'monster' and board.cells[r][c].mtype not in ('cage', 'spider')]}\n"
                   f"Nhện (hàng, cột, số bước cần): {[(r, c, board.cells[r][c].n) for (r, c) in spiders]}\n"
                   f"Ô gỗ đóng (như đá): {box_closed}; ô gỗ mở (như thú thường): {box_open}\n"
                   f"Lồng (hàng, cột, số bước cần): {[(r, c, board.cells[r][c].n) for r in range(ROWS) for c in range(COLS) if board.cells[r][c].kind == 'monster' and board.cells[r][c].mtype == 'cage']}\n"
                   f"Bộ giải: {plan.solver}{' (tối ưu đã chứng minh)' if plan.optimal else ''}, diệt {plan.kills} quái, dùng {plan.diamonds} kim cương, thưởng {plan.reward}\n"
                   f"Phạt vị trí cuối (kẹt/góc/mép): {plan.end_pen:.0f}\n")
            where = self._save(f"{stamp}_luot{self._turn}_ke_hoach", draw_plan(frame, geo, board, plan, draw_info), txt)
            if where:
                self.log("info", f"Ngưu Ma Vương: đã lưu ảnh kế hoạch (đường đi + số đọc được trên quái to): {where}")
            self._trim_shots()
        if not plan.path:
            self.log("warn", "Ngưu Ma Vương: không có đường đi")
            return plan
        if self.test:
            return plan
        t_ = time.perf_counter()
        self._tap_path(plan.path, geo, board)
        if self.verify_steps:
            self._verify_steps(plan, geo, board)
        self._tm["bấm ô"] = time.perf_counter() - t_
        self.log("info", f"Ngưu Ma Vương: thời gian lượt {self._turn}: " + ", ".join(f"{k} {v:.1f}s" for k, v in self._tm.items())
                 + f" (cộng {sum(self._tm.values()):.1f}s)")
        if self.press_attack:
            self._check()
            time.sleep(self.attack_delay)
            if self.save_shots:
                try:                                  # ảnh NGAY TRƯỚC KHI BẤM CHIẾN: màn hình thật sau khi nối + số bot đã đọc
                    fb = self._shot()
                    if fb is not None:
                        draw_info["title"] += " | TRUOC KHI BAM CHIEN"
                        w2 = self._save(f"{stamp}_luot{self._turn}_truoc_chien", draw_plan(fb, geo, board, plan, draw_info))
                        if w2:
                            self.log("info", f"Ngưu Ma Vương: đã lưu ảnh trước khi bấm Chiến: {w2}")
                except _Stop:
                    raise
                except Exception:
                    pass
            self._press_attack(frame)
            self._pending_wait = (self.attack_wait_base + self.attack_wait_per_step * plan.steps
                                  + self.attack_wait_per_kill * plan.kills)
            if self.turns_left is not None:
                self.turns_left = max(0, self.turns_left - 1)       # đã đánh 1 lượt; lượt sau đọc lại để chỉnh
        return plan

    def run(self) -> bool:
        turns = 0
        rage_tries = 0
        try:
            while turns < self.max_turns:
                self._check()
                t_ = time.perf_counter()
                frame = self._settle(self._pending_wait) if turns else self._shot()
                self._tm = {"chờ bàn cờ": time.perf_counter() - t_}
                self._pending_wait = 0.0
                if frame is None:
                    self.log("error", "Ngưu Ma Vương: không chụp được màn hình")
                    return False
                if self._left_board:
                    self.log("info", f"Ngưu Ma Vương: xong {turns} lượt (đã thoát bàn cờ)")
                    return True
                # NHỆN: còn nhện (hoặc thấy ổ khoá) -> nộ bị KHOÁ: bỏ qua đọc/bấm nộ (đỡ bấm nhầm, đỡ OCR vô ích)
                locked = False
                if self.use_skill and self.spider_lock_rage:
                    n_sp = self._count_spiders(frame)
                    icon = self._rage_lock_visible(frame)
                    locked = n_sp > 0 or icon
                    if locked != self._rage_locked:
                        self._rage_locked = locked
                        if locked:
                            self.log("info", f"Ngưu Ma Vương: nộ đang bị KHOÁ ({n_sp} nhện" + (", thấy ổ khoá" if icon else "")
                                             + ") -> không dùng nộ, ưu tiên diệt nhện")
                        else:
                            self.log("info", "Ngưu Ma Vương: hết nhện -> nộ đã mở khoá, dùng nộ lại như thường")
                    if locked:
                        rage_tries = 0
                if self.use_skill and not locked and not self.test and rage_tries < 2:
                    t_ = time.perf_counter()
                    rage = self.read_rage(frame)
                    self._tm["đọc nộ"] = time.perf_counter() - t_
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
                elif self.use_skill and not locked and self.test:
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
      diamond_cost (0)       - điểm TRỪ mỗi kim cương phải đi qua (mặc định 0 = kim cương không quan trọng; vd 40 = tiết kiệm kim cương)
      diamond_reward (0)     - điểm CỘNG cho mỗi kim cương được thưởng (cứ đủ 10 bước thưởng 1 viên; vd 60 = ưu tiên đi tròn mốc 10/20/30)
      reward_every (10)      - số bước để được thưởng 1 kim cương
      end_safety (true)      - phạt bước cuối đi vào góc/mép/chỗ lượt sau bị kẹt (false = tắt)
      fall_down (true)       - mô phỏng ô rơi xuống theo cột khi tính chỗ kẹt (false = coi ô đã đi thành ô mới tại chỗ)
      box_alternate (true)   - ô gỗ đổi xen kẽ mỗi lượt (đóng -> mở -> đóng): tính chỗ kẹt theo trạng thái lượt SAU (false = coi giữ nguyên)
      w_corner (60) / w_edge (8) - điểm phạt kết thúc ở góc / mép (nhẹ; chỉ để tránh kẹt, không đánh đổi nhiều bước)
      save_shots (true)      - LUÔN lưu ảnh kiểm tra mỗi lượt vào debug_dir: *_ke_hoach.png (đường đi đánh số + số bước bot đọc trên từng quái to,
                               viền xanh=diệt/cam=bỏ, '?'=đọc chưa chắc) và *_truoc_chien.png (màn hình thật ngay trước khi bấm Chiến)
      shots_keep (40)        - giữ tối đa N lượt gần nhất (xoá ảnh cũ); 0 = không xoá
      read_turns (true)      - đọc 'Hiệp còn lại' mỗi lượt; còn 1 hiệp = lượt cuối: tắt thưởng/chống kẹt, dồn diệt quái
      start_turns (0)        - đặt tay số hiệp ban đầu khi OCR chưa đọc được (0 = tự đọc)
      exit_when_gone (true)  - đang chờ bàn cờ mà không thấy nhân vật + thanh nộ + khung bàn cờ (đã thoát bàn cờ) thì kết thúc ngay, khỏi chờ settle_max
      gone_frames (3)        - số khung chụp liên tiếp 'thoát bàn cờ' mới kết luận (tránh nhầm lúc hoạt ảnh)
      w_spider (5000)        - điểm ưu tiên diệt NHỆN (cộng thêm w_kill); còn nhện thì nộ bị khoá nên cần diệt hết nhện trước (quái thường 500)
      spider_lock_rage (false) - true: còn nhện (hoặc thấy ổ khoá ở thanh nộ) thì KHÔNG đọc/bấm nộ; false (mặc định) = dùng nộ như bình thường
      verify_steps (true)    - nối xong đọc số bước trên nút Chiến; thiếu so với kế hoạch (bấm rớt) thì bấm bù phần còn lại
      verify_retries (2)     - số lần bấm bù tối đa mỗi lượt
      kill_tap_delay (0.7)   - nghỉ thêm (giây) sau khi bấm 1 ô quái to/lồng (game chạy hoạt ảnh diệt và bỏ qua lần bấm đến quá sớm)
      use_exact (true)       - dùng bộ giải chính xác thtg_solver.py trước (false = chỉ beam)
      exact_nodes (400000)   - giới hạn số nút của bộ giải chính xác (không phải giây -> kết quả xác định)
    """
    # beam < 5000 từng khiến ~1/8 bàn bị bỏ sót đường tốt hơn (đo 40 bàn ngẫu nhiên: 5000 = 0 bàn thua beam 12000, ~0.12s/bàn)
    # nên coi 5000 là mức tối thiểu, kể cả kịch bản cũ đã lưu beam=2000.
    params = SolverParams(beam=max(5000, int(step.get("beam", 5000))),
                          monster_weights={"boss": 500.0, "spider": float(step.get("w_spider", 5000.0))},
                          use_exact=bool(step.get("use_exact", True)),
                          exact_nodes=int(step.get("exact_nodes", 400000)),
                          count_step_first=bool(step.get("count_step_first", False)),
                          w_diamond=-abs(float(step.get("diamond_cost", 0.0))),
                          w_reward=float(step.get("diamond_reward", 0.0)),
                          reward_every=max(1, int(step.get("reward_every", 10))),
                          end_safety=bool(step.get("end_safety", True)),
                          fall_down=bool(step.get("fall_down", True)),
                          box_alternate=bool(step.get("box_alternate", True)),
                          w_corner=float(step.get("w_corner", 60.0)),
                          w_edge=float(step.get("w_edge", 8.0)))
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
                  save_shots=bool(step.get("save_shots", True)),
                  shots_keep=int(step.get("shots_keep", 40)),
                  read_turns=bool(step.get("read_turns", True)),
                  start_turns=int(step.get("start_turns", 0)),
                  exit_when_gone=bool(step.get("exit_when_gone", True)),
                  gone_frames=int(step.get("gone_frames", 3)),
                  spider_lock_rage=bool(step.get("spider_lock_rage", False)),
                  verify_steps=bool(step.get("verify_steps", True)),
                  verify_retries=int(step.get("verify_retries", 2)),
                  kill_tap_delay=float(step.get("kill_tap_delay", 0.7)),
                  settle_max=float(step.get("settle_max", 20.0)))
    return bot.run()


def _put(img, text, org, scale, color, thick=2):
    """Chữ có viền đen để đọc được trên mọi nền (cv2 chỉ vẽ ASCII nên ghi tiếng Việt không dấu)."""
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


# nhãn màu lồng trên ảnh kiểm tra (khung lồng): 0 xanh lá (ếch) / 1 cam (bò) / 2 xanh dương (mèo) / 3 đỏ (heo), -1 = không rõ (BGR để vẽ)
_CAGE_COLOR_LABEL = {0: ("XANH LA", (0, 220, 0)), 1: ("CAM", (0, 140, 255)),
                     2: ("XANH DG", (255, 160, 0)), 3: ("DO", (80, 80, 255)), -1: ("MAU ?", (200, 200, 200))}


def draw_plan(frame, geo: Geometry, board: Board, plan: Plan, info=None):
    """Ảnh KIỂM TRA: vẽ lên ảnh chụp (1) số bước bot ĐỌC được ở mỗi quái to (chữ lớn góc trên-trái ô, so với số game in ở góc
    dưới-phải ô), lồng, (2) quái nào kế hoạch diệt (viền xanh) / không diệt (viền cam), (3) đường đi có đánh số từng bước,
    nhân vật (H) và ô kết thúc (END), (4) dòng tóm tắt. info (tuỳ chọn): {'title': str, 'unsure': {(r,c),...}} - ô đọc chưa chắc đánh dấu '?'."""
    info = info or {}
    img = frame.copy()
    p = float(geo.pitch)
    k = max(0.6, p / 90.0)                                   # co giãn theo cỡ ô
    killed = set(map(tuple, plan.killed))
    unsure = set(map(tuple, info.get("unsure", ())))
    # ô gỗ: ĐÓNG (đỏ, "GO DONG" = như đá) / MỞ (xanh lá nhạt, "GO MO" = như thú thường)
    for r in range(ROWS):
        for c in range(COLS):
            x = board.cells[r][c]
            if not x.box:
                continue
            cx, cy = geo.center(r, c)
            col, lab = ((0, 0, 255), "GO DONG") if x.box == "closed" else ((120, 255, 120), "GO MO")
            cv2.rectangle(img, (int(cx - p * .5) + 2, int(cy - p * .5) + 2), (int(cx + p * .5) - 2, int(cy + p * .5) - 2), col, max(1, int(2 * k)))
            _put(img, lab, (int(cx - p * .5) + 5, int(cy - p * .5) + int(20 * k)), 0.5 * k, col, max(1, int(2 * k)))
    # quái to / lồng
    for r in range(ROWS):
        for c in range(COLS):
            x = board.cells[r][c]
            if x.kind != "monster":
                continue
            cx, cy = geo.center(r, c)
            x0, y0 = int(cx - p * .5), int(cy - p * .5)
            x1, y1 = int(cx + p * .5), int(cy + p * .5)
            if x.mtype == "cage":
                col, lab = (255, 200, 0), f"LONG {x.n}"
                opened = (r, c) in set(map(tuple, plan.path))
                if opened:
                    col = (0, 220, 0)
            else:
                col = (0, 220, 0) if (r, c) in killed else (0, 140, 255)
                lab = f"{x.n}"
                if x.mtype == "spider":
                    lab = f"NHEN {x.n}"
            if (r, c) in unsure:
                lab += "?"
            cv2.rectangle(img, (x0 + 2, y0 + 2), (x1 - 2, y1 - 2), col, max(2, int(3 * k)))
            _put(img, lab, (x0 + 5, y0 + int(26 * k)), 0.95 * k, (0, 255, 255) if x.mtype != "cage" else (255, 255, 0), max(2, int(2 * k)))
            if x.mtype != "cage":
                _put(img, ("NHEN " if x.mtype == "spider" else "") + ("DIET" if (r, c) in killed else "BO"), (x0 + 5, y1 - 8), 0.55 * k, col, max(1, int(2 * k)))
            else:                                    # màu lồng bot nhận được (viền cyan chỉ báo "đây là lồng", KHÔNG phải màu lồng)
                cname, ccol = _CAGE_COLOR_LABEL.get(x.color, _CAGE_COLOR_LABEL[-1])
                _put(img, cname, (x0 + 5, y1 - 8), 0.55 * k, ccol, max(1, int(2 * k)))
    # đường đi
    pts = [geo.center(*board.hero)] + [geo.center(r, c) for r, c in plan.path]
    for i in range(len(pts) - 1):
        cv2.line(img, tuple(int(v) for v in pts[i]), tuple(int(v) for v in pts[i + 1]), (0, 0, 255), max(3, int(4 * k)), cv2.LINE_AA)
    hx, hy = pts[0]
    cv2.circle(img, (int(hx), int(hy)), int(14 * k), (255, 120, 0), -1)
    _put(img, "H", (int(hx) - int(8 * k), int(hy) + int(8 * k)), 0.7 * k, (255, 255, 255), 2)
    for i, (x, y) in enumerate(pts[1:], 1):
        rad = int(13 * k)
        cv2.circle(img, (int(x), int(y)), rad, (0, 0, 0), -1)
        cv2.circle(img, (int(x), int(y)), rad, (255, 255, 255), 1)
        txt = str(i)
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5 * k, 1)
        cv2.putText(img, txt, (int(x - tw / 2), int(y + th / 2)), cv2.FONT_HERSHEY_SIMPLEX, 0.5 * k, (255, 255, 255), 1, cv2.LINE_AA)
    if len(pts) > 1:
        ex, ey = pts[-1]
        _put(img, "END", (int(ex) - int(18 * k), int(ey) - int(18 * k)), 0.6 * k, (0, 255, 255), 2)
    # dòng tóm tắt (ảnh có thể là toàn màn hình: vẽ ở đầu bàn cờ)
    n_big = sum(1 for r in range(ROWS) for c in range(COLS) if board.cells[r][c].kind == "monster" and board.cells[r][c].mtype != "cage")
    head = info.get("title") or "KE HOACH"
    n_spi = sum(1 for r in range(ROWS) for c in range(COLS) if board.cells[r][c].kind == "monster" and board.cells[r][c].mtype == "spider")
    line = f"{head} | {plan.steps} buoc | diet {plan.kills}/{n_big} quai to | dung {plan.diamonds} kim cuong"
    if n_spi:
        line += f" | NHEN {sum(1 for q in killed if board.cells[q[0]][q[1]].mtype == 'spider')}/{n_spi} (no bi khoa)"
    ytop = max(int(geo.cy0 - p * .5) - int(8 * k), int(22 * k))
    cv2.rectangle(img, (0, max(0, ytop - int(24 * k))), (img.shape[1], ytop + int(8 * k)), (0, 0, 0), -1)
    sc = 0.6 * k
    while sc > 0.3 and cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, sc, max(1, int(2 * k)))[0][0] > img.shape[1] - 12:
        sc -= 0.03                                           # co chữ cho vừa bề ngang ảnh
    _put(img, line, (6, ytop), sc, (255, 255, 255), max(1, int(2 * k)))
    return img


def add_monster_template(img_path, row, col, prefix="thtg_monster_"):
    """Cắt ô (row, col) của ảnh chụp thành mẫu quái mới: templates/<prefix><n>.png (hàng/cột đếm từ 0; mặc định thtg_monster_<n>.png,
    mẫu nhện dùng prefix thtg_spider_ qua `add_spider_template`)."""
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
    n = len(glob.glob(os.path.join(_TPL_DIR, prefix + "*.png"))) + 1
    out = os.path.join(_TPL_DIR, f"{prefix}{n}.png")
    ok, buf = cv2.imencode(".png", crop)
    if ok:
        buf.tofile(out)
    print("Đã lưu mẫu quái:", out)
    return out


def add_spider_template(img_path, row, col):
    """Cắt ô (row, col) thành mẫu NHỆN: templates/thtg_spider_<n>.png (không bắt buộc - không có mẫu vẫn nhận nhện bằng màu)."""
    return add_monster_template(img_path, row, col, prefix="thtg_spider_")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "--add-num" and len(sys.argv) >= 6:
        print("đã lưu", add_number_template(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])))
        sys.exit(0)
    if sys.argv[1] == "--add-turns" and len(sys.argv) >= 4:
        print("đã lưu", add_turns_template(sys.argv[2], int(sys.argv[3])))
        sys.exit(0)
    if sys.argv[1] == "--add-monster" and len(sys.argv) >= 5:
        add_monster_template(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        sys.exit(0)
    if sys.argv[1] == "--add-spider" and len(sys.argv) >= 5:
        add_spider_template(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        sys.exit(0)
    frame = _imread(sys.argv[1])
    prm = SolverParams(beam=int(sys.argv[2]) if len(sys.argv) > 2 else 5000)
    bd = BoardDetector()
    brd, geo = bd.detect(frame)
    if brd is None:
        print("Không thấy nhân vật trong ảnh.")
        sys.exit(1)
    print(brd.pretty())
    tl = read_turns_left(frame)
    print("Hiệp còn lại:", tl if tl is not None else "không đọc được")
    if tl is not None:
        prm.turns_left = tl
    t = time.time()
    pl = solve(brd, prm)
    print(f"{pl.steps} bước, diệt {pl.kills} quái, dùng {pl.diamonds} kim cương, thưởng {pl.reward}, phạt cuối {pl.end_pen:.0f}, "
          f"còn {pl.final_balance} bước, {time.time()-t:.2f}s")
    print(pl.path)
    cv2.imwrite("thtg_debug.png", draw_plan(frame, geo, brd, pl))
