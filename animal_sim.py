# -*- coding: utf-8 -*-
"""
animal_sim.py - Game GIẢ "Thế Giới Động Vật" để chơi thử/chỉnh trọng số cho animal_bot.py (không cần LDPlayer, không import tkinter).

Luật dùng đúng như mô phỏng của animal_bot.py (docstring mục 1; bản 3: trâu co lại, điểm theo thanh + Buff; loài sinh ngẫu nhiên theo độ dài, KHÔNG mô phỏng cú tấn công của trâu và kỹ năng): bàn 9x11, kéo thanh ngang, rơi cứng, hàng đầy thì ăn (dây chuyền),
mỗi hiệp đẩy 1 hàng mới từ đáy lên, còn thú ở hàng 0 khi hàng mới tới = THUA. Hàng mới sinh NGẪU NHIÊN (phân bố độ dài/độ đầy đo
xấp xỉ từ 2 ảnh màn chơi: mỗi hàng mới khoảng 6/9 ô có thú), dải xem trước báo đúng hàng sắp tới.

Chạy:  python animal_sim.py [số_ván] [depth] [beam]      (mặc định 20 ván, depth 2, beam 30)
       python animal_sim.py --compare                  (so vài bộ trọng số)
       (thêm --real / --real-hard: độ dài thú sát game thật, xem AI_PROGRESS 18/10; mặc định mô phỏng quá dễ)
       python animal_sim.py --skill-compare [số_ván] [depth] [beam] [--kinds=KYPB] [--hard]   (so: không kỹ năng | Gấu luôn trước | kỹ năng giá trị cao nhất; in hiệp sống TB + điểm TB)
       python animal_sim.py --skill [số_ván] [depth] [beam]   (bật KỸ NĂNG kiểu bản 5: năng lượng = điểm ăn (tối đa 10000), `SKILL_COST` 3000/lần, CHỈ GẤU: khi KẸT/chắc chắn thua hoặc trâu thừa >= 8 ô; cap 400)
Kết quả: số hiệp sống sót trung bình (tối đa `cap`), số hàng ăn, số lần dùng kỹ năng.
Mô phỏng kỹ năng: CHỈ khi kẹt/chắc chắn thua lượt sau, không tốn hiệp; Gấu đóng băng 3 hiệp + rút trâu còn 1 ô; cứ `BULL_EVERY` hiệp thêm 1 trâu dài.
"""
from __future__ import annotations

import random
import sys
import time
from dataclasses import replace

import animal_bot as ab

LEN_W = [(1, 0.45), (2, 0.30), (3, 0.15), (4, 0.10)]
SKILL_COST = 3000                     # giá 1 lần kỹ năng (thanh năng lượng ảnh 17/10: "7000/3000"; thực tế tăng dần sau mỗi lần dùng)
SKILL_KINDS = "K"                     # --kinds=KYPB
BEAR_FIRST = True                     # --best: chọn kỹ năng giá trị cao nhất, không ưu tiên Gấu
BULL_EVERY = 20                       # cứ N hiệp hiện THÊM 1 con trâu (đếm ngược 20 hiệp của game; trâu không làm gì khác, chỉ dài và khó diệt)
FILL_CHOICES = [5, 6, 6, 6, 7]       # --hard: hàng mới đầy hơn (7-8/9 ô) để thử sức chịu đựng


def rand_len(rng):
    x = rng.random()
    a = 0.0
    for ln, p in LEN_W:
        a += p
        if x <= a:
            return ln
    return 1


KIND_BY_LEN = {1: "OOP", 2: "PW", 3: "BY", 4: "KRR"}      # loài theo độ dài (đoán từ ảnh: đà điểu 1, hươu 1-2, ngựa vằn 2, voi/sư tử 3, gấu 4, trâu 4)


def rand_kind(rng, ln):
    return rng.choice(KIND_BY_LEN.get(ln, "O"))


def rand_row(rng, fill=None):
    """Hàng mới: list (cột, dài) với khoảng 6/9 ô có thú, luôn còn ít nhất 1 ô trống."""
    target = fill or rng.choice(FILL_CHOICES)
    for _ in range(50):
        bars = []
        col = 0
        used = 0
        # đặt thanh lần lượt từ trái sang phải với khe ngẫu nhiên
        free = ab.COLS - target
        while col < ab.COLS:
            if free > 0 and rng.random() < 0.35:
                col += 1
                free -= 1
                continue
            ln = min(rand_len(rng), ab.COLS - col)
            bars.append((col, ln))
            used += ln
            col += ln
            if col < ab.COLS and rng.random() < 0.25 and free > 0:
                col += 1
                free -= 1
        if 4 <= used <= ab.COLS - 1:
            return bars
    return [(0, 3), (4, 2)]


def new_game(rng, start_rows=8):
    items = []
    for _ in range(start_rows):
        items = [(t[0] - 1, t[1], t[2], t[3]) for t in items]
        for c, ln in rand_row(rng):
            items.append((ab.ROWS - 1, c, ln, rand_kind(rng, ln)))
        items, _, _, _, _ = ab._settle_items(items)
    return items


def play(seed, depth=2, beam=30, weights=None, cap=150, start_rows=8, policy="beam", skill=False, stats=None):
    rng = random.Random(seed)
    energy = 0.0
    score = 0.0
    freeze = 0
    cd_until = 0
    used = 0
    items = new_game(rng, start_rows)
    preview = rand_row(rng)
    w = weights or ab.Weights()
    turns = rows = 0
    while turns < cap:
        bars = [ab.Bar(*t) for t in items]
        pv = [] if freeze > 0 else preview
        if skill and energy >= SKILL_COST and policy != "random":
            ch = ab.choose_skill(bars, pv, None, SKILL_KINDS, depth=depth, beam=beam, w=weights, bear_first=BEAR_FIRST)
            if ch is not None:
                _gain, cand, _bsc, _why = ch
                items = [(t[0], t[1], t[2], t[3]) for t in cand[2]]
                energy -= SKILL_COST
                used += 1
                if cand[3]:
                    freeze = ab.FREEZE_TURNS
                energy += cand[4]
                score += cand[4]
                continue
        if policy == "random":
            mv = ab._gen_moves_items(items)
            if not mv:
                break
            i, nc = rng.choice(mv)
        else:
            path, _ = ab.beam_search(bars, depth, beam, w=w, preview=pv)
            if not path:
                break
            r, c0, ln, nc = path[0]
            i = next(k for k, t in enumerate(items) if (t[0], t[1], t[2]) == (r, c0, ln))
        items, pts, dead, cl = ab.step_state(items, i, nc, pv)
        score += pts
        energy = min(energy + pts, 10000.0)
        if freeze > 0:
            freeze -= 1
        us = [k for k, t in enumerate(items) if t[3] == "U"]
        bull_k = max(us, key=lambda k: items[k][2]) if (us and turns % BULL_EVERY == BULL_EVERY - 1) else None
        items = [(t[0], t[1], t[2], "R" if k == bull_k else (rand_kind(rng, t[2]) if t[3] == "U" else t[3])) for k, t in enumerate(items)]     # hàng mới 'U' -> loài ngẫu nhiên
        rows += cl
        turns += 1
        if dead:
            break
        if not items:                              # dọn sạch bàn: thêm 2 hàng
            for _ in range(2):
                for c, ln in rand_row(rng):
                    items.append((ab.ROWS - 1, c, ln, rand_kind(rng, ln)))
                items = [(t[0] - 1, t[1], t[2], t[3]) if t[0] == ab.ROWS - 1 and False else t for t in items]
        preview = rand_row(rng)
    if stats is not None:
        stats.append(used)
    return turns, rows, score


def run(n=20, depth=2, beam=30, weights=None, cap=150, label="", start_rows=8, policy="beam", seed0=1000, skill=False):
    t = time.time()
    used = []
    res = [play(seed0 + s, depth, beam, weights, cap, start_rows, policy, skill, used) for s in range(n)]
    tu = sum(r[0] for r in res) / n
    ro = sum(r[1] for r in res) / n
    full = sum(1 for r in res if r[0] >= cap)
    sc = sum(r[2] for r in res) / n
    print(f"{label:28s} hiệp TB {tu:6.1f} | hàng ăn TB {ro:5.1f} | sống tới cap {full}/{n} | điểm TB {sc:8.0f} | kỹ năng TB {sum(used) / max(1, len(used)):.1f} | {time.time() - t:.0f}s", flush=True)
    return tu


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 20
    depth = int(args[1]) if len(args) > 1 else 2
    beam = int(args[2]) if len(args) > 2 else 30
    if "--hard" in sys.argv:
        FILL_CHOICES[:] = [7, 7, 8]
    if "--real" in sys.argv:             # độ dài thú sát bàn thật (18/10: bàn thật chỉ ~8% thú 1 ô, mặc định mô phỏng 45% nên QUÁ DỄ): bot depth 3 chết ở hiệp ~300-480 như các ván thật
        LEN_W[:] = [(1, 0.30), (2, 0.30), (3, 0.25), (4, 0.15)]
    if "--real-hard" in sys.argv:        # khó hơn nữa (1 ô 22%): để phân biệt các bản bot với nhau
        LEN_W[:] = [(1, 0.22), (2, 0.30), (3, 0.30), (4, 0.18)]
    for a_ in sys.argv:
        if a_.startswith("--kinds="):
            SKILL_KINDS = a_.split("=", 1)[1].upper()
    if "--best" in sys.argv:
        BEAR_FIRST = False
    if "--skill-compare" in sys.argv:        # so: Gấu luôn trước  vs  chọn kỹ năng giá trị cao nhất (cùng seed)
        SKILL_KINDS = SKILL_KINDS if SKILL_KINDS != "K" else "KYPB"
        run(n, depth, beam, cap=400, label="không kỹ năng", skill=False)
        BEAR_FIRST = True
        run(n, depth, beam, cap=400, label=f"{SKILL_KINDS}: Gấu luôn trước", skill=True)
        BEAR_FIRST = False
        run(n, depth, beam, cap=400, label=f"{SKILL_KINDS}: giá trị cao nhất", skill=True)
    elif "--skill" in sys.argv:
        run(n, depth, beam, cap=400, label="không kỹ năng (cap 400)", skill=False)
        run(n, depth, beam, cap=400, label="kỹ năng khi cần (cap 400)", skill=True)
    elif "--compare" in sys.argv:
        W = ab.Weights
        run(n, 1, beam, W(), label="ngẫu nhiên", policy="random")
        run(n, 1, beam, W(), label="depth1 mặc định")
        run(n, 2, beam, W(), label="depth2 mặc định")
        run(n, 2, beam, replace(W(), danger=0.0), label="depth2 danger=0")
        run(n, 2, beam, replace(W(), fit=0.0), label="depth2 fit=0")
    else:
        run(n, depth, beam, label=f"depth{depth} beam{beam}")
